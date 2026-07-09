"""Natural language, semantic hybrid, and chat search endpoints."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from flask import Blueprint, jsonify, request
from pydantic import ValidationError

from utils.db import with_db
from utils.responses import error_bad_request, error_server_error

from lightroom_tagger.core import nl_catalog_search
from lightroom_tagger.core.catalog_nl_filter import (
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
from lightroom_tagger.core.semantic_search import run_semantic_hybrid_search
from lightroom_tagger.core.structured_output import StructuredOutputError

from .catalog import (
    _CATALOG_SCORE_PERSPECTIVE_SLUG_RE,
    _effective_catalog_nl_kwargs,
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


@search_bp.route("/nl-search", methods=["POST"])
@with_db
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
            raw = nl_catalog_search.run_nl_catalog_filter_llm(
                str(query).strip(),
                provider_id=body.get("provider_id"),
                model=body.get("model"),
                log_callback=None,
            )
            filters = parse_catalog_nl_filter_from_llm(raw)
        except (json.JSONDecodeError, ValidationError, StructuredOutputError) as exc:
            return error_bad_request(f"NL filter: {exc}")

        qkwargs = catalog_nl_filter_to_query_kwargs(filters)
        qkwargs["limit"] = limit
        qkwargs["offset"] = offset

        score_perspective_arg = (filters.score_perspective or "").strip() or None

        try:
            rows, total = query_catalog_images(db, **qkwargs)
        except ValueError as err:
            return error_bad_request(str(err))

        images = _rows_to_catalog_api_images(rows, score_perspective_arg)
        return jsonify(
            {
                "filters": filters.model_dump(exclude_none=True),
                "total": total,
                "images": images,
            }
        )
    except Exception as e:
        return error_server_error(str(e))


@search_bp.route("/semantic-search", methods=["POST"])
@with_db
def semantic_search_images(db):
    """Hybrid FTS + embedding search with RRF; same catalog row shape as NL search + score / why_matched / thumbnail_url."""
    try:
        body = request.get_json(silent=True)
        if not body or not isinstance(body, dict):
            return error_bad_request("JSON body required")

        query = body.get("query")
        if query is None or not str(query).strip():
            return error_bad_request("query must be non-empty")

        qstrip = str(query).strip()
        if len(qstrip) < 2:
            return error_bad_request("query must be at least 2 characters")

        limit, offset = _clamp_pagination(body.get("limit", 50), body.get("offset", 0))

        score_perspective_arg = None
        if "score_perspective" in body and body.get("score_perspective") is not None:
            sp = str(body.get("score_perspective") or "").strip()
            if sp:
                if not _CATALOG_SCORE_PERSPECTIVE_SLUG_RE.match(sp):
                    return error_bad_request("invalid score_perspective slug")
                score_perspective_arg = sp

        match_str, fts_err = build_description_fts_query(qstrip)
        if fts_err is not None:
            return error_bad_request(fts_err)
        if match_str is None:
            return error_bad_request("query must contain at least one searchable term")

        blob = embed_query_to_vec_blob(qstrip)
        rows, total, meta = run_semantic_hybrid_search(
            db,
            user_query=qstrip,
            fts_match=match_str,
            query_vec_blob=blob,
            limit=limit,
            offset=offset,
        )

        keys = [r.image_key for r in rows]
        catalog_rows = query_catalog_images_by_keys(
            db, keys, score_perspective=score_perspective_arg
        )
        images = _rows_to_catalog_api_images(catalog_rows, score_perspective_arg)

        sem_by_key = {r.image_key: r for r in rows}
        for img in images:
            sem_row = sem_by_key.get(img["key"])
            if sem_row is not None:
                img["score"] = float(sem_row.rrf_score)
                img["why_matched"] = sem_row.why_matched
                img["thumbnail_url"] = f"/api/images/catalog/{sem_row.image_key}/thumbnail"

        return jsonify(
            {
                "total": total,
                "images": images,
                "metadata": {
                    "missing_embeddings_count": meta.missing_embeddings_count,
                    "semantic_index_empty": meta.semantic_index_empty,
                    "rrf_k": meta.rrf_k,
                    "fts_no_match": meta.fts_no_match,
                },
            }
        )
    except Exception as e:
        return error_server_error(str(e))


@search_bp.route("/chat-search", methods=["POST"])
@with_db
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
            score_perspective_for_tool: str | None = None
            if "score_perspective" in body and body.get("score_perspective") is not None:
                sp = str(body.get("score_perspective") or "").strip()
                if sp:
                    if not _CATALOG_SCORE_PERSPECTIVE_SLUG_RE.match(sp):
                        return error_bad_request("invalid score_perspective slug")
                    score_perspective_for_tool = sp
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

        available_slugs = get_all_current_perspective_slugs(db)

        try:
            raw = nl_catalog_search.run_nl_catalog_filter_llm_multi_turn(
                turns_for_llm,
                provider_id=body.get("provider_id"),
                model=body.get("model"),
                log_callback=None,
                score_perspective_slugs=available_slugs,
            )
            filters = parse_catalog_nl_filter_from_llm(raw)
        except (json.JSONDecodeError, ValidationError, StructuredOutputError) as exc:
            return error_bad_request(f"NL filter: {exc}")

        kwargs_eff = _effective_catalog_nl_kwargs(filters)

        score_perspective_arg = None
        if "score_perspective" in body and body.get("score_perspective") is not None:
            sp = str(body.get("score_perspective") or "").strip()
            if sp:
                if not _CATALOG_SCORE_PERSPECTIVE_SLUG_RE.match(sp):
                    return error_bad_request("invalid score_perspective slug")
                score_perspective_arg = sp

        if not kwargs_eff:
            qstrip = message_stripped
            if len(qstrip) < 2:
                return error_bad_request(
                    "message must be at least 2 characters for semantic search"
                )

            match_str, fts_err = build_description_fts_query(qstrip)
            if fts_err is not None:
                return error_bad_request(fts_err)
            if match_str is None:
                return error_bad_request("query must contain at least one searchable term")

            blob = embed_query_to_vec_blob(qstrip)
            rows, total, meta = run_semantic_hybrid_search(
                db,
                user_query=qstrip,
                fts_match=match_str,
                query_vec_blob=blob,
                limit=limit,
                offset=offset,
                restrict_to_keys=pin_restrict,
            )

            keys = [r.image_key for r in rows]
            catalog_rows = query_catalog_images_by_keys(
                db, keys, score_perspective=score_perspective_arg
            )
            images = _rows_to_catalog_api_images(catalog_rows, score_perspective_arg)

            sem_by_key = {r.image_key: r for r in rows}
            for img in images:
                sem_row = sem_by_key.get(img["key"])
                if sem_row is not None:
                    img["score"] = float(sem_row.rrf_score)
                    img["why_matched"] = sem_row.why_matched
                    img["thumbnail_url"] = f"/api/images/catalog/{sem_row.image_key}/thumbnail"

            sem_meta = {
                "missing_embeddings_count": meta.missing_embeddings_count,
                "semantic_index_empty": meta.semantic_index_empty,
                "rrf_k": meta.rrf_k,
                "fts_no_match": meta.fts_no_match,
            }
            return jsonify(
                {
                    "search_mode": "semantic",
                    "total": total,
                    "images": images,
                    "filters": None,
                    "metadata": _merge_chat_search_metadata(sem_meta, pin_meta),
                }
            )

        qkwargs = dict(kwargs_eff)
        qkwargs["limit"] = limit
        qkwargs["offset"] = offset
        if pin_restrict is not None:
            qkwargs["restrict_to_keys"] = pin_restrict

        score_perspective_from_filter = (filters.score_perspective or "").strip() or None

        try:
            rows, total = query_catalog_images(db, **qkwargs)
        except ValueError as err:
            return error_bad_request(str(err))

        images = _rows_to_catalog_api_images(rows, score_perspective_from_filter)
        return jsonify(
            {
                "search_mode": "nl_filter",
                "total": total,
                "images": images,
                "filters": filters.model_dump(exclude_none=True),
                "metadata": _merge_chat_search_metadata(None, pin_meta),
            }
        )
    except Exception as e:
        return error_server_error(str(e))


__all__ = ("search_bp",)
