/**
 * Structured catalog filtering and listing queries.
 *
 * The SQL is transcribed rather than rewritten. It is the part of the port most
 * likely to change behaviour invisibly — clause order determines positional binding
 * order, and the `ORDER BY` expressions decide what the grid shows first.
 */
import type { Db } from '../connection.js';
import {
  CATALOG_BEST_SCORE_JOIN_SQL,
  CATALOG_BEST_SCORE_SELECT_COLS,
} from './catalog-best-score.js';
import {
  appendQueryCatalogImageFilters,
  type Binding,
  type CatalogImageFilters,
} from './catalog-query-filters.js';
import { deserializeRow, type Row } from './catalog.js';

export type { CatalogImageFilters };

/** Raised for caller mistakes the API maps to HTTP 400. */
export class CatalogQueryError extends Error {}

export type SortByScore = 'asc' | 'desc';
export type SortByDate = 'newest' | 'oldest';

const SELECT_COLS =
  'i.*, d.summary AS description_summary, ' +
  'd.best_perspective AS description_best_perspective, ' +
  `${CATALOG_BEST_SCORE_SELECT_COLS}, ` +
  'st.stack_id AS stack_id, st.stack_size AS stack_member_count, ' +
  'CASE WHEN st.stack_id IS NOT NULL AND i.key = st.representative_key ' +
  'THEN 1 ELSE 0 END AS is_stack_representative';

/**
 * Build the FROM/JOIN chain shared by every catalog query.
 *
 * The optional `image_scores` join is what `score_perspective` switches on, and it
 * contributes a binding that must precede the WHERE bindings — hence the returned
 * `joinBindings`, which callers concatenate first.
 */
function buildJoin(scorePerspective: string): { sql: string; joinBindings: Binding[] } {
  let sql =
    'FROM images i ' +
    "LEFT JOIN image_descriptions d ON i.key = d.image_key AND d.image_type = 'catalog' ";
  const joinBindings: Binding[] = [];
  if (scorePerspective) {
    sql +=
      'LEFT JOIN image_scores s ON s.image_key = i.key ' +
      "AND s.image_type = 'catalog' AND s.perspective_slug = ? AND s.is_current = 1 ";
    joinBindings.push(scorePerspective);
  }
  sql += CATALOG_BEST_SCORE_JOIN_SQL;
  sql +=
    'LEFT JOIN image_stack_members AS m_st ON m_st.image_key = i.key ' +
    'LEFT JOIN image_stacks AS st ON st.stack_id = m_st.stack_id ';
  return { sql, joinBindings };
}

/**
 * Re-throw a filter-builder range error as a `CatalogQueryError`.
 *
 * `appendQueryCatalogImageFilters` signals the FTS short-query rule and the
 * `min_score_on_active` range with `RangeError`; both are 400s to the caller, and
 * both carry the exact message the Flask API returned.
 */
function appendFilters(clauses: string[], bindings: Binding[], f: CatalogImageFilters): void {
  try {
    appendQueryCatalogImageFilters(clauses, bindings, f);
  } catch (err) {
    if (err instanceof RangeError) throw new CatalogQueryError(err.message);
    throw err;
  }
}

function validateScoreArgs(f: CatalogImageFilters, useScoreJoin: boolean): void {
  if (f.minScore !== null && f.minScore !== undefined) {
    if (!useScoreJoin) throw new CatalogQueryError('min_score requires score_perspective');
    if (!(f.minScore >= 1 && f.minScore <= 10)) {
      throw new CatalogQueryError('min_score must be between 1 and 10');
    }
  }
}

export interface QueryCatalogImagesOptions extends CatalogImageFilters {
  scorePerspective?: string | null;
  sortByScore?: SortByScore | null;
  sortByDate?: SortByDate | null;
  /** When present, restricts the result to these keys; an empty list matches nothing. */
  restrictToKeys?: readonly string[] | null;
  limit?: number;
  offset?: number;
}

/**
 * Catalog keys from `keys` that satisfy the same filters as `queryCatalogImages`,
 * in **input order**.
 *
 * `sortBy*` are not applicable to membership and are omitted. Empty `keys` → `[]`.
 * This is the visual-similarity post-filter: results stay in CLIP distance order,
 * so only membership matters.
 */
export function filterOrderKeysInCatalog(
  db: Db,
  keys: readonly string[],
  opts: CatalogImageFilters & { scorePerspective?: string | null } = {},
): string[] {
  if (keys.length === 0) return [];
  const sp = (opts.scorePerspective ?? '').trim();
  validateScoreArgs(opts, Boolean(sp));

  const ph = keys.map(() => '?').join(',');
  const clauses: string[] = [`i.key IN (${ph})`];
  const bindings: Binding[] = [...keys];
  appendFilters(clauses, bindings, opts);

  const { sql: joinSql, joinBindings } = buildJoin(sp);
  const rows = db
    .prepare(`SELECT i.key AS image_key ${joinSql} WHERE ${clauses.join(' AND ')}`)
    .all(...joinBindings, ...bindings) as { image_key: string }[];

  const matched = new Set(rows.map((r) => String(r.image_key)));
  return keys.filter((k) => matched.has(k));
}

/**
 * List catalog images with AND-combined filters, SQL-level pagination, and a total.
 *
 * `sortByScore` requires `scorePerspective`; unscored rows for that perspective sort
 * after scored ones in both directions. When both sorts are set, score is the
 * primary key and date the tiebreaker.
 */
export function queryCatalogImages(
  db: Db,
  opts: QueryCatalogImagesOptions = {},
): { rows: Row[]; total: number } {
  const { sortByScore = null, sortByDate = null } = opts;
  if (sortByScore !== null && sortByScore !== 'asc' && sortByScore !== 'desc') {
    throw new CatalogQueryError("sort_by_score must be 'asc' or 'desc'");
  }
  if (sortByDate !== null && sortByDate !== 'newest' && sortByDate !== 'oldest') {
    throw new CatalogQueryError("sort_by_date must be 'newest' or 'oldest'");
  }

  const sp = (opts.scorePerspective ?? '').trim();
  const useScoreJoin = Boolean(sp);
  if (sortByScore !== null && !useScoreJoin) {
    throw new CatalogQueryError('sort_by_score requires score_perspective');
  }
  validateScoreArgs(opts, useScoreJoin);
  if (opts.minScoreOnActive !== null && opts.minScoreOnActive !== undefined) {
    if (!(opts.minScoreOnActive >= 1 && opts.minScoreOnActive <= 10)) {
      throw new CatalogQueryError('min_score_on_active must be between 1 and 10');
    }
  }

  const clauses: string[] = ['1=1'];
  const bindings: Binding[] = [];
  appendFilters(clauses, bindings, opts);

  if (opts.restrictToKeys !== null && opts.restrictToKeys !== undefined) {
    const rk = opts.restrictToKeys.filter(Boolean).map(String);
    if (rk.length === 0) {
      // An explicit empty restriction matches nothing, rather than everything.
      clauses.push('1=0');
    } else {
      clauses.push(`i.key IN (${rk.map(() => '?').join(',')})`);
      bindings.push(...rk);
    }
  }

  const whereSql = `WHERE ${clauses.join(' AND ')}`;
  const { sql: joinSql, joinBindings } = buildJoin(sp);

  // Date becomes a tiebreaker for score sorts only when the caller asked for it;
  // otherwise keep the original `i.key ASC` so unrelated callers are not silently
  // re-ordered by date.
  const dateTiebreaker =
    sortByDate === null
      ? 'i.key ASC'
      : `i.date_taken ${sortByDate === 'oldest' ? 'ASC' : 'DESC'}, i.key ASC`;

  let orderSql: string;
  if (sortByScore === 'desc') {
    orderSql = `ORDER BY (s.score IS NULL) ASC, s.score DESC, ${dateTiebreaker}`;
  } else if (sortByScore === 'asc') {
    orderSql = `ORDER BY (s.score IS NULL) ASC, s.score ASC, ${dateTiebreaker}`;
  } else if (sortByDate === 'oldest') {
    orderSql = 'ORDER BY i.date_taken ASC, i.key ASC';
  } else {
    orderSql = 'ORDER BY i.date_taken DESC, i.key ASC';
  }

  const countRow = db
    .prepare(`SELECT COUNT(*) AS cnt ${joinSql} ${whereSql}`)
    .get(...joinBindings, ...bindings) as { cnt: number };

  const rows = db
    .prepare(`SELECT ${SELECT_COLS} ${joinSql} ${whereSql} ${orderSql} LIMIT ? OFFSET ?`)
    .all(...joinBindings, ...bindings, opts.limit ?? 50, opts.offset ?? 0) as Row[];

  return { rows: rows.map(deserializeRow), total: Math.trunc(countRow.cnt) };
}

/**
 * Load catalog rows for `keys` with the same columns and joins as
 * `queryCatalogImages`, preserving **input order**.
 *
 * `primaryGridOnly` (the default) excludes non-representative stack members, the
 * same collapse the grid applies. Pass `false` to load every key — burst stack
 * member lists need exactly that.
 */
export function queryCatalogImagesByKeys(
  db: Db,
  keys: readonly string[],
  opts: { scorePerspective?: string | null; primaryGridOnly?: boolean } = {},
): Row[] {
  if (keys.length === 0) return [];
  const keyList = keys.map(String);
  const sp = (opts.scorePerspective ?? '').trim();
  const primaryGridOnly = opts.primaryGridOnly ?? true;

  const ph = keyList.map(() => '?').join(',');
  // Input order is restored with a bound CASE ladder, so a key containing a quote
  // cannot break the ORDER BY.
  const caseWhen = keyList.map((_k, i) => `WHEN ? THEN ${i}`).join(' ');
  const orderSql = `ORDER BY CASE i.key ${caseWhen} END`;

  const { sql: joinSql, joinBindings } = buildJoin(sp);

  const whereSql = primaryGridOnly
    ? `WHERE i.key IN (${ph}) AND (m_st.image_key IS NULL OR i.key = st.representative_key)`
    : `WHERE i.key IN (${ph})`;

  const rows = db
    .prepare(`SELECT ${SELECT_COLS} ${joinSql} ${whereSql} ${orderSql}`)
    .all(...joinBindings, ...keyList, ...keyList) as Row[];
  return rows.map(deserializeRow);
}

/**
 * True for catalog keys that are stack representatives or not in a stack at all.
 *
 * False for a **non-representative** stack member, which the default grid hides.
 */
export function catalogKeyIsPrimaryGridRow(db: Db, imageKey: string): boolean {
  const row = db
    .prepare(
      `
        SELECT NOT EXISTS(
            SELECT 1 FROM image_stack_members m
            INNER JOIN image_stacks s ON s.stack_id = m.stack_id
            WHERE m.image_key = ? AND m.image_key <> s.representative_key
        ) AS ok
        `,
    )
    .get(imageKey) as { ok: number } | undefined;
  return Boolean(row && Math.trunc(row.ok));
}
