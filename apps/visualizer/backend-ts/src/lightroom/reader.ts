/**
 * Reads image metadata out of a Lightroom `.lrcat`. Port of
 * `lightroom_tagger/lightroom/reader.py`.
 *
 * The counterpart to `writer.ts`, and deliberately a separate connection function:
 * this one opens the catalog **read-only** so a browse or a sync cannot mutate a
 * file Lightroom owns. `writer.connectCatalog` opens it read-write and is guarded
 * by `raiseIfCatalogLocked` plus a backup; nothing here should ever reach for it.
 *
 * Only the functions `catalog_sync` needs are ported. `get_image_records`,
 * `get_image_count` and the `main()` CLI in the Python module are for the CLI
 * (step 6) and the schema explorer, neither of which runs in the backend.
 */
import Database from 'better-sqlite3';
import { homedir } from 'node:os';
import { join } from 'node:path';
import type { Db } from '../db/connection.js';

/**
 * The legacy `LIGHTRoom_*` spelling, still documented in the README and used by
 * `core/config.py`'s env overrides. The TS config loader dropped that whole family,
 * but these two are different in kind: they are the documented workaround for a
 * catalog on SMB/NAS that will not open at all, so a user who has one exported has
 * no other way in.
 */
const LEGACY_ENV_ALIASES: Record<string, string> = {
  LIGHTROOM_CATALOG_READONLY_URI: 'LIGHTRoom_CATALOG_READONLY_URI',
  LIGHTROOM_CATALOG_LOCKING_MODE: 'LIGHTRoom_CATALOG_LOCKING_MODE',
};

function catalogEnv(name: string): string | undefined {
  const value = process.env[name];
  if (value !== undefined) return value;
  const legacy = LEGACY_ENV_ALIASES[name];
  return legacy === undefined ? undefined : process.env[legacy];
}

/** True when `connectCatalogReadOnly` opens the catalog read-only (the default). */
export function catalogReadonlyUriEnabled(): boolean {
  return catalogEnv('LIGHTROOM_CATALOG_READONLY_URI') !== '0';
}

/**
 * The locking mode a catalog connection should ask for.
 *
 * Read-only opens default to NORMAL because `locking_mode=EXCLUSIVE` needs a write
 * lock and fails on some filesystems. Read-write opens default to EXCLUSIVE, which
 * is what lets SQLite use WAL without shared memory on NAS/SMB — the case where a
 * plain open fails with "unable to open database file".
 */
export function resolveCatalogLockingMode(readOnly: boolean): string {
  const raw = catalogEnv('LIGHTROOM_CATALOG_LOCKING_MODE');
  if (raw !== undefined) return raw.toUpperCase();
  return readOnly ? 'NORMAL' : 'EXCLUSIVE';
}

/** Apply the locking pragma when asked, falling back to NORMAL when it is refused. */
function applyLockingMode(conn: Db, lockingMode: string, readOnly: boolean): string {
  if (lockingMode !== 'EXCLUSIVE') return lockingMode;
  try {
    conn.pragma('locking_mode=EXCLUSIVE');
    return 'EXCLUSIVE';
  } catch (e) {
    const msg = String(e instanceof Error ? e.message : e).toLowerCase();
    if (readOnly || msg.includes('disk i/o error')) return 'NORMAL';
    throw e;
  }
}

/**
 * Open a Lightroom catalog for reading.
 *
 * `readonly: true` is better-sqlite3's `SQLITE_OPEN_READONLY`, which is what
 * Python's `file:...?mode=ro` URI asks for. Set `LIGHTROOM_CATALOG_READONLY_URI=0`
 * for the legacy read-write open, and `LIGHTROOM_CATALOG_LOCKING_MODE=EXCLUSIVE` to
 * request exclusive locking on a read-only open (with the NORMAL fallback above).
 *
 * The 30-second busy timeout matters: Lightroom holds the catalog while it is open,
 * and a scan that starts a second before Lightroom releases it should wait rather
 * than fail.
 */
export function connectCatalogReadOnly(catalogPath: string): Db {
  const readOnly = catalogReadonlyUriEnabled();
  const path = catalogPath.startsWith('~')
    ? join(homedir(), catalogPath.slice(1))
    : catalogPath;
  const conn = new Database(path, { readonly: readOnly, timeout: 30_000 });
  applyLockingMode(conn, resolveCatalogLockingMode(readOnly), readOnly);
  return conn;
}

/**
 * Normalize a Lightroom `captureTime` the way Python's `strptime`/`isoformat`
 * round-trip does.
 *
 * That round-trip is the identity for a well-formed `YYYY-MM-DDTHH:MM:SS`, and
 * anything it cannot parse comes back unchanged — so the only thing it really does
 * is zero-pad. That is load-bearing rather than cosmetic: the first ten characters
 * become the image key, so a catalog row reading `2024-1-5T…` has to produce
 * `2024-01-05_…` or the sync writes a second row for a photo Python already stored.
 */
export function parseCatalogDate(dateStr: string | null | undefined): string | null {
  if (!dateStr) return null;
  const m = /^(\d{1,4})-(\d{1,2})-(\d{1,2})T(\d{1,2}):(\d{1,2}):(\d{1,2})$/.exec(dateStr);
  if (!m) return dateStr;
  const [, y, mo, d, hh, mi, ss] = m;
  const pad = (v: string, width: number): string => v.padStart(width, '0');
  return `${pad(y!, 4)}-${pad(mo!, 2)}-${pad(d!, 2)}T${pad(hh!, 2)}:${pad(mi!, 2)}:${pad(ss!, 2)}`;
}

/**
 * A GPS coordinate as a number, or `null`.
 *
 * Note that an exact `0` also becomes `null`, because Python tests the raw value
 * for truthiness before parsing. Null Island is not in this catalog and matching
 * the existing rows is worth more than fixing that.
 */
export function parseGps(value: unknown): number | null {
  if (!value) return null;
  const n = Number(String(value).trim());
  return Number.isFinite(n) ? n : null;
}

/** The library key for a record: `YYYY-MM-DD_basename`. */
export function generateRecordKey(record: { date_taken?: string; filename?: string }): string {
  const dateTaken = record.date_taken ?? 'unknown';
  const datePart = dateTaken ? dateTaken.slice(0, 10) : 'unknown';
  return `${datePart}_${record.filename ?? 'unknown'}`;
}

/** One catalog image, in the shape `store_image` writes to `library.db`. */
export interface CatalogRecord {
  id: number;
  key: string;
  filename: string;
  filepath: string;
  date_taken: string;
  rating: number;
  pick: boolean;
  color_label: string;
  keywords: string[];
  title: string;
  caption: string;
  copyright: string;
  camera_make: string;
  camera_model: string;
  lens: string;
  focal_length: string | number;
  aperture: string | number;
  shutter_speed: string | number;
  iso: number;
  gps_latitude: number | null;
  gps_longitude: number | null;
  width: number;
  height: number;
  file_size: number;
}

/**
 * The metadata join. `AgLibraryFile` is the anchor because `catalog_sync` diffs on
 * `AgLibraryFile.id_local` — note that this is a *different* id from the
 * `Adobe_images.id_local` the keyword writer links against.
 */
const IMAGE_METADATA_SQL = `
    SELECT
        f.id_local as file_id,
        f.baseName as filename,
        f.extension as extension,
        fl.pathFromRoot as folder_path,
        rf.absolutePath as root_path,

        img.rating as rating,
        img.pick as pick_flag,
        img.colorLabels as color_label,
        img.fileWidth as width,
        img.fileHeight as height,

        img.captureTime as date_taken,

        exif.aperture as aperture,
        exif.focalLength as focal_length,
        exif.shutterSpeed as shutter_speed,
        exif.isoSpeedRating as iso,
        exif.gpsLatitude as gps_latitude,
        exif.gpsLongitude as gps_longitude,

        iptc.caption as caption,
        iptc.copyright as copyright

    FROM AgLibraryFile f
    JOIN AgLibraryFolder fl ON f.folder = fl.id_local
    JOIN AgLibraryRootFolder rf ON fl.rootFolder = rf.id_local
    LEFT JOIN Adobe_images img ON f.id_local = img.rootFile
    LEFT JOIN AgHarvestedExifMetadata exif ON img.id_local = exif.image
    LEFT JOIN AgLibraryIPTC iptc ON img.id_local = iptc.image
    WHERE f.id_local = ?
`;

/**
 * Keywords linked to an image — and a faithful port of a bug.
 *
 * `AgLibraryKeywordImage.image` references `Adobe_images.id_local`, but every
 * caller passes the `AgLibraryFile.id_local` the metadata join is keyed on. Those
 * are different id spaces, which is the exact mistake `writer.ts` warns about, so
 * this returns nothing: all 43,794 rows in the real `library.db` have `keywords`
 * of `[]`.
 *
 * Left as-is rather than repaired, because the sync is additions-only. A fix would
 * populate keywords for newly imported photos and leave the other 43,794 empty,
 * which makes `search_by_keyword` inconsistent instead of uniformly silent — a
 * worse failure than the one it replaces. Repairing it means a backfill, not a
 * one-line join change; tracked as #304.
 */
function keywordsForImage(conn: Db, imageId: number): string[] {
  const rows = conn
    .prepare(
      `SELECT k.name AS name
       FROM AgLibraryKeywordImage ki
       JOIN AgLibraryKeyword k ON ki.tag = k.id_local
       WHERE ki.image = ?`,
    )
    .all(imageId) as { name: string }[];
  return rows.map((r) => r.name);
}

/**
 * Fetch one image by `AgLibraryFile.id_local`, or `null` when the file is gone.
 *
 * `?? fallback` is wrong throughout this function and `|| fallback` is right:
 * Python coalesces on *falsiness*, so a zero focal length reads as `''` and a
 * missing caption as `''`. Half the rows in a real catalog already went through
 * those rules, so changing them would rewrite values on the next sync.
 */
export function getImageById(conn: Db, imageId: number): CatalogRecord | null {
  const row = conn.prepare(IMAGE_METADATA_SQL).get(imageId) as Record<string, unknown> | undefined;
  if (!row) return null;

  const filename = (row['filename'] as string) || '';
  const extension = (row['extension'] as string) || '';
  const rootPath = (row['root_path'] as string) || '';
  const folderPath = (row['folder_path'] as string) || '';
  const pickFlag = row['pick_flag'];

  const record: CatalogRecord = {
    id: row['file_id'] as number,
    key: '',
    filename,
    // Concatenated without a separator, because Lightroom stores both halves with
    // their trailing slash already on.
    filepath: rootPath + folderPath + (extension ? `${filename}.${extension}` : filename),
    date_taken: parseCatalogDate(row['date_taken'] as string | null) ?? '',
    rating: (row['rating'] as number) || 0,
    pick: pickFlag === null || pickFlag === undefined ? false : Boolean(pickFlag),
    color_label: (row['color_label'] as string) || '',
    keywords: keywordsForImage(conn, imageId),
    title: '',
    caption: (row['caption'] as string) || '',
    copyright: (row['copyright'] as string) || '',
    camera_make: '',
    camera_model: '',
    lens: '',
    focal_length: (row['focal_length'] as number) || '',
    aperture: (row['aperture'] as number) || '',
    shutter_speed: (row['shutter_speed'] as number) || '',
    iso: (row['iso'] as number) || 0,
    gps_latitude: parseGps(row['gps_latitude']),
    gps_longitude: parseGps(row['gps_longitude']),
    width: (row['width'] as number) || 0,
    height: (row['height'] as number) || 0,
    file_size: 0,
  };
  record.key = generateRecordKey(record);
  return record;
}

/** Every `AgLibraryFile.id_local` in the catalog — the set-difference input. */
export function listCatalogFileIds(conn: Db): number[] {
  const rows = conn.prepare('SELECT f.id_local AS id FROM AgLibraryFile f').all() as {
    id: number;
  }[];
  return rows.map((r) => Number(r.id));
}
