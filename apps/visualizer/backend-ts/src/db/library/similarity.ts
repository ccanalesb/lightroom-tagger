/**
 * Catalog similarity job output. Port of `core/database/similarity.py`.
 *
 * `batch_catalog_similarity` materializes these rows; the API only reads them.
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

/** Drop every materialized group and candidate; the job rebuilds them wholesale. */
export function clearCatalogSimilarityResults(db: Db): void {
  db.exec('DELETE FROM catalog_similarity_candidates');
  db.exec('DELETE FROM catalog_similarity_groups');
}

export interface SimilarityCandidateInput {
  candidate_key: string;
  similarity: number;
  rank?: number;
  why_matched?: string;
}

/** Persist one group and its ranked candidates. Returns the new `group_id`. */
export function insertCatalogSimilarityGroup(
  db: Db,
  args: { seedKey: string; candidates: readonly SimilarityCandidateInput[]; jobId?: string | null },
): number {
  if (args.candidates.length === 0) throw new Error('candidates must not be empty');
  const bestSimilarity = Math.max(...args.candidates.map((c) => Number(c.similarity) || 0));
  const info = db
    .prepare(
      `
        INSERT INTO catalog_similarity_groups
          (seed_key, candidate_count, best_similarity, job_id, created_at)
        VALUES (?, ?, ?, ?, ?)
        `,
    )
    .run(
      args.seedKey,
      args.candidates.length,
      bestSimilarity,
      args.jobId ?? null,
      localIsoNow(),
    );
  const groupId = Number(info.lastInsertRowid);

  const stmt = db.prepare(
    `
      INSERT INTO catalog_similarity_candidates
        (group_id, candidate_key, similarity, rank, why_matched)
      VALUES (?, ?, ?, ?, ?)
      `,
  );
  args.candidates.forEach((c, idx) => {
    stmt.run(
      groupId,
      String(c.candidate_key),
      Number(c.similarity),
      Math.trunc(c.rank || idx + 1),
      String(c.why_matched ?? ''),
    );
  });
  return groupId;
}

/**
 * `datetime.now().isoformat()` — local time, no offset suffix.
 *
 * Naive local time is what every `created_at` already in this table holds, and the
 * groups list sorts on the column as text, so a UTC or offset-bearing string here
 * would order new groups against old ones by timezone rather than by time.
 */
function localIsoNow(): string {
  const d = new Date();
  const p = (n: number, width = 2): string => String(n).padStart(width, '0');
  return (
    `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}` +
    `T${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}.${p(d.getMilliseconds(), 3)}000`
  );
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
