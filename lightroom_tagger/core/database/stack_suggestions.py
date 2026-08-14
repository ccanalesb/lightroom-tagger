"""Catalog similarity pairs reframed as stack suggestions (#226 / #231)."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from lightroom_tagger.core.database.catalog_query_best_score import get_best_current_catalog_score

# #226: blank-frame false positives average ~4.53 vs ~4.88 catalog-wide.
BLANK_FRAME_SCORE_FLOOR = 4.5

_PENDING_PAIRS_SQL = """
WITH pairs AS (
    SELECT
        g.group_id,
        g.seed_key,
        c.candidate_key,
        c.similarity,
        c.why_matched,
        CASE WHEN g.seed_key < c.candidate_key THEN g.seed_key ELSE c.candidate_key END AS key_a,
        CASE WHEN g.seed_key < c.candidate_key THEN c.candidate_key ELSE g.seed_key END AS key_b
    FROM catalog_similarity_groups g
    INNER JOIN catalog_similarity_candidates c ON c.group_id = g.group_id
)
SELECT
    p.group_id,
    p.seed_key,
    p.candidate_key,
    p.similarity,
    p.why_matched,
    p.key_a,
    p.key_b,
    i1.date_taken AS seed_date_taken,
    i2.date_taken AS candidate_date_taken,
    m1.stack_id AS seed_stack_id,
    m2.stack_id AS candidate_stack_id,
    CASE
        WHEN m1.stack_id IS NULL AND m2.stack_id IS NULL THEN 0
        WHEN m1.stack_id IS NULL OR m2.stack_id IS NULL THEN 1
        ELSE 2
    END AS stack_status_rank,
    ABS(
        COALESCE(strftime('%s', i1.date_taken), 0)
        - COALESCE(strftime('%s', i2.date_taken), 0)
    ) AS time_gap_seconds
FROM pairs p
INNER JOIN images i1 ON i1.key = p.seed_key
INNER JOIN images i2 ON i2.key = p.candidate_key
LEFT JOIN image_stack_members m1 ON m1.image_key = p.seed_key
LEFT JOIN image_stack_members m2 ON m2.image_key = p.candidate_key
LEFT JOIN catalog_similarity_rejections r
    ON r.key_a = p.key_a AND r.key_b = p.key_b
WHERE r.key_a IS NULL
  AND NOT (
      m1.stack_id IS NOT NULL
      AND m2.stack_id IS NOT NULL
      AND m1.stack_id = m2.stack_id
  )
  AND NOT EXISTS (
      SELECT 1
      FROM (
          SELECT s1.image_key, s1.score
          FROM image_scores s1
          WHERE s1.image_type = 'catalog' AND s1.is_current = 1
            AND NOT EXISTS (
                SELECT 1 FROM image_scores s2
                WHERE s2.image_key = s1.image_key
                  AND s2.image_type = 'catalog' AND s2.is_current = 1
                  AND (
                      s2.score > s1.score
                      OR (s2.score = s1.score AND s2.perspective_slug < s1.perspective_slug)
                  )
            )
      ) best
      WHERE best.image_key IN (p.seed_key, p.candidate_key)
        AND best.score < ?
  )
"""


def normalize_image_pair(key_a: str, key_b: str) -> tuple[str, str]:
    """Return lexicographically ordered pair so (a,b) and (b,a) collide."""
    a, b = str(key_a), str(key_b)
    if a == b:
        raise ValueError("image keys must differ")
    return (a, b) if a < b else (b, a)


def is_blank_frame_catalog_key(db: sqlite3.Connection, image_key: str) -> bool:
    """True when the image has a current catalog score below the blank-frame floor."""
    score, _slug = get_best_current_catalog_score(db, image_key)
    return score is not None and float(score) < BLANK_FRAME_SCORE_FLOOR


def is_catalog_similarity_pair_rejected(
    db: sqlite3.Connection, key_a: str, key_b: str
) -> bool:
    a, b = normalize_image_pair(key_a, key_b)
    row = db.execute(
        """
        SELECT 1 AS o FROM catalog_similarity_rejections
        WHERE key_a = ? AND key_b = ?
        LIMIT 1
        """,
        (a, b),
    ).fetchone()
    return row is not None


def reject_catalog_similarity_pair(
    db: sqlite3.Connection, key_a: str, key_b: str
) -> None:
    """Persist a user rejection for a normalized image-key pair."""
    a, b = normalize_image_pair(key_a, key_b)
    db.execute(
        """
        INSERT OR IGNORE INTO catalog_similarity_rejections (key_a, key_b, rejected_at)
        VALUES (?, ?, ?)
        """,
        (a, b, datetime.now().isoformat()),
    )
    db.commit()


def count_pending_stack_suggestions(db: sqlite3.Connection) -> int:
    """Pending stack-to-confirm pairs after rejection, blank-frame, and stack filters."""
    row = db.execute(
        f"SELECT COUNT(*) AS c FROM ({_PENDING_PAIRS_SQL}) pending",
        (BLANK_FRAME_SCORE_FLOOR,),
    ).fetchone()
    return int(row["c"]) if row else 0


def list_pending_stack_suggestions(
    db: sqlite3.Connection, *, limit: int, offset: int
) -> tuple[list[dict], int]:
    """Page of pending pairs ranked by stack status then time proximity."""
    total = count_pending_stack_suggestions(db)
    rows = db.execute(
        f"""
        SELECT *
        FROM ({_PENDING_PAIRS_SQL}) pending
        ORDER BY stack_status_rank ASC, time_gap_seconds ASC, group_id DESC
        LIMIT ? OFFSET ?
        """,
        (BLANK_FRAME_SCORE_FLOOR, int(limit), int(offset)),
    ).fetchall()
    return [dict(r) for r in rows], total
