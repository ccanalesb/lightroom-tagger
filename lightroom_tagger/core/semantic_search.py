"""Hybrid semantic search: FTS5 BM25 ranks + sqlite-vec KNN + RRF fusion (Phase 3, plan 03-04).

sqlite-vec 0.1.9 KNN: bind query vector as a single float32 blob for ``embedding MATCH ?``;
``k`` is a separate bound parameter. See module docstring in plan 03-RESEARCH.md.
"""

from __future__ import annotations

import sqlite3

RRF_K: int = 60

FTS_CANDIDATE_LIMIT: int = 200
KNN_K: int = 200


def fts_ranked_catalog_keys(
    conn: sqlite3.Connection, fts_match: str, *, limit: int
) -> list[str]:
    """Ordered catalog ``image_key`` values by FTS5 BM25 (lower is better)."""
    rows = conn.execute(
        """
        SELECT d.image_key AS image_key
        FROM image_descriptions_fts
        INNER JOIN image_descriptions d ON d.rowid = image_descriptions_fts.rowid
        WHERE d.image_type = 'catalog' AND image_descriptions_fts MATCH ?
        ORDER BY bm25(image_descriptions_fts) ASC
        LIMIT ?
        """,
        (fts_match, limit),
    ).fetchall()
    return [str(r["image_key"]) for r in rows]


def knn_embedded_catalog_keys(
    conn: sqlite3.Connection, query_vec_blob: bytes, *, k: int
) -> list[tuple[str, float]]:
    """KNN over ``image_text_embeddings`` (cosine distance); order preserved."""
    rows = conn.execute(
        """
        SELECT image_key, distance
        FROM image_text_embeddings
        WHERE embedding MATCH ?
          AND k = ?
        """,
        (query_vec_blob, k),
    ).fetchall()
    out: list[tuple[str, float]] = []
    for r in rows:
        out.append((str(r["image_key"]), float(r["distance"])))
    return out


def rrf_scores_from_ranks(lists: dict[str, list[str]]) -> dict[str, float]:
    """Sum ``1.0 / (RRF_K + rank)`` per list where the key appears; rank is 1-based."""
    scores: dict[str, float] = {}
    for _source, keys in lists.items():
        for idx, key in enumerate(keys):
            rank = idx + 1
            scores[key] = scores.get(key, 0.0) + 1.0 / (RRF_K + rank)
    return scores


def sort_keys_by_rrf_scores(scores: dict[str, float]) -> list[str]:
    """Descending by score; tie-break ascending by key string."""
    return sorted(scores.keys(), key=lambda k: (-scores[k], k))
