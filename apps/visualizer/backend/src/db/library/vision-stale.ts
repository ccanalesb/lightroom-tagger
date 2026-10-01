/**
 * Descriptions and scores made from a cached image that has since been turned.
 *
 * Marking keeps the old output on show; the describe and score jobs treat a
 * stale output as not done and overwrite it, and the write deletes the mark.
 * See `vision_stale` in `bootstrap.ts`.
 */
import type { Db } from '../connection.js';

const DESCRIPTION = 'description';
const scoreOutput = (slug: string): string => `score:${slug}`;

/**
 * Mark everything already made from the images as stale, and drop their CLIP
 * vectors so the embed job, which only picks unembedded images, computes them
 * again. Call inside `libraryWrite`.
 */
export function markVisionOutputsStale(db: Db, imageKeys: readonly string[]): void {
  if (!imageKeys.length) return;
  const insert = db.prepare(
    'INSERT OR IGNORE INTO vision_stale (image_key, output) VALUES (?, ?)',
  );
  const described = db.prepare('SELECT 1 FROM image_descriptions WHERE image_key = ?');
  const scored = db.prepare(
    'SELECT DISTINCT perspective_slug AS slug FROM image_scores WHERE image_key = ? AND is_current = 1',
  );
  for (const key of imageKeys) {
    if (described.get(key)) insert.run(key, DESCRIPTION);
    for (const { slug } of scored.all(key) as { slug: string }[]) insert.run(key, scoreOutput(slug));
  }

  // `vec0` scans the whole table for a WHERE on `image_key`; only rowid is indexed.
  const keys = new Set(imageKeys);
  const drop = db.prepare('DELETE FROM image_clip_embeddings WHERE rowid = ?');
  const vectors = db.prepare('SELECT rowid, image_key FROM image_clip_embeddings').all() as {
    rowid: number;
    image_key: string;
  }[];
  for (const v of vectors) if (keys.has(String(v.image_key))) drop.run(v.rowid);
}

export function clearStaleDescription(db: Db, imageKey: string): void {
  db.prepare('DELETE FROM vision_stale WHERE image_key = ? AND output = ?').run(imageKey, DESCRIPTION);
}

export function clearStaleScore(db: Db, imageKey: string, slug: string): void {
  db.prepare('DELETE FROM vision_stale WHERE image_key = ? AND output = ?').run(
    imageKey,
    scoreOutput(slug),
  );
}

export function isDescriptionStale(db: Db, imageKey: string): boolean {
  return (
    db
      .prepare('SELECT 1 FROM vision_stale WHERE image_key = ? AND output = ?')
      .get(imageKey, DESCRIPTION) !== undefined
  );
}

export function isScoreStale(db: Db, imageKey: string, slug: string): boolean {
  return (
    db
      .prepare('SELECT 1 FROM vision_stale WHERE image_key = ? AND output = ?')
      .get(imageKey, scoreOutput(slug)) !== undefined
  );
}

export function staleDescriptionKeys(db: Db): Set<string> {
  const rows = db
    .prepare('SELECT image_key FROM vision_stale WHERE output = ?')
    .all(DESCRIPTION) as { image_key: string }[];
  return new Set(rows.map((r) => r.image_key));
}

/** `key|slug` for every stale score. */
export function staleScoreLabels(db: Db): Set<string> {
  const rows = db
    .prepare("SELECT image_key, output FROM vision_stale WHERE output LIKE 'score:%'")
    .all() as { image_key: string; output: string }[];
  return new Set(rows.map((r) => `${r.image_key}|${r.output.slice('score:'.length)}`));
}
