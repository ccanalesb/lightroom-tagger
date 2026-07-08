"""Instagram dump/list endpoints and enrichment helpers."""

from __future__ import annotations

import json
import os
import sqlite3

from flask import Blueprint, jsonify, request, send_file
from utils.db import with_db
from utils.responses import (
    error_bad_request,
    error_not_found,
    error_server_error,
    success_paginated,
)

from lightroom_tagger.core.database import (
    get_image_description,
    get_image_descriptions_by_type,
    get_instagram_dump_media,
    get_instagram_dump_media_filtered,
    get_matches_model_mapping,
    get_matches_with_scores,
)

from .common import (
    _clamp_pagination,
    _extract_source_folder,
    _filter_by_date,
    _instagram_thumbnail_roots,
    _is_path_under_allowed_roots,
)

instagram_bp = Blueprint("images_instagram", __name__)

_DESC_JSON_COLS = (
    "composition",
    "perspectives",
    "technical",
    "subjects",
    "dominant_colors",
    "mood_tags",
)


def _dump_media_wire_row(row: dict) -> dict:
    """Preserve legacy JSON wire shape for ``list_dump_media`` rows."""
    out = dict(row)
    if isinstance(out.get("processed"), bool):
        out["processed"] = int(out["processed"])
    exif = out.get("exif_data")
    if exif is not None and not isinstance(exif, str):
        out["exif_data"] = json.dumps(exif)
    return out


def _deserialize_description(row: dict) -> dict:
    """Deserialize JSON columns in an image_descriptions row."""
    out = dict(row)
    for col in _DESC_JSON_COLS:
        val = out.get(col)
        if isinstance(val, str):
            try:
                out[col] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                pass
    return out


def _enrich_instagram_media(media_items, model_lookup=None, desc_lookup=None):
    """Transform database media items to API response format."""
    model_lookup = model_lookup or {}
    desc_lookup = desc_lookup or {}
    enriched = []
    for media in media_items:
        file_path = media.get("file_path", "")
        source_folder = _extract_source_folder(file_path)

        exif_data = media.get("exif_data")
        if isinstance(exif_data, str):
            try:
                exif_data = json.loads(exif_data)
            except (json.JSONDecodeError, TypeError):
                pass

        media_key = media["media_key"]
        ai_desc = desc_lookup.get((media_key, "instagram"))

        enriched.append(
            {
                "key": media_key,
                "local_path": file_path,
                "filename": media.get("filename", ""),
                "instagram_folder": media.get("date_folder", ""),
                "date_folder": media.get("date_folder", ""),
                "created_at": media.get("created_at"),
                "source_folder": source_folder,
                "image_hash": media.get("image_hash"),
                "description": ai_desc.get("summary", "") if ai_desc else "",
                "caption": media.get("caption", ""),
                "crawled_at": media.get("added_at", ""),
                "image_index": 1,
                "total_in_post": 1,
                "post_url": media.get("post_url"),
                "exif_data": exif_data,
                "processed": bool(media.get("processed")),
                "matched_catalog_key": media.get("matched_catalog_key"),
                "matched_model": model_lookup.get(media_key),
            }
        )
    return enriched


def _build_instagram_detail(db, image_key):
    """Build the instagram detail payload; returns (payload_dict, 404_flag)."""
    row = get_instagram_dump_media(db, image_key)
    if not row:
        return None, True

    out = dict(row)
    out["image_type"] = "instagram"
    out["key"] = row.get("media_key") or image_key
    out["instagram_folder"] = row.get("date_folder") or ""
    out["source_folder"] = _extract_source_folder(row.get("file_path") or "")
    out["local_path"] = row.get("file_path") or ""
    out["processed"] = bool(row.get("processed"))
    out["matched_catalog_key"] = row.get("matched_catalog_key")

    desc_row = get_image_description(db, image_key)
    if desc_row and desc_row.get("image_type") == "instagram":
        out["ai_analyzed"] = True
        out["description_summary"] = desc_row.get("summary") or ""
        out["description_best_perspective"] = desc_row.get("best_perspective") or ""
        persp = desc_row.get("perspectives")
        out["description_perspectives"] = persp if isinstance(persp, dict) else {}
    else:
        out["ai_analyzed"] = False
        out["description_summary"] = None
        out["description_best_perspective"] = None
        out["description_perspectives"] = None

    out["identity_aggregate_score"] = None
    out["identity_perspectives_covered"] = 0
    out["identity_eligible"] = False
    out["identity_per_perspective"] = []
    out["catalog_perspective_score"] = None
    out["catalog_score_perspective"] = None
    out["available_score_perspectives"] = []

    return out, False


@instagram_bp.route("", methods=["GET"])
@with_db
def list_instagram_images(db):
    """List Instagram images with filtering and pagination."""
    try:
        media_items = get_instagram_dump_media_filtered(db)

        model_lookup = {}
        score_lookup = {}
        try:
            model_lookup = get_matches_model_mapping(db)
            score_lookup = get_matches_with_scores(db)
        except sqlite3.OperationalError:
            pass

        desc_lookup = {}
        try:
            for desc in get_image_descriptions_by_type(db, "instagram"):
                key = (desc.get("image_key"), desc.get("image_type"))
                desc_lookup[key] = desc
        except sqlite3.OperationalError:
            pass

        enriched_images = _enrich_instagram_media(media_items, model_lookup, desc_lookup)

        for img in enriched_images:
            best = score_lookup.get(img.get("key"))
            img["match_score"] = best if best else None

        date_from = request.args.get("date_from", "")
        date_to = request.args.get("date_to", "")
        date_folder = request.args.get("date_folder", "")

        enriched_images = _filter_by_date(enriched_images, date_folder, date_from, date_to)

        sort_date_raw = (request.args.get("sort_by_date") or "").strip().lower()
        if sort_date_raw and sort_date_raw not in ("newest", "oldest"):
            return error_bad_request("sort_by_date must be newest or oldest")
        sort_reverse = sort_date_raw != "oldest"

        enriched_images.sort(
            key=lambda x: (x.get("instagram_folder") or "", x.get("key") or ""),
            reverse=sort_reverse,
        )

        limit, offset = _clamp_pagination(
            request.args.get("limit", 50, type=int),
            request.args.get("offset", 0, type=int),
        )
        total = len(enriched_images)

        paginated = enriched_images[offset : offset + limit]

        return jsonify(
            {
                "total": total,
                "images": paginated,
                "pagination": {
                    "offset": offset,
                    "limit": limit,
                    "current_page": (offset // limit) + 1,
                    "total_pages": (total + limit - 1) // limit,
                    "has_more": (offset + limit) < total,
                },
            }
        )
    except Exception as e:
        return error_server_error(str(e))


@instagram_bp.route("/months", methods=["GET"])
@with_db
def get_instagram_months(db):
    """Get unique months available in Instagram images."""
    try:
        media_items = get_instagram_dump_media_filtered(db)
        months = set()
        for media in media_items:
            date_folder = media.get("date_folder", "")
            if date_folder:
                months.add(date_folder)
        return jsonify({"months": sorted(months, reverse=True)})
    except Exception as e:
        return error_server_error(str(e))


@instagram_bp.route("/<path:image_key>/thumbnail", methods=["GET"])
@with_db
def get_instagram_thumbnail(db, image_key):
    """Get thumbnail for Instagram image."""
    try:
        media = get_instagram_dump_media(db, image_key)
        if not media:
            return error_not_found("image")
        local_path = media.get("file_path")

        if not local_path or not os.path.exists(local_path):
            return error_not_found("file")

        allowed_insta = _instagram_thumbnail_roots()
        if not allowed_insta or not _is_path_under_allowed_roots(local_path, allowed_insta):
            return error_not_found("file")

        return send_file(local_path, mimetype="image/jpeg")
    except Exception as e:
        return error_server_error(str(e))


@with_db
def list_dump_media(db):
    """List dump media with optional filtering."""
    try:
        processed = request.args.get("processed")
        matched = request.args.get("matched")
        limit, offset = _clamp_pagination(
            request.args.get("limit", 50, type=int),
            request.args.get("offset", 0, type=int),
        )

        if processed == "true":
            media = get_instagram_dump_media_filtered(db, processed=True)
        elif processed == "false":
            media = get_instagram_dump_media_filtered(db, processed=False)
        elif matched == "true":
            media = get_instagram_dump_media_filtered(db, matched=True)
        elif matched == "false":
            media = get_instagram_dump_media_filtered(db, matched=False)
        else:
            media = get_instagram_dump_media_filtered(db)

        total = len(media)
        paginated = [_dump_media_wire_row(row) for row in media[offset : offset + limit]]

        return jsonify(
            {
                "total": total,
                "media": paginated,
            }
        )
    except Exception as e:
        return error_server_error(str(e))


@instagram_bp.route("/<path:image_key>", methods=["GET"])
@with_db
def get_instagram_image_detail(db, image_key):
    """Single instagram image detail for the consolidated image-view modal."""
    score_perspective = (request.args.get("score_perspective") or "").strip()
    if score_perspective:
        return error_bad_request("score_perspective is only valid for catalog images")
    try:
        payload, not_found = _build_instagram_detail(db, image_key)
        if not_found:
            return error_not_found("image")
        return jsonify(payload)
    except Exception as e:
        return error_server_error(str(e))


__all__ = (
    "instagram_bp",
    "_build_instagram_detail",
    "_deserialize_description",
    "_enrich_instagram_media",
    "get_instagram_image_detail",
    "list_dump_media",
)
