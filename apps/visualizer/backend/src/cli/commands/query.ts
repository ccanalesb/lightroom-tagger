/**
 * The three commands that only read `library.db`: `search`, `export`, `stats`.
 *
 * All three take the same shape — resolve one filter, run one whole-table query,
 * print a count — because that is what the CLI has always been next to the
 * visualizer: the coarse view, without paging or ordering.
 */
import { writeFileSync } from 'node:fs';
import type { Db } from '../../db/connection.js';
import type { Row } from '../../db/library/catalog.js';
import {
  getAllImages,
  getImageCount,
  searchByColorLabel,
  searchByDate,
  searchByKeyword,
  searchByRating,
} from '../../db/library/catalog-search.js';
import { withLibraryDb } from '../library-db.js';
import { intFlag, stringFlag } from '../parse.js';
import type { CommandContext } from '../registry.js';

/**
 * The first filter the user gave, in the order the flags are checked.
 *
 * First rather than combined, matching Python's `if/elif` chain: two filters
 * together are not an intersection, the earlier one simply wins. `--rating 0` is
 * a filter, not an absent one, which is why it is tested for `null` rather than
 * for truthiness.
 */
function selectRows(db: Db, ctx: CommandContext): Row[] {
  const keyword = stringFlag(ctx.args, 'keyword');
  if (keyword !== null) return searchByKeyword(db, keyword);

  const rating = intFlag(ctx.args, 'rating');
  if (rating !== null) return searchByRating(db, rating);

  const colorLabel = stringFlag(ctx.args, 'color-label');
  if (colorLabel !== null) return searchByColorLabel(db, colorLabel);

  const dateStart = stringFlag(ctx.args, 'date-start');
  if (dateStart !== null) return searchByDate(db, dateStart, stringFlag(ctx.args, 'date-end'));

  return getAllImages(db);
}

/** Apply `--limit`, which truncates the result rather than bounding the query. */
function limited(rows: Row[], ctx: CommandContext): Row[] {
  const limit = intFlag(ctx.args, 'limit');
  // Falsy rather than null: Python's `if args.limit` treats `--limit 0` as unset,
  // so it returns everything rather than nothing.
  return limit ? rows.slice(0, limit) : rows;
}

export function cmdSearch(ctx: CommandContext): number {
  return withLibraryDb(ctx, { mustExist: true }, (db) => {
    const results = limited(selectRows(db, ctx), ctx);
    ctx.out(`Found ${results.length} images`);
    for (const record of results) {
      ctx.out(`  ${record['key']}: ${record['filename']} (rating: ${record['rating']})`);
    }
    return 0;
  });
}

export function cmdExport(ctx: CommandContext): number {
  return withLibraryDb(ctx, { mustExist: true }, (db) => {
    // `export` reads only `--keyword` and `--rating`; a `--date-start` is not one
    // of its flags, so this is the same chain with two links.
    const keyword = stringFlag(ctx.args, 'keyword');
    const rating = intFlag(ctx.args, 'rating');
    const selected =
      keyword !== null
        ? searchByKeyword(db, keyword)
        : rating !== null
          ? searchByRating(db, rating)
          : getAllImages(db);
    const results = limited(selected, ctx);

    const outputPath = stringFlag(ctx.args, 'output')!;
    const format = stringFlag(ctx.args, 'format') ?? 'json';
    if (format === 'json') {
      writeFileSync(outputPath, JSON.stringify(results, null, 2));
    } else if (results.length > 0) {
      writeFileSync(outputPath, toCsv(results));
    }
    // Python writes no file at all for an empty CSV export, and still reports
    // success. Kept, because the alternative — a header-only file — would need
    // column names that an empty result set does not have.

    ctx.out(`Exported ${results.length} images to ${outputPath}`);
    return 0;
  });
}

/**
 * `csv.DictWriter` over the first row's keys, with its `\r\n` line ending.
 *
 * Two cells do not match Python byte-for-byte, both because `DictWriter` falls
 * back to `str()` on a non-string: a decoded `keywords` writes as
 * `['sunset', 'beach']` there and `["sunset","beach"]` here, and a decoded
 * `instagram_posted` writes as `False` there and `false` here. Those are Python
 * reprs leaking into a data format rather than a contract anything reads back —
 * the JSON export, which is the one with a parser on the other end, is
 * identical. Emitting Python reprs from TypeScript to preserve them was the
 * worse trade.
 */
function toCsv(rows: readonly Row[]): string {
  const fieldnames = Object.keys(rows[0]!);
  const cell = (value: unknown): string => {
    const text =
      value === null || value === undefined
        ? ''
        : typeof value === 'object'
          ? JSON.stringify(value)
          : String(value);
    return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
  };
  return [
    fieldnames.join(','),
    ...rows.map((row) => fieldnames.map((f) => cell(row[f])).join(',')),
  ].join('\r\n') + '\r\n';
}

export function cmdStats(ctx: CommandContext): number {
  return withLibraryDb(ctx, { mustExist: true }, (db, dbPath) => {
    const count = getImageCount(db);

    // One row per distinct rating, where Python reads the whole table into memory
    // and tallies it. The column is `INTEGER DEFAULT 0` but nullable, and a null
    // sorts first here — Python raises `TypeError` comparing it to an int, which
    // its own error mapper then reports as a failed command.
    const rows = db
      .prepare('SELECT rating, COUNT(*) AS c FROM images GROUP BY rating ORDER BY rating')
      .all() as { rating: number | null; c: number }[];

    ctx.out(`Database: ${dbPath}`);
    ctx.out(`Total images: ${count}`);
    ctx.out('Ratings breakdown:');
    for (const row of rows) ctx.out(`  ${row.rating} star: ${row.c}`);
    return 0;
  });
}
