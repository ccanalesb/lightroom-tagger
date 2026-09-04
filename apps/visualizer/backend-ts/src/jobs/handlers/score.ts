/**
 * Score job handlers. Port of the score half of `jobs/handlers/analyze.py`.
 *
 * One image, one perspective at a time. The loop is sequential and the first hard
 * failure stops the job, because a perspective failing means the provider or the
 * rubric is wrong, and the remaining perspectives would fail the same way — a
 * partially-scored image is worse than an unscored one, since the identity
 * aggregate would then average a subset of the rubric without saying so.
 */
import { listPerspectives } from '../../db/library/scores.js';
import type { CancelCheck } from '../../providers/retry.js';
import { scoreImageForPerspective } from '../../vision/scoring-service.js';
import { VisionOpOutcome } from '../../vision/vision-op.js';
import type { Db } from '../../db/connection.js';
import type { JobRunner } from '../runner.js';
import {
  asMetadata,
  failureSeverityFromError,
  jobLogLevel,
  resolveLibraryDbOrFail,
  withLibraryDb,
} from './common.js';
import { PathSkipDiagnostics } from './path-diagnostics.js';

/** Score one image for one perspective, turning a thrown error into an outcome. */
export async function scoreSingleImage(
  db: Db,
  key: string,
  perspectiveSlug: string,
  opts: {
    force: boolean;
    providerId?: string | null;
    model?: string | null;
    logCallback?: (level: string, message: string) => void;
    cancelCheck?: CancelCheck;
  },
): Promise<VisionOpOutcome> {
  try {
    return await scoreImageForPerspective(db, key, perspectiveSlug, {
      force: opts.force,
      providerId: opts.providerId ?? null,
      model: opts.model ?? null,
      logCallback: opts.logCallback ?? null,
      cancelCheck: opts.cancelCheck ?? null,
    });
  } catch (e) {
    return new VisionOpOutcome('failed', e instanceof Error ? e.message : String(e));
  }
}

/**
 * Read the perspectives a job should score.
 *
 * An explicit list is taken as given — including perspectives that are inactive,
 * which `scoreImageForPerspective` then rejects — while the default is every
 * active one. Asking for nothing is an error rather than a no-op success, because
 * "scored 0 perspectives" reported as done looks identical to a scored image.
 */
export function resolveScoreSlugs(db: Db, metadata: Record<string, unknown>): string[] {
  const raw = metadata['perspective_slugs'];
  if (Array.isArray(raw) && raw.length > 0) return raw.map((x) => String(x));
  return listPerspectives(db, { activeOnly: true }).map((p) => p.slug);
}

/** Score a single image for one or more perspectives, as an async job. */
export async function handleSingleScore(
  runner: JobRunner,
  jobId: string,
  rawMetadata: unknown,
): Promise<void> {
  const metadata = asMetadata(rawMetadata);
  try {
    const imageKey = metadata['image_key'];
    const imageType = String(metadata['image_type'] ?? 'catalog');
    const force = Boolean(metadata['force']);
    const providerId = (metadata['provider_id'] as string | null | undefined) ?? null;
    const providerModel = (metadata['provider_model'] as string | null | undefined) ?? null;

    if (typeof imageKey !== 'string' || !imageKey) {
      runner.failJob(jobId, 'image_key is required in metadata');
      return;
    }
    if (imageType !== 'catalog') {
      runner.failJob(jobId, 'image_type must be catalog');
      return;
    }

    const dbPath = resolveLibraryDbOrFail(runner, jobId);
    if (dbPath === null) return;

    await withLibraryDb(dbPath, async (db) => {
      const slugs = resolveScoreSlugs(db, metadata);
      if (slugs.length === 0) {
        runner.failJob(
          jobId,
          'No perspectives to score (provide perspective_slugs or activate perspectives)',
        );
        return;
      }

      runner.updateProgress(jobId, 10, `Scoring ${imageType} image…`);

      const diag = new PathSkipDiagnostics(runner, jobId, db, { jobLabel: 'single_score' });
      await diag.runPreflight([imageKey]);

      let scored = 0;
      let skipped = 0;

      for (const slug of slugs) {
        const outcome = await scoreSingleImage(db, imageKey, slug, {
          force,
          providerId,
          model: providerModel,
          logCallback: (level, message) => runner.log(jobId, jobLogLevel(level), message),
        });

        if (outcome.wrote) {
          scored += 1;
        } else if (outcome.status === 'skipped') {
          skipped += 1;
        } else {
          runner.failJob(jobId, outcome.reason || `Scoring failed for perspective '${slug}'`);
          return;
        }
      }

      runner.completeJob(jobId, {
        image_key: imageKey,
        image_type: imageType,
        scored,
        skipped,
        // Always zero on this path: a failure returns above. The key stays in the
        // payload because the UI reads it, and Python emits it for the same reason.
        failed: 0,
        skip_reason_counts: diag.skipReasonCounts,
      });
    });
  } catch (e) {
    runner.failJob(jobId, e instanceof Error ? e.message : String(e), failureSeverityFromError(e));
  }
}
