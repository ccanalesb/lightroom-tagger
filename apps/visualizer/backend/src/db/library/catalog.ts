/**
 * Catalog image rows.
 */
import { existsSync } from 'node:fs';
import type { Db } from '../connection.js';
import { decodeJsonColumns, type Row } from './row-decode.js';

export type { Row };

/**
 * Columns stored as JSON text and decoded on read.
 *
 * `exif` is JSON-eligible even though the API types it as a string; in practice
 * the column is empty on every row.
 */
const JSON_COLUMNS = ['keywords', 'exif', 'exif_data', 'logs', 'metadata', 'result'] as const;

/** Columns SQLite stores as 0/1 that the API contract exposes as booleans. */
const BOOL_COLUMNS = ['instagram_posted', 'processed', 'is_stack_representative'] as const;

/** Decode JSON columns and coerce 0/1 columns to booleans, in place on a copy. */
export function deserializeRow<T extends Row>(row: T): T {
  const out = decodeJsonColumns(row, JSON_COLUMNS);
  for (const col of BOOL_COLUMNS) {
    // `is_stack_representative` stays null when absent from a stack; the other bool
    // columns coerce whenever the key is present.
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

/** The library key for a record: `YYYY-MM-DD_basename`, as `lightroom/reader` builds it. */
export function generateKey(record: { date_taken?: unknown; filename?: unknown }): string {
  const dateTaken = record.date_taken ?? 'unknown';
  const datePart = dateTaken ? String(dateTaken).slice(0, 10) : 'unknown';
  return `${datePart}_${record.filename ?? 'unknown'}`;
}

/** JSON text for a value already stored as text, or `null`. */
function serializeJson(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  return typeof value === 'string' ? value : JSON.stringify(value);
}

/** An `images` column value better-sqlite3 will bind: booleans become 0/1. */
function bindable(value: unknown): unknown {
  return typeof value === 'boolean' ? (value ? 1 : 0) : (value ?? null);
}

/**
 * `images.id` — the catalog's `AgLibraryFile.id_local` — as an integer bind.
 *
 * JavaScript numbers bind as SQLite REAL; a plain `100` becomes `'100.0'` in a
 * TEXT column, and `catalog_sync` diffs parse that as no id. BigInt triggers
 * `sqlite3_bind_int64`. Other numeric columns stay as doubles — existing rows
 * already store `'800.0'` and `'50.0'`.
 */
function bindableCatalogId(value: unknown): unknown {
  if (typeof value === 'number' && Number.isInteger(value)) return BigInt(value);
  return bindable(value);
}

/**
 * `images` columns in insert order. Every one is written on conflict except `key`
 * (the conflict target) and `instagram_posted`, which is the user's own flag and
 * would be wiped by a catalog that knows nothing about it.
 */
const IMAGE_COLUMNS = [
  'key',
  'id',
  'filename',
  'filepath',
  'date_taken',
  'rating',
  'pick',
  'color_label',
  'keywords',
  'title',
  'caption',
  'description',
  'copyright',
  'camera_make',
  'camera_model',
  'lens',
  'focal_length',
  'aperture',
  'shutter_speed',
  'iso',
  'gps_latitude',
  'gps_longitude',
  'width',
  'height',
  'file_size',
  'instagram_posted',
  'image_hash',
  'analyzed_at',
  'phash',
  'exif',
  'catalog_path',
] as const;

const IMAGE_UPSERT_SQL =
  `INSERT INTO images (${IMAGE_COLUMNS.join(', ')})\n` +
  `VALUES (${IMAGE_COLUMNS.map((c) => `:${c}`).join(', ')})\n` +
  'ON CONFLICT(key) DO UPDATE SET ' +
  IMAGE_COLUMNS.filter((c) => c !== 'key' && c !== 'instagram_posted')
    .map((c) => `${c}=excluded.${c}`)
    .join(', ');

/** Column defaults, matching `record.get(col, default)` in `store_image`. */
const IMAGE_DEFAULTS: Partial<Record<(typeof IMAGE_COLUMNS)[number], unknown>> = {
  filename: '',
  filepath: '',
  date_taken: '',
  rating: 0,
  pick: 0,
  color_label: '',
  keywords: [],
  title: '',
  caption: '',
  description: '',
  copyright: '',
  camera_make: '',
  camera_model: '',
  lens: '',
  focal_length: '',
  aperture: '',
  shutter_speed: '',
  iso: '',
  instagram_posted: false,
  catalog_path: '',
};

/**
 * Bind one image's columns by name.
 *
 * Accepts `object` because callers pass `CatalogRecord`, which has no index signature.
 */
function imageParams(source: object): Record<string, unknown> {
  const record = source as Record<string, unknown>;
  const params: Record<string, unknown> = { key: generateKey(record) };
  for (const col of IMAGE_COLUMNS) {
    if (col === 'key') continue;
    const raw = record[col] ?? IMAGE_DEFAULTS[col] ?? null;
    if (col === 'keywords' || col === 'exif') params[col] = serializeJson(raw);
    else if (col === 'id') params[col] = bindableCatalogId(raw);
    else params[col] = bindable(raw);
  }
  return params;
}

/**
 * Upsert one catalog image and return its key. Does NOT commit — call inside
 * `libraryWrite`.
 */
export function storeImage(db: Db, record: object): string {
  const params = imageParams(record);
  db.prepare(IMAGE_UPSERT_SQL).run(params);
  return String(params['key']);
}

/**
 * Upsert many catalog images through one prepared statement. Returns the count.
 *
 * Caller wraps the batch in one `libraryWrite` transaction.
 */
export function storeImagesBatch(db: Db, records: readonly object[]): number {
  const stmt = db.prepare(IMAGE_UPSERT_SQL);
  for (const record of records) stmt.run(imageParams(record));
  return records.length;
}

/**
 * Catalog images with no usable vision-cache entry, for `enrich-catalog` to warm.
 *
 * Two passes: anti-join for uncached rows, then filesystem check for rows whose
 * compressed file is gone (the cache directory is disposable while `vision_cache`
 * is not).
 */
export function getCatalogImagesMissingCache(db: Db): Row[] {
  const uncached = db
    .prepare(
      `
        SELECT i.* FROM images i
        LEFT JOIN vision_cache vc ON i.key = vc.key
        WHERE vc.key IS NULL OR vc.compressed_path IS NULL
        `,
    )
    .all() as Row[];
  const images = uncached.map((r) => deserializeRow(r));

  const cached = db
    .prepare(
      `
        SELECT i.*, vc.compressed_path FROM images i
        INNER JOIN vision_cache vc ON i.key = vc.key
        WHERE vc.compressed_path IS NOT NULL
        `,
    )
    .all() as Row[];

  for (const row of cached) {
    const compressedPath = row['compressed_path'];
    // The oversized sentinel is not a path; missing files re-offer the image each run.
    if (typeof compressedPath === 'string' && compressedPath && !existsSync(compressedPath)) {
      images.push(deserializeRow(row));
    }
  }

  return images;
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
