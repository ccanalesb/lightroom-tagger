/**
 * Writing and selecting CLIP embedding rows.
 *
 * `image_clip_embeddings` is a sqlite-vec `vec0` virtual table, which has no
 * UPDATE path for the vector column — a re-embed is a delete followed by an
 * insert, and both must happen inside one `libraryWrite` so a crash between them
 * cannot leave the image with no vector at all.
 */
import type { Db } from '../connection.js';

/** Replace the vector for `imageKey`. Call inside `libraryWrite`. */
export function upsertImageClipEmbedding(db: Db, imageKey: string, embeddingBlob: Buffer): void {
  db.prepare('DELETE FROM image_clip_embeddings WHERE image_key = ?').run(imageKey);
  db.prepare('INSERT INTO image_clip_embeddings(embedding, image_key) VALUES (?, ?)').run(
    embeddingBlob,
    imageKey,
  );
}

export interface ClipEmbedWindow {
  months: number | null;
  year: string | null;
  minRating: number | null;
}

/**
 * Newest first, undated last — the order the embed job works through the catalog.
 *
 * `COALESCE(date_taken, '')` orders undated rows last under SQLite's default collation.
 */
function windowedCatalogKeys(db: Db, window: ClipEmbedWindow): string[] {
  const conditions = ["i.filepath IS NOT NULL AND TRIM(COALESCE(i.filepath, '')) != ''"];
  const params: unknown[] = [];

  if (window.months !== null) {
    conditions.push("i.date_taken >= date('now', ?)");
    params.push(`-${window.months} months`);
  }
  if (window.year !== null) {
    conditions.push("strftime('%Y', i.date_taken) = ?");
    params.push(window.year);
  }
  if (window.minRating !== null) {
    conditions.push('i.rating >= ?');
    params.push(window.minRating);
  }

  const rows = db
    .prepare(
      `SELECT i.key AS key FROM images i WHERE ${conditions.join(' AND ')}` +
        " ORDER BY COALESCE(i.date_taken, '') DESC, i.key DESC",
    )
    .all(...(params as never[])) as { key: string }[];
  return rows.map((r) => r.key);
}

/** Catalog keys in the window that have no vector yet. */
export function listCatalogKeysNeedingClipEmbedding(db: Db, window: ClipEmbedWindow): string[] {
  const keys = windowedCatalogKeys(db, window);
  // Read the embedded keys in one pass rather than joining: `vec0` is a virtual
  // table, and a correlated subquery against one is not something to rely on.
  const embedded = new Set(
    (db.prepare('SELECT image_key FROM image_clip_embeddings').all() as { image_key: string }[]).map(
      (r) => String(r.image_key),
    ),
  );
  return keys.filter((k) => !embedded.has(k));
}

/** Every catalog key in the window, including ones already embedded. */
export function listCatalogKeysForClipEmbedForce(db: Db, window: ClipEmbedWindow): string[] {
  return windowedCatalogKeys(db, window);
}
