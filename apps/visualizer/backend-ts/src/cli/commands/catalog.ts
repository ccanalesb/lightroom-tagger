/**
 * The two commands that read a `.lrcat` into `library.db`: `scan` and `sync`.
 * Port of `cmd_scan` and `cmd_sync` in `core/cli.py`.
 *
 * `scan` reads the whole catalog and upserts every row; `sync` diffs catalog ids
 * against the ones already indexed and fetches only what is missing. Both run on
 * drivers the visualizer's `catalog_sync` job already uses.
 */
import { existsSync } from 'node:fs';
import type { Db } from '../../db/connection.js';
import { storeImagesBatch } from '../../db/library/catalog.js';
import { libraryWrite } from '../../db/library/write.js';
import { syncCatalog } from '../../lightroom/catalog-sync.js';
import {
  connectCatalogReadOnly,
  getImageCount,
  getImageRecords,
} from '../../lightroom/reader.js';
import { CliError, withLibraryDb } from '../library-db.js';
import { boolFlag, intFlag, stringFlag } from '../parse.js';
import type { CommandContext } from '../registry.js';

/** `--catalog` if given, else `catalog_path` from `config.yaml`, and it must exist. */
function resolveCatalogPath(ctx: CommandContext): string {
  const catalogPath = stringFlag(ctx.args, 'catalog') ?? ctx.config.catalogPath;
  if (!catalogPath) {
    throw new CliError('No catalog path provided. Use --catalog or config.yaml');
  }
  if (!existsSync(catalogPath)) throw new CliError(`Catalog not found: ${catalogPath}`);
  return catalogPath;
}

/**
 * Refuse a `library.db` that has no schema in it.
 *
 * Python does not need this: its `managed_library_db` runs `init_database`, so
 * opening a path that is not there builds the whole schema on the way in. TS has
 * no bootstrap yet — `openLibraryDb` opens, and a fresh path yields an empty
 * file — so without this guard `scan` and `sync` would fail on `no such table:
 * images` from somewhere deep in a driver. The guard goes away when `init` lands.
 */
function requireSchema(db: Db, dbPath: string): void {
  const table = db
    .prepare("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'images'")
    .get();
  if (table === undefined) {
    throw new CliError(
      `Database has no schema: ${dbPath}. The TypeScript CLI cannot create one yet; ` +
        'initialize it with the Python CLI (`lightroom-tagger init`) first.',
    );
  }
}

export function cmdScan(ctx: CommandContext): number {
  const catalogPath = resolveCatalogPath(ctx);
  ctx.out(`Scanning catalog: ${catalogPath}`);

  // Read-only, as `connect_catalog` is: a scan must not be able to mutate a file
  // Lightroom owns.
  const catalog = connectCatalogReadOnly(catalogPath);
  let records;
  try {
    // `--verbose` prints the catalog total; Python reads it unconditionally, so
    // the query runs either way and the flag only decides whether it is shown.
    const total = getImageCount(catalog);
    if (boolFlag(ctx.args, 'verbose')) ctx.out(`Total images in catalog: ${total}`);
    records = getImageRecords(catalog, intFlag(ctx.args, 'limit'));
  } finally {
    catalog.close();
  }

  ctx.out(`Retrieved ${records.length} image records`);

  return withLibraryDb(ctx, { mustExist: false }, (db, dbPath) => {
    requireSchema(db, dbPath);
    // One transaction for the batch, where Python commits once per record — the
    // difference `storeImagesBatch` was written for. On a 43,000-image catalog
    // that is one fsync instead of 43,000, and an interrupted run leaves the
    // library untouched rather than half-synced.
    const count = libraryWrite(db, () => storeImagesBatch(db, records));
    ctx.out(`Indexed ${count} images to ${dbPath}`);
    return 0;
  });
}

export function cmdSync(ctx: CommandContext): number {
  const catalogPath = resolveCatalogPath(ctx);

  return withLibraryDb(ctx, { mustExist: false }, (db, dbPath) => {
    requireSchema(db, dbPath);
    ctx.out(`Syncing catalog: ${catalogPath}`);
    // No progress or cancellation callbacks: this is a foreground command, and
    // the driver only reports through them when a job runner is listening.
    const { result } = syncCatalog(catalogPath, db);
    ctx.out(
      `Added ${result.added} images; ${result.stale} stale in library ` +
        `(locking_mode=${result.locking_mode})`,
    );
    return 0;
  });
}
