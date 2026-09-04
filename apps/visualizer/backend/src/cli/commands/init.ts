/**
 * `init` — create an empty `library.db`.
 *
 * Opening with `mustExist: false` applies the schema; this command does only that.
 */
import { withLibraryDb } from '../library-db.js';
import type { CommandContext } from '../registry.js';

export function cmdInit(ctx: CommandContext): number {
  return withLibraryDb(ctx, { mustExist: false }, (_db, dbPath) => {
    ctx.out(`Initialized database at ${dbPath}`);
    return 0;
  });
}
