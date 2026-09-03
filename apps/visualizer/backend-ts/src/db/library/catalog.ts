/**
 * Catalog image rows. Port of the read/write helpers the images API uses from
 * `core/database/catalog.py` and `core/database/catalog_statistics.py`.
 */
import type { Db } from '../connection.js';

export type Row = Record<string, unknown>;

/**
 * Columns stored as JSON text and decoded on read.
 *
 * A value that fails to parse is left as the raw string rather than raising,
 * matching Python's `except (JSONDecodeError, TypeError): pass`. `exif` is on this
 * list even though the API contract types it as a string — that is the Python
 * behaviour, and in this catalog the column is empty on every one of the 43,451
 * rows, so the two never actually disagree. Ported as-is rather than "fixed",
 * because a divergence here would be invisible until some future row had JSON in it.
 */
const JSON_COLUMNS = ['keywords', 'exif', 'exif_data', 'logs', 'metadata', 'result'] as const;

/** Columns SQLite stores as 0/1 that the API contract exposes as booleans. */
const BOOL_COLUMNS = ['instagram_posted', 'processed', 'is_stack_representative'] as const;

/** Decode JSON columns and coerce 0/1 columns to booleans, in place on a copy. */
export function deserializeRow<T extends Row>(row: T): T {
  const out = { ...row };
  for (const col of JSON_COLUMNS) {
    const val = out[col];
    if (typeof val === 'string') {
      try {
        (out as Row)[col] = JSON.parse(val);
      } catch {
        // Leave the raw string in place, as Python does.
      }
    }
  }
  for (const col of BOOL_COLUMNS) {
    // Python coerces `instagram_posted` / `processed` whenever the key is present,
    // but `is_stack_representative` only when it is also non-null — a null there
    // means "not part of a stack" and must stay null, not become false.
    if (!(col in out)) continue;
    if (col === 'is_stack_representative' && out[col] === null) continue;
    (out as Row)[col] = Boolean(out[col]);
  }
  return out;
}

/** One `images` row by key, JSON/bool columns normalized. */
export function getImage(db: Db, key: string): Row | null {
  const row = db.prepare('SELECT * FROM images WHERE key = ?').get(key) as Row | undefined;
  return row ? deserializeRow(row) : null;
}

/**
 * Set `images.instagram_posted`. Does NOT commit — call inside `libraryWrite`.
 * Returns whether a row was updated.
 */
export function setInstagramPosted(db: Db, key: string, posted: boolean): boolean {
  const info = db
    .prepare('UPDATE images SET instagram_posted = ? WHERE key = ?')
    .run(posted ? 1 : 0, key);
  return info.changes > 0;
}

/** Distinct `YYYYMM` months from catalog `date_taken`, newest first. */
export function getCatalogMonths(db: Db): string[] {
  const rows = db
    .prepare(
      `
        SELECT DISTINCT strftime('%Y%m', date_taken) AS month
        FROM images
        WHERE date_taken IS NOT NULL
        ORDER BY month DESC
        `,
    )
    .all() as { month: string | null }[];
  return rows.filter((r) => r.month).map((r) => String(r.month));
}
