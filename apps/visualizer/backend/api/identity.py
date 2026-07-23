"""Identity API: best-photos ranking, mirror signature, post-next suggestions (phase 08-01).

Thumbnails are not inlined here; responses include ``image_key`` and ``filename`` so the
frontend can use the existing catalog thumbnail/image routes.
"""

from __future__ import annotations

import sqlite3

from flask import Blueprint, jsonify, request
from flask.typing import ResponseReturnValue
from spectree import Response
from utils.db import with_db
from utils.responses import error_bad_request, error_server_error

from api.openapi import spec
from api.schemas.identity import (
    IdentityBestPhotosQuery,
    IdentityBestPhotosResponse,
    MirrorResponse,
    PostNextSuggestionsQuery,
    PostNextSuggestionsResponse,
)
from api.schemas.jobs import ErrorBody
from utils.pagination import _clamp_pagination
from lightroom_tagger.core.identity_service import (
    build_mirror,
    rank_best_photos,
    suggest_what_to_post_next,
)

bp = Blueprint('identity', __name__)


def _parse_optional_min_perspectives() -> tuple[int | None, ResponseReturnValue | None]:
    raw = request.args.get("min_perspectives")
    if raw is None or str(raw).strip() == "":
        return None, None
    try:
        v = int(str(raw).strip())
    except (TypeError, ValueError):
        return None, error_bad_request("min_perspectives must be an integer")
    if v < 1:
        return None, error_bad_request("min_perspectives must be at least 1")
    if v > 50:
        v = 50
    return v, None


def _parse_sort_by_date() -> tuple[str | None, ResponseReturnValue | None]:
    raw = (request.args.get("sort_by_date") or "").strip().lower()
    if not raw:
        return None, None
    if raw not in ("newest", "oldest"):
        return None, error_bad_request("sort_by_date must be newest or oldest")
    return raw, None


def _parse_optional_posted() -> tuple[bool | None, ResponseReturnValue | None]:
    raw = request.args.get("posted")
    if raw is None or str(raw).strip() == "":
        return None, None
    key = str(raw).strip().lower()
    if key in ("true", "1", "yes"):
        return True, None
    if key in ("false", "0", "no"):
        return False, None
    return None, error_bad_request("posted must be true or false")


@bp.route("/best-photos", methods=["GET"])
@with_db
@spec.validate(
    query=IdentityBestPhotosQuery,
    resp=Response(HTTP_200=IdentityBestPhotosResponse, HTTP_400=ErrorBody, HTTP_500=ErrorBody),
    tags=['identity'],
)
def best_photos(db: sqlite3.Connection):
    """Paginated eligible catalog images ranked by peak within-perspective percentile."""
    try:
        limit, offset = _clamp_pagination(
            request.args.get("limit", 50, type=int),
            request.args.get("offset", 0, type=int),
        )
        min_p, err = _parse_optional_min_perspectives()
        if err is not None:
            return err
        sort_by_date, err2 = _parse_sort_by_date()
        if err2 is not None:
            return err2
        posted_value, err3 = _parse_optional_posted()
        if err3 is not None:
            return err3

        items, total, meta = rank_best_photos(
            db,
            limit=limit,
            offset=offset,
            min_perspectives=min_p,
            sort_by_date=sort_by_date,
            posted=posted_value,
        )
        return jsonify({"items": items, "total": total, "meta": meta})
    except Exception:
        return error_server_error()


@bp.route("/mirror", methods=["GET"])
@with_db
@spec.validate(
    resp=Response(HTTP_200=MirrorResponse, HTTP_500=ErrorBody),
    tags=['identity'],
)
def mirror(db: sqlite3.Connection):
    """Catalog Mirror: crowned signature techniques and exemplar rails."""
    try:
        return jsonify(build_mirror(db))
    except Exception:
        return error_server_error()


@bp.route("/suggestions", methods=["GET"])
@with_db
@spec.validate(
    query=PostNextSuggestionsQuery,
    resp=Response(HTTP_200=PostNextSuggestionsResponse, HTTP_400=ErrorBody, HTTP_500=ErrorBody),
    tags=['identity'],
)
def suggestions(db: sqlite3.Connection):
    """What to post next: unposted, coverage-eligible images with reason codes."""
    try:
        limit, offset = _clamp_pagination(
            request.args.get("limit", 20, type=int),
            request.args.get("offset", 0, type=int),
        )
        sort_by_date, err = _parse_sort_by_date()
        if err is not None:
            return err

        payload = suggest_what_to_post_next(
            db,
            limit=limit,
            offset=offset,
            sort_by_date=sort_by_date,
        )
        return jsonify(
            {
                "candidates": payload["candidates"],
                "total": payload["total"],
                "meta": payload["meta"],
                "empty_state": payload["empty_state"],
            }
        )
    except Exception:
        return error_server_error()
