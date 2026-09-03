/**
 * Explicit job-type registry. Port of `jobs/registry.py`.
 *
 * `JOB_TYPES` is the single source of truth for dispatch, catalog requirements and
 * checkpoint co-location. Mirrors ADR-0006's explicit CLI `COMMANDS` list —
 * greppable, no decorators, no auto-discovery, so adding a job type is a visible
 * edit rather than a side effect of importing a module.
 *
 * The handlers are not wired up yet: they are 3,394 lines that depend on the vision
 * client, the description and scoring services, the RAW decode pipeline and the
 * `.lrcat` reader. `handler: null` marks a type whose dispatch is still to come —
 * the *declaration* has to exist first, because `requiresCatalog` gates job creation
 * and `/api/jobs/health` publishes the list.
 */

export interface JobType {
  name: string;
  /** `null` until the handler is ported; the runner reports such a job as failed. */
  handler: null;
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
    handler: null,
    requiresCatalog: true,
    checkpointMismatchMessage:
      'checkpoint mismatch: batch_describe fingerprint changed, starting fresh',
  },
  { name: 'single_describe', handler: null, requiresCatalog: true, checkpointMismatchMessage: null },
  { name: 'single_score', handler: null, requiresCatalog: true, checkpointMismatchMessage: null },
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
    handler: null,
    requiresCatalog: true,
    checkpointMismatchMessage:
      'checkpoint mismatch: batch_stack_detect fingerprint changed, starting fresh',
  },
  {
    name: 'batch_catalog_similarity',
    handler: null,
    requiresCatalog: true,
    checkpointMismatchMessage: null,
  },
  {
    name: 'batch_embed_image',
    handler: null,
    requiresCatalog: true,
    checkpointMismatchMessage:
      'checkpoint mismatch: batch_embed_image fingerprint changed, starting fresh',
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
