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
