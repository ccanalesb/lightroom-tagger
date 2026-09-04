/**
 * Catalog image rows. Port of the read/write helpers the images API uses from
 * `core/database/catalog.py` and `core/database/catalog_statistics.py`.
 */
import { existsSync } from 'node:fs';
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

/** The library key for a record: `YYYY-MM-DD_basename`, as `lightroom/reader` builds it. */
export function generateKey(record: { date_taken?: unknown; filename?: unknown }): string {
  const dateTaken = record.date_taken ?? 'unknown';
  const datePart = dateTaken ? String(dateTaken).slice(0, 10) : 'unknown';
  return `${datePart}_${record.filename ?? 'unknown'}`;
}

/** JSON text for a value already stored as text, or `null` — Python's `_serialize_json`. */
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
 * Every JavaScript number binds as SQLite REAL, and `id` is a TEXT column, so a
 * plain `100` lands as `'100.0'` where Python's int bind gives `'100'`. That is not
 * cosmetic: `catalog_sync` diffs on this column and parses it back as an integer,
 * so `'100.0'` reads as no id at all and every sync re-fetches the whole catalog.
 * A BigInt is the only way to ask better-sqlite3 for `sqlite3_bind_int64`.
 *
 * The other numeric columns are left alone deliberately. Lightroom types
 * `isoSpeedRating`, `focalLength` and `aperture` as REAL, and the 43,794 rows
 * already in `library.db` read `'800.0'` and `'50.0'` — which is exactly what a
 * double bind produces.
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
 * Takes `object` rather than `Record<string, unknown>` because the callers pass
 * `CatalogRecord`, a declared interface with no index signature, which does not
 * satisfy that type. The one assertion belongs here, in the module that owns the
 * column mapping, rather than at each call site.
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
 * Python commits inside `store_image`, once per record: 43,000 fsyncs on a first
 * sync, and a run interrupted halfway leaves a partially synced catalog. Here the
 * caller wraps the whole batch in one `libraryWrite`.
 */
export function storeImagesBatch(db: Db, records: readonly object[]): number {
  const stmt = db.prepare(IMAGE_UPSERT_SQL);
  for (const record of records) stmt.run(imageParams(record));
  return records.length;
}

/**
 * Catalog images with no usable vision-cache entry, for `enrich-catalog` to warm.
 *
 * Two passes, as in Python. The first is a plain anti-join. The second reads
 * every row that *claims* a cached file and keeps the ones whose file is gone,
 * which is the case that matters in practice: the cache directory is local and
 * disposable while `vision_cache` is not, so deleting it leaves 43,000 rows
 * pointing at nothing.
 *
 * The second pass therefore stats one file per cached row. That is the cost of
 * the query and there is no cheaper way to ask the question.
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
    // The oversized sentinel is not a path, so it never exists and every
    // oversized image is re-offered on every run. Python does the same, and the
    // retry is cheap next to being unable to notice a sidecar that has appeared
    // since — see `isVisionCacheValid`.
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
