/**
 * Image description queries. Port of the read paths in
 * `lightroom_tagger/core/database/descriptions.py`.
 */
import type { Db } from '../connection.js';

/**
 * Columns stored as JSON text. They are decoded on read; a value that fails to
 * parse is left as the raw string rather than raising, matching the Python
 * `except (JSONDecodeError, TypeError): pass`. Older rows predate the current
 * shape, and a malformed one should not take down the whole page.
 */
const JSON_COLUMNS = [
  'composition',
  'perspectives',
  'technical',
  'subjects',
  'dominant_colors',
  'mood_tags',
] as const;

export type DescriptionRow = Record<string, unknown>;

function decodeJsonColumns(row: DescriptionRow): DescriptionRow {
  const out = { ...row };
  for (const col of JSON_COLUMNS) {
    const val = out[col];
    if (typeof val === 'string') {
      try {
        out[col] = JSON.parse(val);
      } catch {
        // Leave the raw string in place, as Python does.
      }
    }
  }
  return out;
}

/** One `image_descriptions` row by image key, JSON columns decoded. */
export function getImageDescription(db: Db, imageKey: string): DescriptionRow | null {
  const row = db
    .prepare('SELECT * FROM image_descriptions WHERE image_key = ?')
    .get(imageKey) as DescriptionRow | undefined;
  return row ? decodeJsonColumns(row) : null;
}

export interface DescriptionListItem {
  image_key: string;
  /** The query selects `'catalog' AS image_type` literally, so this is never
   *  anything else — the Instagram scope was removed (#218). */
  image_type: 'catalog';
  filename: string | null;
  date_ref: string | null;
  summary: string | null;
  best_perspective: string | null;
  desc_model: string | null;
  described_at: string | null;
  has_description: number;
}

/**
 * Images joined with their descriptions for the descriptions page.
 *
 * Ordering matches Python exactly: described rows first (NULL `described_at`
 * sorts last), then newest description, then newest capture date. The UI depends
 * on undescribed images sinking to the bottom.
 */
export function getAllImagesWithDescriptions(
  db: Db,
  opts: { describedOnly?: boolean; limit?: number; offset?: number } = {},
): { items: DescriptionListItem[]; total: number } {
  const base = `
    SELECT i.key AS image_key, 'catalog' AS image_type,
           i.filename, i.date_taken AS date_ref,
           d.summary, d.best_perspective, d.model_used AS desc_model,
           d.described_at,
           CASE WHEN d.image_key IS NOT NULL THEN 1 ELSE 0 END AS has_description
    FROM images i
    LEFT JOIN image_descriptions d
      ON i.key = d.image_key AND d.image_type = 'catalog'
  `;
  const wrapper = opts.describedOnly
    ? `SELECT * FROM (${base}) t WHERE t.has_description = 1`
    : `SELECT * FROM (${base}) t`;

  const total = Number(
    (db.prepare(`SELECT COUNT(*) AS cnt FROM (${wrapper})`).get() as { cnt: number }).cnt,
  );

  const items = db
    .prepare(
      `${wrapper} ORDER BY CASE WHEN t.described_at IS NULL THEN 1 ELSE 0 END, ` +
        `t.described_at DESC, t.date_ref DESC LIMIT ? OFFSET ?`,
    )
    .all(opts.limit ?? 50, opts.offset ?? 0) as DescriptionListItem[];

  return { items, total };
}

/**
 * Build an FTS5 `MATCH` string (AND-joined tokens) for `description_search`
 * (NLS-02, D-11–D-13).
 *
 * Returns `{ match, error }` where `match` is suitable as the sole bound parameter
 * to `... MATCH ?`, or `null` when no FTS filter should apply. `error` is non-null
 * only for the short-query rule (D-12), which the caller turns into a 400.
 *
 * Tokenization: maximal ASCII alphanumeric runs on the trimmed input, so punctuation
 * and FTS/SQL metacharacters can never reach the match string. Tokens shorter than
 * two characters are dropped; if none remain, no filter applies (D-13).
 */
export function buildDescriptionFtsQuery(raw: string | null | undefined): {
  match: string | null;
  error: string | null;
} {
  if (raw === null || raw === undefined) return { match: null, error: null };
  const s = raw.trim();
  if (!s) return { match: null, error: null };
  if (s.length < 2) {
    return { match: null, error: 'description_search must be at least 2 characters' };
  }
  const words = (s.match(/[A-Za-z0-9]+/g) ?? []).filter((t) => t.length >= 2);
  if (words.length === 0) return { match: null, error: null };
  // Double-quote each term so FTS5 reserved words (OR, AND, NOT) stay literals.
  const quoted = words.map((t) => `"${t.replaceAll('"', '""')}"`);
  return { match: quoted.join(' AND '), error: null };
}

/**
 * Subquery yielding catalog image keys whose description matches an FTS `?` param.
 * Shared by the CLI keyword search and the catalog `description_search` filter.
 */
export const DESCRIPTION_FTS_KEY_SUBQUERY =
  'SELECT d2.image_key FROM image_descriptions d2 ' +
  'INNER JOIN image_descriptions_fts ON image_descriptions_fts.rowid = d2.rowid ' +
  "WHERE d2.image_type = 'catalog' AND image_descriptions_fts MATCH ?";
