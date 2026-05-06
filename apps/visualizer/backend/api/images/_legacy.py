import json
import os
import sqlite3
from collections import OrderedDict
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
    catalog_nl_filter_to_query_kwargs,
    parse_catalog_nl_filter_from_llm,
)
from lightroom_tagger.core.clip_similarity import (
    NoClipEmbeddingError,
    list_pin_similarity_candidate_keys,
)
from lightroom_tagger.core.database import (
    build_description_fts_query,
    get_image_description,
    get_instagram_dump_media,
    query_catalog_images,
    query_catalog_images_by_keys,
    reject_match,
    unvalidate_match,
    validate_match,
)
from lightroom_tagger.core.embedding_service import embed_query_to_vec_blob
from lightroom_tagger.core.provider_errors import ModelUnavailableError
from lightroom_tagger.core.provider_registry import ProviderRegistry
from lightroom_tagger.core.semantic_search import run_semantic_hybrid_search
from lightroom_tagger.core.structured_output import StructuredOutputError

from .catalog import (
    _CATALOG_SCORE_PERSPECTIVE_SLUG_RE,
    _effective_catalog_nl_kwargs,
    _rows_to_catalog_api_images,
)
from .common import (
    _clamp_pagination,
    _extract_source_folder,
    _filter_by_date,
    _instagram_thumbnail_roots,
    _is_path_under_allowed_roots,
)

legacy_bp = Blueprint("images_legacy", __name__)

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


@legacy_bp.route("/instagram", methods=["GET"])
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


@legacy_bp.route("/instagram/months", methods=["GET"])
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


@legacy_bp.route("/instagram/<path:image_key>/thumbnail", methods=["GET"])
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




@legacy_bp.route("/nl-search", methods=["POST"])
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


@legacy_bp.route("/semantic-search", methods=["POST"])
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


@legacy_bp.route("/chat-search", methods=["POST"])
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


@legacy_bp.route("/dump-media", methods=["GET"])
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


@legacy_bp.route("/matches", methods=["GET"])
@with_db
def list_matches(db):
    """List matches grouped by Instagram image.

    Filters out **conflicting candidates**: a row whose ``catalog_key`` is
    already validated against a *different* ``insta_key`` is dropped from the
    response. The row stays in the ``matches`` table (preserved for downstream
    model fine-tuning), but the UI never sees it because a single Lightroom
    photo can only be claimed by one Instagram post.
    """
    try:
        matches = db.execute(
            "SELECT * FROM matches ORDER BY insta_key, COALESCE(rank, 1), total_score DESC"
        ).fetchall()

        claimed_catalog_keys = {
            row["catalog_key"]
            for row in db.execute(
                "SELECT DISTINCT catalog_key FROM matches "
                "WHERE validated_at IS NOT NULL AND catalog_key IS NOT NULL"
            ).fetchall()
            if row.get("catalog_key")
        }

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

            # Conflict filter: catalog already validated against a different
            # insta_key → hide this row from the UI. The validated row itself
            # has ``validated_at IS NOT NULL`` so it survives.
            if (
                catalog_key
                and catalog_key in claimed_catalog_keys
                and not match.get("validated_at")
            ):
                continue

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


@legacy_bp.route("/matches/<path:catalog_key>/<path:insta_key>/validate", methods=["PATCH"])
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


@legacy_bp.route("/matches/<path:catalog_key>/<path:insta_key>/reject", methods=["PATCH"])
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
