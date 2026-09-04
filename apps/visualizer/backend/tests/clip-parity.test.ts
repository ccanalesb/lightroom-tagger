/**
 * Do Node CLIP embeddings match the vectors already stored in `library.db`?
 *
 * Requires the real library.db, the vision cache on disk, and a model download.
 * Skips unless LT_CLIP_PARITY=1:
 *
 *   LT_CLIP_PARITY=1 LIBRARY_DB=/path/to/library.db npx vitest run tests/clip-parity.test.ts
 */
import { describe, expect, it } from 'vitest';
import { existsSync } from 'node:fs';
import { config } from '../src/config.js';
import { deserializeFloat32, openLibraryDb } from '../src/db/connection.js';
import { CLIP_EMBED_DIM, decodeRgb, encodePixels } from '../src/imaging/clip-embed.js';

const enabled = process.env.LT_CLIP_PARITY === '1' && existsSync(config.LIBRARY_DB);
const describeMaybe = enabled ? describe : describe.skip;

function cosine(a: ArrayLike<number>, b: ArrayLike<number>): number {
  let dot = 0;
  let na = 0;
  let nb = 0;
  for (let i = 0; i < a.length; i++) {
    dot += a[i]! * b[i]!;
    na += a[i]! * a[i]!;
    nb += b[i]! * b[i]!;
  }
  return dot / (Math.sqrt(na) * Math.sqrt(nb));
}

interface Sample {
  key: string;
  path: string;
  stored: Float32Array;
}

function loadSamples(limit: number): Sample[] {
  const db = openLibraryDb(config.LIBRARY_DB, { readonly: true });
  try {
    const stored = new Map<string, Buffer>(
      (
        db.prepare('select image_key, embedding from image_clip_embeddings').all() as {
          image_key: string;
          embedding: Buffer;
        }[]
      ).map((r) => [r.image_key, r.embedding]),
    );
    const cache = db.prepare('select key, compressed_path from vision_cache').all() as {
      key: string;
      compressed_path: string | null;
    }[];

    const out: Sample[] = [];
    // Spread the picks across the catalog rather than taking a single burst.
    const stride = Math.max(1, Math.floor(cache.length / (limit * 4)));
    for (let i = 0; i < cache.length && out.length < limit; i += stride) {
      const row = cache[i]!;
      const blob = stored.get(row.key);
      if (!blob || !row.compressed_path || !existsSync(row.compressed_path)) continue;
      out.push({ key: row.key, path: row.compressed_path, stored: deserializeFloat32(blob) });
    }
    return out;
  } finally {
    db.close();
  }
}

describeMaybe('CLIP embeddings are drop-in compatible with the stored corpus', () => {
  it('reproduces stored vectors to within floating-point noise', async () => {
    const samples = loadSamples(8);
    expect(samples.length).toBeGreaterThan(0);

    const results: { key: string; cos: number }[] = [];
    for (const s of samples) {
      const vec = await encodePixels(await decodeRgb(s.path));
      expect(vec.length).toBe(CLIP_EMBED_DIM);
      results.push({ key: s.key, cos: cosine(vec, s.stored) });
    }

    for (const r of results) {
      // 1 - cos must sit at floating-point noise, not merely "high".
      expect(1 - r.cos, `${r.key} cosine=${r.cos}`).toBeLessThan(1e-5);
    }

    const worst = Math.min(...results.map((r) => r.cos));
    console.log(
      `CLIP parity over ${results.length} images: worst cosine ${worst.toFixed(9)}, ` +
        `worst 1-cos ${(1 - worst).toExponential(2)}`,
    );
  }, 600_000);

  it('retrieves the same neighbours as the stored query vector', async () => {
    // The failure this guards is ranking drift, which a cosine threshold alone can
    // miss. Naive preprocessing scored 5.3/10 top-10 overlap here.
    const samples = loadSamples(4);
    const db = openLibraryDb(config.LIBRARY_DB, { readonly: true });
    try {
      const knn = db.prepare(
        `select image_key from image_clip_embeddings
         where embedding match ? and k = 10 order by distance`,
      );
      const asBlob = (v: Float32Array) => Buffer.from(v.buffer, v.byteOffset, v.byteLength);

      for (const s of samples) {
        const vec = await encodePixels(await decodeRgb(s.path));
        const fromStored = (knn.all(asBlob(s.stored)) as { image_key: string }[]).map(
          (r) => r.image_key,
        );
        const fromOurs = (knn.all(asBlob(vec)) as { image_key: string }[]).map((r) => r.image_key);
        expect(fromOurs, `neighbour drift for ${s.key}`).toEqual(fromStored);
      }
    } finally {
      db.close();
    }
  }, 600_000);
});
