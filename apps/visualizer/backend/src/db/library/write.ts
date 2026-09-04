/**
 * Single-writer discipline for `library.db`.
 *
 * Uses `BEGIN IMMEDIATE` to take the writer seat up front; better-sqlite3 does not
 * auto-begin deferred transactions, but immediate mode still honours `busy_timeout`
 * when multiple connections contend. Retries cover an external process holding the
 * lock longer than the timeout. Nested calls reuse the open transaction.
 */
import type { Db } from '../connection.js';

/** Default retry count for lock contention. */
const DEFAULT_RETRIES = 5;

export interface LibraryWriteOptions {
  retries?: number;
  /** Receives `(level, message)` so job runs can surface retries in the UI. */
  log?: (level: string, message: string) => void;
}

function isBusy(err: unknown): boolean {
  const code = (err as { code?: string } | null)?.code;
  return code === 'SQLITE_BUSY' || /database is locked/i.test(String(err));
}

/**
 * Sleep without yielding the thread.
 *
 * better-sqlite3 is synchronous, so `libraryWrite` callers are synchronous too and
 * cannot await. `Atomics.wait` on an unshared buffer blocks precisely and without a
 * spin loop. This only ever runs while waiting out another process's write lock, and
 * inside a job worker rather than the request thread.
 */
function sleepSync(ms: number): void {
  const view = new Int32Array(new SharedArrayBuffer(4));
  Atomics.wait(view, 0, 0, ms);
}

/**
 * Run `fn` inside one `BEGIN IMMEDIATE` transaction on `library.db`.
 *
 * Commits on success, rolls back and rethrows on failure. Nested calls reuse the
 * open transaction — the outer block owns commit/rollback.
 */
export function libraryWrite<T>(db: Db, fn: () => T, opts: LibraryWriteOptions = {}): T {
  const retries = opts.retries ?? DEFAULT_RETRIES;

  if (db.inTransaction) {
    return fn();
  }

  let lastError: unknown;
  let began = false;
  for (let attempt = 0; attempt < retries; attempt += 1) {
    try {
      db.exec('BEGIN IMMEDIATE');
      began = true;
      break;
    } catch (err) {
      lastError = err;
      if (isBusy(err) && attempt < retries - 1) {
        opts.log?.('warning', `[library-write] lock busy, retry ${attempt + 1}/${retries}`);
        // Exponential backoff with small jitter to desynchronize competing writers.
        sleepSync(100 * 2 ** attempt + attempt * 7);
        continue;
      }
      throw err;
    }
  }
  if (!began) {
    throw lastError ?? new Error('library_write: failed to acquire writer seat');
  }

  try {
    const result = fn();
    db.exec('COMMIT');
    return result;
  } catch (err) {
    try {
      db.exec('ROLLBACK');
    } catch {
      // A rollback failure must not mask the original error.
    }
    throw err;
  }
}
