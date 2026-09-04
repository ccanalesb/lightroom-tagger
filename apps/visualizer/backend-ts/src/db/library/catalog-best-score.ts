/**
 * Best current catalog perspective score, for list and detail queries.
 */
import type { Db } from '../connection.js';

/**
 * Single source of truth for winner selection: a correlated `NOT EXISTS` that keeps
 * only the row `s1` for which no other current catalog score ranks higher. Higher
 * score wins; ties break toward the lexicographically smallest `perspective_slug`.
 *
 * Referenced from both the list-query JOIN and the single-image lookup so the
 * tie-break cannot be stated two different ways.
 */
const BEST_SCORE_TIEBREAK_PREDICATE = `NOT EXISTS (
    SELECT 1 FROM image_scores s2
    WHERE s2.image_key = s1.image_key
      AND s2.image_type = 'catalog' AND s2.is_current = 1
      AND (
        s2.score > s1.score
        OR (s2.score = s1.score AND s2.perspective_slug < s1.perspective_slug)
      )
)`;

export const CATALOG_BEST_SCORE_JOIN_SQL = `
LEFT JOIN (
    SELECT
        s1.image_key,
        s1.score AS best_score,
        s1.perspective_slug AS best_perspective_slug
    FROM image_scores s1
    WHERE s1.image_type = 'catalog' AND s1.is_current = 1
      AND ${BEST_SCORE_TIEBREAK_PREDICATE}
) best_s ON best_s.image_key = i.key
`;

export const CATALOG_BEST_SCORE_SELECT_COLS =
  'best_s.best_score AS catalog_perspective_score, ' +
  'best_s.best_perspective_slug AS catalog_score_perspective';

/**
 * `[max current score, winning perspective slug]` for a catalog image, or
 * `[null, null]` when it has no current catalog score.
 */
export function getBestCurrentCatalogScore(
  db: Db,
  imageKey: string,
): [number | null, string | null] {
  const row = db
    .prepare(
      `
        SELECT s1.score, s1.perspective_slug
        FROM image_scores s1
        WHERE s1.image_key = ?
          AND s1.image_type = 'catalog'
          AND s1.is_current = 1
          AND ${BEST_SCORE_TIEBREAK_PREDICATE}
        LIMIT 1
        `,
    )
    .get(imageKey) as { score: number; perspective_slug: string } | undefined;
  if (!row) return [null, null];
  return [Math.trunc(row.score), String(row.perspective_slug)];
}
