"""Read-only REST API for persisted ``image_scores`` rows (library DB)."""
from __future__ import annotations

import sqlite3
from typing import Any

from flask import Blueprint, jsonify, request
from flask.typing import ResponseReturnValue
from utils.db import with_db
from utils.responses import error_bad_request

from api.perspectives import _SLUG_RE
from lightroom_tagger.core.database import (
    get_current_scores_for_image,
    list_score_history_for_perspective,
)

bp = Blueprint("scores", __name__)


def _normalize_score_row(row: dict) -> dict:
    out = dict(row)
    out["is_current"] = bool(out.get("is_current"))
    out["repaired_from_malformed"] = bool(out.get("repaired_from_malformed"))
    return out


def _image_type_from_request() -> tuple[str | None, Any]:
    raw = (request.args.get("image_type") or "catalog").strip().lower()
    if raw not in ("catalog", "instagram"):
        return None, error_bad_request("image_type must be catalog or instagram")
    return raw, None


@bp.route("/<path:image_key>/history", methods=["GET"])
@with_db
def get_score_history(db: sqlite3.Connection, image_key: str) -> ResponseReturnValue:
    image_type, err = _image_type_from_request()
    if err is not None:
        return err
    assert image_type is not None

    perspective_slug = (request.args.get("perspective_slug") or "").strip()
    if not perspective_slug:
        return error_bad_request("perspective_slug is required")
    if not _SLUG_RE.match(perspective_slug):
        return error_bad_request("invalid perspective_slug")

    rows = list_score_history_for_perspective(db, image_key, image_type, perspective_slug)
    return jsonify(
        {
            "image_key": image_key,
            "image_type": image_type,
            "perspective_slug": perspective_slug,
            "history": [_normalize_score_row(r) for r in rows],
        }
    )


@bp.route("/<path:image_key>", methods=["GET"])
@with_db
def get_current_scores(db: sqlite3.Connection, image_key: str) -> ResponseReturnValue:
    image_type, err = _image_type_from_request()
    if err is not None:
        return err
    assert image_type is not None

    rows = get_current_scores_for_image(db, image_key, image_type)
    return jsonify(
        {
            "image_key": image_key,
            "image_type": image_type,
            "current": [_normalize_score_row(r) for r in rows],
        }
    )
