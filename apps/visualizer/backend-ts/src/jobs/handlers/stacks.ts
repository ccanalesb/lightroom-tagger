/**
 * Burst-stack detection and catalog CLIP similarity.
 *
 * Both jobs read the vectors `batch_embed_image` wrote and turn them into
 * something the grid shows: stacks collapse a burst to one row, similarity groups
 * queue near-duplicates for review. Neither touches a file or a provider, so both
 * are pure SQLite work — the cost is the KNN, not IO.
 *
 * `catalog_cache_build`, the third type in this family, chains sync → embed →
 * stack → similarity; it lives in `catalog-cache.ts` and drives the two passes
 * below through their `stage` argument.
 */
import { clipSimilarityWhyMatchedLine } from '../../api/images/row-shaping.js';
import { NoClipEmbeddingError, runClipSimilarForSeed } from '../../clip/similarity.js';
import { config, loadLibraryConfig } from '../../config.js';
import type { Db } from '../../db/connection.js';
import { catalogKeyIsPrimaryGridRow } from '../../db/library/catalog-query.js';
import { isFrameSubstanceFlagged } from '../../db/library/frame-substance.js';
import {
  clearCatalogSimilarityResults,
  insertCatalogSimilarityGroup,
  listClipEmbeddedCatalogKeysNewestFirst,
  type SimilarityCandidateInput,
} from '../../db/library/similarity.js';
import { selectStackRepresentativeKeyForKeys } from '../../db/library/stacks.js';
import { isCatalogSimilarityPairRejected } from '../../db/library/stack-suggestions.js';
import { libraryWrite } from '../../db/library/write.js';
import {
  CHECKPOINT_MAX_ENTRIES,
  buildBatchStackDetectCheckpointBody,
  fingerprintBatchStackDetect,
  loadResumeState,
} from '../checkpoint.js';
import type { JobRunner } from '../runner.js';
import {
  asMetadata,
  failureSeverityFromError,
  mapStageProgress,
  readIntOrNull,
  resolveLibraryDbOrFail,
  withLibraryDb,
  type StageBand,
} from './common.js';

/** Re-report progress every this many seeds; a per-seed update is pure noise. */
const CATALOG_SIMILARITY_SUMMARY_EVERY = 500;

/** Same, per image finished by stack detection. */
const STACK_DETECT_SUMMARY_EVERY = 500;

/* -------------------------------------------------------------------------- */
/* batch_catalog_similarity                                                    */
/* -------------------------------------------------------------------------- */

export interface BatchCatalogSimilarityResult {
  groups_created: number;
  candidates_created: number;
  embedded_catalog_images: number;
  skipped_non_primary: number;
  skipped_no_embedding: number;
  skipped_flagged_frame: number;
  skipped_rejected: number;
  min_similarity: number;
  limit_per_seed: number;
}

/** Materialize catalog-to-catalog CLIP similarity groups for later review. */
export async function handleBatchCatalogSimilarity(
  runner: JobRunner,
  jobId: string,
  rawMetadata: unknown,
): Promise<void> {
  const metadata = asMetadata(rawMetadata);
  try {
    const dbPath = resolveLibraryDbOrFail(runner, jobId);
    if (dbPath === null) return;
    await withLibraryDb(dbPath, async (db) => {
      runSimilarityPass(runner, jobId, metadata, db);
    });
  } catch (e) {
    runner.failJob(jobId, e instanceof Error ? e.message : String(e), failureSeverityFromError(e));
  }
}

/** A metadata number clamped into `[lo, hi]`, or `fallback` when it is not one. */
function clampedNumber(raw: unknown, fallback: number, lo: number, hi: number): number {
  const n = typeof raw === 'number' ? raw : Number(raw);
  return Math.min(hi, Math.max(lo, Number.isFinite(n) ? n : fallback));
}

/**
 * Group the catalog's near-duplicates.
 *
 * Returns the summary when running as a stage of `catalog_cache_build`, and
 * `null` whenever the job has already been settled — the contract every pass in
 * this backend follows.
 */
export function runSimilarityPass(
  runner: JobRunner,
  jobId: string,
  metadata: Record<string, unknown>,
  db: Db,
  stage?: StageBand,
): BatchCatalogSimilarityResult | null {
  const prefix = stage?.logPrefix ?? '';
  const log = (message: string): void => runner.log(jobId, 'info', `${prefix}${message}`);
  const progress = (pct: number, message: string): void =>
    runner.updateProgress(jobId, mapStageProgress(stage, pct), `${prefix}${message}`);

  const minSimilarity = clampedNumber(metadata['min_similarity'], 0.9, 0, 1);
  const limitPerSeed = Math.trunc(
    clampedNumber(readIntOrNull(metadata['limit_per_seed']) ?? 8, 8, 1, 50),
  );

  const allKeys = listClipEmbeddedCatalogKeysNewestFirst(db);
  const total = allKeys.length;
  log(
    'batch_catalog_similarity stage=find_similar_photos ' +
      `min_similarity=${minSimilarity.toFixed(2)}, limit_per_seed=${limitPerSeed}, ` +
      `embedded_catalog_images=${total}`,
  );
  progress(5, `Found ${total} embedded catalog images`);

  // The whole table, not a diff: this job has no checkpoint, so a rerun that kept
  // the old rows would double every group it re-derives.
  libraryWrite(db, () => clearCatalogSimilarityResults(db));

  let groupsCreated = 0;
  let candidatesCreated = 0;
  let skippedNonPrimary = 0;
  let skippedNoEmbedding = 0;
  let skippedFlaggedFrame = 0;
  let skippedRejected = 0;

  // A pair is a group under whichever of its two images comes up first as a seed;
  // without this the same near-duplicate appears twice, once from each side.
  const seenPairs = new Set<string>();

  for (const [index, seedKey] of allKeys.entries()) {
    if (runner.isCancelled(jobId)) {
      runner.finalizeCancelled(jobId);
      return null;
    }
    if (!catalogKeyIsPrimaryGridRow(db, seedKey)) {
      skippedNonPrimary += 1;
      continue;
    }
    if (isFrameSubstanceFlagged(db, seedKey)) {
      skippedFlaggedFrame += 1;
      continue;
    }

    let pairs: readonly [string, number][] = [];
    try {
      pairs = runClipSimilarForSeed(db, seedKey, { limit: limitPerSeed, offset: 0 }).pairs;
    } catch (e) {
      // The key came from `image_clip_embeddings`, so this only fires if the row
      // went away mid-run; it is counted rather than fatal.
      if (!(e instanceof NoClipEmbeddingError)) throw e;
      skippedNoEmbedding += 1;
      continue;
    }

    const candidates: SimilarityCandidateInput[] = [];
    for (const [candidateKey, distance] of pairs) {
      const similarity = Math.min(1, Math.max(0, 1 - distance));
      if (similarity < minSimilarity) continue;
      const pairKey = [seedKey, candidateKey].sort().join('\u0000');
      if (seenPairs.has(pairKey)) continue;
      if (isCatalogSimilarityPairRejected(db, seedKey, candidateKey)) {
        skippedRejected += 1;
        continue;
      }
      if (isFrameSubstanceFlagged(db, candidateKey)) {
        skippedFlaggedFrame += 1;
        continue;
      }
      seenPairs.add(pairKey);
      candidates.push({
        candidate_key: candidateKey,
        similarity,
        rank: candidates.length + 1,
        why_matched: clipSimilarityWhyMatchedLine(similarity),
      });
    }

    if (candidates.length > 0) {
      libraryWrite(db, () => insertCatalogSimilarityGroup(db, { seedKey, candidates, jobId }));
      groupsCreated += 1;
      candidatesCreated += candidates.length;
    }

    const done = index + 1;
    if (done % CATALOG_SIMILARITY_SUMMARY_EVERY === 0 || done === total) {
      progress(
        Math.min(100, Math.trunc(5 + (done / Math.max(total, 1)) * 95)),
        `Similarity scan ${done}/${total}: groups=${groupsCreated}, ` +
          `candidates=${candidatesCreated}, skipped_non_primary=${skippedNonPrimary}`,
      );
    }
  }

  const result: BatchCatalogSimilarityResult = {
    groups_created: groupsCreated,
    candidates_created: candidatesCreated,
    embedded_catalog_images: total,
    skipped_non_primary: skippedNonPrimary,
    skipped_no_embedding: skippedNoEmbedding,
    skipped_flagged_frame: skippedFlaggedFrame,
    skipped_rejected: skippedRejected,
    min_similarity: minSimilarity,
    limit_per_seed: limitPerSeed,
  };
  log(
    `Catalog similarity complete: groups_created=${groupsCreated}, ` +
      `candidates_created=${candidatesCreated}, embedded_catalog_images=${total}, ` +
      `skipped_non_primary=${skippedNonPrimary}, skipped_no_embedding=${skippedNoEmbedding}, ` +
      `skipped_flagged_frame=${skippedFlaggedFrame}, skipped_rejected=${skippedRejected}`,
  );
  if (stage !== undefined) return result;
  runner.completeJob(jobId, result);
  return null;
}

/* -------------------------------------------------------------------------- */
/* batch_stack_detect                                                          */
/* -------------------------------------------------------------------------- */

/** Logged when a resumed `batch_stack_detect` checkpoint no longer fits the inputs. */
export const BATCH_STACK_DETECT_CHECKPOINT_MISMATCH =
  'checkpoint mismatch: batch_stack_detect fingerprint changed, starting fresh';

export type StackDetectForceMode = 'incremental' | 'full' | 'preserve_edited';

export interface BatchStackDetectResult {
  stacks_created: number;
  stacks_updated: number;
  images_stacked: number;
  images_skipped_no_date: number;
  images_skipped_already_stacked: number;
}

/**
 * `incremental` | `full` | `preserve_edited` (CONTEXT D-05).
 *
 * `preserve_edited` still clears everything, because `user_modified` is always 0
 * today; STACK-05 is where it starts meaning something.
 */
export function normalizeStackDetectForce(metadata: Record<string, unknown>): StackDetectForceMode {
  const raw = metadata['force'];
  if (raw === true) return 'full';
  if (raw === 'preserve_edited') return 'preserve_edited';
  return 'incremental';
}

/**
 * `date_taken` as epoch milliseconds, or `null` when it is missing or unparseable.
 *
 * Hand-parsed rather than handed to `new Date()`, which reads a naive
 * `2024-01-10T09:15:00` as *local* time. Python's `fromisoformat` produces a naive
 * datetime that this job then stamps as UTC, so on any machine east or west of
 * Greenwich the two would disagree about where a burst begins.
 */
export function parseDateTakenUtc(value: unknown): number | null {
  if (value === null || value === undefined) return null;
  const text = String(value).trim();
  if (!text) return null;

  const m =
    /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,6}))?)?)?(Z|[+-]\d{2}:?\d{2})?$/.exec(
      text,
    );
  if (!m) return null;

  const [, y, mo, d, hh = '0', mi = '0', ss = '0', frac = '', offset] = m;
  const ms = Date.UTC(Number(y), Number(mo) - 1, Number(d), Number(hh), Number(mi), Number(ss));
  if (!Number.isFinite(ms)) return null;
  // Kept sub-millisecond because the gap is compared against `delta_ms` as a float.
  const micros = frac ? Number(frac.padEnd(6, '0')) : 0;

  let offsetMinutes = 0;
  if (offset && offset !== 'Z') {
    const sign = offset.startsWith('-') ? -1 : 1;
    const digits = offset.slice(1).replace(':', '');
    offsetMinutes = sign * (Number(digits.slice(0, 2)) * 60 + Number(digits.slice(2)));
  }
  return ms + micros / 1000 - offsetMinutes * 60_000;
}

export interface BurstRow {
  key: string;
  date_taken: string | null;
}

export interface BurstSegments {
  segments: string[][];
  skippedNoDate: number;
}

/**
 * Split `rows` into runs of images taken less than `deltaMs` apart.
 *
 * Newest segment first, so an interrupted run has covered the recent photos —
 * within a segment the keys stay in ascending time order, which is what the
 * representative query and the members table expect.
 */
export function buildBurstSegments(rows: readonly BurstRow[], deltaMs: number): BurstSegments {
  const parsed: [string, number][] = [];
  let skippedNoDate = 0;
  for (const row of rows) {
    const at = parseDateTakenUtc(row.date_taken);
    if (at === null) {
      skippedNoDate += 1;
      continue;
    }
    parsed.push([String(row.key ?? ''), at]);
  }
  if (parsed.length === 0) return { segments: [], skippedNoDate };

  parsed.sort((a, b) => a[1] - b[1] || (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0));

  const segments: string[][] = [];
  let current: string[] = [parsed[0]![0]];
  let previous = parsed[0]![1];
  for (const [key, at] of parsed.slice(1)) {
    if (at - previous > deltaMs) {
      segments.push(current);
      current = [key];
    } else {
      current.push(key);
    }
    previous = at;
  }
  segments.push(current);
  return { segments: segments.reverse(), skippedNoDate };
}

/** Group catalog images into burst stacks by `date_taken` gaps. */
export async function handleBatchStackDetect(
  runner: JobRunner,
  jobId: string,
  rawMetadata: unknown,
): Promise<void> {
  const metadata = asMetadata(rawMetadata);
  try {
    const dbPath = resolveLibraryDbOrFail(runner, jobId);
    if (dbPath === null) return;
    await withLibraryDb(dbPath, (db) => runStackDetectPass(runner, jobId, metadata, db));
  } catch (e) {
    runner.failJob(jobId, e instanceof Error ? e.message : String(e), failureSeverityFromError(e));
  }
}

/**
 * The burst gap in milliseconds, or `null` after failing the job.
 *
 * `0` means unset, not "no gap" (CONTEXT D-07): it is what a client sends for an
 * omitted field, and a zero-millisecond gap would stack nothing.
 */
function resolveBurstDeltaMs(
  runner: JobRunner,
  jobId: string,
  metadata: Record<string, unknown>,
): number | null {
  const raw = metadata['delta_ms'];
  if (raw === null || raw === undefined || raw === 0) {
    const configured = loadLibraryConfig(config.LT_CONFIG_YAML).stackBurstDeltaMs;
    return configured >= 1 ? configured : 2000;
  }
  const parsed = readIntOrNull(raw);
  if (parsed === null) {
    runner.failJob(jobId, 'Invalid delta_ms in metadata (must be integer >= 1)', 'warning');
    return null;
  }
  if (parsed < 1) {
    runner.failJob(
      jobId,
      'delta_ms override must be >= 1 when non-zero (invalid delta_ms)',
      'warning',
    );
    return null;
  }
  return parsed;
}

/**
 * Group the catalog into burst stacks.
 *
 * Returns the summary when running as a stage of `catalog_cache_build`, and
 * `null` whenever the job has already been settled. A stage keeps no checkpoint,
 * for the reason given on `runEmbedPass`.
 */
export async function runStackDetectPass(
  runner: JobRunner,
  jobId: string,
  metadata: Record<string, unknown>,
  db: Db,
  stage?: StageBand,
): Promise<BatchStackDetectResult | null> {
  const prefix = stage?.logPrefix ?? '';
  const progress = (pct: number, message: string): void =>
    runner.updateProgress(jobId, mapStageProgress(stage, pct), `${prefix}${message}`);

  const deltaMs = resolveBurstDeltaMs(runner, jobId, metadata);
  if (deltaMs === null) return null;
  const forceMode = normalizeStackDetectForce(metadata);

  // Reported only for an incremental run, where it explains the shortfall between
  // the catalog size and the work list. A full rebuild skips nothing.
  const imagesSkippedAlreadyStacked =
    forceMode === 'incremental'
      ? Number(
          (db.prepare('SELECT COUNT(*) AS c FROM image_stack_members').get() as { c: number }).c,
        )
      : 0;

  if (forceMode !== 'incremental') {
    // Members go with it: the table cascades on `stack_id`.
    libraryWrite(db, () => db.exec('DELETE FROM image_stacks'));
  }

  /*
   * One query where Python ran two — a key list, then the same rows re-fetched in
   * 500-key `IN (...)` chunks with a fallback row for any key the second query did
   * not return. Both queries read `images`, so that fallback covers a case the
   * first query cannot produce.
   *
   * Incremental mode only looks at unstacked images, which means a gap is measured
   * against the unstacked neighbours alone; images still stacked from a previous
   * run are invisible to it. `force: true` is the global re-scan.
   */
  const rows = db
    .prepare(
      forceMode === 'incremental'
        ? 'SELECT key, date_taken FROM images WHERE key NOT IN ' +
            '(SELECT image_key FROM image_stack_members)'
        : 'SELECT key, date_taken FROM images',
    )
    .all() as BurstRow[];

  const allKeys = [...new Set(rows.filter((r) => r.key).map((r) => String(r.key)))].sort();
  const totalAtStart = allKeys.length;
  const fingerprint = await fingerprintBatchStackDetect(allKeys, {
    resolvedDeltaMs: deltaMs,
    forceMode,
  });

  const processed =
    stage === undefined
      ? loadResumeState({
          metadata: runner.readMetadata(jobId),
          jobType: 'batch_stack_detect',
          resumeKey: 'processed_image_keys',
          fingerprint,
          mismatchMessage: BATCH_STACK_DETECT_CHECKPOINT_MISMATCH,
          log: (message) => runner.log(jobId, 'info', message),
        })
      : new Set<string>();

  /** Log the summary, then either complete the job or hand it to the chain. */
  const finish = (result: BatchStackDetectResult): BatchStackDetectResult | null => {
    runner.log(
      jobId,
      'info',
      `${prefix}Stack detection complete: stacks_created=${result.stacks_created}, ` +
        `images_stacked=${result.images_stacked}, ` +
        `images_skipped_no_date=${result.images_skipped_no_date}, ` +
        `images_skipped_already_stacked=${result.images_skipped_already_stacked}`,
    );
    if (stage !== undefined) return result;
    runner.clearCheckpoint(jobId);
    runner.completeJob(jobId, result);
    return null;
  };

  if (totalAtStart === 0) {
    progress(5, 'No catalog images in stack-detect work list');
    return finish({
      stacks_created: 0,
      stacks_updated: 0,
      images_stacked: 0,
      images_skipped_no_date: 0,
      images_skipped_already_stacked: imagesSkippedAlreadyStacked,
    });
  }

  progress(5, `Found ${totalAtStart} images to scan for stacks`);

  const { segments, skippedNoDate } = buildBurstSegments(rows, deltaMs);
  const totalWorkUnits = segments.reduce((n, seg) => n + seg.length, 0);
  if (totalWorkUnits === 0) {
    return finish({
      stacks_created: 0,
      stacks_updated: 0,
      images_stacked: 0,
      images_skipped_no_date: skippedNoDate,
      images_skipped_already_stacked: imagesSkippedAlreadyStacked,
    });
  }

  let stacksCreated = 0;
  let imagesStacked = 0;
  let lastSummaryAt = 0;

  const emitSummary = (force = false): void => {
    const done = processed.size;
    if (!force && done - lastSummaryAt < STACK_DETECT_SUMMARY_EVERY) return;
    lastSummaryAt = done;
    progress(
      Math.min(100, Math.trunc(5 + (done / Math.max(totalWorkUnits, 1)) * 95)),
      `Stack scan ${done}/${totalWorkUnits}: stacks_created=${stacksCreated}, ` +
        `images_stacked=${imagesStacked}, skipped_no_date=${skippedNoDate}`,
    );
  };

  /**
   * Mark a segment done and persist. Returns false once the checkpoint has
   * outgrown what belongs in one metadata column, which stops the run rather than
   * letting the jobs row grow without bound.
   */
  const recordDone = (segment: readonly string[]): boolean => {
    for (const key of segment) processed.add(key);
    // A chain stage writes no checkpoint, so the set is only a progress counter
    // and cannot outgrow anything.
    if (stage !== undefined) return true;
    if (processed.size > CHECKPOINT_MAX_ENTRIES) {
      runner.failJob(jobId, 'checkpoint too large: exceeds 100000 entries');
      return false;
    }
    runner.persistCheckpoint(
      jobId,
      buildBatchStackDetectCheckpointBody({ fingerprint, processed, totalAtStart }),
    );
    return true;
  };

  for (const segment of segments) {
    if (runner.isCancelled(jobId)) {
      runner.finalizeCancelled(jobId);
      return null;
    }
    if (segment.length === 0) continue;
    if (segment.every((key) => processed.has(key))) continue;

    // A lone image is not a burst, but it is still work: recording it keeps the
    // checkpoint's idea of progress equal to the number of images examined.
    if (segment.length > 1) {
      const representative = selectStackRepresentativeKeyForKeys(db, segment);
      if (representative === null || !segment.includes(representative)) {
        runner.failJob(jobId, 'Stack representative selection failed (internal error)');
        return null;
      }
      libraryWrite(db, () => {
        const info = db
          .prepare(
            'INSERT INTO image_stacks (representative_key, stack_size, user_modified) ' +
              'VALUES (?, ?, 0)',
          )
          .run(representative, segment.length);
        const stackId = Number(info.lastInsertRowid);
        const stmt = db.prepare(
          'INSERT INTO image_stack_members (stack_id, image_key) VALUES (?, ?)',
        );
        for (const key of segment) stmt.run(stackId, key);
      });
      stacksCreated += 1;
      imagesStacked += segment.length;
    }

    if (!recordDone(segment)) return null;
    emitSummary();
  }

  if (runner.isCancelled(jobId)) {
    runner.finalizeCancelled(jobId);
    return null;
  }
  // `recordDone` may already have failed the job; do not overwrite that outcome.
  if (runner.hasFailed(jobId)) return null;

  emitSummary(true);
  return finish({
    stacks_created: stacksCreated,
    // Always 0: this job only ever creates stacks. The field is in the result
    // because the UI reads it, and STACK-05's edit-preserving mode will fill it.
    stacks_updated: 0,
    images_stacked: imagesStacked,
    images_skipped_no_date: skippedNoDate,
    images_skipped_already_stacked: imagesSkippedAlreadyStacked,
  });
}
