/**
 * `init` — create an empty `library.db`. Port of `cmd_init` in
 * `core/cli_cmds_extra.py`.
 *
 * The command itself is a print, in both languages: opening a library DB with
 * `mustExist: false` is what applies the schema, so `init` is the name for doing
 * only that. What it buys is a database to point `scan` at before there is
 * anything to scan.
 */
import { withLibraryDb } from '../library-db.js';
import type { CommandContext } from '../registry.js';

export function cmdInit(ctx: CommandContext): number {
  return withLibraryDb(ctx, { mustExist: false }, (_db, dbPath) => {
    ctx.out(`Initialized database at ${dbPath}`);
    return 0;
  });
}
