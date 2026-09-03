/**
 * Cross-family helpers shared by job handlers. Port of `jobs/handlers/common.py`
 * and the `managed_library_db` lifecycle in `jobs/handlers/db_lifecycle.py`.
 */
import { openLibraryDb, type Db } from '../../db/connection.js';
import { AuthenticationError, InvalidRequestError } from '../../providers/errors.js';
import { requireLibraryDb } from '../library-db.js';
import type { ErrorSeverity, JobRunner } from '../runner.js';

/**
 * The library DB path, or `null` after failing the job with the reason.
 *
 * Centralized so every catalog-dependent handler reports the same accurate
 * message — the resolution failure is presentable text, not a stack trace.
 */
export function resolveLibraryDbOrFail(runner: JobRunner, jobId: string): string | null {
  try {
    return requireLibraryDb();
  } catch (e) {
    runner.failJob(jobId, e instanceof Error ? e.message : String(e), 'warning');
    return null;
  }
}

/**
 * Open the catalog for the duration of `fn` and always close it.
 *
 * Writable: handlers exist to mutate the catalog, unlike the routes, which open
 * read-only unless they declare otherwise.
 */
export async function withLibraryDb<T>(path: string, fn: (db: Db) => Promise<T>): Promise<T> {
  const db = openLibraryDb(path);
  try {
    return await fn(db);
  } finally {
    db.close();
  }
}

/**
 * How loudly the UI should report a failure.
 *
 * `warning` is for the user's own inputs — a bad key or an expired token is not a
 * defect. `critical` is for the two cases where continuing would be unsafe: the
 * filesystem refusing the process, and a write attempted against a catalog
 * Lightroom still holds open.
 */
export function failureSeverityFromError(e: unknown): ErrorSeverity {
  if (e instanceof AuthenticationError || e instanceof InvalidRequestError) return 'warning';
  // Node reports filesystem and permission failures as an Error carrying both an
  // `errno` and a `code`, which is the closest analogue to Python's `OSError`.
  if (
    typeof e === 'object' &&
    e !== null &&
    typeof (e as { errno?: unknown }).errno === 'number' &&
    typeof (e as { code?: unknown }).code === 'string'
  ) {
    return 'critical';
  }
  if (e instanceof Error && e.message === 'Close Lightroom before writing to catalog.') {
    return 'critical';
  }
  return 'error';
}

/** Job metadata as a plain object, whatever the column happened to hold. */
export function asMetadata(metadata: unknown): Record<string, unknown> {
  return metadata && typeof metadata === 'object' && !Array.isArray(metadata)
    ? (metadata as Record<string, unknown>)
    : {};
}
