"""Tests for vision image cache (size limits and invalidation)."""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from lightroom_tagger.core.database import (
    VISION_CACHE_OVERSIZED_SENTINEL,
    get_vision_cached_image,
    init_database,
    is_vision_cache_valid,
    store_vision_cached_image,
)
from lightroom_tagger.core import vision_cache as vc


@pytest.fixture
def temp_db(tmp_path):
    db_path = str(tmp_path / "lib.db")
    return init_database(db_path)


def test_get_or_create_returns_none_when_uncompressed_file_exceeds_max_kb(temp_db, tmp_path):
    """No conversion/compression and file > MAX_CACHED_IMAGE_KB → None + oversized sentinel row."""
    fd, huge = tempfile.mkstemp(suffix=".jpg", dir=tmp_path)
    os.write(fd, b"x" * (600 * 1024))
    os.close(fd)
    cache_dir = str(tmp_path / "cache")
    os.makedirs(cache_dir, exist_ok=True)

    with patch.object(vc, "load_config") as cfg:
        m = MagicMock()
        m.vision_cache_enabled = True
        m.vision_cache_dir = cache_dir
        cfg.return_value = m
        with patch("lightroom_tagger.core.vision_cache.compress_image", return_value=huge):
            with patch("lightroom_tagger.core.vision_cache.get_viewable_path", return_value=huge):
                with patch("lightroom_tagger.core.vision_cache.compute_phash", return_value="ph"):
                    out = vc.get_or_create_cached_image(temp_db, "key-huge", huge)

    assert out is None
    row = get_vision_cached_image(temp_db, "key-huge")
    assert row["compressed_path"] == VISION_CACHE_OVERSIZED_SENTINEL
    os.unlink(huge)


def test_get_or_create_returns_cache_path_when_compression_small(temp_db, tmp_path):
    """Successful compression under the cap returns the cache JPEG path."""
    fd, orig = tempfile.mkstemp(suffix=".jpg", dir=tmp_path)
    os.write(fd, b"orig")
    os.close(fd)

    fd2, compressed = tempfile.mkstemp(suffix=".jpg", dir=tmp_path)
    os.write(fd2, b"y" * 4000)
    os.close(fd2)

    cache_dir = str(tmp_path / "cache")
    os.makedirs(cache_dir, exist_ok=True)

    with patch.object(vc, "load_config") as cfg:
        m = MagicMock()
        m.vision_cache_enabled = True
        m.vision_cache_dir = cache_dir
        cfg.return_value = m
        with patch("lightroom_tagger.core.vision_cache.compress_image", return_value=compressed):
            with patch("lightroom_tagger.core.vision_cache.get_viewable_path", return_value=orig):
                with patch("lightroom_tagger.core.vision_cache.compute_phash", return_value="phash1"):
                    out = vc.get_or_create_cached_image(temp_db, "key-ok", orig)

    assert out is not None
    assert out.endswith(".jpg")
    assert os.path.isfile(out)
    assert os.path.getsize(out) / 1024 <= vc.MAX_CACHED_IMAGE_KB
    row = get_vision_cached_image(temp_db, "key-ok")
    assert row["compressed_path"] == out
    os.unlink(orig)


def test_is_vision_cache_invalid_when_raw_cached_as_original_path(temp_db, tmp_path):
    """Stale rows that stored the RAW file path as compressed_path are invalidated."""
    p = tmp_path / "old.sr2"
    p.write_bytes(b"\0")
    p = str(p)
    mtime = os.path.getmtime(p)
    store_vision_cached_image(temp_db, "sr2-key", p, "ph", mtime)
    assert is_vision_cache_valid(temp_db, "sr2-key", p) is False


def test_is_vision_cache_invalid_when_raw_has_oversized_sentinel(temp_db, tmp_path):
    """RAW + __oversized__ sentinel is invalidated so conversion can be retried."""
    raw = tmp_path / "retry.sr2"
    raw.write_bytes(b"\0")
    p = str(raw)
    mtime = os.path.getmtime(p)
    store_vision_cached_image(temp_db, "sr2-retry", VISION_CACHE_OVERSIZED_SENTINEL, None, mtime)
    assert is_vision_cache_valid(temp_db, "sr2-retry", p) is False


def test_oversized_sentinel_still_valid_for_non_raw(temp_db, tmp_path):
    """Non-RAW oversized sentinel remains valid on mtime match (no endless retries)."""
    jpg = tmp_path / "big.jpg"
    jpg.write_bytes(b"x")
    p = str(jpg)
    mtime = os.path.getmtime(p)
    store_vision_cached_image(temp_db, "jpg-big", VISION_CACHE_OVERSIZED_SENTINEL, None, mtime)
    assert is_vision_cache_valid(temp_db, "jpg-big", p) is True


def test_warm_vision_cache_processes_missing_cache_entries(temp_db, tmp_path):
    """Catalog images missing from cache are warmed and counted as processed."""
    img_path = tmp_path / "photo.jpg"
    img_path.write_bytes(b"jpeg")
    temp_db.execute(
        "INSERT INTO images (key, filepath, date_taken, filename) VALUES (?, ?, ?, ?)",
        ("key-warm", str(img_path), "2020-01-01", "photo.jpg"),
    )
    temp_db.commit()

    with patch("lightroom_tagger.core.vision_cache.resolve_catalog_path", return_value=str(img_path)):
        with patch.object(vc, "get_or_create_cached_image", return_value="/cache/key-warm.jpg") as mock_cache:
            result = vc.warm_vision_cache(temp_db, limit=None)

    assert result == {"processed": 1, "skipped": 0, "errors": 0}
    mock_cache.assert_called_once_with(temp_db, "key-warm", str(img_path))


def test_warm_vision_cache_skips_unresolvable_paths(temp_db):
    """Unresolvable or missing file paths are skipped without warming."""
    temp_db.execute(
        "INSERT INTO images (key, filepath, date_taken, filename) VALUES (?, ?, ?, ?)",
        ("key-missing", "/nonexistent/path.jpg", "2020-01-01", "x.jpg"),
    )
    temp_db.commit()

    with patch("lightroom_tagger.core.vision_cache.resolve_catalog_path", return_value=""):
        with patch.object(vc, "get_or_create_cached_image") as mock_cache:
            result = vc.warm_vision_cache(temp_db, limit=None)

    assert result == {"processed": 0, "skipped": 1, "errors": 0}
    mock_cache.assert_not_called()


def test_warm_vision_cache_honors_limit(temp_db, tmp_path):
    """Limit caps how many missing-cache images are processed."""
    for i in range(5):
        img_path = tmp_path / f"p{i}.jpg"
        img_path.write_bytes(b"x")
        temp_db.execute(
            "INSERT INTO images (key, filepath, date_taken, filename) VALUES (?, ?, ?, ?)",
            (f"key{i}", str(img_path), "2020-01-01", f"p{i}.jpg"),
        )
    temp_db.commit()

    with patch("lightroom_tagger.core.vision_cache.resolve_catalog_path", side_effect=lambda fp: fp):
        with patch.object(vc, "get_or_create_cached_image", return_value="/cache/x.jpg") as mock_cache:
            result = vc.warm_vision_cache(temp_db, limit=2)

    assert result == {"processed": 2, "skipped": 0, "errors": 0}
    assert mock_cache.call_count == 2


def test_resolve_vision_image_falls_back_to_cache_when_original_missing(temp_db, tmp_path):
    """Original unreachable (e.g. unmounted NAS) → use the pre-existing cached JPEG."""
    cached = tmp_path / "cache" / "k1.jpg"
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(b"jpegbytes")
    store_vision_cached_image(temp_db, "k1", str(cached), "phash", 123.0)

    missing_original = str(tmp_path / "nas" / "does_not_exist.ARW")
    path, silent = vc.resolve_vision_image(temp_db, "k1", missing_original)

    assert path == str(cached)
    assert silent is True


def test_resolve_vision_image_skips_when_original_missing_and_no_cache(temp_db, tmp_path):
    """No original and no cache → (None, False) so the caller skips cleanly."""
    path, silent = vc.resolve_vision_image(
        temp_db, "nokey", str(tmp_path / "gone.ARW")
    )
    assert path is None
    assert silent is False


def test_resolve_vision_image_no_cache_fallback_for_oversized_sentinel(temp_db, tmp_path):
    """An oversized-sentinel cache row is not a usable image when original is gone."""
    store_vision_cached_image(temp_db, "big", VISION_CACHE_OVERSIZED_SENTINEL, None, 1.0)
    path, silent = vc.resolve_vision_image(temp_db, "big", str(tmp_path / "gone.ARW"))
    assert path is None
    assert silent is False


def test_resolve_vision_image_skips_when_reachable_but_unpreparable(temp_db, tmp_path):
    """Reachable original with no usable compressed image → skip, not raw original."""
    original = tmp_path / "scan.tif"
    original.write_bytes(b"tiff")
    with patch.object(vc, "get_or_create_cached_image", return_value=None):
        path, silent = vc.resolve_vision_image(temp_db, "scan-key", str(original))
    assert path is None
    assert silent is False
    assert path != str(original)


def test_resolve_vision_image_unreachable_and_unpreparable_match(temp_db, tmp_path):
    """Unreachable and reachable-but-unpreparable both yield no usable image."""
    missing = str(tmp_path / "gone.tif")
    reachable = tmp_path / "bad.tif"
    reachable.write_bytes(b"tiff")

    with patch.object(vc, "get_or_create_cached_image", return_value=None):
        reachable_path, reachable_silent = vc.resolve_vision_image(
            temp_db, "k", str(reachable),
        )
    missing_path, missing_silent = vc.resolve_vision_image(temp_db, "k", missing)

    assert reachable_path is None
    assert missing_path is None
    assert reachable_silent is False
    assert missing_silent is False


def test_resolve_vision_image_small_original_still_silent_compressed(temp_db, tmp_path):
    """Small files stored as-is in cache still resolve with silent_compression=True."""
    small = tmp_path / "tiny.jpg"
    small.write_bytes(b"jpeg")
    with patch.object(vc, "get_or_create_cached_image", return_value=str(small)):
        path, silent = vc.resolve_vision_image(temp_db, "tiny", str(small))
    assert path == str(small)
    assert silent is True


def test_get_or_create_16_bit_tiff_caches_jpeg_under_ceiling(temp_db, tmp_path):
    """16-bit TIFF source produces a normal cache entry, not the oversized sentinel."""
    from PIL import Image

    tiff = tmp_path / "scan.tif"
    img = Image.new('I;16', (800, 600))
    px = img.load()
    for y in range(img.height):
        for x in range(img.width):
            px[x, y] = (x * 257 + y * 131) % 65536
    img.save(tiff, 'TIFF')

    cache_dir = str(tmp_path / "cache")
    os.makedirs(cache_dir, exist_ok=True)

    with patch.object(vc, "load_config") as cfg:
        m = MagicMock()
        m.vision_cache_enabled = True
        m.vision_cache_dir = cache_dir
        cfg.return_value = m
        out = vc.get_or_create_cached_image(temp_db, "scan-key", str(tiff))

    assert out is not None
    assert out.endswith(".jpg")
    assert os.path.getsize(out) / 1024 <= vc.MAX_CACHED_IMAGE_KB
    row = get_vision_cached_image(temp_db, "scan-key")
    assert row["compressed_path"] == out
    assert row["compressed_path"] != VISION_CACHE_OVERSIZED_SENTINEL


def test_get_or_create_records_oversized_after_successful_compression(temp_db, tmp_path):
    """Compression that succeeds but exceeds the ceiling still records oversized sentinel."""
    fd, orig = tempfile.mkstemp(suffix=".jpg", dir=tmp_path)
    os.write(fd, b"orig")
    os.close(fd)

    fd2, compressed = tempfile.mkstemp(suffix=".jpg", dir=tmp_path)
    os.write(fd2, b"y" * (600 * 1024))
    os.close(fd2)

    cache_dir = str(tmp_path / "cache")
    os.makedirs(cache_dir, exist_ok=True)

    with patch.object(vc, "load_config") as cfg:
        m = MagicMock()
        m.vision_cache_enabled = True
        m.vision_cache_dir = cache_dir
        cfg.return_value = m
        with patch("lightroom_tagger.core.vision_cache.compress_image", return_value=compressed):
            with patch("lightroom_tagger.core.vision_cache.get_viewable_path", return_value=orig):
                with patch("lightroom_tagger.core.vision_cache.compute_phash", return_value="ph"):
                    out = vc.get_or_create_cached_image(temp_db, "too-big", orig)

    assert out is None
    row = get_vision_cached_image(temp_db, "too-big")
    assert row["compressed_path"] == VISION_CACHE_OVERSIZED_SENTINEL
    os.unlink(orig)
