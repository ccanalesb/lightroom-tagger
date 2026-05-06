"""Burst stack members and mutations."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from utils.db import with_db
from utils.responses import error_bad_request, error_not_found, error_server_error

from lightroom_tagger.core.database import (
    StackMutationError,
    library_write,
    stack_merge_into,
    stack_set_representative,
    stack_split_member_out,
)

from .catalog import _query_catalog_rows_for_stack_member_keys, _rows_to_catalog_api_images

stacks_bp = Blueprint("images_stacks", __name__)


@stacks_bp.route("/stacks/<int:stack_id>/members", methods=["GET"])
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


@stacks_bp.route("/stacks/<int:stack_id>/split-member", methods=["POST"])
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


@stacks_bp.route("/stacks/<int:target_stack_id>/merge", methods=["POST"])
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


@stacks_bp.route("/stacks/<int:stack_id>/representative", methods=["POST"])
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


__all__ = ("stacks_bp",)
