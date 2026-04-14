"""Identity API: best-photos ranking, style fingerprint, post-next suggestions (phase 08-01).

Thumbnails are not inlined here; responses include ``image_key`` and ``filename`` so the
frontend can use the existing catalog thumbnail/image routes.
"""

from __future__ import annotations

import sqlite3

from flask import Blueprint, jsonify, request
from flask.typing import ResponseReturnValue
from utils.db import with_db
from utils.responses import error_bad_request, error_server_error

from api.images import _clamp_pagination
from lightroom_tagger.core.identity_service import (
    build_style_fingerprint,
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


@bp.route("/best-photos", methods=["GET"])
@with_db
def best_photos(db: sqlite3.Connection) -> ResponseReturnValue:
    """Paginated eligible catalog images ranked by aggregate perspective score."""
    try:
        limit, offset = _clamp_pagination(
            request.args.get("limit", 50, type=int),
            request.args.get("offset", 0, type=int),
        )
        min_p, err = _parse_optional_min_perspectives()
        if err is not None:
            return err

        items, total, meta = rank_best_photos(
            db, limit=limit, offset=offset, min_perspectives=min_p
        )
        return jsonify({"items": items, "total": total, "meta": meta})
    except Exception:
        return error_server_error()


@bp.route("/style-fingerprint", methods=["GET"])
@with_db
def style_fingerprint(db: sqlite3.Connection) -> ResponseReturnValue:
    """Catalog-wide style fingerprint (per-perspective stats, tokens, evidence)."""
    try:
        return jsonify(build_style_fingerprint(db))
    except Exception:
        return error_server_error()


@bp.route("/suggestions", methods=["GET"])
@with_db
def suggestions(db: sqlite3.Connection) -> ResponseReturnValue:
    """What to post next: unposted, coverage-eligible images with reason codes."""
    try:
        limit, offset = _clamp_pagination(
            request.args.get("limit", 20, type=int),
            request.args.get("offset", 0, type=int),
        )
        look_recent = request.args.get("lookback_days_recent", type=int)
        look_base = request.args.get("lookback_days_baseline", type=int)
        if look_recent is not None and look_recent < 1:
            return error_bad_request("lookback_days_recent must be at least 1")
        if look_base is not None and look_base < 1:
            return error_bad_request("lookback_days_baseline must be at least 1")

        payload = suggest_what_to_post_next(
            db,
            limit=limit,
            offset=offset,
            lookback_days_recent=look_recent if look_recent is not None else 30,
            lookback_days_baseline=look_base if look_base is not None else 90,
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
