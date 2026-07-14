"""Catalog search front door — unified entry for NL, semantic, and chat paths (ADR-0008)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from lightroom_tagger.core.database import (
    build_description_fts_query,
    query_catalog_images_by_keys,
)
from lightroom_tagger.core.embedding_service import embed_query_to_vec_blob
from lightroom_tagger.core.semantic_search import run_semantic_hybrid_search


class CatalogSearchInputError(ValueError):
    """Invalid search input; map to HTTP 400 in the web layer."""


@dataclass(frozen=True)
class SearchResult:
    """Detached catalog search result — core rows + signals, not API-shaped."""

    images: list[dict]
    total: int
    mode: str
    filters: dict | None = None
    assistant_message: str | None = None
    messages: list[dict] | None = None
    metadata: dict | None = None


def _validate_semantic_message(message: str | None) -> str:
    if message is None or not str(message).strip():
        raise CatalogSearchInputError("query must be non-empty")
    qstrip = str(message).strip()
    if len(qstrip) < 2:
        raise CatalogSearchInputError("query must be at least 2 characters")
    return qstrip


def _run_semantic_search(
    db: sqlite3.Connection,
    message: str | None,
    *,
    score_perspective: str | None,
    limit: int,
    offset: int,
    restrict_to_keys: frozenset[str] | None = None,
) -> SearchResult:
    qstrip = _validate_semantic_message(message)

    match_str, fts_err = build_description_fts_query(qstrip)
    if fts_err is not None:
        raise CatalogSearchInputError(fts_err)
    if match_str is None:
        raise CatalogSearchInputError("query must contain at least one searchable term")

    blob = embed_query_to_vec_blob(qstrip)
    hybrid_kwargs: dict[str, object] = {
        "user_query": qstrip,
        "fts_match": match_str,
        "query_vec_blob": blob,
        "limit": limit,
        "offset": offset,
    }
    if restrict_to_keys is not None:
        hybrid_kwargs["restrict_to_keys"] = restrict_to_keys
    sem_rows, total, meta = run_semantic_hybrid_search(db, **hybrid_kwargs)

    keys = [r.image_key for r in sem_rows]
    catalog_rows = query_catalog_images_by_keys(
        db, keys, score_perspective=score_perspective
    )
    sem_by_key = {r.image_key: r for r in sem_rows}

    images: list[dict] = []
    for catalog_row in catalog_rows:
        row = dict(catalog_row)
        key = row.get("key")
        sem_row = sem_by_key.get(key) if key is not None else None
        row["score"] = float(sem_row.rrf_score) if sem_row is not None else None
        row["why_matched"] = sem_row.why_matched if sem_row is not None else None
        images.append(row)

    metadata = {
        "missing_embeddings_count": meta.missing_embeddings_count,
        "semantic_index_empty": meta.semantic_index_empty,
        "rrf_k": meta.rrf_k,
        "fts_no_match": meta.fts_no_match,
    }

    return SearchResult(
        images=images,
        total=total,
        mode="semantic",
        metadata=metadata,
    )


def search_catalog(
    db: sqlite3.Connection,
    message: str | None,
    *,
    history: list[dict] | None = None,
    pin_key: str | None = None,
    provider_id: str | None = None,
    model: str | None = None,
    score_perspective: str | None = None,
    limit: int,
    offset: int,
    mode: str = "auto",
) -> SearchResult:
    """Run catalog search. Only ``mode='semantic'`` is implemented in slice 1."""
    _ = (history, pin_key, provider_id, model)

    if mode == "semantic":
        return _run_semantic_search(
            db,
            message,
            score_perspective=score_perspective,
            limit=limit,
            offset=offset,
        )

    raise NotImplementedError(f"search mode {mode!r} not implemented")
