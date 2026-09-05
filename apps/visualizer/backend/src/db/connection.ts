/**
 * SQLite connection helpers.
 *
 * `better-sqlite3` is synchronous — long-running work must run on a worker thread,
 * not the HTTP event loop. Job handlers open their own connection per thread.
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
 * The sqlite-vec pin matches the extension version used to write existing `vec0`
 * tables, so embeddings remain readable across backends.
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
