/**
 * The CLIP embedding job handler. Port of `jobs/handlers/embed.py`.
 *
 * This job writes nothing a user reads directly: it fills
 * `image_clip_embeddings`, which stack detection and catalog similarity then rank
 * over. That is worth saying in the log, because a run that ends "embedded 40,000"
 * with no visible change otherwise reads like it did nothing.
 *
 * Python buffered eight paths and called `encode_images(paths, batch_size=8)`,
 * with a per-image retry loop for when the batch threw. Neither survives here:
 * `encodeImages` is a sequential loop over `encodePixels` — the ONNX session is
 * already internally threaded, so batching bought only peak memory — which makes
 * the buffer an indirection around a one-element list and the fallback a retry of
 * work that never shared a fate. Encoding one image at a time also drops a
 * double-count in the original, where a file that failed *both* the batch and the
 * retry was tallied under `encode_failed` twice.
 */
import type { Db } from '../../db/connection.js';
import {
  listCatalogKeysForClipEmbedForce,
  listCatalogKeysNeedingClipEmbedding,
  upsertImageClipEmbedding,
} from '../../db/library/embeddings.js';
import { libraryWrite } from '../../db/library/write.js';
import { CLIP_EMBED_MODEL_ID, clipVecBlob, encodeImages } from '../../imaging/clip-embed.js';
import {
  CHECKPOINT_MAX_ENTRIES,
  buildBatchEmbedImageCheckpointBody,
  fingerprintBatchEmbedImage,
  loadResumeState,
} from '../checkpoint.js';
import type { JobRunner } from '../runner.js';
import {
  asMetadata,
  failureSeverityFromError,
  readIntOrNull,
  resolveDateWindow,
  resolveLibraryDbOrFail,
  withLibraryDb,
} from './common.js';
import { PathSkipDiagnostics, emptySkipReasonCounts } from './path-diagnostics.js';

/** Logged when a resumed `batch_embed_image` checkpoint no longer fits the inputs. */
export const BATCH_EMBED_IMAGE_CHECKPOINT_MISMATCH =
  'checkpoint mismatch: batch_embed_image fingerprint changed, starting fresh';

const PRECOMPUTE_NOTICE =
  'batch_embed_image stage=precompute_embeddings (builds similarity index only). ' +
  'After completion, run stack detection or catalog similarity.';

export interface BatchEmbedImageResult {
  embedded: number;
  skipped: number;
  failed: number;
  total: number;
  skip_reason_counts: Record<string, number>;
}

/** Embed catalog images into `image_clip_embeddings`. */
export async function handleBatchEmbedImage(
  runner: JobRunner,
  jobId: string,
  rawMetadata: unknown,
): Promise<void> {
  const metadata = asMetadata(rawMetadata);
  try {
    const rawScope = metadata['image_type'];
    const imageType = rawScope === null || rawScope === undefined ? 'catalog' : String(rawScope).trim();
    if (imageType !== 'catalog') {
      runner.failJob(jobId, "batch_embed_image: image_type must be 'catalog'", 'warning');
      return;
    }

    const dbPath = resolveLibraryDbOrFail(runner, jobId);
    if (dbPath === null) return;

    await withLibraryDb(dbPath, (db) => runEmbedPass(runner, jobId, metadata, db));
  } catch (e) {
    runner.failJob(jobId, e instanceof Error ? e.message : String(e), failureSeverityFromError(e));
  }
}

async function runEmbedPass(
  runner: JobRunner,
  jobId: string,
  metadata: Record<string, unknown>,
  db: Db,
): Promise<void> {
  runner.log(jobId, 'info', `batch_embed_image: model=${CLIP_EMBED_MODEL_ID}`);
  runner.log(jobId, 'info', PRECOMPUTE_NOTICE);

  const { months, year } = resolveDateWindow(metadata);
  const minRating = readIntOrNull(metadata['min_rating']);
  const force = Boolean(metadata['force']);
  runner.log(
    jobId,
    'info',
    `batch_embed_image filters: force=${force}, months=${months}, year=${year}, ` +
      `min_rating=${minRating}`,
  );

  const window = { months, year, minRating };
  const fullList = force
    ? listCatalogKeysForClipEmbedForce(db, window)
    : listCatalogKeysNeedingClipEmbedding(db, window);

  const totalAtStart = fullList.length;
  const fingerprint = await fingerprintBatchEmbedImage(metadata, fullList, {
    resolvedMonths: months,
    resolvedYear: year,
  });

  const processed = loadResumeState({
    metadata: runner.readMetadata(jobId),
    jobType: 'batch_embed_image',
    resumeKey: 'processed_pairs',
    fingerprint,
    mismatchMessage: BATCH_EMBED_IMAGE_CHECKPOINT_MISMATCH,
    log: (message) => runner.log(jobId, 'info', message),
  });

  const pending = fullList.filter((key) => !processed.has(key));
  const alreadyDone = totalAtStart - pending.length;
  const progressFor = (done: number): number =>
    Math.trunc(5 + (done / Math.max(totalAtStart, 1)) * 95);

  runner.updateProgress(
    jobId,
    progressFor(alreadyDone),
    `Found ${totalAtStart} images to embed (${pending.length} remaining)`,
  );

  if (totalAtStart === 0) {
    runner.clearCheckpoint(jobId);
    runner.completeJob(jobId, {
      embedded: 0,
      skipped: 0,
      failed: 0,
      total: 0,
      skip_reason_counts: emptySkipReasonCounts(),
    });
    return;
  }

  const diag = new PathSkipDiagnostics(runner, jobId, db, {
    jobLabel: 'batch_embed_image',
    logAction: 'image embed',
  });
  await diag.runPreflight(pending);

  let embedded = 0;
  let skipped = 0;
  let failed = 0;

  /**
   * Mark a key done and persist. Returns false once the checkpoint has outgrown
   * what belongs in one metadata column, which stops the run rather than letting
   * the jobs row grow without bound.
   */
  const recordDone = (key: string): boolean => {
    processed.add(key);
    if (processed.size > CHECKPOINT_MAX_ENTRIES) {
      runner.failJob(jobId, 'checkpoint too large: exceeds 100000 entries');
      return false;
    }
    runner.persistCheckpoint(
      jobId,
      buildBatchEmbedImageCheckpointBody({ fingerprint, processed, totalAtStart }),
    );
    return true;
  };

  for (const key of pending) {
    if (runner.isCancelled(jobId)) {
      runner.finalizeCancelled(jobId);
      return;
    }

    const { path, reason, detail } = await diag.classify(key);
    if (reason !== null || path === null) {
      skipped += 1;
      if (reason !== null) diag.recordSkip(reason, key, { detail });
    } else {
      try {
        const [vector] = await encodeImages([path]);
        if (vector === undefined) throw new Error('encoder returned no vector');
        const blob = clipVecBlob(vector);
        libraryWrite(db, () => upsertImageClipEmbedding(db, key, blob));
        embedded += 1;
      } catch (e) {
        failed += 1;
        diag.recordSkip('encode_failed', key, {
          detail: e instanceof Error ? e.message : String(e),
        });
      }
    }

    // Failures are recorded too: the file is unreadable, so a resume that retried
    // it would fail again at the same cost.
    if (!recordDone(key)) return;

    const done = embedded + skipped + failed;
    runner.updateProgress(
      jobId,
      progressFor(alreadyDone + done),
      `Embedded ${embedded}/${totalAtStart}${skipped > 0 ? ` (skipped ${skipped})` : ''}`,
    );
    diag.maybeLogSummary(alreadyDone + done, totalAtStart, { embedded, skipped, failed });
  }

  if (runner.isCancelled(jobId)) {
    runner.finalizeCancelled(jobId);
    return;
  }

  const summary: BatchEmbedImageResult = {
    embedded,
    skipped,
    failed,
    total: totalAtStart,
    skip_reason_counts: diag.skipReasonCounts,
  };
  runner.clearCheckpoint(jobId);
  runner.completeJob(jobId, summary);
}
