"""Score catalog and Instagram-dump images per perspective into ``image_scores``.

Vision + compression route through :func:`lightroom_tagger.core.vision_op.run_vision_op_persist`
via :func:`lightroom_tagger.core.analyzer.build_score_op_spec`.
"""

from __future__ import annotations

import hashlib
import os
import re
import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone

from lightroom_tagger.core.analyzer import VIDEO_EXTENSIONS, build_score_op_spec
from lightroom_tagger.core.database import (
    get_image,
    get_instagram_dump_media,
    get_perspective_by_slug,
    insert_image_score,
    library_write,
    resolve_filepath,
    supersede_previous_current_scores,
)
from lightroom_tagger.core.prompt_builder import build_scoring_user_prompt
from lightroom_tagger.core.structured_output import StructuredOutputError
from lightroom_tagger.core.vision_cache import get_or_create_cached_image
from lightroom_tagger.core.vision_op import VisionOpOutcome, run_vision_op_persist

LogCallback = Callable[[str, str], None] | None


def compute_prompt_version(perspective_row: dict) -> str:
    """Stable rubric id: ``{slug}:{sha256(prompt_markdown_utf8)[:16]}`` (see D-23)."""
    slug = str(perspective_row["slug"])
    md = str(perspective_row.get("prompt_markdown", "") or "")
    digest = hashlib.sha256(md.encode("utf-8")).hexdigest()[:16]
    return f"{slug}:{digest}"


def perspective_score_already_current(
    conn: sqlite3.Connection,
    image_key: str,
    image_type: str,
    perspective_slug: str,
    prompt_version: str,
) -> bool:
    row = conn.execute(
        """
        SELECT 1 AS ok FROM image_scores
        WHERE image_key = ? AND image_type = ? AND perspective_slug = ?
          AND prompt_version = ? AND is_current = 1
        LIMIT 1
        """,
        (image_key, image_type, perspective_slug, prompt_version),
    ).fetchone()
    return row is not None


def delete_scores_for_version(
    conn: sqlite3.Connection,
    image_key: str,
    image_type: str,
    perspective_slug: str,
    prompt_version: str,
) -> None:
    conn.execute(
        """
        DELETE FROM image_scores
        WHERE image_key = ? AND image_type = ? AND perspective_slug = ?
          AND prompt_version = ?
        """,
        (image_key, image_type, perspective_slug, prompt_version),
    )


def _normalize_perspective_slug(raw_slug: str) -> str:
    return re.sub(r"\s*\(.*\)\s*$", "", raw_slug.strip()).lower().strip()


def _run_score_persist(
    db: sqlite3.Connection,
    *,
    image_key: str,
    image_type: str,
    perspective_slug: str,
    prompt_version: str,
    force: bool,
    image_path: str,
    provider_id: str | None,
    model: str | None,
    log_callback: LogCallback,
    user_prompt: str,
    silent_compression: bool,
) -> VisionOpOutcome:
    spec = build_score_op_spec(
        image_path,
        user_prompt=user_prompt,
        provider_id=provider_id,
        model=model,
        log_callback=log_callback,
        silent_compression=silent_compression,
    )

    reject_reason: dict[str, str] = {}

    def accept_result(parsed_bundle: tuple) -> bool:
        parsed, _repaired = parsed_bundle
        got_slug = _normalize_perspective_slug(parsed.perspective_slug)
        if got_slug != perspective_slug.strip():
            if log_callback:
                log_callback(
                    "warning",
                    f"Slug mismatch: model returned {parsed.perspective_slug!r}, "
                    f"normalized to {got_slug!r}, expected {perspective_slug!r} — skipping",
                )
            reject_reason["msg"] = (
                f"Model returned perspective_slug {parsed.perspective_slug!r}; "
                f"expected {perspective_slug!r}"
            )
            return False
        return True

    def persist(parsed_bundle: tuple, provider: str, model_used: str) -> None:
        parsed, repaired = parsed_bundle
        model_label = f"{provider}:{model_used}"
        scored_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        with library_write(db, log=log_callback):
            if force:
                delete_scores_for_version(
                    db, image_key, image_type, perspective_slug, prompt_version,
                )
            supersede_previous_current_scores(
                db, image_key, image_type, perspective_slug, prompt_version,
            )
            insert_image_score(
                db,
                {
                    "image_key": image_key,
                    "image_type": image_type,
                    "perspective_slug": perspective_slug,
                    "score": parsed.score,
                    "rationale": parsed.rationale,
                    "model_used": model_label,
                    "prompt_version": prompt_version,
                    "scored_at": scored_at,
                    "is_current": 1,
                    "repaired_from_malformed": 1 if repaired else 0,
                    "not_attempted": 1 if parsed.not_attempted else 0,
                },
            )

    outcome = run_vision_op_persist(
        spec,
        accept_result=accept_result,
        persist=persist,
    )
    if outcome.status == "failed" and outcome.reason == "invalid result":
        if "msg" in reject_reason:
            return VisionOpOutcome(status="failed", reason=reject_reason["msg"])
        return VisionOpOutcome(
            status="failed",
            reason="model returned empty or invalid score response",
        )
    return outcome


def score_image_for_perspective(
    db: sqlite3.Connection,
    *,
    image_key: str,
    image_type: str,
    perspective_slug: str,
    force: bool,
    provider_id: str | None,
    model: str | None,
    log_callback: LogCallback = None,
) -> VisionOpOutcome:
    """Score one image for one perspective.

    Returns a :class:`VisionOpOutcome`. ``wrote`` is True when a new score row
    was written.
    """
    if image_type == "catalog":
        image = get_image(db, image_key)
        if not image or not image.get("filepath"):
            return VisionOpOutcome(status="skipped", reason="Catalog image missing or has no filepath")
        filepath = resolve_filepath(str(image["filepath"]))
        if not os.path.exists(filepath):
            return VisionOpOutcome(status="skipped", reason=f"Image file not found: {filepath}")
    elif image_type == "instagram":
        dump = get_instagram_dump_media(db, image_key)
        if not dump or not dump.get("file_path"):
            return VisionOpOutcome(status="skipped", reason="Instagram media missing or has no file_path")
        filepath = str(dump["file_path"])
        if not os.path.exists(filepath):
            return VisionOpOutcome(status="skipped", reason=f"Image file not found: {filepath}")
    else:
        return VisionOpOutcome(status="failed", reason=f"Invalid image_type: {image_type!r}")

    if os.path.splitext(filepath)[1].lower() in VIDEO_EXTENSIONS:
        return VisionOpOutcome(
            status="skipped",
            reason=f"Video file not scorable: {os.path.basename(filepath)}",
        )

    prow = get_perspective_by_slug(db, perspective_slug)
    if not prow:
        return VisionOpOutcome(status="failed", reason=f"Unknown perspective slug: {perspective_slug!r}")
    if int(prow.get("active") or 0) != 1:
        return VisionOpOutcome(status="failed", reason=f"Perspective {perspective_slug!r} is not active")

    pv = compute_prompt_version(prow)

    if not force and perspective_score_already_current(db, image_key, image_type, perspective_slug, pv):
        return VisionOpOutcome(
            status="skipped",
            reason="Score already current for this image, perspective, and prompt version",
        )

    silent_compression = False
    if image_type == "catalog":
        cached = get_or_create_cached_image(db, image_key, filepath)
        if cached and os.path.exists(cached):
            image_for_score = cached
            silent_compression = True
        else:
            image_for_score = filepath
    else:
        image_for_score = filepath

    user_prompt = build_scoring_user_prompt(prow)

    try:
        return _run_score_persist(
            db,
            image_key=image_key,
            image_type=image_type,
            perspective_slug=perspective_slug,
            prompt_version=pv,
            force=force,
            image_path=image_for_score,
            provider_id=provider_id,
            model=model,
            log_callback=log_callback,
            user_prompt=user_prompt,
            silent_compression=silent_compression,
        )
    except StructuredOutputError as exc:
        return VisionOpOutcome(status="failed", reason=str(exc))
    except sqlite3.IntegrityError as exc:
        if "UNIQUE constraint" in str(exc):
            return VisionOpOutcome(status="skipped", reason="Score already written by concurrent worker")
        return VisionOpOutcome(status="failed", reason=str(exc))
    except Exception as exc:
        return VisionOpOutcome(status="failed", reason=str(exc))


__all__ = [
    "compute_prompt_version",
    "delete_scores_for_version",
    "perspective_score_already_current",
    "score_image_for_perspective",
]
