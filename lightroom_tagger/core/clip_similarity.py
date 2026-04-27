"""CLIP-only visual similarity (KNN on ``image_clip_embeddings``), SIM-02 / D-05.

Uses sqlite-vec cosine KNN like :func:`lightroom_tagger.core.semantic_search.knn_embedded_catalog_keys`
but **only** against the 512-d CLIP vec0 table (same name as the Phase 5 catalog).
Does not use the 768-d Phase 3 text embedding table.

Over-fetch: KNN retrieves up to ``KNN_K_MAX`` neighbors so post-filters (catalog
constraints + primary-grid / stack representative rule) can still fill a page.
Response metadata uses model id **clip-ViT-B-32** and dimension **512** (``CLIP_EMBED_*``).
"""

from __future__ import annotations

import sqlite3
from typing import Any

from lightroom_tagger.core.clip_embedding_service import CLIP_EMBED_DIM, CLIP_EMBED_MODEL_ID
from lightroom_tagger.core.database import (
    catalog_key_is_primary_grid_row,
    filter_order_keys_in_catalog,
)

# Match order-of-magnitude to semantic_search.KNN_K (200) with headroom for filtering.
KNN_K_MAX = 500


class NoClipEmbeddingError(Exception):
    """Seed image has no row in ``image_clip_embeddings`` (maps to HTTP 404 in 06-03)."""

    def __init__(self, seed_key: str) -> None:
        self.seed_key = seed_key
        super().__init__(f"No CLIP embedding for catalog key {seed_key!r}")


def knn_clip_catalog_keys(
    db: sqlite3.Connection, query_vec_blob: bytes, *, k: int
) -> list[tuple[str, float]]:
    """KNN over ``image_clip_embeddings`` (cosine distance); order is ascending distance."""
    k = min(KNN_K_MAX, max(1, int(k)))
    rows = db.execute(
        """
        SELECT image_key, distance
        FROM image_clip_embeddings
        WHERE embedding MATCH ?
          AND k = ?
        """,
        (query_vec_blob, k),
    ).fetchall()
    out: list[tuple[str, float]] = []
    for r in rows:
        out.append((str(r["image_key"]), float(r["distance"])))
    return out


def get_clip_embedding_blob_for_key(db: sqlite3.Connection, image_key: str) -> bytes | None:
    """Return the 512-d float32 blob for *image_key*, or ``None`` if missing."""
    row = db.execute(
        "SELECT embedding FROM image_clip_embeddings WHERE image_key = ?",
        (image_key,),
    ).fetchone()
    if row is None or row["embedding"] is None:
        return None
    return bytes(row["embedding"])


def list_pin_similarity_candidate_keys(
    db: sqlite3.Connection,
    seed_key: str,
    *,
    max_candidates: int = 600,
) -> list[str]:
    """Ordered catalog keys for pin-to-similar chat search: *seed_key* first, then CLIP
    neighbors (primary-grid rows only). Raises :class:`NoClipEmbeddingError` if the
    seed has no CLIP row."""
    blob = get_clip_embedding_blob_for_key(db, seed_key)
    if blob is None:
        raise NoClipEmbeddingError(seed_key)

    max_candidates = max(1, int(max_candidates))
    need_neighbors = max(0, max_candidates - 1)
    knn_k = min(KNN_K_MAX, max(50, need_neighbors * 20)) if need_neighbors else 1
    knn_k = min(KNN_K_MAX, max(knn_k, 1))

    raw = knn_clip_catalog_keys(db, blob, k=knn_k)
    out: list[str] = [seed_key]
    for image_key, _dist in raw:
        if image_key == seed_key:
            continue
        if not catalog_key_is_primary_grid_row(db, image_key):
            continue
        out.append(image_key)
        if len(out) >= max_candidates:
            break
    return out


def shortlist_catalog_candidates_by_clip(
    db: sqlite3.Connection,
    insta_media_key: str,
    candidate_keys: list[str],
    top_k: int,
) -> list[str]:
    """Intersect CLIP KNN neighbors with *candidate_keys*, preserving KNN order.

    *candidate_keys* must already be representative-only catalog rows (Phase 7 filter).
    """
    top_k = max(1, min(int(top_k), KNN_K_MAX))
    if not candidate_keys:
        return []

    blob = get_clip_embedding_blob_for_key(db, insta_media_key)
    if blob is None:
        return []

    allowed = set(candidate_keys)
    need_neighbors = max(0, top_k - 1)
    knn_k = min(KNN_K_MAX, max(50, need_neighbors * 20)) if need_neighbors > 0 else 1
    knn_k = min(KNN_K_MAX, max(knn_k, 1))

    raw = knn_clip_catalog_keys(db, blob, k=knn_k)
    out: list[str] = []
    seen: set[str] = set()
    for image_key, _dist in raw:
        if image_key not in allowed or image_key in seen:
            continue
        seen.add(image_key)
        out.append(image_key)
        if len(out) >= top_k:
            break
    return out


def run_clip_similar_for_seed(
    db: sqlite3.Connection,
    seed_key: str,
    *,
    limit: int,
    offset: int,
    **catalog_filter_kwargs: Any,
) -> tuple[list[tuple[str, float]], dict[str, Any]]:
    """Return CLIP KNN neighbors for *seed_key* with catalog + primary-grid post-filters.

    **catalog_filter_kwargs** are passed to :func:`filter_order_keys_in_catalog` (optional
    ``posted``, ``month``, ``keyword``, ``min_rating``, ``date_from``, ``date_to``,
    ``color_label``, ``analyzed``, ``score_perspective``, ``min_score``,
    ``description_search``, ``dominant_colors``, ``mood_tags``, ``has_repetition``).

    Neighbors are processed in KNN (distance) order. The *seed_key* is never included.
    Non–primary-grid stack members are excluded via :func:`catalog_key_is_primary_grid_row`.

    Raises:
        NoClipEmbeddingError: No CLIP row for *seed_key*.
    """
    blob = get_clip_embedding_blob_for_key(db, seed_key)
    if blob is None:
        raise NoClipEmbeddingError(seed_key)

    # Over-fetch so filters can still return enough rows (same spirit as hybrid semantic).
    need = max(0, int(offset) + int(limit))
    knn_k = min(KNN_K_MAX, max(50, need * 20))
    knn_k = min(KNN_K_MAX, max(knn_k, 1))

    raw = knn_clip_catalog_keys(db, blob, k=knn_k)

    ordered: list[tuple[str, float]] = []
    for image_key, dist in raw:
        if image_key == seed_key:
            continue
        if not catalog_key_is_primary_grid_row(db, image_key):
            continue
        ordered.append((image_key, dist))

    if not ordered:
        return [], _clip_meta(knn_fetched=len(raw))

    keys_in_order = [k for k, _ in ordered]
    allowed = set(
        filter_order_keys_in_catalog(db, keys_in_order, **catalog_filter_kwargs)
    )
    filtered = [(k, d) for k, d in ordered if k in allowed]

    page = filtered[int(offset) : int(offset) + int(limit)]
    return page, _clip_meta(knn_fetched=len(raw), knn_k_used=knn_k)


def _clip_meta(*, knn_fetched: int, knn_k_used: int | None = None) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "clip_model_id": CLIP_EMBED_MODEL_ID,
        "clip_embed_dim": CLIP_EMBED_DIM,
        "knn_fetched": knn_fetched,
    }
    if knn_k_used is not None:
        meta["knn_k_used"] = knn_k_used
    return meta
