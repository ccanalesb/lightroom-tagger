/**
 * The three commands that only read `library.db`: `search`, `export`, `stats`.
 */
import { writeFileSync } from 'node:fs';
import type { Db } from '../../db/connection.js';
import type { Row } from '../../db/library/catalog.js';
import {
  getAllImages,
  searchByColorLabel,
  searchByDate,
  searchByKeyword,
  searchByRating,
} from '../../db/library/catalog-search.js';
import { getImageCount } from '../../db/library/statistics.js';
import { withLibraryDb } from '../library-db.js';
import { intFlag, stringFlag } from '../parse.js';
import type { CommandContext } from '../registry.js';

/**
 * The first filter given wins; multiple filters are not combined.
 *
 * `--rating 0` is a filter, tested for `null` not truthiness.
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
  // `--limit 0` is treated as unset and returns everything.
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
    // Empty CSV export writes no file and still reports success (no column names to infer).

    ctx.out(`Exported ${results.length} images to ${outputPath}`);
    return 0;
  });
}

/** CSV with `\r\n` line endings. Arrays JSON-encoded; booleans lowercase. */
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

    // `rating` is nullable despite DEFAULT 0; null sorts first here.
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
