/**
 * `enrich-catalog`. Port of `cmd_enrich_catalog` in `core/cli_cmds_extra.py`,
 * reduced to its cache-warming half.
 *
 * Python's command has two modes. `--cache-only` warms the vision cache, which is
 * what this does. The default mode calls `lightroom/enricher.py`, and that half
 * is deliberately not ported — see `docs/plans/ts-backend-migration.md`. The
 * short version is that it has never run: it stamps `images.analyzed_at` on every
 * image it stores, and that column is NULL on all 43,794 rows.
 *
 * So the flag is accepted and the command always warms the cache, the way `scan`
 * still accepts `--workers`. An existing `enrich-catalog --cache-only` is
 * unchanged; a bare `enrich-catalog` now does the useful half instead of opening
 * an LLM call per image in the catalog.
 */
import { warmVisionCache } from '../../vision/vision-cache.js';
import { withLibraryDbAsync } from '../library-db.js';
import { intFlag } from '../parse.js';
import type { CommandContext } from '../registry.js';

export function cmdEnrichCatalog(ctx: CommandContext): Promise<number> {
  return withLibraryDbAsync(ctx, { mustExist: true }, async (db) => {
    const result = await warmVisionCache(db, intFlag(ctx.args, 'limit'));
    ctx.out(`Processed: ${result.processed}`);
    ctx.out(`Skipped: ${result.skipped}`);
    ctx.out(`Errors: ${result.errors}`);
    return 0;
  });
}
