"""Describe matched catalog images on demand."""
import os

from lightroom_tagger.core.analyzer import describe_image, get_description_model
from lightroom_tagger.core.database import (
    get_image,
    get_image_description,
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

    store_image_description(db, {
        'image_key': catalog_key,
        'image_type': 'catalog',
        'summary': structured.get('summary', ''),
        'composition': structured.get('composition', {}),
        'perspectives': structured.get('perspectives', {}),
        'technical': structured.get('technical', {}),
        'subjects': structured.get('subjects', []),
        'best_perspective': structured.get('best_perspective', ''),
        'model_used': get_description_model(),
    })
    return True
