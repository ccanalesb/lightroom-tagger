"""Posting analytics API (library DB validated dump matches)."""

from __future__ import annotations

import re
from typing import Literal, cast

from flask import Blueprint, jsonify, request
from utils.db import with_db
from utils.responses import error_bad_request, error_server_error

from api.images import _clamp_pagination
from lightroom_tagger.core.posting_analytics import (
    get_caption_hashtag_stats,
    get_posting_frequency,
    get_posting_time_heatmap,
    query_unposted_catalog,
)

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

bp = Blueprint('analytics', __name__)


def _parse_required_iso_date(label: str) -> str | None:
    raw = (request.args.get(label) or "").strip()
    if not raw or not _ISO_DATE_RE.match(raw):
        return None
    return raw


@bp.route("/posting-frequency", methods=["GET"])
@with_db
def posting_frequency(db):
    """Bucket counts of validated posts (see ``get_posting_frequency``)."""
    try:
        date_from = _parse_required_iso_date("date_from")
        date_to = _parse_required_iso_date("date_to")
        if not date_from or not date_to:
            return error_bad_request("date_from and date_to are required (YYYY-MM-DD)")

        gran_raw = (request.args.get("granularity") or "day").strip().lower()
        if gran_raw not in ("day", "week", "month"):
            return error_bad_request("granularity must be day, week, or month")

        buckets, meta = get_posting_frequency(
            db,
            date_from=date_from,
            date_to=date_to,
            granularity=cast(Literal["day", "week", "month"], gran_raw),
        )
        return jsonify({"buckets": buckets, "meta": meta})
    except Exception:
        return error_server_error()


@bp.route("/posting-heatmap", methods=["GET"])
@with_db
def posting_heatmap(db):
    """Day-of-week × hour heatmap for validated posts."""
    try:
        date_from = _parse_required_iso_date("date_from")
        date_to = _parse_required_iso_date("date_to")
        if not date_from or not date_to:
            return error_bad_request("date_from and date_to are required (YYYY-MM-DD)")

        cells, meta = get_posting_time_heatmap(db, date_from=date_from, date_to=date_to)
        return jsonify({"cells": cells, "meta": meta})
    except Exception:
        return error_server_error()


@bp.route("/caption-stats", methods=["GET"])
@with_db
def caption_stats(db):
    """Caption length and hashtag aggregates for validated posts."""
    try:
        date_from = _parse_required_iso_date("date_from")
        date_to = _parse_required_iso_date("date_to")
        if not date_from or not date_to:
            return error_bad_request("date_from and date_to are required (YYYY-MM-DD)")

        stats = get_caption_hashtag_stats(db, date_from=date_from, date_to=date_to)
        return jsonify(stats)
    except Exception:
        return error_server_error()


@bp.route("/unposted-catalog", methods=["GET"])
@with_db
def unposted_catalog(db):
    """Paginated catalog images with ``instagram_posted = 0`` (matches catalog filters)."""
    try:
        month = request.args.get("month")
        if month is not None and str(month).strip() != "":
            month = str(month).strip()
            if len(month) != 6 or not month.isdigit():
                return error_bad_request("month must be YYYYMM")
        else:
            month = None

        min_rating = request.args.get("min_rating", type=int)

        date_from = request.args.get("date_from", "").strip() or None
        date_to = request.args.get("date_to", "").strip() or None
        if date_from and not _ISO_DATE_RE.match(date_from):
            return error_bad_request("date_from must be YYYY-MM-DD")
        if date_to and not _ISO_DATE_RE.match(date_to):
            return error_bad_request("date_to must be YYYY-MM-DD")

        limit, offset = _clamp_pagination(
            request.args.get("limit", 50, type=int),
            request.args.get("offset", 0, type=int),
        )

        images, total = query_unposted_catalog(
            db,
            date_from=date_from,
            date_to=date_to,
            min_rating=min_rating,
            month=month,
            limit=limit,
            offset=offset,
        )

        return jsonify(
            {
                "total": total,
                "images": images,
                "pagination": {
                    "offset": offset,
                    "limit": limit,
                    "current_page": (offset // limit) + 1,
                    "total_pages": (total + limit - 1) // limit if limit else 0,
                    "has_more": (offset + limit) < total,
                },
            }
        )
    except Exception:
        return error_server_error()
