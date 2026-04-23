"""Hybrid semantic search: FTS5 BM25 ranks + sqlite-vec KNN + RRF fusion (Phase 3, plan 03-04).

sqlite-vec 0.1.9 KNN: bind query vector as a single float32 blob for ``embedding MATCH ?``;
``k`` is a separate bound parameter. See module docstring in plan 03-RESEARCH.md.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from lightroom_tagger.core.database import count_catalog_images_missing_text_embedding

RRF_K: int = 60
FTS_CANDIDATE_LIMIT: int = 200
KNN_K: int = 200


@dataclass(frozen=True)
class SemanticSearchMeta:
    missing_embeddings_count: int
    semantic_index_empty: bool
    rrf_k: int
    fts_no_match: bool = False


@dataclass(frozen=True)
class SemanticSearchRow:
    image_key: str
    rrf_score: float
    why_matched: str


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


def _why_matched_for_key(
    key: str,
    *,
    fts_rank: int | None,
    vec_rank: int | None,
    distance: float | None,
) -> str:
    _ = key
    similarity = (
        None
        if distance is None
        else max(0.0, min(1.0, 1.0 - float(distance)))
    )
    if fts_rank is not None and vec_rank is not None and similarity is not None:
        return f"FTS match · embedding: {similarity:.2f}"
    if fts_rank is not None and vec_rank is None:
        return "FTS match"
    if vec_rank is not None and similarity is not None:
        return f"Embedding match ({similarity:.2f})"
    return "Match"


def run_semantic_hybrid_search(
    conn: sqlite3.Connection,
    *,
    user_query: str,
    fts_match: str,
    query_vec_blob: bytes,
    limit: int,
    offset: int,
) -> tuple[list[SemanticSearchRow], int, SemanticSearchMeta]:
    """Fuse FTS BM25 ordering with vec KNN (cosine) via RRF; D-09 post-filter when vec index non-empty."""
    _ = user_query
    missing = count_catalog_images_missing_text_embedding(conn)
    vec_row = conn.execute("SELECT COUNT(*) AS c FROM image_text_embeddings").fetchone()
    vec_n = int(vec_row["c"] if vec_row else 0)
    semantic_index_empty = vec_n == 0

    fts_keys = fts_ranked_catalog_keys(conn, fts_match, limit=FTS_CANDIDATE_LIMIT)
    knn_pairs: list[tuple[str, float]] = (
        []
        if semantic_index_empty
        else knn_embedded_catalog_keys(conn, query_vec_blob, k=KNN_K)
    )

    if not semantic_index_empty and len(fts_keys) == 0:
        return (
            [],
            0,
            SemanticSearchMeta(
                missing_embeddings_count=missing,
                semantic_index_empty=False,
                rrf_k=RRF_K,
                fts_no_match=True,
            ),
        )

    fts_rank: dict[str, int] = {k: i + 1 for i, k in enumerate(fts_keys)}
    vec_rank: dict[str, int] = {}
    vec_dist: dict[str, float] = {}
    for i, (vk, dist) in enumerate(knn_pairs):
        vec_rank[vk] = i + 1
        vec_dist[vk] = dist

    lists: dict[str, list[str]] = {"fts": fts_keys}
    if not semantic_index_empty:
        lists["vec"] = [k for k, _ in knn_pairs]

    scores = rrf_scores_from_ranks(lists)
    ordered = sort_keys_by_rrf_scores(scores)

    if not semantic_index_empty:
        embedded_rows = conn.execute("SELECT image_key FROM image_text_embeddings").fetchall()
        embedded_keys = {str(r["image_key"]) for r in embedded_rows}
        ordered = [k for k in ordered if k in embedded_keys]

    total = len(ordered)
    page_keys = ordered[offset : offset + limit]

    rows: list[SemanticSearchRow] = []
    for img_key in page_keys:
        fr = fts_rank.get(img_key)
        vr = vec_rank.get(img_key)
        dist = vec_dist.get(img_key)
        rows.append(
            SemanticSearchRow(
                image_key=img_key,
                rrf_score=scores[img_key],
                why_matched=_why_matched_for_key(
                    img_key,
                    fts_rank=fr,
                    vec_rank=vr,
                    distance=dist,
                ),
            )
        )

    return (
        rows,
        total,
        SemanticSearchMeta(
            missing_embeddings_count=missing,
            semantic_index_empty=semantic_index_empty,
            rrf_k=RRF_K,
            fts_no_match=False,
        ),
    )
