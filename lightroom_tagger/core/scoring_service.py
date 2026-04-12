"""Score catalog and Instagram-dump images per perspective into ``image_scores``.

Vision + compression follow :func:`lightroom_tagger.core.analyzer._describe_image_via_provider`.
``FallbackDispatcher.call_with_fallback`` uses ``operation="score"`` as the log label (same
registry, retry, and fallback order as ``"describe"`` — only the tag string differs).
"""

from __future__ import annotations

import contextlib
import functools
import hashlib
import os
import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

import ollama

from lightroom_tagger.core.analyzer import (
    compress_image,
    get_description_model,
    get_viewable_path,
    run_local_agent,
)
from lightroom_tagger.core.database import (
    get_image,
    get_instagram_dump_media,
    get_perspective_by_slug,
    insert_image_score,
    resolve_filepath,
    supersede_previous_current_scores,
)
from lightroom_tagger.core.fallback import FallbackDispatcher
from lightroom_tagger.core.prompt_builder import build_scoring_user_prompt
from lightroom_tagger.core.provider_registry import ProviderRegistry
from lightroom_tagger.core.structured_output import (
    StructuredOutputError,
    parse_score_response_with_retry,
)
from lightroom_tagger.core.vision_client import (
    complete_chat_text,
    generate_description,
    make_score_json_llm_fixer,
)

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


def _ollama_complete_text_for_repair(*, system: str, user: str, **_kwargs: Any) -> str:
    response = ollama.chat(
        model=get_description_model(),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    content = getattr(response.message, "content", None) if response and response.message else None
    return content or ""


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
) -> tuple[str, bool, str | None]:
    """Score one image for one perspective. Returns ``(status, success, error)`` like describe helpers.

    *status* is ``scored``, ``skipped``, or ``failed``. *success* is ``True`` only when a new score row
    was written.
    """
    if image_type == "catalog":
        image = get_image(db, image_key)
        if not image or not image.get("filepath"):
            return ("skipped", False, "Catalog image missing or has no filepath")
        filepath = resolve_filepath(str(image["filepath"]))
        if not os.path.exists(filepath):
            return ("skipped", False, f"Image file not found: {filepath}")
    elif image_type == "instagram":
        dump = get_instagram_dump_media(db, image_key)
        if not dump or not dump.get("file_path"):
            return ("skipped", False, "Instagram media missing or has no file_path")
        filepath = str(dump["file_path"])
        if not os.path.exists(filepath):
            return ("skipped", False, f"Image file not found: {filepath}")
    else:
        return ("failed", False, f"Invalid image_type: {image_type!r}")

    prow = get_perspective_by_slug(db, perspective_slug)
    if not prow:
        return ("failed", False, f"Unknown perspective slug: {perspective_slug!r}")
    if int(prow.get("active") or 0) != 1:
        return ("failed", False, f"Perspective {perspective_slug!r} is not active")

    pv = compute_prompt_version(prow)

    if not force and perspective_score_already_current(db, image_key, image_type, perspective_slug, pv):
        return (
            "skipped",
            False,
            "Score already current for this image, perspective, and prompt version",
        )

    if force:
        delete_scores_for_version(db, image_key, image_type, perspective_slug, pv)

    temp_files: list[str] = []
    viewable = get_viewable_path(filepath)
    if viewable != filepath:
        temp_files.append(viewable)
    compressed = compress_image(viewable)
    if compressed != viewable:
        temp_files.append(compressed)

    user_prompt = build_scoring_user_prompt(prow)

    def _log_repair(msg: str) -> None:
        if log_callback is not None:
            log_callback("info", msg)

    try:
        if provider_id is not None:
            registry = ProviderRegistry()
            dispatcher = FallbackDispatcher(registry)
            if model is None:
                models = registry.list_models(provider_id)
                use_model = models[0]["id"] if models else "gemma3:27b"
            else:
                use_model = model

            def fn_factory(client: Any, mdl: str) -> Callable[[], str]:
                return lambda: generate_description(
                    client,
                    mdl,
                    compressed,
                    log_callback=log_callback,
                    user_prompt=user_prompt,
                )

            raw, actual_provider, actual_model = dispatcher.call_with_fallback(
                operation="score",
                fn_factory=fn_factory,
                provider_id=provider_id,
                model=use_model,
                log_callback=log_callback,
            )
            client = registry.get_client(actual_provider)
            llm_fixer = make_score_json_llm_fixer(
                functools.partial(complete_chat_text, client, actual_model),
            )
            model_label = f"{actual_provider}:{actual_model}"
        else:
            raw = run_local_agent(compressed, user_prompt=user_prompt)
            llm_fixer = make_score_json_llm_fixer(_ollama_complete_text_for_repair)
            model_label = f"ollama:{get_description_model()}"

        parsed, repaired = parse_score_response_with_retry(
            raw,
            llm_fixer=llm_fixer,
            log_repair=_log_repair,
        )
    except StructuredOutputError as exc:
        return ("failed", False, str(exc))
    except Exception as exc:
        return ("failed", False, str(exc))
    finally:
        for f in temp_files:
            if os.path.exists(f):
                with contextlib.suppress(Exception):
                    os.unlink(f)

    got_slug = parsed.perspective_slug.strip()
    if got_slug != perspective_slug.strip():
        return (
            "failed",
            False,
            f"Model returned perspective_slug {got_slug!r}; expected {perspective_slug!r}",
        )

    scored_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    try:
        supersede_previous_current_scores(db, image_key, image_type, perspective_slug, pv)
        insert_image_score(
            db,
            {
                "image_key": image_key,
                "image_type": image_type,
                "perspective_slug": perspective_slug,
                "score": parsed.score,
                "rationale": parsed.rationale,
                "model_used": model_label,
                "prompt_version": pv,
                "scored_at": scored_at,
                "is_current": 1,
                "repaired_from_malformed": 1 if repaired else 0,
            },
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        return ("failed", False, str(exc))

    return ("scored", True, None)


__all__ = [
    "compute_prompt_version",
    "delete_scores_for_version",
    "perspective_score_already_current",
    "score_image_for_perspective",
]
