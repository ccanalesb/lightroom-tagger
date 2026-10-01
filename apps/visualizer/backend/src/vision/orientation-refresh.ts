/**
 * Carry Lightroom's orientation codes into `library.db`, and deal with what a
 * changed code means for the vision cache.
 *
 * A cache JPEG is only valid at its photo's current code (`vision-cache.ts`), so
 * a changed code is enough to get the JPEG rebuilt. What it cannot do by itself
 * is retire the descriptions, scores and CLIP vector made from the old JPEG —
 * that happens here, once per change, because the stored code is updated in the
 * same pass.
 *
 * Caches built before codes were recorded carry no code. Most are unturned, but
 * some RAWs came out of the decoder already turned by the camera's tag; for a
 * quarter turn that is visible in the JPEG's shape, and those keep their outputs.
 */
import sharp from 'sharp';
import { existsSync } from 'node:fs';
import type { Db } from '../db/connection.js';
import { VISION_CACHE_OVERSIZED_SENTINEL } from '../db/library/vision-cache.js';
import { markVisionOutputsStale } from '../db/library/vision-stale.js';
import { libraryWrite } from '../db/library/write.js';
import {
  isQuarterTurn,
  normalizeOrientation,
  UPRIGHT,
  type OrientationCode,
} from '../imaging/orientation.js';

export interface OrientationRefreshResult {
  /** Rows whose `images.orientation` changed. */
  updated: number;
  /** Images whose outputs were marked stale and whose cache JPEG must be rebuilt. */
  stale: number;
}

interface Row {
  key: string;
  id: unknown;
  orientation: string | null;
  width: number | null;
  height: number | null;
  cached: string | null;
  compressed_path: string | null;
  cache_orientation: string | null;
}

/** Whether a pre-orientation cache JPEG already shows the photo the way `want` does. */
async function legacyCacheMatches(row: Row, want: OrientationCode): Promise<boolean> {
  if (want === UPRIGHT) return true;
  if (!isQuarterTurn(want)) return false;
  const path = row.compressed_path;
  if (!path || path === VISION_CACHE_OVERSIZED_SENTINEL || !existsSync(path)) return false;
  const w = row.width ?? 0;
  const h = row.height ?? 0;
  if (!w || !h || w === h) return false;
  const meta = await sharp(path).metadata().catch(() => null);
  if (!meta?.width || !meta.height || meta.width === meta.height) return false;
  // `images.width/height` are the stored pixels'; turned upright they swap.
  return meta.width > meta.height === h > w;
}

/**
 * Store each image's code from `catalogCodes` (keyed by `AgLibraryFile.id_local`).
 * Where a code changed: stamp a cache JPEG that already matches it, otherwise mark
 * the image's outputs stale.
 */
export async function refreshImageOrientations(
  db: Db,
  catalogCodes: ReadonlyMap<number, string | null>,
): Promise<OrientationRefreshResult> {
  const rows = db
    .prepare(
      `SELECT i.key, i.id, i.orientation, i.width, i.height,
              vc.key AS cached, vc.compressed_path, vc.orientation AS cache_orientation
       FROM images i LEFT JOIN vision_cache vc ON vc.key = i.key`,
    )
    .all() as Row[];

  const updates: { key: string; code: string | null }[] = [];
  const stamps: { key: string; code: OrientationCode }[] = [];
  const stale: string[] = [];

  for (const row of rows) {
    const id = Number(String(row.id ?? '').trim());
    if (!Number.isInteger(id) || !catalogCodes.has(id)) continue;
    const code = catalogCodes.get(id) ?? null;
    if (code === row.orientation) continue;
    updates.push({ key: row.key, code });

    if (row.cached === null) continue;
    const want = normalizeOrientation(code);
    if (row.cache_orientation !== null) {
      if (normalizeOrientation(row.cache_orientation) !== want) stale.push(row.key);
    } else if (await legacyCacheMatches(row, want)) {
      stamps.push({ key: row.key, code: want });
    } else {
      stale.push(row.key);
    }
  }

  if (updates.length) {
    libraryWrite(db, () => {
      const setCode = db.prepare('UPDATE images SET orientation = ? WHERE key = ?');
      for (const u of updates) setCode.run(u.code, u.key);
      const stamp = db.prepare('UPDATE vision_cache SET orientation = ? WHERE key = ?');
      for (const s of stamps) stamp.run(s.code, s.key);
      markVisionOutputsStale(db, stale);
    });
  }
  return { updated: updates.length, stale: stale.length };
}
