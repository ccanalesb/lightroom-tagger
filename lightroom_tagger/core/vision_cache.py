"""Vision image caching module for efficient re-compression.

This module provides caching for compressed images used in vision comparison,
eliminating redundant compression of the same images across multiple matching runs.
"""

import contextlib
import os

from lightroom_tagger.core.analyzer import compress_image, compute_phash
from lightroom_tagger.core.config import load_config
from lightroom_tagger.core.database import (
    get_vision_cached_image,
    is_vision_cache_valid,
    store_vision_cached_image,
)


def get_or_create_cached_image(db, catalog_key: str, original_path: str) -> str | None:
    """Get compressed image path from cache or create it atomically.

    Uses file modification time for cache invalidation. Compresses to temp file first,
    then atomically moves to final location to prevent corruption.

    Args:
        db: TinyDB instance
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

    # Compress to temp file first (atomic write pattern)
    try:
        temp_path = compress_image(original_path)
        if temp_path == original_path:
            # Compression failed or not needed, use original
            return original_path

        # Atomic move to final location using os.replace to prevent EXDEV errors
        os.replace(temp_path, target_path)

        # Compute pHash and get mtime
        phash = compute_phash(original_path)
        original_mtime = os.path.getmtime(original_path)

        # Store in database
        store_vision_cached_image(db, catalog_key, target_path, phash or '', original_mtime)

        return target_path

    except Exception:
        # Clean up temp file if exists
        if 'temp_path' in dir() and os.path.exists(temp_path):
            with contextlib.suppress(BaseException):
                os.unlink(temp_path)
        raise


def get_cached_phash(db, catalog_key: str) -> str | None:
    """Get pre-computed pHash from cache.

    Args:
        db: TinyDB instance
        catalog_key: Key of catalog image

    Returns:
        Pre-computed pHash string, or None if not cached
    """
    cached = get_vision_cached_image(db, catalog_key)
    return cached.get('phash') if cached else None


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
