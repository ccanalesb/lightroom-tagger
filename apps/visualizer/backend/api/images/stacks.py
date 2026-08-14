"""Burst stack members and mutations."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from spectree import Response
from utils.db import with_db
from utils.responses import error_bad_request, error_not_found, error_server_error

from api.openapi import spec
from api.schemas.jobs import ErrorBody
from api.schemas.stacks import (
    StackMembersResponse,
    StackMergeRequest,
    StackMergeResponse,
    StackRepresentativeRequest,
    StackRepresentativeResponse,
    StackSplitMemberRequest,
    StackSplitMemberResponse,
    StackSuggestionAcceptResponse,
    StackSuggestionPairRequest,
    StackSuggestionRejectResponse,
    StackSuggestionsResponse,
)
from lightroom_tagger.core.database import (
    StackMutationError,
    library_write,
    list_pending_stack_suggestions,
    list_stack_member_keys,
    query_catalog_images_by_keys,
    reject_catalog_similarity_pair,
    stack_accept_suggestion_pair,
    stack_exists,
    stack_merge_into,
    stack_set_representative,
    stack_split_member_out,
)

from .catalog import _query_catalog_rows_for_stack_member_keys, _rows_to_catalog_api_images

stacks_bp = Blueprint("images_stacks", __name__)


def _clamp_pagination(limit: int, offset: int) -> tuple[int, int]:
    return max(1, min(int(limit), 100)), max(0, int(offset))


@stacks_bp.route("/suggestions", methods=["GET"])
@with_db
@spec.validate(
    resp=Response(HTTP_200=StackSuggestionsResponse),
    tags=['images-stacks'],
)
def list_stack_suggestions(db):
    """Pending catalog-similarity pairs ranked as stacks to confirm."""
    try:
        limit, offset = _clamp_pagination(
            request.args.get("limit", 20, type=int),
            request.args.get("offset", 0, type=int),
        )
        rows, total = list_pending_stack_suggestions(db, limit=limit, offset=offset)
        items: list[dict] = []
        for row in rows:
            keys = [str(row["seed_key"]), str(row["candidate_key"])]
            catalog_rows = query_catalog_images_by_keys(db, keys)
            images = _rows_to_catalog_api_images(catalog_rows)
            by_key = {img["key"]: img for img in images}
            image_a = by_key.get(str(row["seed_key"]))
            image_b = by_key.get(str(row["candidate_key"]))
            if not image_a or not image_b:
                continue
            image_a["thumbnail_url"] = f"/api/images/catalog/{image_a['key']}/thumbnail"
            image_b["thumbnail_url"] = f"/api/images/catalog/{image_b['key']}/thumbnail"
            gap = row.get("time_gap_seconds")
            items.append(
                {
                    "group_id": int(row["group_id"]),
                    "image_a": image_a,
                    "image_b": image_b,
                    "similarity": float(row["similarity"] or 0.0),
                    "why_matched": str(row["why_matched"] or ""),
                    "time_gap_seconds": int(gap) if gap is not None else None,
                }
            )
        return jsonify({"items": items, "total": total})
    except Exception as e:
        return error_server_error(str(e))


@stacks_bp.route("/suggestions/accept", methods=["POST"])
@with_db
@spec.validate(
    json=StackSuggestionPairRequest,
    resp=Response(
        HTTP_200=StackSuggestionAcceptResponse,
        HTTP_400=ErrorBody,
        HTTP_404=ErrorBody,
    ),
    tags=['images-stacks'],
)
def post_stack_suggestion_accept(db):
    """Accept a suggested pair by creating, extending, or merging stacks."""
    try:
        body = request.get_json(silent=True)
        if not body or not isinstance(body, dict):
            return error_bad_request("JSON body required")
        key_a = body.get("image_key_a")
        key_b = body.get("image_key_b")
        if not key_a or not isinstance(key_a, str) or not key_b or not isinstance(key_b, str):
            return error_bad_request("image_key_a and image_key_b required")
        with library_write(db):
            result = stack_accept_suggestion_pair(db, key_a.strip(), key_b.strip())
        # stack_accept_suggestion_pair may merge two stacks and return merged_stack_id;
        # the accept contract is stack-only (extra='forbid'), so shape to {stack}.
        return jsonify({"stack": result["stack"]}), 200
    except StackMutationError as e:
        if e.status_code == 404:
            return error_not_found("image")
        if e.status_code >= 500:
            return error_server_error(str(e))
        return error_bad_request(str(e))
    except Exception as e:
        return error_server_error(str(e))


@stacks_bp.route("/suggestions/reject", methods=["POST"])
@with_db
@spec.validate(
    json=StackSuggestionPairRequest,
    resp=Response(HTTP_200=StackSuggestionRejectResponse, HTTP_400=ErrorBody),
    tags=['images-stacks'],
)
def post_stack_suggestion_reject(db):
    """Reject a suggested pair so it does not return on the next batch run."""
    try:
        body = request.get_json(silent=True)
        if not body or not isinstance(body, dict):
            return error_bad_request("JSON body required")
        key_a = body.get("image_key_a")
        key_b = body.get("image_key_b")
        if not key_a or not isinstance(key_a, str) or not key_b or not isinstance(key_b, str):
            return error_bad_request("image_key_a and image_key_b required")
        a = key_a.strip()
        b = key_b.strip()
        if a == b:
            return error_bad_request("image_key_a and image_key_b must differ")
        with library_write(db):
            reject_catalog_similarity_pair(db, a, b)
        return jsonify({"image_key_a": a, "image_key_b": b, "rejected": True}), 200
    except ValueError as e:
        return error_bad_request(str(e))
    except Exception as e:
        return error_server_error(str(e))


@stacks_bp.route("/<int:stack_id>/members", methods=["GET"])
@with_db
@spec.validate(
    resp=Response(HTTP_200=StackMembersResponse, HTTP_404=ErrorBody),
    tags=['images-stacks'],
)
def get_stack_members(db, stack_id: int):
    """Members of a burst stack as catalog-shaped rows (representative + collapsed rules)."""
    try:
        if stack_id < 1:
            return error_not_found("stack")
        if not stack_exists(db, stack_id):
            return error_not_found("stack")

        keys = list_stack_member_keys(db, stack_id)
        if not keys:
            return jsonify({"items": []})

        catalog_rows = _query_catalog_rows_for_stack_member_keys(db, keys, score_perspective=None)
        items = _rows_to_catalog_api_images(catalog_rows)
        for it in items:
            it["thumbnail_url"] = f"/api/images/catalog/{it['key']}/thumbnail"
        return jsonify({"items": items})
    except Exception as e:
        return error_server_error(str(e))


@stacks_bp.route("/<int:stack_id>/split-member", methods=["POST"])
@with_db
@spec.validate(
    json=StackSplitMemberRequest,
    resp=Response(
        HTTP_200=StackSplitMemberResponse,
        HTTP_400=ErrorBody,
        HTTP_404=ErrorBody,
    ),
    tags=['images-stacks'],
)
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


@stacks_bp.route("/<int:target_stack_id>/merge", methods=["POST"])
@with_db
@spec.validate(
    json=StackMergeRequest,
    resp=Response(
        HTTP_200=StackMergeResponse,
        HTTP_400=ErrorBody,
        HTTP_404=ErrorBody,
    ),
    tags=['images-stacks'],
)
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


@stacks_bp.route("/<int:stack_id>/representative", methods=["POST"])
@with_db
@spec.validate(
    json=StackRepresentativeRequest,
    resp=Response(
        HTTP_200=StackRepresentativeResponse,
        HTTP_400=ErrorBody,
        HTTP_404=ErrorBody,
    ),
    tags=['images-stacks'],
)
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
