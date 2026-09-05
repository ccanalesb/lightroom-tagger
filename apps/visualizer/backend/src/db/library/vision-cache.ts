/**
 * Vision cache rows.
 */
import type { Db } from '../connection.js';

/**
 * Written into `compressed_path` when an image was too large to cache. It is a
 * sentinel, not a path, so every consumer must check for it before touching the
 * filesystem.
 */
export const VISION_CACHE_OVERSIZED_SENTINEL = '__oversized__';

export interface VisionCacheRow {
  key: string;
  compressed_path: string | null;
  phash: string | null;
  compressed_at: string | null;
  original_mtime: number | null;
}

/** The cached compressed-image row for a catalog key. */
export function getVisionCachedImage(db: Db, catalogKey: string): VisionCacheRow | null {
  const row = db.prepare('SELECT * FROM vision_cache WHERE key = ?').get(catalogKey) as
    | VisionCacheRow
    | undefined;
  return row ?? null;
}
