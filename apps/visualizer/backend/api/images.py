import json
import os
import re
import sqlite3
from collections import OrderedDict
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from flask import Blueprint, jsonify, request, send_file
from pydantic import ValidationError
from utils.db import with_db
from utils.responses import (
    error_bad_request,
    error_not_found,
    error_server_error,
    success_paginated,
)

from lightroom_tagger.core import nl_catalog_search
from lightroom_tagger.core.catalog_nl_filter import (
    CatalogNlFilter,
    catalog_nl_filter_to_query_kwargs,
    parse_catalog_nl_filter_from_llm,
)
from lightroom_tagger.core.clip_similarity import (
    NoClipEmbeddingError,
    list_pin_similarity_candidate_keys,
    run_clip_similar_for_seed,
)
from lightroom_tagger.core.database import (
    StackMutationError,
    _deserialize_row,
    build_description_fts_query,
    catalog_image_stack_row_fields,
    get_image,
    get_image_description,
    get_instagram_dump_media,
    library_write,
    query_catalog_images,
    query_catalog_images_by_keys,
    reject_match,
    stack_merge_into,
    stack_set_representative,
    stack_split_member_out,
    unvalidate_match,
    validate_match,
)
from lightroom_tagger.core.embedding_service import embed_query_to_vec_blob
from lightroom_tagger.core.identity_service import (
    compute_single_image_aggregate_scores,
)
from lightroom_tagger.core.provider_errors import ModelUnavailableError
from lightroom_tagger.core.provider_registry import ProviderRegistry
from lightroom_tagger.core.semantic_search import run_semantic_hybrid_search
from lightroom_tagger.core.structured_output import StructuredOutputError

_CATALOG_SCORE_PERSPECTIVE_SLUG_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

bp = Blueprint("images", __name__)

_DESC_JSON_COLS = (
    "composition",
    "perspectives",
    "technical",
    "subjects",
    "dominant_colors",
    "mood_tags",
)


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
    row = db.execute("SELECT 1 FROM images WHERE key = ?", (pk,)).fetchone()
    if not row:
        return None, {"pin_state": "inactive", "fallback_reason": "invalid_pin_key"}
    try:
        keys = list_pin_similarity_candidate_keys(db, pk)
        return frozenset(keys), {"pin_state": "active"}
    except NoClipEmbeddingError:
        return None, {"pin_state": "inactive", "fallback_reason": "no_clip_embedding"}


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
                "date_folder": media.get(
                    "date_folder", ""
                ),  # Add explicit date_folder for frontend
                "created_at": media.get("created_at"),  # Add created_at timestamp
                "source_folder": source_folder,
                "image_hash": media.get("image_hash"),
                "description": ai_desc.get("summary", "") if ai_desc else "",  # AI description
                "caption": media.get("caption", ""),  # Instagram caption
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


def _canonical_path(path: str) -> str | None:
    if not path or not str(path).strip():
        return None
    try:
        return os.path.realpath(os.path.expanduser(str(path).strip()))
    except OSError:
        return None


def _parent_dir_if_exists(path: str) -> str | None:
    base = _canonical_path(path)
    if not base:
        return None
    parent = os.path.dirname(base)
    if parent and os.path.isdir(parent):
        return parent
    return None


def _is_path_under_allowed_roots(file_path: str, roots: list[str]) -> bool:
    if not file_path or not roots:
        return False
    try:
        real_file = os.path.realpath(file_path)
    except OSError:
        return False
    for root in roots:
        if not root:
            continue
        if real_file == root:
            return True
        prefix = root + os.sep
        if real_file.startswith(prefix):
            return True
    return False


def _instagram_thumbnail_roots() -> list[str]:
    from lightroom_tagger.core.config import load_config

    cfg = load_config()
    dump = (cfg.instagram_dump_path or "").strip()
    if not dump:
        return []
    root = _canonical_path(dump)
    if root and os.path.isdir(root):
        return [root]
    return []


def _catalog_thumbnail_roots() -> list[str]:
    from lightroom_tagger.core.config import load_config

    cfg = load_config()
    roots: list[str] = []
    vc = _canonical_path(cfg.vision_cache_dir)
    if vc:
        roots.append(vc)
    mp = (cfg.mount_point or "").strip()
    if mp:
        mp_real = _canonical_path(mp)
        if mp_real and os.path.isdir(mp_real):
            roots.append(mp_real)
    for p in (cfg.catalog_path, cfg.small_catalog_path):
        par = _parent_dir_if_exists(p)
        if par and par not in roots:
            roots.append(par)
    seen: set[str] = set()
    out: list[str] = []
    for r in roots:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def _extract_source_folder(file_path):
    """Extract source folder (posts, archived_posts) from file path."""
    if "/media/" in file_path:
        parts = file_path.split("/media/")
        if len(parts) > 1:
            subpath = parts[1].split("/")
            if len(subpath) > 0:
                return subpath[0]
    return "unknown"


def _clamp_pagination(limit, offset, default_limit=50):
    if limit is None:
        limit = default_limit
    else:
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = default_limit
    limit = max(1, min(500, limit))
    if offset is None:
        offset = 0
    else:
        try:
            offset = int(offset)
        except (TypeError, ValueError):
            offset = 0
    offset = max(0, offset)
    return limit, offset


# CLIP /similar: ``why_matched`` line. NN = round(similarity*100) from 1.0 - cosine distance.
def _clip_similarity_why_matched_line(similarity: float) -> str:
    pct = max(0, min(100, int(round(float(similarity) * 100.0))))
    return f"Visual match ({pct}%)"


def _query_catalog_rows_for_stack_member_keys(
    db: sqlite3.Connection,
    keys: Sequence[str],
    *,
    score_perspective: str | None = None,
) -> list[dict]:
    """Catalog-shaped rows for *keys* in input order, **without** primary-grid stack collapse.

    :func:`query_catalog_images_by_keys` hides non–stack-representative members; the stack
    members strip (``/stacks/<id>/members``) must list every key in the burst, including
    non-representatives, with the same columns/joins as the normal catalog by-keys path.
    """
    if not keys:
        return []
    key_list = [str(k) for k in keys]
    sp = (score_perspective or "").strip()
    use_score_join = bool(sp)

    ph = ",".join("?" * len(key_list))
    case_when = " ".join(f"WHEN ? THEN {i}" for i in range(len(key_list)))
    order_sql = f"ORDER BY CASE i.key {case_when} END"

    select_cols = (
        "i.*, d.summary AS description_summary, "
        "d.best_perspective AS description_best_perspective, "
        "d.perspectives AS description_perspectives_json"
    )
    if use_score_join:
        select_cols += ", s.score AS catalog_perspective_score"
    select_cols += (
        ", st.stack_id AS stack_id, st.stack_size AS stack_member_count, "
        "CASE WHEN st.stack_id IS NOT NULL AND i.key = st.representative_key "
        "THEN 1 ELSE 0 END AS is_stack_representative"
    )

    join_sql = (
        "FROM images i "
        "LEFT JOIN image_descriptions d ON i.key = d.image_key AND d.image_type = 'catalog' "
    )
    join_bindings: list = []
    if use_score_join:
        join_sql += (
            "LEFT JOIN image_scores s ON s.image_key = i.key "
            "AND s.image_type = 'catalog' AND s.perspective_slug = ? AND s.is_current = 1 "
        )
        join_bindings.append(sp)
    join_sql += (
        "LEFT JOIN image_stack_members AS m_st ON m_st.image_key = i.key "
        "LEFT JOIN image_stacks AS st ON st.stack_id = m_st.stack_id "
    )

    where_sql = f"WHERE i.key IN ({ph})"
    params = join_bindings + key_list + key_list

    rows = db.execute(
        f"SELECT {select_cols} {join_sql} {where_sql} {order_sql}",
        params,
    ).fetchall()
    return [_deserialize_row(r) for r in rows]


def _parse_clip_similar_catalog_params():
    """Parse query params for GET /catalog/.../similar; mirrors ``list_catalog_images`` + optional DTO filters.

    **sort_by_*** are validated like the catalog list but are not passed to
    :func:`run_clip_similar_for_seed` (KNN order is by CLIP distance; membership
    filters omit sorts — see :func:`filter_order_keys_in_catalog`).

    Returns:
        ``(error_response, None)`` or ``(None, dict)`` with keys:
        ``limit``, ``offset``, ``score_perspective_arg``, ``clip_filter_kwargs``.
    """
    posted_raw = request.args.get("posted")
    if posted_raw == "true":
        posted_filter = True
    elif posted_raw == "false":
        posted_filter = False
    else:
        posted_filter = None

    analyzed_raw = request.args.get("analyzed")
    if analyzed_raw == "true":
        analyzed_filter = True
    elif analyzed_raw == "false":
        analyzed_filter = False
    else:
        analyzed_filter = None

    month = request.args.get("month")
    keyword = request.args.get("keyword", "")
    min_rating = request.args.get("min_rating", type=int)
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")
    color_label = request.args.get("color_label", "")

    description_search_raw = request.args.get("description_search")
    if description_search_raw is not None and description_search_raw.strip() == "":
        description_search_raw = None
    description_search = (
        description_search_raw.strip() if description_search_raw is not None else None
    )

    score_perspective = (request.args.get("score_perspective") or "").strip()
    if score_perspective and not _CATALOG_SCORE_PERSPECTIVE_SLUG_RE.match(score_perspective):
        return error_bad_request("invalid score_perspective slug"), None

    sort_raw = (request.args.get("sort_by_score") or "").strip().lower()
    has_sort_by_score = bool(sort_raw)
    if sort_raw and sort_raw not in ("asc", "desc"):
        return error_bad_request("sort_by_score must be asc or desc"), None

    if has_sort_by_score and not score_perspective:
        return error_bad_request("sort_by_score requires score_perspective"), None

    sort_date_raw = (request.args.get("sort_by_date") or "").strip().lower()
    if sort_date_raw and sort_date_raw not in ("newest", "oldest"):
        return error_bad_request("sort_by_date must be newest or oldest"), None

    min_score = None
    if "min_score" in request.args:
        min_score_raw = request.args.get("min_score")
        if min_score_raw is None or str(min_score_raw).strip() == "":
            min_score = None
        else:
            try:
                min_score = int(min_score_raw)
            except (TypeError, ValueError):
                return error_bad_request("min_score must be an integer"), None
            if min_score < 1 or min_score > 10:
                return error_bad_request("min_score must be between 1 and 10"), None

    if min_score is not None and not score_perspective:
        return error_bad_request("min_score requires score_perspective"), None

    dominant_list = [x.strip() for x in request.args.getlist("dominant_colors") if str(x).strip()]
    dominant_colors = dominant_list if dominant_list else None
    mood_list = [x.strip() for x in request.args.getlist("mood_tags") if str(x).strip()]
    mood_tags = mood_list if mood_list else None

    has_rep_raw = request.args.get("has_repetition")
    if has_rep_raw in (None, ""):
        has_repetition = None
    elif str(has_rep_raw).lower() in ("true", "1", "yes"):
        has_repetition = True
    elif str(has_rep_raw).lower() in ("false", "0", "no"):
        has_repetition = False
    else:
        return error_bad_request("has_repetition must be true or false"), None

    limit, offset = _clamp_pagination(
        request.args.get("limit", 50, type=int),
        request.args.get("offset", 0, type=int),
    )

    score_perspective_arg = score_perspective or None
    clip_filter_kwargs: dict[str, Any] = {
        "posted": posted_filter,
        "month": month,
        "keyword": keyword.strip() or None,
        "min_rating": min_rating,
        "date_from": date_from or None,
        "date_to": date_to or None,
        "color_label": color_label.strip() or None,
        "analyzed": analyzed_filter,
        "score_perspective": score_perspective_arg,
        "min_score": min_score,
        "description_search": description_search,
        "dominant_colors": dominant_colors,
        "mood_tags": mood_tags,
        "has_repetition": has_repetition,
    }
    return None, {
        "limit": limit,
        "offset": offset,
        "score_perspective_arg": score_perspective_arg,
        "clip_filter_kwargs": clip_filter_kwargs,
    }


def _effective_catalog_nl_kwargs(filters: CatalogNlFilter) -> dict[str, Any]:
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


def _rows_to_catalog_api_images(rows, score_perspective_arg: str | None) -> list[dict]:
    """Transform ``query_catalog_images`` rows to API image dicts (catalog list + NL search)."""
    score_join_active = bool(score_perspective_arg)
    images: list[dict] = []
    for row in rows:
        out = dict(row)
        desc_summary = out.pop("description_summary", None)
        desc_best = out.pop("description_best_perspective", None)
        desc_perspectives_json = out.pop("description_perspectives_json", None)

        if score_join_active:
            cps = out.pop("catalog_perspective_score", None)
            out["catalog_perspective_score"] = int(cps) if cps is not None else None
            out["catalog_score_perspective"] = score_perspective_arg

        ai_analyzed = desc_summary is not None
        out["ai_analyzed"] = ai_analyzed
        if ai_analyzed:
            out["description_summary"] = desc_summary or ""
            out["description_best_perspective"] = desc_best or ""
            if desc_perspectives_json:
                try:
                    out["description_perspectives"] = json.loads(desc_perspectives_json)
                except (json.JSONDecodeError, TypeError):
                    out["description_perspectives"] = {}
            else:
                out["description_perspectives"] = {}
        else:
            out["description_summary"] = None
            out["description_best_perspective"] = None
            out["description_perspectives"] = None

        rid = out.get("id")
        if rid is not None and str(rid).strip().isdigit():
            out["id"] = int(rid)
        else:
            out["id"] = None

        # STACK-03: stack metadata on catalog list / similar / by-keys (JSON types)
        sid = out.get("stack_id")
        out["stack_id"] = int(sid) if sid is not None else None
        smc = out.get("stack_member_count")
        out["stack_member_count"] = int(smc) if smc is not None else None
        isr = out.get("is_stack_representative")
        out["is_stack_representative"] = bool(isr) if isr is not None else False

        images.append(out)
    return images


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


def _filter_by_date(images, date_folder, date_from, date_to):
    """Filter images by date parameters."""
    if date_folder:
        return [img for img in images if img["instagram_folder"] == date_folder]

    if date_from:
        images = [
            img
            for img in images
            if img["instagram_folder"] and img["instagram_folder"] >= date_from
        ]
    if date_to:
        images = [
            img for img in images if img["instagram_folder"] and img["instagram_folder"] <= date_to
        ]

    return images


@bp.route("/instagram", methods=["GET"])
@with_db
def list_instagram_images(db):
    """List Instagram images with filtering and pagination."""
    try:
        media_items = db.execute("SELECT * FROM instagram_dump_media").fetchall()

        model_lookup = {}
        score_lookup = {}
        try:
            for row in db.execute(
                "SELECT insta_key, model_used, total_score, score FROM matches"
            ).fetchall():
                model_lookup[row["insta_key"]] = row["model_used"]
                raw = row.get("total_score") or row.get("score") or 0
                key = row["insta_key"]
                if raw and (key not in score_lookup or raw > score_lookup[key]):
                    score_lookup[key] = float(raw)
        except sqlite3.OperationalError:
            pass

        desc_lookup = {}
        try:
            for desc in db.execute(
                "SELECT * FROM image_descriptions WHERE image_type = 'instagram'"
            ).fetchall():
                key = (desc.get("image_key"), desc.get("image_type"))
                desc_lookup[key] = _deserialize_description(desc)
        except sqlite3.OperationalError:
            pass

        enriched_images = _enrich_instagram_media(media_items, model_lookup, desc_lookup)

        for img in enriched_images:
            best = score_lookup.get(img.get("key"))
            img["match_score"] = best if best else None

        # Get filter parameters
        date_from = request.args.get("date_from", "")
        date_to = request.args.get("date_to", "")
        date_folder = request.args.get("date_folder", "")

        # Apply filters
        enriched_images = _filter_by_date(enriched_images, date_folder, date_from, date_to)

        sort_date_raw = (request.args.get("sort_by_date") or "").strip().lower()
        if sort_date_raw and sort_date_raw not in ("newest", "oldest"):
            return error_bad_request("sort_by_date must be newest or oldest")
        sort_reverse = sort_date_raw != "oldest"

        # Sort by date folder (month). Tiebreak by key (set by
        # ``_enrich_instagram_media`` from the underlying ``media_key``) so
        # rows within the same month have a deterministic order matching the
        # chosen direction.
        enriched_images.sort(
            key=lambda x: (x.get("instagram_folder") or "", x.get("key") or ""),
            reverse=sort_reverse,
        )

        # Pagination
        limit, offset = _clamp_pagination(
            request.args.get("limit", 50, type=int),
            request.args.get("offset", 0, type=int),
        )
        total = len(enriched_images)

        paginated = enriched_images[offset : offset + limit]

        # Build custom response with 'images' key for backward compatibility
        success_paginated(paginated, total, offset, limit)
        # success_paginated returns (response, status) tuple, need to modify the response
        # Let's construct manually for compatibility
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


@bp.route("/instagram/months", methods=["GET"])
@with_db
def get_instagram_months(db):
    """Get unique months available in Instagram images."""
    try:
        media_items = db.execute("SELECT * FROM instagram_dump_media").fetchall()
        months = set()
        for media in media_items:
            date_folder = media.get("date_folder", "")
            if date_folder:
                months.add(date_folder)
        return jsonify({"months": sorted(months, reverse=True)})
    except Exception as e:
        return error_server_error(str(e))


@bp.route("/instagram/<path:image_key>/thumbnail", methods=["GET"])
@with_db
def get_instagram_thumbnail(db, image_key):
    """Get thumbnail for Instagram image."""
    try:
        media_items = db.execute(
            "SELECT * FROM instagram_dump_media WHERE media_key = ?",
            (image_key,),
        ).fetchall()

        if not media_items:
            return error_not_found("image")

        media = media_items[0]
        local_path = media.get("file_path")

        if not local_path or not os.path.exists(local_path):
            return error_not_found("file")

        allowed_insta = _instagram_thumbnail_roots()
        if not allowed_insta or not _is_path_under_allowed_roots(local_path, allowed_insta):
            return error_not_found("file")

        return send_file(local_path, mimetype="image/jpeg")
    except Exception as e:
        return error_server_error(str(e))


@bp.route("/catalog/<path:image_key>/thumbnail", methods=["GET"])
@with_db
def get_catalog_thumbnail(db, image_key):
    """Get thumbnail for catalog image, creating cache if needed."""
    try:
        images = db.execute(
            "SELECT * FROM images WHERE key = ?",
            (image_key,),
        ).fetchall()

        if not images:
            return error_not_found("image")

        image = images[0]
        allowed_cat = _catalog_thumbnail_roots()

        # Check vision cache first
        cached = db.execute(
            "SELECT compressed_path FROM vision_cache WHERE key = ?",
            (image_key,),
        ).fetchone()
        if cached and cached.get("compressed_path") and os.path.exists(cached["compressed_path"]):
            cp = cached["compressed_path"]
            if not _is_path_under_allowed_roots(cp, allowed_cat):
                return error_not_found("file")
            return send_file(cp, mimetype="image/jpeg")

        # Resolve original path
        from lightroom_tagger.core.path_utils import resolve_catalog_path

        filepath = resolve_catalog_path(image.get("filepath", ""))

        if not filepath or not os.path.exists(filepath):
            return error_not_found("file")

        if not _is_path_under_allowed_roots(filepath, allowed_cat):
            return error_not_found("file")

        # Generate cache on-the-fly for missing thumbnails
        try:
            from lightroom_tagger.core.vision_cache import get_or_create_cached_image

            cached_path = get_or_create_cached_image(db, image_key, filepath)
            if cached_path and os.path.exists(cached_path):
                if not _is_path_under_allowed_roots(cached_path, allowed_cat):
                    return error_not_found("file")
                return send_file(cached_path, mimetype="image/jpeg")
        except Exception as cache_err:
            # If cache generation fails, log but don't break the request
            print(f"Cache generation failed for {image_key}: {cache_err}")

        # Last resort: send original (may not be browser-compatible)
        return send_file(filepath, mimetype="image/jpeg")
    except Exception as e:
        return error_server_error(str(e))


@bp.route("/catalog/months", methods=["GET"])
@with_db
def get_catalog_months(db):
    """Get available year-months from catalog images based on date_taken."""
    try:
        rows = db.execute("""
            SELECT DISTINCT strftime('%Y%m', date_taken) as month
            FROM images
            WHERE date_taken IS NOT NULL
            ORDER BY month DESC
        """).fetchall()
        months = [row["month"] for row in rows if row["month"]]
        return jsonify({"months": months})
    except Exception as e:
        return error_server_error(str(e))


@bp.route("/catalog", methods=["GET"])
@with_db
def list_catalog_images(db):
    """List catalog images with optional filtering and SQL-level pagination."""
    try:
        posted_raw = request.args.get("posted")
        if posted_raw == "true":
            posted_filter = True
        elif posted_raw == "false":
            posted_filter = False
        else:
            posted_filter = None

        analyzed_raw = request.args.get("analyzed")
        if analyzed_raw == "true":
            analyzed_filter = True
        elif analyzed_raw == "false":
            analyzed_filter = False
        else:
            analyzed_filter = None

        month = request.args.get("month")
        keyword = request.args.get("keyword", "")
        min_rating = request.args.get("min_rating", type=int)
        date_from = request.args.get("date_from", "")
        date_to = request.args.get("date_to", "")
        color_label = request.args.get("color_label", "")

        description_search_raw = request.args.get("description_search")
        if description_search_raw is not None and description_search_raw.strip() == "":
            description_search_raw = None
        description_search = (
            description_search_raw.strip() if description_search_raw is not None else None
        )

        score_perspective = (request.args.get("score_perspective") or "").strip()
        if score_perspective and not _CATALOG_SCORE_PERSPECTIVE_SLUG_RE.match(score_perspective):
            return error_bad_request("invalid score_perspective slug")

        sort_raw = (request.args.get("sort_by_score") or "").strip().lower()
        sort_by_score = None
        if sort_raw:
            if sort_raw not in ("asc", "desc"):
                return error_bad_request("sort_by_score must be asc or desc")
            sort_by_score = sort_raw

        if sort_by_score and not score_perspective:
            return error_bad_request("sort_by_score requires score_perspective")

        sort_date_raw = (request.args.get("sort_by_date") or "").strip().lower()
        sort_by_date = None
        if sort_date_raw:
            if sort_date_raw not in ("newest", "oldest"):
                return error_bad_request("sort_by_date must be newest or oldest")
            sort_by_date = sort_date_raw

        min_score = None
        if "min_score" in request.args:
            min_score_raw = request.args.get("min_score")
            if min_score_raw is None or str(min_score_raw).strip() == "":
                min_score = None
            else:
                try:
                    min_score = int(min_score_raw)
                except (TypeError, ValueError):
                    return error_bad_request("min_score must be an integer")
                if min_score < 1 or min_score > 10:
                    return error_bad_request("min_score must be between 1 and 10")

        if min_score is not None and not score_perspective:
            return error_bad_request("min_score requires score_perspective")

        limit, offset = _clamp_pagination(
            request.args.get("limit", 50, type=int),
            request.args.get("offset", 0, type=int),
        )

        score_perspective_arg = score_perspective or None
        try:
            rows, total = query_catalog_images(
                db,
                posted=posted_filter,
                month=month,
                keyword=keyword.strip() or None,
                min_rating=min_rating,
                date_from=date_from or None,
                date_to=date_to or None,
                color_label=color_label.strip() or None,
                analyzed=analyzed_filter,
                score_perspective=score_perspective_arg,
                min_score=min_score,
                sort_by_score=sort_by_score,
                sort_by_date=sort_by_date,
                description_search=description_search,
                limit=limit,
                offset=offset,
            )
        except ValueError as err:
            return error_bad_request(str(err))

        images = _rows_to_catalog_api_images(rows, score_perspective_arg)

        return jsonify(
            {
                "total": total,
                "images": images,
            }
        )
    except Exception as e:
        return error_server_error(str(e))


@bp.route("/catalog/<path:image_key>/similar", methods=["GET"])
@with_db
def get_catalog_image_similar(db, image_key: str):
    """CLIP-only visual neighbors; same catalog row shape + ``similarity`` / ``why_matched``."""
    try:
        if get_image(db, image_key) is None:
            return error_not_found("image")

        err, parsed = _parse_clip_similar_catalog_params()
        if err is not None:
            return err
        assert parsed is not None
        limit = parsed["limit"]
        offset = parsed["offset"]
        score_perspective_arg = parsed["score_perspective_arg"]
        clip_filter_kwargs = parsed["clip_filter_kwargs"]

        try:
            # One KNN pass: fetch up to 500 filtered neighbors, then paginate in-process
            # (``|filtered|`` is bounded by KNN_K_MAX; see SIM-02).
            full_pairs, meta = run_clip_similar_for_seed(
                db,
                image_key,
                limit=500,
                offset=0,
                **clip_filter_kwargs,
            )
        except NoClipEmbeddingError:
            return jsonify({"error": "Visual similarity is unavailable"}), 404
        except ValueError as verr:
            return error_bad_request(str(verr))

        total = len(full_pairs)
        page_pairs = full_pairs[offset : offset + limit]

        keys = [k for k, _dist in page_pairs]
        if not keys:
            return jsonify({"images": [], "total": total, "meta": meta})

        catalog_rows = query_catalog_images_by_keys(
            db, keys, score_perspective=score_perspective_arg
        )
        images = _rows_to_catalog_api_images(catalog_rows, score_perspective_arg)
        dist_by_key = {k: float(d) for k, d in page_pairs}
        for img in images:
            d = dist_by_key.get(img["key"], 0.0)
            sim = max(0.0, min(1.0, 1.0 - d))
            img["similarity"] = sim
            img["why_matched"] = _clip_similarity_why_matched_line(sim)
            img["thumbnail_url"] = f"/api/images/catalog/{img['key']}/thumbnail"

        return jsonify(
            {
                "images": images,
                "total": total,
                "meta": meta,
            }
        )
    except Exception as e:
        return error_server_error(str(e))


@bp.route("/catalog-similarity-groups", methods=["GET"])
@with_db
def list_catalog_similarity_groups(db):
    """Reviewable catalog visual similarity groups materialized by batch jobs."""
    try:
        limit, offset = _clamp_pagination(
            request.args.get("limit", 20, type=int),
            request.args.get("offset", 0, type=int),
        )
        total_row = db.execute(
            "SELECT COUNT(*) AS c FROM catalog_similarity_groups"
        ).fetchone()
        total = int(total_row["c"] if total_row else 0)
        groups = db.execute(
            """
            SELECT group_id, seed_key, candidate_count, best_similarity, job_id, created_at
            FROM catalog_similarity_groups
            ORDER BY created_at DESC, group_id DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()

        items: list[dict] = []
        for group in groups:
            seed_key = str(group["seed_key"])
            seed_rows = query_catalog_images_by_keys(db, [seed_key])
            seed_images = _rows_to_catalog_api_images(seed_rows, None)
            if not seed_images:
                continue
            candidate_rows = db.execute(
                """
                SELECT candidate_key, similarity, rank, why_matched
                FROM catalog_similarity_candidates
                WHERE group_id = ?
                ORDER BY rank ASC, similarity DESC
                """,
                (group["group_id"],),
            ).fetchall()
            candidate_keys = [str(r["candidate_key"]) for r in candidate_rows]
            catalog_rows = query_catalog_images_by_keys(db, candidate_keys)
            candidates = _rows_to_catalog_api_images(catalog_rows, None)
            by_key = {img["key"]: img for img in candidates}
            ordered_candidates = []
            for row in candidate_rows:
                img = by_key.get(str(row["candidate_key"]))
                if not img:
                    continue
                sim = float(row["similarity"] or 0.0)
                img["similarity"] = sim
                img["why_matched"] = row["why_matched"] or _clip_similarity_why_matched_line(sim)
                img["thumbnail_url"] = f"/api/images/catalog/{img['key']}/thumbnail"
                ordered_candidates.append(img)
            seed = seed_images[0]
            seed["thumbnail_url"] = f"/api/images/catalog/{seed['key']}/thumbnail"
            items.append(
                {
                    "group_id": int(group["group_id"]),
                    "seed": seed,
                    "candidates": ordered_candidates,
                    "candidate_count": int(group["candidate_count"] or len(ordered_candidates)),
                    "best_similarity": float(group["best_similarity"] or 0.0),
                    "job_id": group["job_id"],
                    "created_at": group["created_at"],
                }
            )

        return jsonify({"items": items, "total": total})
    except Exception as e:
        return error_server_error(str(e))


# Stack strip order: members by ``image_key`` ASC (stable for UI).
@bp.route("/stacks/<int:stack_id>/members", methods=["GET"])
@with_db
def get_stack_members(db, stack_id: int):
    """Members of a burst stack as catalog-shaped rows (representative + collapsed rules)."""
    try:
        if stack_id < 1:
            return error_not_found("stack")
        found = db.execute(
            "SELECT 1 AS o FROM image_stacks WHERE stack_id = ?",
            (stack_id,),
        ).fetchone()
        if not found:
            return error_not_found("stack")

        mem_rows = db.execute(
            """
            SELECT image_key FROM image_stack_members
            WHERE stack_id = ?
            ORDER BY image_key ASC
            """,
            (stack_id,),
        ).fetchall()
        keys = [str(r["image_key"]) for r in mem_rows]
        if not keys:
            return jsonify({"items": []})

        catalog_rows = _query_catalog_rows_for_stack_member_keys(db, keys, score_perspective=None)
        items = _rows_to_catalog_api_images(catalog_rows, None)
        for it in items:
            it["thumbnail_url"] = f"/api/images/catalog/{it['key']}/thumbnail"
        return jsonify({"items": items})
    except Exception as e:
        return error_server_error(str(e))


@bp.route("/stacks/<int:stack_id>/split-member", methods=["POST"])
@with_db
def post_stack_split_member(db, stack_id: int):
    """Remove a member from a stack (solo image) or dissolve a two-member stack."""
    try:
        if stack_id < 1:
            return error_not_found("stack")
        body = request.get_json(silent=True)
        if not body or not isinstance(body, dict):
            return error_bad_request("JSON body required")
        image_key = body.get("image_key")
        if not image_key or not isinstance(image_key, str):
            return error_bad_request("image_key required")
        with library_write(db):
            result = stack_split_member_out(db, stack_id, image_key.strip())
        return jsonify(result), 200
    except StackMutationError as e:
        if e.status_code == 404:
            return error_not_found("stack")
        if e.status_code >= 500:
            return error_server_error(str(e))
        return error_bad_request(str(e))
    except Exception as e:
        return error_server_error(str(e))


@bp.route("/stacks/<int:target_stack_id>/merge", methods=["POST"])
@with_db
def post_stack_merge(db, target_stack_id: int):
    """Merge *source_stack_id* into *target_stack_id* (all members moved, source row deleted)."""
    try:
        if target_stack_id < 1:
            return error_not_found("stack")
        body = request.get_json(silent=True)
        if not body or not isinstance(body, dict):
            return error_bad_request("JSON body required")
        raw_source = body.get("source_stack_id")
        if raw_source is None:
            return error_bad_request("source_stack_id required")
        try:
            source_stack_id = int(raw_source)
        except (TypeError, ValueError):
            return error_bad_request("source_stack_id must be an integer")
        with library_write(db):
            result = stack_merge_into(db, target_stack_id, source_stack_id)
        return jsonify(result), 200
    except StackMutationError as e:
        if e.status_code == 404:
            return error_not_found("stack")
        if e.status_code >= 500:
            return error_server_error(str(e))
        return error_bad_request(str(e))
    except Exception as e:
        return error_server_error(str(e))


@bp.route("/stacks/<int:stack_id>/representative", methods=["POST"])
@with_db
def post_stack_representative(db, stack_id: int):
    """Change which catalog key is the stack representative (must be a current member)."""
    try:
        if stack_id < 1:
            return error_not_found("stack")
        body = request.get_json(silent=True)
        if not body or not isinstance(body, dict):
            return error_bad_request("JSON body required")
        image_key = body.get("image_key")
        if not image_key or not isinstance(image_key, str):
            return error_bad_request("image_key required")
        with library_write(db):
            result = stack_set_representative(db, stack_id, image_key.strip())
        return jsonify(result), 200
    except StackMutationError as e:
        if e.status_code == 404:
            return error_not_found("stack")
        if e.status_code >= 500:
            return error_server_error(str(e))
        return error_bad_request(str(e))
    except Exception as e:
        return error_server_error(str(e))


@bp.route("/nl-search", methods=["POST"])
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


@bp.route("/semantic-search", methods=["POST"])
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


@bp.route("/chat-search", methods=["POST"])
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

        slug_rows = db.execute(
            "SELECT DISTINCT perspective_slug FROM image_scores "
            "WHERE is_current = 1 ORDER BY perspective_slug"
        ).fetchall()
        available_slugs = [str(r["perspective_slug"]) for r in slug_rows]

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


@bp.route("/dump-media", methods=["GET"])
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
            media = db.execute("SELECT * FROM instagram_dump_media WHERE processed = 1").fetchall()
        elif processed == "false":
            media = db.execute("SELECT * FROM instagram_dump_media WHERE processed = 0").fetchall()
        elif matched == "true":
            media = db.execute(
                "SELECT * FROM instagram_dump_media WHERE matched_catalog_key IS NOT NULL"
            ).fetchall()
        elif matched == "false":
            media = db.execute(
                "SELECT * FROM instagram_dump_media WHERE matched_catalog_key IS NULL"
            ).fetchall()
        else:
            media = db.execute("SELECT * FROM instagram_dump_media").fetchall()

        total = len(media)
        paginated = media[offset : offset + limit]

        return jsonify(
            {
                "total": total,
                "media": paginated,
            }
        )
    except Exception as e:
        return error_server_error(str(e))


@bp.route("/matches", methods=["GET"])
@with_db
def list_matches(db):
    """List matches grouped by Instagram image."""
    try:
        matches = db.execute(
            "SELECT * FROM matches ORDER BY insta_key, COALESCE(rank, 1), total_score DESC"
        ).fetchall()

        # Build lookup tables for images (avoid N+1 queries)
        instagram_lookup = {}
        for img in db.execute("SELECT * FROM instagram_images").fetchall():
            instagram_lookup[img.get("key")] = img

        catalog_lookup = {}
        for img in db.execute("SELECT * FROM images").fetchall():
            catalog_lookup[img.get("key")] = img

        desc_lookup = {}
        try:
            for desc in db.execute("SELECT * FROM image_descriptions").fetchall():
                key = (desc.get("image_key"), desc.get("image_type"))
                desc_lookup[key] = _deserialize_description(desc)
        except sqlite3.OperationalError:
            pass

        model_lookup = {}
        try:
            for row in db.execute("SELECT insta_key, model_used FROM matches").fetchall():
                model_lookup[row["insta_key"]] = row["model_used"]
        except sqlite3.OperationalError:
            pass

        insta_keys = {m.get("insta_key") for m in matches if m.get("insta_key")}
        dump_instagram_by_key = {}
        if insta_keys:
            keys_list = list(insta_keys)
            chunk_size = 500
            dump_rows = []
            for i in range(0, len(keys_list), chunk_size):
                chunk = keys_list[i : i + chunk_size]
                placeholders = ",".join("?" * len(chunk))
                dump_rows.extend(
                    db.execute(
                        f"SELECT * FROM instagram_dump_media WHERE media_key IN ({placeholders})",
                        chunk,
                    ).fetchall()
                )
            enriched_dump_list = _enrich_instagram_media(dump_rows, model_lookup, desc_lookup)
            dump_instagram_by_key = {row["key"]: row for row in enriched_dump_list}

        groups = OrderedDict()
        all_enriched = []

        for match in matches:
            insta_key = match.get("insta_key")
            catalog_key = match.get("catalog_key")

            enriched = {
                **match,
                "instagram_key": insta_key,
                "score": match.get("total_score", 0),
            }

            resolved_insta = None
            if insta_key:
                resolved_insta = instagram_lookup.get(insta_key) or dump_instagram_by_key.get(
                    insta_key
                )
            if resolved_insta:
                enriched["instagram_image"] = resolved_insta
            if catalog_key and catalog_key in catalog_lookup:
                enriched["catalog_image"] = catalog_lookup[catalog_key]

            enriched["catalog_description"] = (
                desc_lookup.get((catalog_key, "catalog")) if catalog_key else None
            )
            enriched["insta_description"] = (
                desc_lookup.get((insta_key, "instagram")) if insta_key else None
            )

            groups.setdefault(insta_key, []).append(enriched)
            all_enriched.append(enriched)

        match_groups = []
        for insta_key, candidates in groups.items():
            best = max((c.get("score") or 0) for c in candidates) if candidates else 0
            match_groups.append(
                {
                    "instagram_key": insta_key,
                    "instagram_image": instagram_lookup.get(insta_key)
                    or dump_instagram_by_key.get(insta_key),
                    "candidates": candidates,
                    "best_score": best,
                    "candidate_count": len(candidates),
                    "has_validated": any(c.get("validated_at") for c in candidates),
                    "all_rejected": False if len(candidates) > 0 else True,
                }
            )

        insta_keys_with_matches = frozenset(groups.keys())

        try:
            rejected_inst_keys = [
                row["insta_key"]
                for row in db.execute("SELECT DISTINCT insta_key FROM rejected_matches").fetchall()
                if row.get("insta_key")
            ]
        except sqlite3.OperationalError:
            rejected_inst_keys = []

        tombstone_only_keys = []
        for ik in rejected_inst_keys:
            if ik in insta_keys_with_matches:
                continue
            still_has = db.execute(
                "SELECT 1 FROM matches WHERE insta_key = ? LIMIT 1", (ik,)
            ).fetchone()
            if not still_has:
                tombstone_only_keys.append(ik)

        if tombstone_only_keys:
            keys_to_enrich = [
                k
                for k in tombstone_only_keys
                if k not in dump_instagram_by_key and k not in instagram_lookup
            ]
            if keys_to_enrich:
                chunk_size = 500
                extra_dump_rows = []
                for i in range(0, len(keys_to_enrich), chunk_size):
                    chunk = keys_to_enrich[i : i + chunk_size]
                    placeholders = ",".join("?" * len(chunk))
                    extra_dump_rows.extend(
                        db.execute(
                            f"SELECT * FROM instagram_dump_media WHERE media_key IN ({placeholders})",
                            chunk,
                        ).fetchall()
                    )
                for row in _enrich_instagram_media(extra_dump_rows, model_lookup, desc_lookup):
                    dump_instagram_by_key[row["key"]] = row

        for ik in tombstone_only_keys:
            match_groups.append(
                {
                    "instagram_key": ik,
                    "instagram_image": instagram_lookup.get(ik) or dump_instagram_by_key.get(ik),
                    "candidates": [],
                    "best_score": 0.0,
                    "candidate_count": 0,
                    "has_validated": False,
                    "all_rejected": True,
                }
            )

        def _parse_ts(ts):
            if not ts:
                return None
            s = str(ts).replace("Z", "+00:00")
            try:
                return datetime.fromisoformat(s).timestamp()
            except ValueError:
                return None

        def _photo_ts_float(group_dict):
            ig = group_dict.get("instagram_image") or {}
            if isinstance(ig, dict):
                ts = _parse_ts(ig.get("created_at"))
                if ts is not None:
                    return ts
            best_cat_ts = None
            for c in group_dict.get("candidates") or []:
                cat = c.get("catalog_image") or {}
                dt = cat.get("date_taken")
                t = _parse_ts(dt)
                if t is not None and (best_cat_ts is None or t > best_cat_ts):
                    best_cat_ts = t
            return best_cat_ts

        sort_date_raw = (request.args.get("sort_by_date") or "").strip().lower()
        if sort_date_raw and sort_date_raw not in ("newest", "oldest"):
            return error_bad_request("sort_by_date must be newest or oldest")
        # Default behaviour (no param): newest first within each bucket.
        oldest_first = sort_date_raw == "oldest"

        def _match_group_sort_key(g):
            # Bucket 0 = actionable (unvalidated, not all-rejected tombstone); 1 = reviewed bucket.
            sort_bucket = 1 if (g.get("all_rejected") or g.get("has_validated")) else 0
            photo_ts = _photo_ts_float(g)
            if photo_ts is None:
                return (sort_bucket, 1, 0.0)
            # Invert when sorting ascending within the bucket.
            return (sort_bucket, 0, photo_ts if oldest_first else -photo_ts)

        match_groups.sort(key=_match_group_sort_key)

        limit, offset = _clamp_pagination(
            request.args.get("limit", 50, type=int),
            request.args.get("offset", 0, type=int),
        )
        paginated_groups = match_groups[offset : offset + limit]
        paginated_matches = []
        for grp in paginated_groups:
            paginated_matches.extend(grp["candidates"])

        total_groups = len(match_groups)
        total_matches = len(all_enriched)

        return jsonify(
            {
                "total": total_groups,
                "total_groups": total_groups,
                "total_matches": total_matches,
                "match_groups": paginated_groups,
                "matches": paginated_matches,
            }
        )
    except Exception as e:
        return error_server_error(str(e))


@bp.route("/matches/<path:catalog_key>/<path:insta_key>/validate", methods=["PATCH"])
@with_db
def toggle_match_validation(db, catalog_key, insta_key):
    """Toggle human validation on a match."""
    try:
        match_row = db.execute(
            "SELECT validated_at FROM matches WHERE catalog_key = ? AND insta_key = ?",
            (catalog_key, insta_key),
        ).fetchone()
        if not match_row:
            return error_not_found("match")

        if match_row["validated_at"]:
            unvalidate_match(db, catalog_key, insta_key)
            return jsonify({"validated": False})
        else:
            validate_match(db, catalog_key, insta_key)
            return jsonify({"validated": True})
    except Exception as e:
        return error_server_error(str(e))


@bp.route("/matches/<path:catalog_key>/<path:insta_key>/reject", methods=["PATCH"])
@with_db
def reject_match_endpoint(db, catalog_key, insta_key):
    """Reject a match: delete it and blocklist the pair."""
    try:
        match_row = db.execute(
            "SELECT validated_at FROM matches WHERE catalog_key = ? AND insta_key = ?",
            (catalog_key, insta_key),
        ).fetchone()
        if not match_row:
            return error_not_found("match")
        if match_row["validated_at"]:
            return (
                jsonify(
                    {
                        "error": "Match has been validated; un-validate it before rejecting.",
                        "rejected": False,
                    }
                ),
                409,
            )

        reject_match(db, catalog_key, insta_key)
        return jsonify({"rejected": True})
    except Exception as e:
        return error_server_error(str(e))


_DETAIL_IMAGE_TYPES = ("catalog", "instagram")


def _build_catalog_detail(db, image_key, score_perspective):
    """Build the catalog detail payload; returns (payload_dict, 404_flag)."""
    row = get_image(db, image_key)
    if not row:
        return None, True

    out = dict(row)
    out["image_type"] = "catalog"

    desc_row = get_image_description(db, image_key)
    if desc_row and desc_row.get("image_type") == "catalog":
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

    # Identity aggregate (may be None when no scores yet).
    identity = compute_single_image_aggregate_scores(db, image_key)
    if identity is not None:
        out["identity_aggregate_score"] = identity["aggregate_score"]
        out["identity_perspectives_covered"] = identity["perspectives_covered"]
        out["identity_eligible"] = identity["eligible"]
        out["identity_per_perspective"] = identity["per_perspective"]
    else:
        out["identity_aggregate_score"] = None
        out["identity_perspectives_covered"] = 0
        out["identity_eligible"] = False
        out["identity_per_perspective"] = []

    # Per-slug catalog score (same semantics as list endpoint).
    if score_perspective:
        score_row = db.execute(
            "SELECT score FROM image_scores "
            "WHERE image_key = ? AND image_type = 'catalog' "
            "AND perspective_slug = ? AND is_current = 1",
            (image_key, score_perspective),
        ).fetchone()
        out["catalog_perspective_score"] = int(score_row["score"]) if score_row else None
        out["catalog_score_perspective"] = score_perspective
    else:
        out["catalog_perspective_score"] = None
        out["catalog_score_perspective"] = None

    # Every persisted current score perspective for this image (drives modal picker).
    slug_rows = db.execute(
        "SELECT DISTINCT perspective_slug FROM image_scores "
        "WHERE image_key = ? AND image_type = 'catalog' AND is_current = 1 "
        "ORDER BY perspective_slug",
        (image_key,),
    ).fetchall()
    out["available_score_perspectives"] = [str(r["perspective_slug"]) for r in slug_rows]

    rid = out.get("id")
    if rid is not None and str(rid).strip().isdigit():
        out["id"] = int(rid)
    else:
        out["id"] = None

    out.update(catalog_image_stack_row_fields(db, image_key))

    return out, False


def _build_instagram_detail(db, image_key):
    """Build the instagram detail payload; returns (payload_dict, 404_flag)."""
    row = get_instagram_dump_media(db, image_key)
    if not row:
        return None, True

    out = dict(row)
    out["image_type"] = "instagram"
    # Normalize to the same ``key`` alias catalog uses.
    out["key"] = row.get("media_key") or image_key
    # Parity with ``_enrich_instagram_media`` so the detail modal renders
    # the same folder / source fields the list tiles would have.
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

    # Instagram rows have no identity scoring (catalog-only by design).
    out["identity_aggregate_score"] = None
    out["identity_perspectives_covered"] = 0
    out["identity_eligible"] = False
    out["identity_per_perspective"] = []
    out["catalog_perspective_score"] = None
    out["catalog_score_perspective"] = None
    out["available_score_perspectives"] = []

    return out, False


@bp.route("/<string:image_type>/<path:image_key>", methods=["GET"])
@with_db
def get_image_detail(db, image_type, image_key):
    """Single-image detail payload — used by the consolidated image-view modal."""
    if image_type not in _DETAIL_IMAGE_TYPES:
        return error_bad_request(f"invalid image_type; expected one of {_DETAIL_IMAGE_TYPES}")

    score_perspective = (request.args.get("score_perspective") or "").strip()
    if score_perspective and not _CATALOG_SCORE_PERSPECTIVE_SLUG_RE.match(score_perspective):
        return error_bad_request("invalid score_perspective slug")
    if score_perspective and image_type != "catalog":
        return error_bad_request("score_perspective is only valid for catalog images")

    try:
        if image_type == "catalog":
            payload, not_found = _build_catalog_detail(db, image_key, score_perspective or None)
        else:
            payload, not_found = _build_instagram_detail(db, image_key)
        if not_found:
            return error_not_found("image")
        return jsonify(payload)
    except Exception as e:
        return error_server_error(str(e))
