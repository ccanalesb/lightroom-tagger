/**
 * Library-DB path resolution and connection lifecycle for the CLI.
 */
import { existsSync } from 'node:fs';
import { openLibraryDb, type Db } from '../db/connection.js';
import { initLibraryDb } from '../db/library/bootstrap.js';
import type { CommandContext } from './registry.js';
import { stringFlag } from './parse.js';

const MISSING_DB_PATH_MSG = 'No database path provided. Use --db or config.yaml';

/** A failure the user can read and act on; printed without a stack trace. */
export class CliError extends Error {}

/** `--db` if given, else `db_path` from `config.yaml`. */
export function resolveLibraryDbPath(ctx: CommandContext, opts: { mustExist: boolean }): string {
  const dbPath = stringFlag(ctx.args, 'db') ?? ctx.config.dbPath;
  if (!dbPath) throw new CliError(MISSING_DB_PATH_MSG);
  if (opts.mustExist && !existsSync(dbPath)) {
    throw new CliError(`Database not found: ${dbPath}`);
  }
  return dbPath;
}

/**
 * Run `body` against an open library DB, closing it whatever happens.
 *
 * `mustExist: false` bootstraps the schema (`init`, `scan`, `sync`). Other commands
 * refuse a missing path instead of opening an empty database — applying the schema
 * on open would make read-only commands writers.
 */
export function withLibraryDb<T>(
  ctx: CommandContext,
  opts: { mustExist: boolean },
  body: (db: Db, dbPath: string) => T,
): T {
  const dbPath = resolveLibraryDbPath(ctx, opts);
  const db = opts.mustExist ? openLibraryDb(dbPath) : initLibraryDb(dbPath);
  try {
    return body(db, dbPath);
  } finally {
    db.close();
  }
}

/**
 * `withLibraryDb` for a body that awaits.
 *
 * A separate function rather than a union return, because the synchronous version's
 * `finally` would close the connection the moment an async body returned its promise.
 */
export async function withLibraryDbAsync<T>(
  ctx: CommandContext,
  opts: { mustExist: boolean },
  body: (db: Db, dbPath: string) => Promise<T>,
): Promise<T> {
  const dbPath = resolveLibraryDbPath(ctx, opts);
  const db = opts.mustExist ? openLibraryDb(dbPath) : initLibraryDb(dbPath);
  try {
    return await body(db, dbPath);
  } finally {
    db.close();
  }
}
