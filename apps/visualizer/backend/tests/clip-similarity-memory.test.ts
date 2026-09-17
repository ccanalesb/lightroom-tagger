/**
 * Regression guard: the catalog similarity scan must not allocate a fresh
 * sqlite3_stmt (and vec0 KNN scratch) on every seed.
 */
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { openLibraryDb, serializeFloat32 } from '../src/db/connection.js';
import { listClipEmbeddedCatalogKeysNewestFirst } from '../src/db/library/similarity.js';
import { runClipSimilarForSeed } from '../src/clip/similarity.js';
import { LibraryFixture } from './helpers/library-fixture.js';

let fx: LibraryFixture;

function vectorAt(theta: number): Float32Array {
  const v = new Float32Array(512);
  v[0] = Math.cos(theta);
  v[1] = Math.sin(theta);
  return v;
}

/** Batch-insert `count` images with CLIP embeddings for scan stress tests. */
function seedEmbeddedCatalog(fixture: LibraryFixture, count: number): void {
  const db = openLibraryDb(fixture.dbPath);
  const imageStmt = db.prepare(
    'INSERT INTO images (key, filename, filepath, date_taken) VALUES (?, ?, ?, ?)',
  );
  const embedStmt = db.prepare(
    'INSERT INTO image_clip_embeddings(embedding, image_key) VALUES (?, ?)',
  );
  for (let i = 0; i < count; i++) {
    const key = `seed-${i}`;
    const blob = serializeFloat32(vectorAt((i / count) * (Math.PI / 2)));
    imageStmt.run(key, `${key}.jpg`, `/photos/${key}.jpg`, `2024-01-${String((i % 28) + 1).padStart(2, '0')}`);
    embedStmt.run(blob, key);
  }
  db.close();
}

beforeEach(() => {
  fx = new LibraryFixture().activate();
});

afterEach(() => {
  fx.cleanup();
});

describe('CLIP similarity scan memory', () => {
  it('reuses prepared statements across thousands of seeds', { timeout: 120_000 }, () => {
    const seedCount = 3000;
    seedEmbeddedCatalog(fx, seedCount);

    const db = openLibraryDb(fx.dbPath, { readonly: true });
    const keys = listClipEmbeddedCatalogKeysNewestFirst(db);
    expect(keys.length).toBe(seedCount);

    const rssBefore = process.memoryUsage().rss;
    for (const seedKey of keys) {
      runClipSimilarForSeed(db, seedKey, { limit: 8, offset: 0 });
    }
    const growthMb = (process.memoryUsage().rss - rssBefore) / (1024 * 1024);

    db.close();
    // Without statement reuse this climbs into the GB range; flat reuse stays modest.
    expect(growthMb).toBeLessThan(200);
  });
});
