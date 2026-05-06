"""Catalog list, thumbnails, CLIP similar, similarity groups, and image detail (catalog branch)."""

from __future__ import annotations

import json
import os
import re
import sqlite3
from collections.abc import Sequence
from typing import Any

from flask import Blueprint, jsonify, request, send_file
from utils.db import with_db
from utils.responses import error_bad_request, error_not_found, error_server_error

from lightroom_tagger.core.catalog_nl_filter import (
    CatalogNlFilter,
    catalog_nl_filter_to_query_kwargs,
)
from lightroom_tagger.core.clip_similarity import NoClipEmbeddingError, run_clip_similar_for_seed
from lightroom_tagger.core.database import (
    _deserialize_row,
    catalog_image_stack_row_fields,
    get_image,
    get_image_description,
    query_catalog_images,
    query_catalog_images_by_keys,
)
from lightroom_tagger.core.identity_service import compute_single_image_aggregate_scores

from .common import _catalog_thumbnail_roots, _clamp_pagination, _is_path_under_allowed_roots

catalog_bp = Blueprint("images_catalog", __name__)

_CATALOG_SCORE_PERSPECTIVE_SLUG_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

_DETAIL_IMAGE_TYPES = ("catalog", "instagram")


def _clip_similarity_why_matched_line(similarity: float) -> str:
    pct = max(0, min(100, int(round(float(similarity) * 100.0))))
    return f"Visual match ({pct}%)"


def _query_catalog_rows_for_stack_member_keys(
    db: sqlite3.Connection,
    keys: Sequence[str],
    *,
    score_perspective: str | None = None,
) -> list[dict]:
    """Catalog-shaped rows for *keys* in input order, **without** primary-grid stack collapse."""
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
    """Parse query params for GET /catalog/.../similar."""
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

        sid = out.get("stack_id")
        out["stack_id"] = int(sid) if sid is not None else None
        smc = out.get("stack_member_count")
        out["stack_member_count"] = int(smc) if smc is not None else None
        isr = out.get("is_stack_representative")
        out["is_stack_representative"] = bool(isr) if isr is not None else False

        images.append(out)
    return images


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


@catalog_bp.route("/<path:image_key>/thumbnail", methods=["GET"])
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

        cached = db.execute(
            "SELECT compressed_path FROM vision_cache WHERE key = ?",
            (image_key,),
        ).fetchone()
        if cached and cached.get("compressed_path") and os.path.exists(cached["compressed_path"]):
            cp = cached["compressed_path"]
            if not _is_path_under_allowed_roots(cp, allowed_cat):
                return error_not_found("file")
            return send_file(cp, mimetype="image/jpeg")

        from lightroom_tagger.core.path_utils import resolve_catalog_path

        filepath = resolve_catalog_path(image.get("filepath", ""))

        if not filepath or not os.path.exists(filepath):
            return error_not_found("file")

        if not _is_path_under_allowed_roots(filepath, allowed_cat):
            return error_not_found("file")

        try:
            from lightroom_tagger.core.vision_cache import get_or_create_cached_image

            cached_path = get_or_create_cached_image(db, image_key, filepath)
            if cached_path and os.path.exists(cached_path):
                if not _is_path_under_allowed_roots(cached_path, allowed_cat):
                    return error_not_found("file")
                return send_file(cached_path, mimetype="image/jpeg")
        except Exception as cache_err:
            print(f"Cache generation failed for {image_key}: {cache_err}")

        return send_file(filepath, mimetype="image/jpeg")
    except Exception as e:
        return error_server_error(str(e))


@catalog_bp.route("/months", methods=["GET"])
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


@catalog_bp.route("", methods=["GET"])
@catalog_bp.route("/", methods=["GET"])
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


@catalog_bp.route("/<path:image_key>/similar", methods=["GET"])
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


@catalog_bp.route("/<path:image_key>", methods=["GET"])
@with_db
def get_catalog_image_detail(db, image_key):
    """Single catalog image detail for the consolidated image-view modal."""
    score_perspective = (request.args.get("score_perspective") or "").strip()
    if score_perspective and not _CATALOG_SCORE_PERSPECTIVE_SLUG_RE.match(score_perspective):
        return error_bad_request("invalid score_perspective slug")

    try:
        payload, not_found = _build_catalog_detail(db, image_key, score_perspective or None)
        if not_found:
            return error_not_found("image")
        return jsonify(payload)
    except Exception as e:
        return error_server_error(str(e))


__all__ = (
    "catalog_bp",
    "_DETAIL_IMAGE_TYPES",
    "_CATALOG_SCORE_PERSPECTIVE_SLUG_RE",
    "_clip_similarity_why_matched_line",
    "_effective_catalog_nl_kwargs",
    "_parse_clip_similar_catalog_params",
    "_query_catalog_rows_for_stack_member_keys",
    "_rows_to_catalog_api_images",
    "list_catalog_similarity_groups",
)
