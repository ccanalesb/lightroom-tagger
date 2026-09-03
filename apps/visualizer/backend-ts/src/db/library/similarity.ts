/**
 * Catalog similarity job output. Port of the read helpers in
 * `core/database/similarity.py`.
 *
 * These rows are materialized by the batch similarity job; the API only reads them.
 */
import type { Db } from '../connection.js';

export interface SimilarityGroupRow {
  group_id: number;
  seed_key: string;
  candidate_count: number | null;
  best_similarity: number | null;
  job_id: string | null;
  created_at: string | null;
}

export interface SimilarityCandidateRow {
  candidate_key: string;
  similarity: number | null;
  rank: number;
  why_matched: string | null;
}

/** Catalog keys with CLIP embeddings, newest first, as batch jobs consume them. */
export function listClipEmbeddedCatalogKeysNewestFirst(db: Db): string[] {
  const rows = db
    .prepare(
      `
        SELECT e.image_key AS key, i.date_taken AS date_taken
        FROM image_clip_embeddings e
        INNER JOIN images i ON i.key = e.image_key
        ORDER BY i.date_taken DESC, i.key DESC
        `,
    )
    .all() as { key: string | null }[];
  return rows.filter((r) => r.key).map((r) => String(r.key));
}

export function getSimilarityGroupsCount(db: Db): number {
  const row = db.prepare('SELECT COUNT(*) AS c FROM catalog_similarity_groups').get() as
    | { c: number }
    | undefined;
  return row ? Math.trunc(row.c) : 0;
}

/** A page of similarity group summary rows plus the total, newest first. */
export function getCatalogSimilarityGroupsPaginated(
  db: Db,
  opts: { limit: number; offset: number },
): { rows: SimilarityGroupRow[]; total: number } {
  const total = getSimilarityGroupsCount(db);
  const rows = db
    .prepare(
      `
        SELECT group_id, seed_key, candidate_count, best_similarity, job_id, created_at
        FROM catalog_similarity_groups
        ORDER BY created_at DESC, group_id DESC
        LIMIT ? OFFSET ?
        `,
    )
    .all(Math.trunc(opts.limit), Math.trunc(opts.offset)) as SimilarityGroupRow[];
  return { rows, total };
}

/** Ranked candidate rows for one similarity group. */
export function getSimilarityCandidatesForGroup(
  db: Db,
  groupId: number,
): SimilarityCandidateRow[] {
  return db
    .prepare(
      `
        SELECT candidate_key, similarity, rank, why_matched
        FROM catalog_similarity_candidates
        WHERE group_id = ?
        ORDER BY rank ASC, similarity DESC
        `,
    )
    .all(Math.trunc(groupId)) as SimilarityCandidateRow[];
}
