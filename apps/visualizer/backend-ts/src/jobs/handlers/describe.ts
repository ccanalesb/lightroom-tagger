/**
 * Describe job handlers. Port of the describe half of `jobs/handlers/analyze.py`.
 *
 * `describeMatchedImage` already reports `written` / `skipped` / `failed`, but a
 * skip carries no reason a user could act on — the service does not care *why* an
 * image was not describable, and the job does. `diagnoseDescribeSkip` re-walks the
 * same preconditions after the fact to turn "skipped" into "the NAS is not
 * mounted" or "that key is not in the catalog", which is the difference between a
 * log line worth reading and one worth ignoring.
 */
import { extname } from 'node:path';
import { existsSync } from 'node:fs';
import type { Db } from '../../db/connection.js';
import { getImage } from '../../db/library/catalog.js';
import { getImageDescription } from '../../db/library/descriptions.js';
import { VIDEO_EXTENSIONS } from '../../imaging/raw-decode.js';
import { resolveFilepath } from '../../utils/path-resolve.js';
import { describeMatchedImage } from '../../vision/description-service.js';
import type { JobRunner } from '../runner.js';
import {
  asMetadata,
  failureSeverityFromError,
  resolveLibraryDbOrFail,
  withLibraryDb,
} from './common.js';
import { PathSkipDiagnostics } from './path-diagnostics.js';

/** What a describe attempt did, in the vocabulary the job result reports. */
export type DescribeStatus = 'described' | 'skipped' | 'failed';

export interface DescribeAttempt {
  status: DescribeStatus;
  success: boolean;
  error: string | null;
}

/** A specific reason `describeMatchedImage` declined, for the job log. */
export function diagnoseDescribeSkip(db: Db, key: string, force: boolean): string {
  try {
    if (!force && getImageDescription(db, key)) {
      return 'Already described (use force to regenerate)';
    }
    const image = getImage(db, key);
    if (!image) return 'Image key not found in catalog';
    const filepath = typeof image['filepath'] === 'string' ? image['filepath'] : '';
    if (!filepath) return 'No filepath in catalog record';

    const resolved = resolveFilepath(filepath);
    if (VIDEO_EXTENSIONS.has(extname(resolved).toLowerCase())) {
      return `Video file not describable: ${resolved.split('/').pop() ?? resolved}`;
    }
    if (!existsSync(resolved)) return `File not found: ${resolved}`;
    return 'Model returned empty or invalid response';
  } catch (e) {
    return `No description generated (${e instanceof Error ? e.message : String(e)})`;
  }
}

/** Describe one image, mapping the outcome into `(status, success, error)`. */
export async function describeSingleImage(
  db: Db,
  key: string,
  opts: { force: boolean; providerId?: string | null; model?: string | null },
): Promise<DescribeAttempt> {
  try {
    const result = await describeMatchedImage(db, key, {
      force: opts.force,
      providerId: opts.providerId ?? null,
      model: opts.model ?? null,
    });

    if (result.status === 'written') return { status: 'described', success: true, error: null };
    if (result.status === 'failed') {
      return {
        status: 'failed',
        success: false,
        error: result.reason || 'model returned empty or invalid response',
      };
    }
    return {
      status: 'skipped',
      success: false,
      error: diagnoseDescribeSkip(db, key, opts.force),
    };
  } catch (e) {
    return { status: 'failed', success: false, error: e instanceof Error ? e.message : String(e) };
  }
}

/** Classify path accessibility for a skipped item, for the grouped counters. */
export async function recordPathSkipFromStatus(
  diag: PathSkipDiagnostics | null,
  key: string,
  status: DescribeStatus,
  logPrefix = '',
): Promise<void> {
  if (diag === null || status !== 'skipped') return;
  const { reason, detail } = await diag.classify(key);
  if (reason) diag.recordSkip(reason, key, { detail, logPrefix });
}

/** Generate an AI description for a single image, as an async job. */
export async function handleSingleDescribe(
  runner: JobRunner,
  jobId: string,
  rawMetadata: unknown,
): Promise<void> {
  const metadata = asMetadata(rawMetadata);
  try {
    const imageKey = metadata['image_key'];
    const imageType = (metadata['image_type'] as string | undefined) ?? 'catalog';
    const force = Boolean(metadata['force']);
    const providerId = (metadata['provider_id'] as string | null | undefined) ?? null;
    const providerModel = (metadata['provider_model'] as string | null | undefined) ?? null;

    if (typeof imageKey !== 'string' || !imageKey) {
      runner.failJob(jobId, 'image_key is required in metadata');
      return;
    }

    const dbPath = resolveLibraryDbOrFail(runner, jobId);
    if (dbPath === null) return;

    await withLibraryDb(dbPath, async (db) => {
      runner.updateProgress(jobId, 10, `Describing ${imageType} image…`);

      const diag = new PathSkipDiagnostics(runner, jobId, db, { jobLabel: 'single_describe' });
      await diag.runPreflight([imageKey]);

      const attempt = await describeSingleImage(db, imageKey, {
        force,
        providerId,
        model: providerModel,
      });

      if (attempt.success) {
        runner.completeJob(jobId, {
          image_key: imageKey,
          image_type: imageType,
          status: attempt.status,
          skip_reason_counts: diag.skipReasonCounts,
        });
        return;
      }

      await recordPathSkipFromStatus(diag, imageKey, attempt.status);
      runner.failJob(jobId, attempt.error || 'Description generation failed');
    });
  } catch (e) {
    runner.failJob(
      jobId,
      e instanceof Error ? e.message : String(e),
      failureSeverityFromError(e),
    );
  }
}
