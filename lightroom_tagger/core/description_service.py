"""Describe matched catalog and Instagram images on demand."""
import os
import sqlite3
import threading
from collections.abc import Callable
from typing import TypedDict

from lightroom_tagger.core.analyzer import VIDEO_EXTENSIONS, build_description_op_spec
from lightroom_tagger.core.config import get_description_model
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
from lightroom_tagger.core.vision_op import VisionOpOutcome, run_vision_op_persist

LogCallback = Callable[[str, str], None] | None


class DescribeTelemetry(TypedDict):
    """Thread-safe telemetry bag for batch describe passes.

    Construct with::

        telemetry: DescribeTelemetry = {
            'silent_compression_skips': 0,
            '_lock': threading.Lock(),
        }

    Pass ``None`` when telemetry is not needed; any partial dict raises KeyError
    at the ``with telemetry['_lock']`` site.
    """

    silent_compression_skips: int
    _lock: threading.Lock


# File extensions the vision pipeline cannot describe. These get short-circuited
# before we ever call into compression / the provider dispatcher — otherwise a
# .mov file falls all the way through to the LLM (compress_image silently
# returns the raw bytes on failure) and stalls the worker on multi-minute retry
# backoffs, which in turn wedges the batch-describe ``as_completed`` loop.
_NON_DESCRIBABLE_EXTENSIONS = VIDEO_EXTENSIONS


def _is_non_describable_path(filepath: str | None) -> bool:
    if not filepath:
        return False
    ext = os.path.splitext(filepath)[1].lower()
    return ext in _NON_DESCRIBABLE_EXTENSIONS


def _description_structured_is_valid(structured: dict) -> bool:
    """True if vision-op description output is worth persisting (non-empty summary)."""
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


def _persist_description_structured(
    db: sqlite3.Connection,
    image_key: str,
    image_type: str,
    structured: dict,
    provider: str,
    model: str,
) -> None:
    model_used = structured.pop("_model", None) or model or get_description_model()
    provider_used = structured.pop("_provider", None) or provider
    model_label = f"{provider_used}:{model_used}" if provider_used else model_used
    _store_structured(db, image_key, image_type, structured, model_label)


def _run_description_persist(
    db: sqlite3.Connection,
    image_key: str,
    image_type: str,
    image_path: str,
    *,
    provider_id: str | None,
    model: str | None,
    log_callback: LogCallback,
    user_prompt: str | None,
    silent_compression: bool,
) -> VisionOpOutcome:
    spec = build_description_op_spec(
        image_path,
        provider_id=provider_id,
        model=model,
        log_callback=log_callback,
        user_prompt=user_prompt,
        silent_compression=silent_compression,
    )

    def persist(structured: dict, provider: str, model_used: str) -> None:
        structured = dict(structured)
        structured["_provider"] = provider
        structured["_model"] = model_used
        _persist_description_structured(db, image_key, image_type, structured, provider, model_used)

    return run_vision_op_persist(
        spec,
        accept_result=_description_structured_is_valid,
        persist=persist,
    )


def describe_matched_image(db: sqlite3.Connection, catalog_key: str, force: bool = False,
                           provider_id: str | None = None,
                           model: str | None = None,
                           log_callback: LogCallback = None,
                           perspective_slugs: list[str] | None = None,
                           *,
                           telemetry: DescribeTelemetry | None = None) -> VisionOpOutcome:
    """Generate and store a description for a catalog image if needed.

    Returns a :class:`VisionOpOutcome`. ``wrote`` is True when a non-empty
    description was stored. Skipped or failed outcomes leave the DB unchanged.
    """
    if not force and get_image_description(db, catalog_key):
        return VisionOpOutcome(status='skipped', reason='description exists')

    image = get_image(db, catalog_key)
    if not image or not image.get('filepath'):
        return VisionOpOutcome(status='skipped', reason='image not found')

    filepath = resolve_filepath(image['filepath'])
    if _is_non_describable_path(filepath):
        return VisionOpOutcome(status='skipped', reason='non-describable file type')
    if not os.path.exists(filepath):
        return VisionOpOutcome(status='skipped', reason='file missing')

    cached_path = get_or_create_cached_image(db, catalog_key, filepath)
    image_for_describe = cached_path if cached_path and os.path.exists(cached_path) else filepath
    user_prompt = _resolve_description_user_prompt(db, perspective_slugs)
    use_silent_compression = (
        bool(cached_path)
        and cached_path == image_for_describe
        and os.path.exists(cached_path)
    )

    outcome = _run_description_persist(
        db,
        catalog_key,
        'catalog',
        image_for_describe,
        provider_id=provider_id,
        model=model,
        log_callback=log_callback,
        user_prompt=user_prompt,
        silent_compression=use_silent_compression,
    )
    if use_silent_compression and telemetry is not None:
        with telemetry['_lock']:
            telemetry['silent_compression_skips'] += 1
    return outcome


def describe_instagram_image(db: sqlite3.Connection, media_key: str, force: bool = False,
                             provider_id: str | None = None,
                             model: str | None = None,
                             log_callback: LogCallback = None,
                             perspective_slugs: list[str] | None = None) -> VisionOpOutcome:
    """Generate and store a description for an Instagram image if needed.

    Uses the local file from instagram_dump_media. ``wrote`` is True when a
    non-empty description was stored.
    """
    if not force and get_image_description(db, media_key):
        return VisionOpOutcome(status='skipped', reason='description exists')

    dump_media = get_instagram_dump_media(db, media_key)
    if not dump_media or not dump_media.get('file_path'):
        return VisionOpOutcome(status='skipped', reason='image not found')

    filepath = dump_media['file_path']
    if _is_non_describable_path(filepath):
        return VisionOpOutcome(status='skipped', reason='non-describable file type')
    if not os.path.exists(filepath):
        return VisionOpOutcome(status='skipped', reason='file missing')

    user_prompt = _resolve_description_user_prompt(db, perspective_slugs)
    return _run_description_persist(
        db,
        media_key,
        'instagram',
        filepath,
        provider_id=provider_id,
        model=model,
        log_callback=log_callback,
        user_prompt=user_prompt,
        silent_compression=False,
    )


def _store_structured(
    db: sqlite3.Connection,
    image_key: str,
    image_type: str,
    structured: dict,
    model_used: str | None = None,
) -> None:
    technical = structured.get('technical')
    if not isinstance(technical, dict):
        technical = {}

    raw_dc = structured.get('dominant_colors')
    if isinstance(raw_dc, list) and len(raw_dc) > 0:
        dc: list | None = raw_dc
    else:
        tc = technical.get('dominant_colors')
        dc = tc if isinstance(tc, list) else None

    raw_mt = structured.get('mood_tags')
    if isinstance(raw_mt, list):
        mt: list | None = raw_mt
    else:
        mt = None
    if mt is None:
        mood = technical.get('mood')
        if isinstance(mood, str) and mood.strip():
            mt = [mood.strip()]

    hr_raw = structured.get('has_repetition')
    if hr_raw is None:
        hr = None
    elif isinstance(hr_raw, bool):
        hr = hr_raw
    elif isinstance(hr_raw, int) and hr_raw in (0, 1):
        hr = hr_raw
    else:
        hr = hr_raw

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
        'dominant_colors': dc,
        'mood_tags': mt,
        'has_repetition': hr,
    })
