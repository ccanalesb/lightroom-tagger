"""Image inspection helpers (perceptual hash, EXIF)."""

from typing import Any


def compute_phash(path: str) -> str | None:
    """Placeholder - delegate to existing hasher."""
    from lightroom_tagger.core.hasher import compute_phash as _compute
    try:
        return _compute(path)
    except Exception:
        return None


def extract_exif(path: str) -> dict[str, Any]:
    """Extract EXIF metadata from image."""
    from PIL import Image
    from PIL.ExifTags import TAGS

    result = {}
    try:
        with Image.open(path) as img:
            exif = img._getexif() # type: ignore[attr-defined]
            if exif:
                for tag_id, value in exif.items():
                    tag = TAGS.get(tag_id, tag_id)
                    if tag in ['Make', 'Model', 'DateTime', 'LensModel', 'ISOSpeedRatings',
                               'FNumber', 'ExposureTime', 'GPSInfo']:
                        result[tag.lower()] = str(value)
    except Exception:
        pass
    return result
