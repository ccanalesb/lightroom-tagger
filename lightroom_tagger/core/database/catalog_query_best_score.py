"""Best current catalog perspective score helpers for list/detail queries."""

from __future__ import annotations

import sqlite3

# Single source of truth for winner selection: a correlated ``NOT EXISTS``
# that keeps only the row ``s1`` for which no other current catalog score
# ``s2`` ranks higher. Higher score wins; ties break toward the
# lexicographically smallest ``perspective_slug``. Referenced from both the
# list-query JOIN and the single-image lookup so the tie-break lives in one place.
_BEST_SCORE_TIEBREAK_PREDICATE = """NOT EXISTS (
    SELECT 1 FROM image_scores s2
    WHERE s2.image_key = s1.image_key
      AND s2.image_type = 'catalog' AND s2.is_current = 1
      AND (
        s2.score > s1.score
        OR (s2.score = s1.score AND s2.perspective_slug < s1.perspective_slug)
      )
)"""

CATALOG_BEST_SCORE_JOIN_SQL = f"""
LEFT JOIN (
    SELECT
        s1.image_key,
        s1.score AS best_score,
        s1.perspective_slug AS best_perspective_slug
    FROM image_scores s1
    WHERE s1.image_type = 'catalog' AND s1.is_current = 1
      AND {_BEST_SCORE_TIEBREAK_PREDICATE}
) best_s ON best_s.image_key = i.key
"""

CATALOG_BEST_SCORE_SELECT_COLS = (
    "best_s.best_score AS catalog_perspective_score, "
    "best_s.best_perspective_slug AS catalog_score_perspective"
)


def get_best_current_catalog_score(
    db: sqlite3.Connection, image_key: str
) -> tuple[int | None, str | None]:
    """Return ``(max current score, winning perspective slug)`` for a catalog image.

    Ties on score break toward the lexicographically smallest ``perspective_slug``.
    """
    row = db.execute(
        f"""
        SELECT s1.score, s1.perspective_slug
        FROM image_scores s1
        WHERE s1.image_key = ?
          AND s1.image_type = 'catalog'
          AND s1.is_current = 1
          AND {_BEST_SCORE_TIEBREAK_PREDICATE}
        LIMIT 1
        """,
        (image_key,),
    ).fetchone()
    if not row:
        return None, None
    return int(row["score"]), str(row["perspective_slug"])


__all__ = (
    "CATALOG_BEST_SCORE_JOIN_SQL",
    "CATALOG_BEST_SCORE_SELECT_COLS",
    "get_best_current_catalog_score",
)
