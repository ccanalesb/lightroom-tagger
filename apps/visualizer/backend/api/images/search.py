"""Natural language, semantic hybrid, and chat search endpoints."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from flask import Blueprint, jsonify, request
from spectree import Response
from utils.db import with_db
from utils.responses import error_bad_request, error_server_error

from api.openapi import spec
from api.schemas.jobs import ErrorBody
from api.schemas.search import (
    ChatSearchRequest,
    ChatSearchResponse,
    NlSearchRequest,
    NlSearchResponse,
    SemanticSearchRequest,
    SemanticSearchResponse,
)
from lightroom_tagger.core import nl_catalog_search
from lightroom_tagger.core.catalog_search import (
    CatalogSearchInputError,
    reset_runtime_deps,
    search_catalog,
    use_runtime_deps,
)
from lightroom_tagger.core.clip_similarity import (
    NoClipEmbeddingError,
    list_pin_similarity_candidate_keys,
)
from lightroom_tagger.core.database import (
    get_image,
    query_catalog_images,
    query_catalog_images_by_keys,
)
from lightroom_tagger.core.embedding_service import embed_query_to_vec_blob
from lightroom_tagger.core.exceptions import ModelUnavailableError
from lightroom_tagger.core.provider_registry import ProviderRegistry
from lightroom_tagger.core.semantic_search import run_semantic_hybrid_search

from .catalog import (
    _CATALOG_SCORE_PERSPECTIVE_SLUG_RE,
    _rows_to_catalog_api_images,
)
from .common import _clamp_pagination

search_bp = Blueprint("images_search", __name__)


def _merge_chat_search_metadata(
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


def _score_perspective_from_filters(filters: dict | None) -> str | None:
    if not filters:
        return None
    sp = str(filters.get("score_perspective") or "").strip()
    return sp or None


def _catalog_rows_with_signals(
    result_images: list[dict],
    score_perspective_arg: str | None,
) -> list[dict]:
    """Map core rows to API images, merging semantic score / why_matched / thumbnail_url."""
    catalog_rows: list[dict] = []
    signals_by_key: dict[str, dict[str, object]] = {}
    for row in result_images:
        r = dict(row)
        key = r.get("key")
        if key is not None:
            signals_by_key[str(key)] = {
                "score": r.pop("score", None),
                "why_matched": r.pop("why_matched", None),
            }
        catalog_rows.append(r)

    images = _rows_to_catalog_api_images(catalog_rows, score_perspective_arg)
    for img in images:
        sig = signals_by_key.get(img["key"])
        if sig is not None and sig.get("score") is not None:
            img["score"] = sig["score"]
            img["why_matched"] = sig["why_matched"]
            img["thumbnail_url"] = f"/api/images/catalog/{img['key']}/thumbnail"
    return images


def _chat_pin_context(
    db: sqlite3.Connection,
    body: dict[str, Any],
) -> tuple[frozenset[str] | None, dict[str, Any] | None]:
    """Return (restrict_to_keys, pin_metadata). ``None`` restrict → full catalog."""
    raw = body.get("pinned_image_key")
    if raw is None:
        return None, None
    pk = str(raw).strip()
    if not pk:
        return None, None
    if get_image(db, pk) is None:
        return None, {"pin_state": "inactive", "fallback_reason": "invalid_pin_key"}
    try:
        keys = list_pin_similarity_candidate_keys(db, pk)
        return frozenset(keys), {"pin_state": "active"}
    except NoClipEmbeddingError:
        return None, {"pin_state": "inactive", "fallback_reason": "no_clip_embedding"}


def _extract_images_from_tool_messages(
    messages: list[dict],
    db: sqlite3.Connection,
    *,
    score_perspective_override: str | None = None,
) -> tuple[list[dict], int]:
    """Parse the last tool result JSON, re-fetch rows in catalog API shape, ordered like the tool result."""
    tool_msgs = [
        m
        for m in messages
        if isinstance(m, dict) and str(m.get("role", "")).strip().lower() == "tool"
    ]
    if not tool_msgs:
        return [], 0
    last = tool_msgs[-1]
    raw_content = last.get("content")
    if raw_content is None or not str(raw_content).strip():
        return [], 0
    try:
        payload = json.loads(str(raw_content))
    except (json.JSONDecodeError, TypeError):
        return [], 0
    if not isinstance(payload, dict) or payload.get("error"):
        return [], 0
    tool_images = payload.get("images")
    if not isinstance(tool_images, list):
        return [], 0
    total = int(payload.get("total_matched", 0) or 0)
    keys: list[str] = []
    sp_from_tool: str | None = None
    for im in tool_images:
        if not isinstance(im, dict):
            continue
        k = im.get("key")
        if k is not None and str(k).strip():
            keys.append(str(k))
        if sp_from_tool is None and im.get("score_perspective"):
            spt = str(im["score_perspective"]).strip()
            if spt:
                sp_from_tool = spt
    sp_arg = score_perspective_override if score_perspective_override else sp_from_tool
    if not keys:
        return [], total
    rows = query_catalog_images_by_keys(db, keys, score_perspective=sp_arg)
    by_key = {r.get("key"): r for r in rows}
    ordered_rows = [by_key[k] for k in keys if k in by_key]
    images = _rows_to_catalog_api_images(ordered_rows, sp_arg)
    for img in images:
        img["thumbnail_url"] = f"/api/images/catalog/{img['key']}/thumbnail"
    return images, total


def _parse_score_perspective_body(body: dict[str, Any]) -> str | None | tuple:
    """Return slug or ``error_bad_request`` response tuple when invalid."""
    if "score_perspective" not in body or body.get("score_perspective") is None:
        return None
    sp = str(body.get("score_perspective") or "").strip()
    if not sp:
        return None
    if not _CATALOG_SCORE_PERSPECTIVE_SLUG_RE.match(sp):
        return error_bad_request("invalid score_perspective slug")
    return sp


@search_bp.route("/nl-search", methods=["POST"])
@with_db
@spec.validate(
    json=NlSearchRequest,
    resp=Response(HTTP_200=NlSearchResponse, HTTP_400=ErrorBody),
    tags=['images-search'],
)
def nl_search_images(db):
    """Natural language → LLM filter JSON → same row shape as GET /api/images/catalog."""
    try:
        body = request.get_json(silent=True)
        if not body or not isinstance(body, dict):
            return error_bad_request("JSON body required")

        query = body.get("query") or ""
        if not str(query).strip():
            return error_bad_request("query must be non-empty")

        limit, offset = _clamp_pagination(body.get("limit", 50), body.get("offset", 0))

        try:
            result = search_catalog(
                db,
                str(query).strip(),
                mode="nl_filter",
                provider_id=body.get("provider_id"),
                model=body.get("model"),
                limit=limit,
                offset=offset,
            )
        except CatalogSearchInputError as exc:
            return error_bad_request(str(exc))

        score_perspective_arg = _score_perspective_from_filters(result.filters)
        images = _rows_to_catalog_api_images(result.images, score_perspective_arg)
        return jsonify(
            {
                "filters": result.filters,
                "total": result.total,
                "images": images,
            }
        )
    except Exception as e:
        return error_server_error(str(e))


@search_bp.route("/semantic-search", methods=["POST"])
@with_db
@spec.validate(
    json=SemanticSearchRequest,
    resp=Response(HTTP_200=SemanticSearchResponse, HTTP_400=ErrorBody),
    tags=['images-search'],
)
def semantic_search_images(db):
    """Hybrid FTS + embedding search with RRF; same catalog row shape as NL search + score / why_matched / thumbnail_url."""
    try:
        body = request.get_json(silent=True)
        if not body or not isinstance(body, dict):
            return error_bad_request("JSON body required")

        limit, offset = _clamp_pagination(body.get("limit", 50), body.get("offset", 0))

        score_perspective_arg = _parse_score_perspective_body(body)
        if isinstance(score_perspective_arg, tuple):
            return score_perspective_arg

        try:
            result = search_catalog(
                db,
                body.get("query"),
                mode="semantic",
                score_perspective=score_perspective_arg,
                limit=limit,
                offset=offset,
            )
        except CatalogSearchInputError as exc:
            return error_bad_request(str(exc))

        images = _catalog_rows_with_signals(result.images, score_perspective_arg)

        return jsonify(
            {
                "total": result.total,
                "images": images,
                "metadata": result.metadata,
            }
        )
    except Exception as e:
        return error_server_error(str(e))


@search_bp.route("/chat-search", methods=["POST"])
@with_db
@spec.validate(
    json=ChatSearchRequest,
    resp=Response(HTTP_200=ChatSearchResponse, HTTP_400=ErrorBody),
    tags=['images-search'],
)
def chat_search_images(db):
    """Multi-turn NL-first cascade: structured catalog filters or semantic hybrid fallback."""
    try:
        body = request.get_json(silent=True)
        if not body or not isinstance(body, dict):
            return error_bad_request("JSON body required")

        msg = body.get("message")
        if msg is None or not str(msg).strip():
            return error_bad_request("message must be non-empty")

        message_stripped = str(msg).strip()

        if "messages" in body:
            raw_history = body.get("messages")
            if raw_history is None:
                raw_history = []
            if not isinstance(raw_history, list):
                return error_bad_request("messages must be a list")
        else:
            raw_history = []

        prior: list[dict] = []
        for item in raw_history:
            if not isinstance(item, dict):
                continue
            prior.append(
                {
                    "role": item.get("role"),
                    "content": item.get("content"),
                }
            )

        limit, offset = _clamp_pagination(body.get("limit", 50), body.get("offset", 0))
        pin_restrict, pin_meta = _chat_pin_context(db, body)

        turns_for_llm = prior + [{"role": "user", "content": message_stripped}]

        registry = ProviderRegistry()
        all_providers = {p["id"]: p for p in registry.list_providers()}
        resolved_provider_id = body.get("provider_id") or registry.defaults.get(
            "description", {}
        ).get("provider")
        provider_config = all_providers.get(resolved_provider_id, {})
        use_tool_calling = bool(provider_config.get("tool_calling", False))

        if use_tool_calling:
            score_perspective_for_tool = _parse_score_perspective_body(body)
            if isinstance(score_perspective_for_tool, tuple):
                return score_perspective_for_tool
            try:
                assistant_text, updated_messages = nl_catalog_search.run_tool_calling_search(
                    turns_for_llm,
                    provider_id=body.get("provider_id"),
                    model=body.get("model"),
                    db=db,
                    log_callback=None,
                    restrict_to_keys=pin_restrict,
                )
            except (ModelUnavailableError, ValueError) as exc:
                return error_bad_request(str(exc))
            images, total = _extract_images_from_tool_messages(
                updated_messages,
                db,
                score_perspective_override=score_perspective_for_tool,
            )
            return jsonify(
                {
                    "search_mode": "tool_calling",
                    "total": total,
                    "images": images,
                    "filters": None,
                    "metadata": _merge_chat_search_metadata(None, pin_meta),
                    "messages": updated_messages,
                    "assistant_message": assistant_text,
                }
            )

        score_perspective_arg = _parse_score_perspective_body(body)
        if isinstance(score_perspective_arg, tuple):
            return score_perspective_arg

        deps_token = use_runtime_deps(
            run_semantic_hybrid_search=run_semantic_hybrid_search,
            embed_query_to_vec_blob=embed_query_to_vec_blob,
            query_catalog_images=query_catalog_images,
            restrict_to_keys=pin_restrict,
        )
        try:
            result = search_catalog(
                db,
                message_stripped,
                history=prior,
                mode="auto",
                provider_id=body.get("provider_id"),
                model=body.get("model"),
                score_perspective=score_perspective_arg,
                limit=limit,
                offset=offset,
            )
        except CatalogSearchInputError as exc:
            return error_bad_request(str(exc))
        finally:
            reset_runtime_deps(deps_token)

        if result.mode == "semantic":
            images = _catalog_rows_with_signals(result.images, score_perspective_arg)
        else:
            sp_from_filter = _score_perspective_from_filters(result.filters)
            images = _rows_to_catalog_api_images(result.images, sp_from_filter)

        return jsonify(
            {
                "search_mode": result.mode,
                "total": result.total,
                "images": images,
                "filters": result.filters,
                "metadata": _merge_chat_search_metadata(result.metadata, pin_meta),
            }
        )
    except Exception as e:
        return error_server_error(str(e))


__all__ = ("search_bp",)
