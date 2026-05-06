"""Catalog ↔ Instagram match endpoints."""

from __future__ import annotations

import sqlite3
from collections import OrderedDict
from datetime import datetime

from flask import Blueprint, jsonify, request

from utils.db import with_db
from utils.responses import error_bad_request, error_not_found, error_server_error

from lightroom_tagger.core.database import (
    reject_match,
    unvalidate_match,
    validate_match,
)

from .common import _clamp_pagination
from .instagram import _deserialize_description, _enrich_instagram_media

matches_bp = Blueprint("images_matches", __name__)


@matches_bp.route("/matches", methods=["GET"])
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


@matches_bp.route("/matches/<path:catalog_key>/<path:insta_key>/validate", methods=["PATCH"])
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


@matches_bp.route("/matches/<path:catalog_key>/<path:insta_key>/reject", methods=["PATCH"])
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


__all__ = ("matches_bp",)
