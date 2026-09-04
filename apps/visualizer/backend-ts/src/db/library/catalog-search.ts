/**
 * Whole-table `images` queries. Port of the `search_by_*` family in
 * `core/database/catalog.py`.
 *
 * These predate the grid's filter builder and are coarser than it: no paging, no
 * ordering, no joins, `SELECT *` over the whole table. The CLI is the only caller
 * — the HTTP API uses `queryCatalogImages`, which composes its filters — so they
 * are kept apart from `catalog-query.ts` rather than folded into it.
 */
import type { Db } from '../connection.js';
import { deserializeRow, type Row } from './catalog.js';
import { buildDescriptionFtsQuery, DESCRIPTION_FTS_KEY_SUBQUERY } from './descriptions.js';

const all = (db: Db, sql: string, params: readonly unknown[] = []): Row[] =>
  (db.prepare(sql).all(...(params as never[])) as Row[]).map(deserializeRow);

/** Every image, JSON and boolean columns normalized. */
export function getAllImages(db: Db): Row[] {
  return all(db, 'SELECT * FROM images');
}

export function getImageCount(db: Db): number {
  return Number((db.prepare('SELECT COUNT(*) AS cnt FROM images').get() as { cnt: number }).cnt);
}

/**
 * Substring match across the Lightroom metadata, widened by an FTS5 match over
 * the AI descriptions.
 *
 * A term too short for FTS still searches the metadata half: the builder's
 * minimum length is the web API's rule, where it answers 400, and here it only
 * means "this term has no FTS half" — a one-character keyword stays a legitimate
 * query (#261).
 */
export function searchByKeyword(db: Db, keyword: string): Row[] {
  const pattern = `%${keyword}%`;
  const params: unknown[] = [pattern, pattern, pattern, pattern];
  let where =
    'keywords LIKE ? COLLATE NOCASE OR filename LIKE ? COLLATE NOCASE OR ' +
    'title LIKE ? COLLATE NOCASE OR description LIKE ? COLLATE NOCASE';

  const { match } = buildDescriptionFtsQuery(keyword);
  if (match !== null) {
    where = `(${where}) OR key IN (${DESCRIPTION_FTS_KEY_SUBQUERY})`;
    params.push(match);
  }

  // `DISTINCT` over `SELECT *`, as Python has it. It cannot deduplicate anything
  // — `key` is the primary key and the FTS subquery is an `IN`, not a join — but
  // it is what the stored query plan has always been.
  return all(db, `SELECT DISTINCT * FROM images WHERE ${where}`, params);
}

export function searchByRating(db: Db, minRating = 0): Row[] {
  return all(db, 'SELECT * FROM images WHERE rating >= ?', [minRating]);
}

export function searchByColorLabel(db: Db, label: string): Row[] {
  return all(db, 'SELECT * FROM images WHERE LOWER(color_label) = LOWER(?)', [label]);
}

/** Images from `startDate` on, bounded by `endDate` when one is given. */
export function searchByDate(db: Db, startDate: string, endDate?: string | null): Row[] {
  return endDate
    ? all(db, 'SELECT * FROM images WHERE date_taken >= ? AND date_taken <= ?', [
        startDate,
        endDate,
      ])
    : all(db, 'SELECT * FROM images WHERE date_taken >= ?', [startDate]);
}
