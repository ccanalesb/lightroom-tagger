"""Hybrid semantic search: FTS5 BM25 ranks + sqlite-vec KNN + RRF fusion (Phase 3, plan 03-04).

sqlite-vec 0.1.9 KNN: bind query vector as a single float32 blob for ``embedding MATCH ?``;
``k`` is a separate bound parameter. See module docstring in plan 03-RESEARCH.md.
"""

from __future__ import annotations

RRF_K: int = 60


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
