"""Describe matched catalog and Instagram images on demand."""
import os

from lightroom_tagger.core.analyzer import describe_image, get_description_model
from lightroom_tagger.core.database import (
    get_image,
    get_image_description,
    get_instagram_dump_media,
    resolve_filepath,
    store_image_description,
)


def _description_structured_is_valid(structured: dict) -> bool:
    """True if describe_image output is worth persisting (non-empty summary)."""
    summary = structured.get('summary')
    return isinstance(summary, str) and bool(summary.strip())


def describe_matched_image(db, catalog_key: str, force: bool = False) -> bool:
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

    structured = describe_image(filepath)
    if not _description_structured_is_valid(structured):
        return False

    _store_structured(db, catalog_key, 'catalog', structured)
    return True


def describe_instagram_image(db, media_key: str, force: bool = False) -> bool:
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

    structured = describe_image(filepath)
    if not _description_structured_is_valid(structured):
        return False

    _store_structured(db, media_key, 'instagram', structured)
    return True


def _store_structured(db, image_key: str, image_type: str, structured: dict):
    store_image_description(db, {
        'image_key': image_key,
        'image_type': image_type,
        'summary': structured.get('summary', ''),
        'composition': structured.get('composition', {}),
        'perspectives': structured.get('perspectives', {}),
        'technical': structured.get('technical', {}),
        'subjects': structured.get('subjects', []),
        'best_perspective': structured.get('best_perspective', ''),
        'model_used': get_description_model(),
    })
