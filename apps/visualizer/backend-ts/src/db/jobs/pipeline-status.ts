/**
 * Latest run per Catalog Cache pipeline trigger.
 * Port of `_CACHE_PIPELINE_BUCKETS` / `_last_job_for_bucket` in `api/system.py`.
 *
 * Reads `visualizer.db`, not `library.db` — jobs live in the app's own database.
 */
import type { Db } from '../connection.js';

/**
 * `null` inside an allowed-values list means "the key is absent or NULL".
 *
 * That is what preserves the historical default for legacy jobs: a
 * `batch_embed_image` row written before `metadata.image_type` existed was
 * implicitly a catalog embed, so it must still count toward the `embed_catalog`
 * bucket rather than vanishing from the UI.
 */
type MetadataFilter = Record<string, readonly (string | null)[]>;

interface Bucket {
  key: string;
  jobType: string;
  metadata: MetadataFilter;
}

/** One entry per button on the Catalog Cache tab. */
const CACHE_PIPELINE_BUCKETS: readonly Bucket[] = [
  { key: 'catalog_sync', jobType: 'catalog_sync', metadata: {} },
  {
    key: 'embed_catalog',
    jobType: 'batch_embed_image',
    metadata: { image_type: ['catalog', null] },
  },
  { key: 'stack_detect', jobType: 'batch_stack_detect', metadata: {} },
  { key: 'catalog_similarity', jobType: 'batch_catalog_similarity', metadata: {} },
  { key: 'catalog_cache_build', jobType: 'catalog_cache_build', metadata: {} },
];

export interface CachePipelineRun {
  job_id: string;
  type: string;
  status: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
}

/**
 * The most recent job row matching a type plus a JSON metadata filter.
 *
 * `json_extract` is what lets one job type split into several UI buckets —
 * `batch_embed_image` covers both the catalog and (historically) other scopes, and
 * only `metadata.image_type` tells them apart.
 */
function lastJobForBucket(
  db: Db,
  jobType: string,
  metadataFilter: MetadataFilter,
): CachePipelineRun | null {
  const clauses = ['type = ?'];
  const params: (string | null)[] = [jobType];

  for (const [key, allowed] of Object.entries(metadataFilter)) {
    // The key is a fixed identifier from the bucket table above, never user input.
    const col = `json_extract(metadata, '$.${key}')`;
    const subClauses: string[] = [];
    for (const value of allowed) {
      if (value === null) {
        subClauses.push(`${col} IS NULL`);
      } else {
        subClauses.push(`${col} = ?`);
        params.push(value);
      }
    }
    if (subClauses.length) clauses.push(`(${subClauses.join(' OR ')})`);
  }

  const row = db
    .prepare(
      'SELECT id, type, status, created_at, started_at, completed_at, error ' +
        `FROM jobs WHERE ${clauses.join(' AND ')} ` +
        'ORDER BY created_at DESC LIMIT 1',
    )
    .get(...params) as
    | {
        id: string;
        type: string;
        status: string;
        created_at: string;
        started_at: string | null;
        completed_at: string | null;
        error: string | null;
      }
    | undefined;

  if (row === undefined) return null;
  // Renamed on the way out: the column is `id`, the API field is `job_id`.
  return {
    job_id: row.id,
    type: row.type,
    status: row.status,
    created_at: row.created_at,
    started_at: row.started_at,
    completed_at: row.completed_at,
    error: row.error,
  };
}

/** Every bucket, with `null` where no matching job has ever run. */
export function getCachePipelineStatus(db: Db): Record<string, CachePipelineRun | null> {
  const out: Record<string, CachePipelineRun | null> = {};
  for (const bucket of CACHE_PIPELINE_BUCKETS) {
    out[bucket.key] = lastJobForBucket(db, bucket.jobType, bucket.metadata);
  }
  return out;
}
