"""Catalog search front door — unified entry for NL, semantic, and chat paths (ADR-0008)."""

from __future__ import annotations

import contextvars
import json
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from lightroom_tagger.core import nl_catalog_search
from lightroom_tagger.core.catalog_nl_filter import (
    CatalogNlFilter,
    catalog_nl_filter_to_query_kwargs,
    parse_catalog_nl_filter_from_llm,
)
from lightroom_tagger.core.database import (
    build_description_fts_query,
    get_all_current_perspective_slugs,
    query_catalog_images,
    query_catalog_images_by_keys,
)
from lightroom_tagger.core.embedding_service import embed_query_to_vec_blob
from lightroom_tagger.core.semantic_search import run_semantic_hybrid_search
from lightroom_tagger.core.structured_output import StructuredOutputError


class CatalogSearchInputError(ValueError):
    """Invalid search input; map to HTTP 400 in the web layer."""


@dataclass(frozen=True)
class _RuntimeDeps:
    """Per-request dependency overrides injected by the web layer.

    The web layer's test suite patches its own module-level ``run_semantic_hybrid_search`` /
    ``embed_query_to_vec_blob`` / ``query_catalog_images`` symbols and needs the pin
    ``restrict_to_keys`` threaded through. We accept those via a greenlet-safe ContextVar
    instead of mutating this module's globals (which would leak across concurrent requests
    under eventlet). Pin plumbing proper lands in slice 3.
    """

    run_semantic_hybrid_search: Callable[..., Any] | None = None
    embed_query_to_vec_blob: Callable[..., Any] | None = None
    query_catalog_images: Callable[..., Any] | None = None
    restrict_to_keys: frozenset[str] | None = None


_runtime_deps: contextvars.ContextVar[_RuntimeDeps | None] = contextvars.ContextVar(
    "catalog_search_runtime_deps", default=None
)


def use_runtime_deps(
    *,
    run_semantic_hybrid_search: Callable[..., Any] | None = None,
    embed_query_to_vec_blob: Callable[..., Any] | None = None,
    query_catalog_images: Callable[..., Any] | None = None,
    restrict_to_keys: frozenset[str] | None = None,
) -> contextvars.Token:
    """Bind per-request runtime deps for the current greenlet; returns a reset token."""
    return _runtime_deps.set(
        _RuntimeDeps(
            run_semantic_hybrid_search=run_semantic_hybrid_search,
            embed_query_to_vec_blob=embed_query_to_vec_blob,
            query_catalog_images=query_catalog_images,
            restrict_to_keys=restrict_to_keys,
        )
    )


def reset_runtime_deps(token: contextvars.Token) -> None:
    """Undo a prior :func:`use_runtime_deps` binding."""
    _runtime_deps.reset(token)


def _deps() -> _RuntimeDeps:
    return _runtime_deps.get() or _RuntimeDeps()


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


def effective_catalog_nl_kwargs(filters: CatalogNlFilter) -> dict[str, Any]:
    """Drop empty-string / empty-list values so ``{}`` means "no structured filters"."""
    raw = catalog_nl_filter_to_query_kwargs(filters)
    out: dict[str, Any] = {}
    for k, v in raw.items():
        if v is None:
            continue
        if isinstance(v, str) and not v.strip():
            continue
        if isinstance(v, list) and len(v) == 0:
            continue
        out[k] = v
    return out


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
) -> SearchResult:
    qstrip = _validate_semantic_message(message)

    match_str, fts_err = build_description_fts_query(qstrip)
    if fts_err is not None:
        raise CatalogSearchInputError(fts_err)
    if match_str is None:
        raise CatalogSearchInputError("query must contain at least one searchable term")

    deps = _deps()
    embed = deps.embed_query_to_vec_blob or embed_query_to_vec_blob
    hybrid = deps.run_semantic_hybrid_search or run_semantic_hybrid_search

    blob = embed(qstrip)
    hybrid_kwargs: dict[str, Any] = {
        "user_query": qstrip,
        "fts_match": match_str,
        "query_vec_blob": blob,
        "limit": limit,
        "offset": offset,
    }
    if deps.restrict_to_keys is not None:
        hybrid_kwargs["restrict_to_keys"] = deps.restrict_to_keys
    sem_rows, total, meta = hybrid(db, **hybrid_kwargs)

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


def _parse_nl_filter_raw(raw: str) -> CatalogNlFilter:
    try:
        return parse_catalog_nl_filter_from_llm(raw)
    except (json.JSONDecodeError, ValidationError, StructuredOutputError) as exc:
        raise CatalogSearchInputError(f"NL filter: {exc}") from exc


def _run_nl_filter_one_shot_raw(
    message: str,
    *,
    provider_id: str | None,
    model: str | None,
) -> str:
    try:
        return nl_catalog_search.run_nl_catalog_filter_llm(
            message,
            provider_id=provider_id,
            model=model,
            log_callback=None,
        )
    except (json.JSONDecodeError, ValidationError, StructuredOutputError) as exc:
        raise CatalogSearchInputError(f"NL filter: {exc}") from exc


def _run_nl_filter_multi_turn_raw(
    turns: list[dict],
    *,
    provider_id: str | None,
    model: str | None,
    score_perspective_slugs: list[str],
) -> str:
    try:
        return nl_catalog_search.run_nl_catalog_filter_llm_multi_turn(
            turns,
            provider_id=provider_id,
            model=model,
            log_callback=None,
            score_perspective_slugs=score_perspective_slugs,
        )
    except (json.JSONDecodeError, ValidationError, StructuredOutputError) as exc:
        raise CatalogSearchInputError(f"NL filter: {exc}") from exc


def _run_nl_filter_query(
    db: sqlite3.Connection,
    filters: CatalogNlFilter,
    *,
    limit: int,
    offset: int,
) -> SearchResult:
    deps = _deps()
    query = deps.query_catalog_images or query_catalog_images
    qkwargs = catalog_nl_filter_to_query_kwargs(filters)
    qkwargs["limit"] = limit
    qkwargs["offset"] = offset
    if deps.restrict_to_keys is not None:
        qkwargs["restrict_to_keys"] = deps.restrict_to_keys
    try:
        rows, total = query(db, **qkwargs)
    except ValueError as err:
        raise CatalogSearchInputError(str(err)) from err
    return SearchResult(
        images=[dict(row) for row in rows],
        total=total,
        mode="nl_filter",
        filters=filters.model_dump(exclude_none=True),
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
    """Run catalog search (semantic, nl_filter, or auto NL-first cascade)."""
    _ = pin_key

    if mode == "semantic":
        return _run_semantic_search(
            db,
            message,
            score_perspective=score_perspective,
            limit=limit,
            offset=offset,
        )

    if mode == "nl_filter":
        qstrip = str(message or "").strip()
        if not qstrip:
            raise CatalogSearchInputError("query must be non-empty")
        raw = _run_nl_filter_one_shot_raw(
            qstrip,
            provider_id=provider_id,
            model=model,
        )
        filters = _parse_nl_filter_raw(raw)
        return _run_nl_filter_query(db, filters, limit=limit, offset=offset)

    if mode == "auto":
        msg_stripped = str(message or "").strip()
        turns = list(history or []) + [{"role": "user", "content": msg_stripped}]
        raw = _run_nl_filter_multi_turn_raw(
            turns,
            provider_id=provider_id,
            model=model,
            score_perspective_slugs=get_all_current_perspective_slugs(db),
        )
        filters = _parse_nl_filter_raw(raw)
        kwargs_eff = effective_catalog_nl_kwargs(filters)
        if not kwargs_eff:
            return _run_semantic_search(
                db,
                message,
                score_perspective=score_perspective,
                limit=limit,
                offset=offset,
            )
        return _run_nl_filter_query(db, filters, limit=limit, offset=offset)

    raise NotImplementedError(f"search mode {mode!r} not implemented")
