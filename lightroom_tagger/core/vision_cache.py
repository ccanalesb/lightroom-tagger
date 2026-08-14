"""Vision image caching module for efficient re-compression.

This module provides caching for compressed images used in vision comparison,
eliminating redundant compression of the same images across multiple matching runs.
"""

import contextlib
import errno
import os
import shutil
import tempfile

from lightroom_tagger.core.analyzer import compress_image, compute_phash, get_viewable_path
from lightroom_tagger.core.config import load_config
from lightroom_tagger.core.database import (
    VISION_CACHE_OVERSIZED_SENTINEL,
    get_catalog_images_missing_cache,
    get_vision_cached_image,
    is_vision_cache_valid,
    store_vision_cached_image,
)
from lightroom_tagger.core.path_utils import resolve_catalog_path

# Working cached JPEGs are ~50–135KB; larger outputs imply failed compression or oversized originals.
MAX_CACHED_IMAGE_KB = 512


def _is_path_in_temp_dir(path: str) -> bool:
    """True if path is under the system temp directory (a file this process may delete)."""
    if not path:
        return False
    tmp = os.path.abspath(tempfile.gettempdir())
    ap = os.path.abspath(path)
    return ap == tmp or ap.startswith(tmp + os.sep)


def _place_into_cache(source: str, target_path: str, temp_files: list[str]) -> None:
    """Move or copy source into the cache path without clobbering user-owned files."""
    if _is_path_in_temp_dir(source):
        try:
            os.replace(source, target_path)
        except OSError as e:
            if e.errno != errno.EXDEV:
                raise
            shutil.copy2(source, target_path)
            with contextlib.suppress(OSError):
                os.unlink(source)
        if source in temp_files:
            temp_files.remove(source)
    else:
        shutil.copy2(source, target_path)


def get_or_create_cached_image(db, catalog_key: str, original_path: str) -> str | None:
    """Get compressed image path from cache or create it atomically.

    Uses file modification time for cache invalidation. Compresses to temp file first,
    then atomically moves to final location to prevent corruption.

    Args:
        db: sqlite3 connection
        catalog_key: Unique key for the catalog image
        original_path: Path to original image file

    Returns:
        Path to compressed image, or None if compression failed
    """
    config = load_config()
    if not config.vision_cache_enabled:
        # Cache disabled, just compress on-the-fly
        return compress_image(original_path)

    cache_dir = config.vision_cache_dir
    os.makedirs(cache_dir, exist_ok=True)

    # Check if already cached and valid (mtime unchanged)
    if is_vision_cache_valid(db, catalog_key, original_path):
        cached = get_vision_cached_image(db, catalog_key)
        if cached:
            path = cached.get('compressed_path')
            if path == VISION_CACHE_OVERSIZED_SENTINEL:
                return None
            return path

    # Need to create cache
    target_path = os.path.join(cache_dir, f"{catalog_key.replace('/', '_')}.jpg")

    temp_files: list[str] = []
    try:
        # Convert RAW/DNG to viewable JPG first
        viewable_path = get_viewable_path(original_path)
        if viewable_path != original_path and _is_path_in_temp_dir(viewable_path):
            temp_files.append(viewable_path)

        temp_path = compress_image(viewable_path)
        if temp_path != viewable_path:
            temp_files.append(temp_path)

        phash = compute_phash(viewable_path)
        original_mtime = os.path.getmtime(original_path)

        if temp_path == viewable_path and viewable_path == original_path:
            # Neither conversion nor compression worked
            size_kb = os.path.getsize(original_path) / 1024
            if size_kb > MAX_CACHED_IMAGE_KB:
                store_vision_cached_image(
                    db, catalog_key, VISION_CACHE_OVERSIZED_SENTINEL, None, original_mtime,
                )
                return None
            store_vision_cached_image(db, catalog_key, original_path, phash, original_mtime)
            return original_path

        # Use the compressed file (or converted file if compression was no-op)
        source = temp_path if temp_path != viewable_path else viewable_path
        _place_into_cache(source, target_path, temp_files)

        if os.path.getsize(target_path) / 1024 > MAX_CACHED_IMAGE_KB:
            with contextlib.suppress(OSError):
                os.unlink(target_path)
            store_vision_cached_image(
                db, catalog_key, VISION_CACHE_OVERSIZED_SENTINEL, None, original_mtime,
            )
            return None

        store_vision_cached_image(db, catalog_key, target_path, phash, original_mtime)
        return target_path

    except Exception:
        raise
    finally:
        for tf in temp_files:
            if tf and os.path.exists(tf):
                with contextlib.suppress(BaseException):
                    os.unlink(tf)


def resolve_vision_image(db, catalog_key: str, original_path: str) -> tuple[str | None, bool]:
    """Resolve the image to feed a vision op, preferring the local cache.

    Returns ``(image_path, silent_compression)`` — ``silent_compression`` is True
    when ``image_path`` is an already-compressed cache file that must not be
    recompressed. Returns ``(None, False)`` when no usable image exists.

    When the original is reachable, this refreshes/validates the cache exactly as
    before (mtime-invalidated). When the original is **unreachable** (e.g. an
    unmounted NAS), it falls back to an already-cached compressed image so
    describe/score run entirely off the local vision cache — the intended contract.
    """
    if os.path.exists(original_path):
        cached = get_or_create_cached_image(db, catalog_key, original_path)
        if cached and os.path.exists(cached):
            # ``cached`` is either the compressed cache file or (rare no-op) the
            # original itself; both are safe to pass with silent_compression=True.
            return cached, True
        return original_path, False

    # Original unreachable — use the pre-existing compressed cache if present.
    rec = get_vision_cached_image(db, catalog_key)
    cache_path = rec.get('compressed_path') if rec else None
    if (
        cache_path
        and cache_path != VISION_CACHE_OVERSIZED_SENTINEL
        and os.path.exists(cache_path)
    ):
        return cache_path, True
    return None, False


def get_cached_phash(db, catalog_key: str) -> str | None:
    """Get pre-computed pHash from cache.

    Args:
        db: sqlite3 connection
        catalog_key: Key of catalog image

    Returns:
        Pre-computed pHash string, or None if not cached or unavailable
    """
    cached = get_vision_cached_image(db, catalog_key)
    if not cached:
        return None
    ph = cached.get('phash')
    return ph if ph else None


def get_cache_stats(db) -> dict:
    """Get vision cache statistics.

    Wrapper around database function for convenience.
    """
    from lightroom_tagger.core.database import get_cache_stats as _get_stats
    return _get_stats(db)


def warm_vision_cache(db, limit: int | None = None) -> dict:
    """Warm vision cache entries for catalog images missing from the cache.

    Returns:
        {processed: N, skipped: N, errors: N}
    """
    images = get_catalog_images_missing_cache(db)
    if limit:
        images = images[:limit]

    processed = 0
    skipped = 0
    errors = 0

    for record in images:
        key = record.get('key')
        if not key:
            skipped += 1
            continue

        filepath = resolve_catalog_path(record.get('filepath', ''))
        if not filepath:
            skipped += 1
            continue

        try:
            cached_path = get_or_create_cached_image(db, key, filepath)
            if cached_path:
                processed += 1
            else:
                errors += 1
        except Exception:
            errors += 1

    return {
        'processed': processed,
        'skipped': skipped,
        'errors': errors,
    }
