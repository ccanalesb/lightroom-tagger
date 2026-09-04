/**
 * Explicit job-type registry. Port of `jobs/registry.py`.
 *
 * `JOB_TYPES` is the single source of truth for dispatch, catalog requirements and
 * checkpoint co-location. Mirrors ADR-0006's explicit CLI `COMMANDS` list —
 * greppable, no decorators, no auto-discovery, so adding a job type is a visible
 * edit rather than a side effect of importing a module.
 *
 * The handlers are being wired one family at a time. `handler: null` marks a type
 * whose dispatch is still to come — the *declaration* has to exist first, because
 * `requiresCatalog` gates job creation and `/api/jobs/health` publishes the list.
 */
import type { JobRunner } from './runner.js';
import {
  BATCH_DESCRIBE_CHECKPOINT_MISMATCH,
  handleBatchDescribe,
  handleSingleDescribe,
} from './handlers/describe.js';
import { BATCH_EMBED_IMAGE_CHECKPOINT_MISMATCH, handleBatchEmbedImage } from './handlers/embed.js';
import { handleSingleScore } from './handlers/score.js';
import {
  BATCH_STACK_DETECT_CHECKPOINT_MISMATCH,
  handleBatchCatalogSimilarity,
  handleBatchStackDetect,
} from './handlers/stacks.js';

/**
 * A handler owns the job's outcome: it calls `completeJob` or `failJob` itself.
 * The processor only steps in for a handler that throws and leaves it running.
 */
export type JobHandler = (
  runner: JobRunner,
  jobId: string,
  metadata: unknown,
) => Promise<void>;

export interface JobType {
  name: string;
  /** `null` until the handler is ported; the runner reports such a job as failed. */
  handler: JobHandler | null;
  /**
   * Whether the handler opens the Lightroom catalog mirror.
   *
   * Gates enqueueing: `POST /api/jobs/` refuses a catalog-requiring type with a 422
   * when `library.db` is missing, rather than accepting a job that cannot run.
   */
  requiresCatalog: boolean;
  /** Message logged when a resumed checkpoint no longer matches the inputs. */
  checkpointMismatchMessage: string | null;
}

export const JOB_TYPES: readonly JobType[] = [
  {
    name: 'batch_describe',
    handler: handleBatchDescribe,
    requiresCatalog: true,
    checkpointMismatchMessage: BATCH_DESCRIBE_CHECKPOINT_MISMATCH,
  },
  {
    name: 'single_describe',
    handler: handleSingleDescribe,
    requiresCatalog: true,
    checkpointMismatchMessage: null,
  },
  {
    name: 'single_score',
    handler: handleSingleScore,
    requiresCatalog: true,
    checkpointMismatchMessage: null,
  },
  {
    name: 'batch_score',
    handler: null,
    requiresCatalog: true,
    checkpointMismatchMessage:
      'checkpoint mismatch: batch_score fingerprint changed, starting fresh',
  },
  { name: 'batch_analyze', handler: null, requiresCatalog: true, checkpointMismatchMessage: null },
  {
    name: 'batch_stack_detect',
    handler: handleBatchStackDetect,
    requiresCatalog: true,
    checkpointMismatchMessage: BATCH_STACK_DETECT_CHECKPOINT_MISMATCH,
  },
  {
    name: 'batch_catalog_similarity',
    handler: handleBatchCatalogSimilarity,
    requiresCatalog: true,
    checkpointMismatchMessage: null,
  },
  {
    name: 'batch_embed_image',
    handler: handleBatchEmbedImage,
    requiresCatalog: true,
    checkpointMismatchMessage: BATCH_EMBED_IMAGE_CHECKPOINT_MISMATCH,
  },
  {
    name: 'batch_frame_substance',
    handler: null,
    // The only type that does not need the catalog: it reads the vision cache.
    requiresCatalog: false,
    checkpointMismatchMessage: null,
  },
  { name: 'catalog_sync', handler: null, requiresCatalog: true, checkpointMismatchMessage: null },
  {
    name: 'catalog_cache_build',
    handler: null,
    requiresCatalog: true,
    checkpointMismatchMessage: null,
  },
];

export const JOB_TYPES_BY_NAME: ReadonlyMap<string, JobType> = new Map(
  JOB_TYPES.map((jt) => [jt.name, jt]),
);

/** Job types whose handlers open the Lightroom catalog SQLite mirror. */
export function catalogRequiringJobTypes(): Set<string> {
  return new Set(JOB_TYPES.filter((jt) => jt.requiresCatalog).map((jt) => jt.name));
}
