/**
 * On-disk compatibility with the real library.db: sqlite-vec version and readable
 * vec0 embeddings. Skips when the production database is not present.
 */
import { describe, expect, it } from 'vitest';
import { existsSync } from 'node:fs';
import { config } from '../src/config.js';
import { deserializeFloat32, openLibraryDb, serializeFloat32 } from '../src/db/connection.js';

const hasLibrary = existsSync(config.LIBRARY_DB);
const describeIfLibrary = hasLibrary ? describe : describe.skip;

describe('sqlite-vec', () => {
  it('pins sqlite-vec 0.1.9, the version the stored embeddings were written with', () => {
    const db = openLibraryDb(':memory:');
    try {
      const { v } = db.prepare('select vec_version() as v').get() as { v: string };
      expect(v).toBe('v0.1.9');
    } finally {
      db.close();
    }
  });

  it('round-trips a float32 vector blob', () => {
    const values = [0.5, -0.25, 0, 1];
    const blob = serializeFloat32(values);
    expect(blob.length).toBe(values.length * 4);
    expect([...deserializeFloat32(blob)]).toEqual(values);
  });
});

describeIfLibrary('live library.db', () => {
  it('reads stored CLIP embeddings as 512-d unit vectors', () => {
    const db = openLibraryDb(config.LIBRARY_DB, { readonly: true });
    try {
      const row = db
        .prepare('select image_key, embedding from image_clip_embeddings limit 1')
        .get() as { image_key: string; embedding: Buffer } | undefined;
      expect(row).toBeDefined();

      const vec = deserializeFloat32(row!.embedding);
      expect(vec.length).toBe(512);
      const norm = Math.sqrt([...vec].reduce((a, x) => a + x * x, 0));
      expect(norm).toBeCloseTo(1, 4);
    } finally {
      db.close();
    }
  });

  it('runs vec0 cosine KNN and ranks the query image first', () => {
    const db = openLibraryDb(config.LIBRARY_DB, { readonly: true });
    try {
      const row = db
        .prepare('select image_key, embedding from image_clip_embeddings limit 1')
        .get() as { image_key: string; embedding: Buffer };

      const hits = db
        .prepare(
          `select image_key, distance from image_clip_embeddings
           where embedding match ? and k = 5 order by distance`,
        )
        .all(row.embedding) as { image_key: string; distance: number }[];

      expect(hits.length).toBe(5);
      expect(hits[0]!.image_key).toBe(row.image_key);
      expect(hits[0]!.distance).toBeCloseTo(0, 5);
    } finally {
      db.close();
    }
  });

  it('has the FTS5 description index available', () => {
    const db = openLibraryDb(config.LIBRARY_DB, { readonly: true });
    try {
      const row = db
        .prepare("select name from sqlite_master where name = 'image_descriptions_fts'")
        .get();
      expect(row).toBeDefined();
    } finally {
      db.close();
    }
  });
});
