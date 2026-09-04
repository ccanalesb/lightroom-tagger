/**
 * CLIP-only visual similarity (KNN over `image_clip_embeddings`), SIM-02 / D-05.
 *
 * Runs against the sqlite-vec `vec0` table already in `library.db` — 43,451 rows of
 * 512-d float32 written by the Python backend, read here with no migration. The
 * npm `sqlite-vec` build is pinned to the same 0.1.9 the Python side pins, so the
 * on-disk format is the same one that wrote it.
 */
import type { Db } from '../db/connection.js';
import { catalogKeyIsPrimaryGridRow, filterOrderKeysInCatalog } from '../db/library/catalog-query.js';
import type { CatalogImageFilters } from '../db/library/catalog-query.js';
import { CLIP_EMBED_DIM, CLIP_EMBED_MODEL_ID } from '../imaging/clip-embed.js';

/** Headroom for post-filters (catalog constraints plus the primary-grid rule). */
export const KNN_K_MAX = 500;

/** The seed image has no row in `image_clip_embeddings`; the API maps this to 404. */
export class NoClipEmbeddingError extends Error {
  readonly seedKey: string;

  constructor(seedKey: string) {
    super(`No CLIP embedding for catalog key '${seedKey}'`);
    this.name = 'NoClipEmbeddingError';
    this.seedKey = seedKey;
  }
}

export interface ClipSimilarMeta {
  clip_model_id: string;
  clip_embed_dim: number;
  knn_fetched: number;
  knn_k_used?: number;
}

/** KNN over `image_clip_embeddings` by cosine distance, ascending. */
export function knnClipCatalogKeys(
  db: Db,
  queryVecBlob: Buffer,
  k: number,
): [string, number][] {
  const bounded = Math.min(KNN_K_MAX, Math.max(1, Math.trunc(k)));
  const rows = db
    .prepare(
      `
        SELECT image_key, distance
        FROM image_clip_embeddings
        WHERE embedding MATCH ?
          AND k = ?
        `,
    )
    .all(queryVecBlob, bounded) as { image_key: string; distance: number }[];
  return rows.map((r) => [String(r.image_key), Number(r.distance)]);
}

/** The 512-d float32 blob for `imageKey`, or `null` when it has no embedding. */
export function getClipEmbeddingBlobForKey(db: Db, imageKey: string): Buffer | null {
  const row = db
    .prepare('SELECT embedding FROM image_clip_embeddings WHERE image_key = ?')
    .get(imageKey) as { embedding: Buffer | null } | undefined;
  if (!row || row.embedding === null || row.embedding === undefined) return null;
  // Copy out: better-sqlite3 hands back a Buffer that views SQLite-owned memory,
  // which is invalidated by the next step on the same statement.
  return Buffer.from(row.embedding);
}

function clipMeta(knnFetched: number, knnKUsed?: number): ClipSimilarMeta {
  return {
    clip_model_id: CLIP_EMBED_MODEL_ID,
    clip_embed_dim: CLIP_EMBED_DIM,
    knn_fetched: knnFetched,
    ...(knnKUsed !== undefined ? { knn_k_used: knnKUsed } : {}),
  };
}

/**
 * Ordered catalog keys for pin-to-similar search: `seedKey` first, then CLIP
 * neighbours restricted to primary-grid rows.
 */
export function listPinSimilarityCandidateKeys(
  db: Db,
  seedKey: string,
  opts: { maxCandidates?: number } = {},
): string[] {
  const blob = getClipEmbeddingBlobForKey(db, seedKey);
  if (blob === null) throw new NoClipEmbeddingError(seedKey);

  const maxCandidates = Math.max(1, Math.trunc(opts.maxCandidates ?? 600));
  const needNeighbors = Math.max(0, maxCandidates - 1);
  let knnK = needNeighbors ? Math.min(KNN_K_MAX, Math.max(50, needNeighbors * 20)) : 1;
  knnK = Math.min(KNN_K_MAX, Math.max(knnK, 1));

  const raw = knnClipCatalogKeys(db, blob, knnK);
  const out: string[] = [seedKey];
  for (const [imageKey] of raw) {
    if (imageKey === seedKey) continue;
    if (!catalogKeyIsPrimaryGridRow(db, imageKey)) continue;
    out.push(imageKey);
    if (out.length >= maxCandidates) break;
  }
  return out;
}

/**
 * CLIP KNN neighbours for `seedKey` with catalog and primary-grid post-filters.
 *
 * Neighbours stay in KNN (distance) order throughout; the seed is never included,
 * and non-representative stack members are dropped so the results match what the
 * grid would show. `filters` are applied by `filterOrderKeysInCatalog`, i.e. by the
 * same SQL the catalog list uses — the point is that "visually similar" and
 * "matches my filters" cannot disagree.
 *
 * The KNN is deliberately over-fetched (20x the page, capped at `KNN_K_MAX`) because
 * the filters run afterwards and would otherwise return a short page.
 */
export function runClipSimilarForSeed(
  db: Db,
  seedKey: string,
  opts: { limit: number; offset: number } & CatalogImageFilters & {
      scorePerspective?: string | null;
    },
): { pairs: [string, number][]; meta: ClipSimilarMeta } {
  const blob = getClipEmbeddingBlobForKey(db, seedKey);
  if (blob === null) throw new NoClipEmbeddingError(seedKey);

  const { limit, offset, ...filters } = opts;
  const need = Math.max(0, Math.trunc(offset) + Math.trunc(limit));
  let knnK = Math.min(KNN_K_MAX, Math.max(50, need * 20));
  knnK = Math.min(KNN_K_MAX, Math.max(knnK, 1));

  const raw = knnClipCatalogKeys(db, blob, knnK);

  const ordered: [string, number][] = [];
  for (const [imageKey, dist] of raw) {
    if (imageKey === seedKey) continue;
    if (!catalogKeyIsPrimaryGridRow(db, imageKey)) continue;
    ordered.push([imageKey, dist]);
  }

  // Note the asymmetry, carried over deliberately: the empty case omits
  // `knn_k_used` from the metadata while the non-empty case includes it.
  if (ordered.length === 0) return { pairs: [], meta: clipMeta(raw.length) };

  const allowed = new Set(
    filterOrderKeysInCatalog(
      db,
      ordered.map(([k]) => k),
      filters,
    ),
  );
  const filtered = ordered.filter(([k]) => allowed.has(k));

  const page = filtered.slice(Math.trunc(offset), Math.trunc(offset) + Math.trunc(limit));
  return { pairs: page, meta: clipMeta(raw.length, knnK) };
}
