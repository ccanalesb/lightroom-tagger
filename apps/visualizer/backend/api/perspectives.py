# image_scores JSON field keys (library DB)
# image_key, image_type, perspective_slug, score, rationale, model_used, prompt_version, scored_at, is_current, repaired_from_malformed
"""REST API for the library ``perspectives`` registry.

List responses (``GET /api/perspectives``) expose these fields per row for UIs and
future catalog consumers: ``id``, ``slug``, ``display_name``, ``description``,
``active``, ``source_filename``, ``updated_at`` (no ``prompt_markdown`` on the list).

``image_scores`` rows (same library DB) use the JSON-friendly keys listed in the
header comment above when exposing score history over HTTP in later phases.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from flask import Blueprint, jsonify, request
from utils.db import with_db
from utils.responses import error_bad_request, error_not_found

from lightroom_tagger.core.database import (
    delete_perspective,
    get_perspective_by_slug,
    insert_perspective,
    list_perspectives,
    update_perspective,
)

bp = Blueprint("perspectives", __name__)

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

_SLUG_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_SOURCE_FILENAME_RE = re.compile(r"^[a-zA-Z0-9_\-]+\.md$")
_MAX_PROMPT_MARKDOWN_BYTES = 256 * 1024


def _prompt_too_large(prompt_markdown: str) -> bool:
    return len(prompt_markdown.encode("utf-8")) > _MAX_PROMPT_MARKDOWN_BYTES


def _row_list_item(row: dict) -> dict:
    return {
        "id": row["id"],
        "slug": row["slug"],
        "display_name": row["display_name"],
        "description": row["description"],
        "active": bool(row["active"]),
        "source_filename": row.get("source_filename"),
        "updated_at": row.get("updated_at"),
    }


def _row_detail(row: dict) -> dict:
    out = _row_list_item(row)
    out["prompt_markdown"] = row["prompt_markdown"]
    out["created_at"] = row.get("created_at")
    return out


@bp.route("/", methods=["GET"])
@with_db
def list_perspectives_route(db):
    """List perspectives; optional ``active_only=true`` query."""
    active_only = request.args.get("active_only", "").lower() == "true"
    rows = list_perspectives(db, active_only=active_only)
    return jsonify([_row_list_item(r) for r in rows])


@bp.route("/<slug>", methods=["GET"])
@with_db
def get_perspective_route(db, slug: str):
    row = get_perspective_by_slug(db, slug)
    if not row:
        return error_not_found("resource")
    return jsonify(_row_detail(row))


@bp.route("/", methods=["POST"])
@with_db
def create_perspective_route(db):
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return error_bad_request("JSON body required")

    slug = data.get("slug")
    display_name = data.get("display_name")
    prompt_markdown = data.get("prompt_markdown")
    if not isinstance(slug, str) or not isinstance(display_name, str) or not isinstance(
        prompt_markdown, str
    ):
        return error_bad_request("slug, display_name, and prompt_markdown are required strings")
    if not _SLUG_RE.match(slug):
        return error_bad_request("invalid slug")
    if _prompt_too_large(prompt_markdown):
        return error_bad_request("prompt too large")

    description = data.get("description", "")
    if description is not None and not isinstance(description, str):
        return error_bad_request("description must be a string")
    description = description or ""

    active = data.get("active", True)
    if not isinstance(active, bool):
        return error_bad_request("active must be a boolean")

    if get_perspective_by_slug(db, slug):
        return error_bad_request("slug already exists")

    try:
        insert_perspective(
            db,
            slug=slug,
            display_name=display_name,
            prompt_markdown=prompt_markdown,
            description=description,
            active=active,
            source_filename=None,
        )
        db.commit()
    except Exception as e:
        db.rollback()
        return error_bad_request(str(e))

    created = get_perspective_by_slug(db, slug)
    assert created is not None
    return jsonify(_row_detail(created)), 201


@bp.route("/<slug>", methods=["PUT"])
@with_db
def update_perspective_route(db, slug: str):
    if not get_perspective_by_slug(db, slug):
        return error_not_found("resource")

    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return error_bad_request("JSON body required")

    display_name = data.get("display_name") if "display_name" in data else None
    description = data.get("description") if "description" in data else None
    prompt_markdown = data.get("prompt_markdown") if "prompt_markdown" in data else None
    active = data.get("active") if "active" in data else None

    if (
        display_name is None
        and description is None
        and prompt_markdown is None
        and active is None
    ):
        return error_bad_request("at least one field required")

    if display_name is not None and not isinstance(display_name, str):
        return error_bad_request("display_name must be a string")
    if description is not None and not isinstance(description, str):
        return error_bad_request("description must be a string")
    if prompt_markdown is not None:
        if not isinstance(prompt_markdown, str):
            return error_bad_request("prompt_markdown must be a string")
        if _prompt_too_large(prompt_markdown):
            return error_bad_request("prompt too large")
    if active is not None and not isinstance(active, bool):
        return error_bad_request("active must be a boolean")

    updated = update_perspective(
        db,
        slug,
        display_name=display_name,
        description=description,
        prompt_markdown=prompt_markdown,
        active=active,
    )
    if not updated:
        return error_bad_request("no valid fields to update")
    db.commit()

    row = get_perspective_by_slug(db, slug)
    assert row is not None
    return jsonify(_row_detail(row))


@bp.route("/<slug>", methods=["DELETE"])
@with_db
def delete_perspective_route(db, slug: str):
    if not delete_perspective(db, slug):
        return error_not_found("resource")
    db.commit()
    return "", 204


@bp.route("/<slug>/reset-default", methods=["POST"])
@with_db
def reset_perspective_default_route(db, slug: str):
    row = get_perspective_by_slug(db, slug)
    if not row:
        return error_not_found("resource")

    source_filename = row.get("source_filename")
    if source_filename:
        if not isinstance(source_filename, str) or not _SOURCE_FILENAME_RE.match(source_filename):
            return error_bad_request("invalid source_filename")
        filename = source_filename
    else:
        filename = f"{slug}.md"

    path = (Path(_REPO_ROOT) / "prompts" / "perspectives" / filename).resolve()
    base = (Path(_REPO_ROOT) / "prompts" / "perspectives").resolve()
    try:
        path.relative_to(base)
    except ValueError:
        return error_bad_request("invalid source_filename")

    if not path.is_file():
        return jsonify({"error": "no default file"}), 404

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        return error_bad_request(str(e))

    if _prompt_too_large(text):
        return error_bad_request("prompt too large")

    update_perspective(db, slug, prompt_markdown=text)
    db.commit()
    refreshed = get_perspective_by_slug(db, slug)
    assert refreshed is not None
    return jsonify(_row_detail(refreshed))
