"""Catalog search front door — unified entry for NL, semantic, and chat paths (ADR-0015).

``search_catalog`` is the only supported orchestration entry for catalog search.
Underlying runners (NL filter, tool-calling, semantic hybrid, pin similarity) are
internal to this module — do not call them from the web layer (see ADR-0015).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, replace
from typing import Any

from pydantic import ValidationError

from lightroom_tagger.core import nl_catalog_search
from lightroom_tagger.core.catalog_nl_filter import (
    CatalogNlFilter,
    catalog_nl_filter_to_query_kwargs,
    parse_catalog_nl_filter_from_llm,
)
from lightroom_tagger.core.clip_similarity import (
    NoClipEmbeddingError,
    list_pin_similarity_candidate_keys,
)
from lightroom_tagger.core.database import (
    build_description_fts_query,
    get_all_current_perspective_slugs,
    get_image,
    query_catalog_images,
    query_catalog_images_by_keys,
)
from lightroom_tagger.core.embedding_service import embed_query_to_vec_blob
from lightroom_tagger.core.exceptions import ModelUnavailableError
from lightroom_tagger.core.provider_registry import ProviderRegistry
from lightroom_tagger.core.search_tools import extract_images_from_tool_messages
from lightroom_tagger.core.semantic_search import run_semantic_hybrid_search
from lightroom_tagger.core.structured_output import StructuredOutputError


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


def _merge_search_metadata(
    base: dict[str, Any] | None,
    pin: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if base is None and pin is None:
        return None
    out: dict[str, Any] = {}
    if base:
        out.update(base)
    if pin:
        out.update(pin)
    return out or None


def _resolve_pin_context(
    db: sqlite3.Connection,
    pin_key: str | None,
) -> tuple[frozenset[str] | None, dict[str, Any] | None]:
    """Return (restrict_to_keys, pin_metadata). ``None`` restrict → full catalog."""
    if pin_key is None:
        return None, None
    pk = str(pin_key).strip()
    if not pk:
        return None, None
    if get_image(db, pk) is None:
        return None, {"pin_state": "inactive", "fallback_reason": "invalid_pin_key"}
    try:
        keys = list_pin_similarity_candidate_keys(db, pk)
        return frozenset(keys), {"pin_state": "active"}
    except NoClipEmbeddingError:
        return None, {"pin_state": "inactive", "fallback_reason": "no_clip_embedding"}


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
    hybrid_kwargs: dict[str, Any] = {
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
    restrict_to_keys: frozenset[str] | None = None,
) -> SearchResult:
    qkwargs = catalog_nl_filter_to_query_kwargs(filters)
    qkwargs["limit"] = limit
    qkwargs["offset"] = offset
    if restrict_to_keys is not None:
        qkwargs["restrict_to_keys"] = restrict_to_keys
    try:
        rows, total = query_catalog_images(db, **qkwargs)
    except ValueError as err:
        raise CatalogSearchInputError(str(err)) from err
    return SearchResult(
        images=[dict(row) for row in rows],
        total=total,
        mode="nl_filter",
        filters=filters.model_dump(exclude_none=True),
    )


def _run_tool_calling_search(
    db: sqlite3.Connection,
    turns: list[dict],
    *,
    provider_id: str | None,
    model: str | None,
    score_perspective: str | None,
    restrict_to_keys: frozenset[str] | None,
) -> SearchResult:
    try:
        assistant_text, updated_messages = nl_catalog_search.run_tool_calling_search(
            turns,
            provider_id=provider_id,
            model=model,
            db=db,
            log_callback=None,
            restrict_to_keys=restrict_to_keys,
        )
    except (ModelUnavailableError, ValueError) as exc:
        raise CatalogSearchInputError(str(exc)) from exc
    images, total = extract_images_from_tool_messages(
        updated_messages,
        db,
        score_perspective=score_perspective,
    )
    return SearchResult(
        images=images,
        total=total,
        mode="tool_calling",
        filters=None,
        assistant_message=assistant_text,
        messages=updated_messages,
    )


def _with_pin_metadata(result: SearchResult, pin_meta: dict[str, Any] | None) -> SearchResult:
    if not pin_meta:
        return result
    return replace(
        result,
        metadata=_merge_search_metadata(result.metadata, pin_meta),
    )


def _provider_uses_tool_calling(provider_id: str | None) -> bool:
    registry = ProviderRegistry()
    by_id = {p["id"]: p for p in registry.list_providers()}
    resolved = provider_id or registry.defaults.get("description", {}).get("provider")
    return bool(by_id.get(resolved, {}).get("tool_calling", False))


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
    """Run catalog search (semantic, nl_filter, tool_calling, or auto cascade).

    Single front door for catalog search (ADR-0015). Returns detached core rows
    and per-row signals via :class:`SearchResult` — never live ``sqlite3.Row``.
    """
    restrict_to_keys, pin_meta = _resolve_pin_context(db, pin_key)

    if mode == "semantic":
        return _with_pin_metadata(
            _run_semantic_search(
                db,
                message,
                score_perspective=score_perspective,
                limit=limit,
                offset=offset,
                restrict_to_keys=restrict_to_keys,
            ),
            pin_meta,
        )

    if mode == "nl_filter":
        qstrip = str(message or "").strip()
        if not qstrip:
            raise CatalogSearchInputError("query must be non-empty")
        filters = _parse_nl_filter_raw(
            _run_nl_filter_one_shot_raw(qstrip, provider_id=provider_id, model=model)
        )
        return _with_pin_metadata(
            _run_nl_filter_query(
                db,
                filters,
                limit=limit,
                offset=offset,
                restrict_to_keys=restrict_to_keys,
            ),
            pin_meta,
        )

    if mode == "auto":
        msg_stripped = str(message or "").strip()
        turns = list(history or []) + [{"role": "user", "content": msg_stripped}]
        if _provider_uses_tool_calling(provider_id):
            return _with_pin_metadata(
                _run_tool_calling_search(
                    db,
                    turns,
                    provider_id=provider_id,
                    model=model,
                    score_perspective=score_perspective,
                    restrict_to_keys=restrict_to_keys,
                ),
                pin_meta,
            )
        filters = _parse_nl_filter_raw(
            _run_nl_filter_multi_turn_raw(
                turns,
                provider_id=provider_id,
                model=model,
                score_perspective_slugs=get_all_current_perspective_slugs(db),
            )
        )
        if not effective_catalog_nl_kwargs(filters):
            result = _run_semantic_search(
                db,
                message,
                score_perspective=score_perspective,
                limit=limit,
                offset=offset,
                restrict_to_keys=restrict_to_keys,
            )
        else:
            result = _run_nl_filter_query(
                db,
                filters,
                limit=limit,
                offset=offset,
                restrict_to_keys=restrict_to_keys,
            )
        return _with_pin_metadata(result, pin_meta)

    raise NotImplementedError(f"search mode {mode!r} not implemented")
