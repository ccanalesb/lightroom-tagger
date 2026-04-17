"""Describe matched catalog and Instagram images on demand."""
import os
import sqlite3
from collections.abc import Callable

from lightroom_tagger.core.analyzer import describe_image, get_description_model
from lightroom_tagger.core.database import (
    get_image,
    get_image_description,
    get_instagram_dump_media,
    list_perspectives,
    resolve_filepath,
    store_image_description,
)
from lightroom_tagger.core.prompt_builder import build_description_user_prompt
from lightroom_tagger.core.vision_cache import get_or_create_cached_image

LogCallback = Callable[[str, str], None] | None


def _description_structured_is_valid(structured: dict) -> bool:
    """True if describe_image output is worth persisting (non-empty summary)."""
    summary = structured.get('summary')
    return isinstance(summary, str) and bool(summary.strip())


def _resolve_description_user_prompt(
    db: sqlite3.Connection, perspective_slugs: list[str] | None
) -> str | None:
    """Return assembled user prompt text, or ``None`` to use the legacy monolithic prompt."""
    active_rows = list_perspectives(db, active_only=True)
    if perspective_slugs:
        by_slug = {r["slug"]: r for r in active_rows}
        rows = [by_slug[s] for s in perspective_slugs if s in by_slug]
    else:
        rows = active_rows
    if not rows:
        return None
    return build_description_user_prompt(rows)


def describe_matched_image(db: sqlite3.Connection, catalog_key: str, force: bool = False,
                           provider_id: str | None = None,
                           model: str | None = None,
                           log_callback: LogCallback = None,
                           perspective_slugs: list[str] | None = None) -> bool:
    """Generate and store a description for a catalog image if needed.

    Returns True if a non-empty description was stored. Returns False if
    skipped, missing file, or describe_image produced no usable summary
    (e.g. model failure / empty fallback) — nothing is persisted in that case.
    """
    if not force and get_image_description(db, catalog_key):
        return False

    image = get_image(db, catalog_key)
    if not image or not image.get('filepath'):
        return False

    filepath = resolve_filepath(image['filepath'])
    if not os.path.exists(filepath):
        return False

    # Use vision cache to avoid redundant RAW→JPG conversion + compression
    cached_path = get_or_create_cached_image(db, catalog_key, filepath)
    image_for_describe = cached_path if cached_path and os.path.exists(cached_path) else filepath

    user_prompt = _resolve_description_user_prompt(db, perspective_slugs)
    structured = describe_image(
        image_for_describe, provider_id=provider_id, model=model,
        log_callback=log_callback, user_prompt=user_prompt,
    )
    if not _description_structured_is_valid(structured):
        return False

    model_used = structured.pop("_model", None) or get_description_model()
    provider_used = structured.pop("_provider", None)
    model_label = f"{provider_used}:{model_used}" if provider_used else model_used

    _store_structured(db, catalog_key, 'catalog', structured, model_label)
    return True


def describe_instagram_image(db: sqlite3.Connection, media_key: str, force: bool = False,
                             provider_id: str | None = None,
                             model: str | None = None,
                             log_callback: LogCallback = None,
                             perspective_slugs: list[str] | None = None) -> bool:
    """Generate and store a description for an Instagram image if needed.

    Uses the local file from instagram_dump_media. Returns True if a
    non-empty description was stored.
    """
    if not force and get_image_description(db, media_key):
        return False

    dump_media = get_instagram_dump_media(db, media_key)
    if not dump_media or not dump_media.get('file_path'):
        return False

    filepath = dump_media['file_path']
    if not os.path.exists(filepath):
        return False

    user_prompt = _resolve_description_user_prompt(db, perspective_slugs)
    structured = describe_image(
        filepath, provider_id=provider_id, model=model,
        log_callback=log_callback, user_prompt=user_prompt,
    )
    if not _description_structured_is_valid(structured):
        return False

    model_used = structured.pop("_model", None) or get_description_model()
    provider_used = structured.pop("_provider", None)
    model_label = f"{provider_used}:{model_used}" if provider_used else model_used

    _store_structured(db, media_key, 'instagram', structured, model_label)
    return True


def _store_structured(
    db: sqlite3.Connection,
    image_key: str,
    image_type: str,
    structured: dict,
    model_used: str | None = None,
) -> None:
    store_image_description(db, {
        'image_key': image_key,
        'image_type': image_type,
        'summary': structured.get('summary', ''),
        'composition': structured.get('composition', {}),
        'perspectives': structured.get('perspectives', {}),
        'technical': structured.get('technical', {}),
        'subjects': structured.get('subjects', []),
        'best_perspective': structured.get('best_perspective', ''),
        'model_used': model_used or get_description_model(),
    })
