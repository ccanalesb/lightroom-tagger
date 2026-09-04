/**
 * Single-writer discipline for `library.db`.
 *
 * The Python version needed two things: a process-wide `RLock` (because parallel
 * describe/score threads shared one process and raced the SQLite writer seat) and
 * `BEGIN IMMEDIATE` (because Python's driver auto-opens a *deferred* transaction on
 * the first SELECT, and the later read→write lock upgrade fails instantly with
 * SQLITE_BUSY, ignoring `busy_timeout`).
 *
 * Only the second reason survives the port, and the first one could not be ported
 * even if it mattered:
 *
 *   - better-sqlite3 does not auto-begin a transaction, so there is no deferred read
 *     lock to upgrade. `BEGIN IMMEDIATE` is still used, because it takes the writer
 *     seat up front and *does* honour `busy_timeout` — which is what makes concurrent
 *     writers queue instead of failing.
 *   - a JavaScript mutex would be worthless here: the job engine runs on
 *     `worker_threads`, each with its own connection, and a module-level lock is
 *     per-isolate, not per-process. Cross-thread serialization is SQLite's job, via
 *     the writer seat plus `busy_timeout`.
 *
 * Retries cover the remaining case Python retried: an *external* process holding the
 * writer seat for longer than `busy_timeout`.
 */
import type { Db } from '../connection.js';

/** Matches the Python default of 5 attempts. */
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
 * Commits on success, rolls back and rethrows on failure. A nested call reuses the
 * open transaction, matching the Python `in_transaction` check — the outer block
 * still owns commit and rollback, so a nested failure aborts the whole unit rather
 * than half-committing.
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
        // Exponential backoff, as in Python. The jitter term there was
        // `time.time() % 0.05`, which is a clock-derived pseudo-random spread;
        // the point is to desynchronize competing writers, so any small spread
        // does the job.
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
