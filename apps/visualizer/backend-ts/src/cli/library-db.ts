/**
 * Library-DB path resolution and connection lifecycle for the CLI. Port of
 * `core/cli_library_db.py`.
 *
 * Python spells this as two decorators, `@map_cli_errors` and
 * `@with_library_db(must_exist=…)`. Here it is one function a command body sits
 * inside, which is the same two jobs — resolve the path, open and always close,
 * turn anything thrown into `Error: …` and exit 1 — without the wrapper layer.
 */
import { existsSync } from 'node:fs';
import { openLibraryDb, type Db } from '../db/connection.js';
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
 * `mustExist: false` is `init` and `sync`, which are allowed to create the file;
 * every other command refuses a path that is not there rather than opening an
 * empty database and reporting zero of everything.
 */
export function withLibraryDb<T>(
  ctx: CommandContext,
  opts: { mustExist: boolean },
  body: (db: Db, dbPath: string) => T,
): T {
  const dbPath = resolveLibraryDbPath(ctx, opts);
  const db = openLibraryDb(dbPath);
  try {
    return body(db, dbPath);
  } finally {
    db.close();
  }
}
