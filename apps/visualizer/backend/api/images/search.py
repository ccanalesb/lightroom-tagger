"""Natural language, semantic hybrid, and chat search endpoints."""

from __future__ import annotations

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
from lightroom_tagger.core.catalog_search import CatalogSearchInputError, search_catalog

from utils.score_perspective import validate_score_perspective_exists

from .catalog import (
    _rows_to_catalog_api_images,
)
from .common import _clamp_pagination

search_bp = Blueprint("images_search", __name__)


def _catalog_rows_with_signals(
    result_images: list[dict],
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

    images = _rows_to_catalog_api_images(catalog_rows)
    for img in images:
        sig = signals_by_key.get(img["key"])
        if sig is not None and sig.get("score") is not None:
            img["score"] = sig["score"]
            img["why_matched"] = sig["why_matched"]
            img["thumbnail_url"] = f"/api/images/catalog/{img['key']}/thumbnail"
    return images


def _parse_score_perspective_body(db, body: dict[str, Any]) -> str | None | tuple:
    """Return slug or ``error_bad_request`` response tuple when unknown."""
    if "score_perspective" not in body or body.get("score_perspective") is None:
        return None
    sp_raw = str(body.get("score_perspective") or "").strip()
    if not sp_raw:
        return None
    sp, err = validate_score_perspective_exists(db, sp_raw)
    if err:
        return error_bad_request(err)
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

        images = _rows_to_catalog_api_images(result.images)
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

        score_perspective_arg = _parse_score_perspective_body(db, body)
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

        images = _catalog_rows_with_signals(result.images)

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

        score_perspective_arg = _parse_score_perspective_body(db, body)
        if isinstance(score_perspective_arg, tuple):
            return score_perspective_arg

        try:
            result = search_catalog(
                db,
                message_stripped,
                history=prior,
                pin_key=body.get("pinned_image_key"),
                provider_id=body.get("provider_id"),
                model=body.get("model"),
                score_perspective=score_perspective_arg,
                mode="auto",
                limit=limit,
                offset=offset,
            )
        except CatalogSearchInputError as exc:
            return error_bad_request(str(exc))

        if result.mode in ("semantic", "tool_calling"):
            images = _catalog_rows_with_signals(result.images)
            if result.mode == "tool_calling":
                for img in images:
                    img["thumbnail_url"] = f"/api/images/catalog/{img['key']}/thumbnail"
        else:
            images = _rows_to_catalog_api_images(result.images)

        payload: dict[str, Any] = {
            "search_mode": result.mode,
            "total": result.total,
            "images": images,
            "filters": result.filters,
            "metadata": result.metadata,
        }
        if result.mode == "tool_calling":
            payload["messages"] = result.messages
            payload["assistant_message"] = result.assistant_message

        return jsonify(payload)
    except Exception as e:
        return error_server_error(str(e))


__all__ = ("search_bp",)
