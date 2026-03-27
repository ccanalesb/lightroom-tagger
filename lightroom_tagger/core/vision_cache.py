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
    get_vision_cached_image,
    is_vision_cache_valid,
    store_vision_cached_image,
)


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
            return cached['compressed_path']

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
            # Neither conversion nor compression worked; cache original path
            store_vision_cached_image(db, catalog_key, original_path, phash, original_mtime)
            return original_path

        # Use the compressed file (or converted file if compression was no-op)
        source = temp_path if temp_path != viewable_path else viewable_path
        _place_into_cache(source, target_path, temp_files)

        store_vision_cached_image(db, catalog_key, target_path, phash, original_mtime)
        return target_path

    except Exception:
        raise
    finally:
        for tf in temp_files:
            if tf and os.path.exists(tf):
                with contextlib.suppress(BaseException):
                    os.unlink(tf)


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


class InstagramCache:
    """In-memory cache for compressed Instagram images during a single matching run.

    Compresses the Instagram image once and holds it in memory for reuse across
    all candidate comparisons.
    """

    _compressed_path: str | None = None
    _original_path: str | None = None

    def __init__(self, db=None):
        self.db = db

    def compress_instagram_image(self, insta_path: str) -> str | None:
        """Compress Instagram image once and cache for this run.

        Args:
            insta_path: Path to Instagram image

        Returns:
            Path to compressed image
        """
        if self._compressed_path is None or self._original_path != insta_path:
            self._original_path = insta_path
            self._compressed_path = compress_image(insta_path)
        return self._compressed_path

    def cleanup(self):
        """Clean up temp file after matching run.

        Note: We don't delete here because the temp file may still be needed
        by the caller. The temp file will be cleaned up by the OS eventually.
        """
        self._compressed_path = None
        self._original_path = None


def get_cache_stats(db) -> dict:
    """Get vision cache statistics.

    Wrapper around database function for convenience.
    """
    from lightroom_tagger.core.database import get_cache_stats as _get_stats
    return _get_stats(db)
