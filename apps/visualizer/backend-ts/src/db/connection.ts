/**
 * SQLite connection helpers.
 *
 * `better-sqlite3` is synchronous, which matches the Python backend's `sqlite3`
 * usage directly — but it means anything long-running must execute on a worker
 * thread, never the HTTP event loop. Job handlers get their own connection per
 * thread, mirroring `JobRunner.thread_db()` in the Python runner.
 */
import Database from 'better-sqlite3';
import * as sqliteVec from 'sqlite-vec';

export type Db = Database.Database;

export interface OpenOptions {
  readonly?: boolean;
  /** Load the sqlite-vec extension (needed for the `vec0` embedding tables). */
  vec?: boolean;
}

/**
 * Open a connection. WAL plus a busy timeout, because the job processor and the
 * HTTP layer write concurrently from different threads.
 */
export function openDb(path: string, opts: OpenOptions = {}): Db {
  const readonly = opts.readonly ?? false;
  const db = new Database(path, { readonly });

  // Changing journal mode writes to the database header, so it can only be set on
  // a writable connection. `busy_timeout` is a connection setting and is safe
  // either way — readers still need it, since a WAL checkpoint can block them.
  if (!readonly) {
    db.pragma('journal_mode = WAL');
    db.pragma('foreign_keys = ON');
  }
  db.pragma('busy_timeout = 10000');

  if (opts.vec !== false) sqliteVec.load(db);
  return db;
}

/**
 * Open `library.db` with sqlite-vec loaded.
 *
 * The npm `sqlite-vec` package is version-matched to the Python `sqlite-vec==0.1.9`
 * pin, so the `vec0` virtual tables written by either side are mutually readable.
 */
export function openLibraryDb(path: string, opts: OpenOptions = {}): Db {
  return openDb(path, { ...opts, vec: true });
}

/** Serialize a float array into the little-endian float32 blob `vec0` expects. */
export function serializeFloat32(values: ArrayLike<number>): Buffer {
  const f = new Float32Array(values);
  return Buffer.from(f.buffer, f.byteOffset, f.byteLength);
}

/** Read a `vec0` embedding blob back into a Float32Array. */
export function deserializeFloat32(blob: Buffer): Float32Array {
  // Copy rather than view: the Buffer may be backed by a pooled ArrayBuffer.
  return new Float32Array(
    blob.buffer.slice(blob.byteOffset, blob.byteOffset + blob.byteLength) as ArrayBuffer,
  );
}
