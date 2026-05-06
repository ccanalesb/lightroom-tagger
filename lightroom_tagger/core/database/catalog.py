"""Catalog images: library-write discipline, CRUD, and structured queries."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import time
from datetime import datetime

from lightroom_tagger.core.database.catalog_query import (
    _append_query_catalog_image_filters,
    _non_empty_str_list_for_json_array_filter,
    catalog_key_is_primary_grid_row,
    filter_order_keys_in_catalog,
    query_catalog_images,
    query_catalog_images_by_keys,
)
from lightroom_tagger.core.database.catalog_write import _LIBRARY_WRITE_LOCK, library_write
from lightroom_tagger.core.database.db_init import _deserialize_row, _serialize_json

def resolve_filepath(path: str) -> str:
    """Resolve UNC/network paths to local mount points.

    Set NAS_PATH_PREFIX and NAS_MOUNT_POINT env vars to configure.
    Falls back to auto-detecting SMB mounts under /Volumes/.
    Handles case-insensitive server names (NAS vs tnas vs TNAS).
    
    Example: //tnas/ccanales/Foo/bar.jpg -> /Volumes/ccanales/Foo/bar.jpg
    """
    if not path or not path.startswith('//'):
        return path

    prefix = os.getenv('NAS_PATH_PREFIX', '')
    mount = os.getenv('NAS_MOUNT_POINT', '')

    # Parse path: //server/share/rest/of/path
    path_parts = path.lstrip('/').split('/', 2)  # ['server', 'share', 'rest/of/path']
    if len(path_parts) < 2:
        return path
    
    server_name = path_parts[0]  # e.g., "tnas", "NAS", "TNAS"
    share_name = path_parts[1]   # e.g., "ccanales"
    rest_of_path = path_parts[2] if len(path_parts) > 2 else ""
    
    # If we have a configured prefix and mount, check if share names match
    if prefix and mount:
        prefix_parts = prefix.lstrip('/').split('/')
        if len(prefix_parts) >= 2 and prefix_parts[1] == share_name:
            configured = os.path.join(mount, rest_of_path) if rest_of_path else mount
            if os.path.exists(configured):
                return configured

    # Auto-detect: scan /Volumes/ for matching mounts (handles -1 suffix etc.)
    try:
        for name in sorted(os.listdir('/Volumes/'), reverse=True):
            if name.startswith(share_name):
                candidate = os.path.join('/Volumes', name)
                if os.path.ismount(candidate):
                    resolved = os.path.join(candidate, rest_of_path) if rest_of_path else candidate
                    if os.path.exists(resolved):
                        return resolved
    except OSError:
        pass

    # Last resort: return configured path even if it doesn't exist
    if prefix and mount:
        prefix_parts = prefix.lstrip('/').split('/')
        if len(prefix_parts) >= 2 and prefix_parts[1] == share_name:
            return os.path.join(mount, rest_of_path) if rest_of_path else mount

    return path

# ---------------------------------------------------------------------------
# Images (catalog)
# ---------------------------------------------------------------------------

def generate_key(record: dict) -> str:
    """Generate unique key from record: {date_taken}_{filename}

    Date portion matches ``lightroom.reader.generate_record_key`` (YYYY-MM-DD only).
    """
    date_taken = record.get('date_taken', 'unknown')
    date_part = date_taken[:10] if date_taken else 'unknown'
    filename = record.get('filename', 'unknown')
    return f"{date_part}_{filename}"

def store_image(db: sqlite3.Connection, record: dict) -> str:
    """Store image record, return key. Upsert if exists."""
    key = generate_key(record)
    record['key'] = key

    params = {
        'key': key,
        'id': record.get('id'),
        'filename': record.get('filename', ''),
        'filepath': record.get('filepath', ''),
        'date_taken': record.get('date_taken', ''),
        'rating': record.get('rating', 0),
        'pick': record.get('pick', 0),
        'color_label': record.get('color_label', ''),
        'keywords': _serialize_json(record.get('keywords', [])),
        'title': record.get('title', ''),
        'caption': record.get('caption', ''),
        'description': record.get('description', ''),
        'copyright': record.get('copyright', ''),
        'camera_make': record.get('camera_make', ''),
        'camera_model': record.get('camera_model', ''),
        'lens': record.get('lens', ''),
        'focal_length': record.get('focal_length', ''),
        'aperture': record.get('aperture', ''),
        'shutter_speed': record.get('shutter_speed', ''),
        'iso': record.get('iso', ''),
        'gps_latitude': record.get('gps_latitude'),
        'gps_longitude': record.get('gps_longitude'),
        'width': record.get('width'),
        'height': record.get('height'),
        'file_size': record.get('file_size'),
        'instagram_posted': int(bool(record.get('instagram_posted', False))),
        'instagram_post_date': record.get('instagram_post_date'),
        'instagram_url': record.get('instagram_url'),
        'instagram_index': record.get('instagram_index', 0),
        'image_hash': record.get('image_hash'),
        'analyzed_at': record.get('analyzed_at'),
        'phash': record.get('phash'),
        'exif': _serialize_json(record.get('exif')),
        'catalog_path': record.get('catalog_path', ''),
    }

    db.execute("""
        INSERT INTO images (key, id, filename, filepath, date_taken, rating, pick,
            color_label, keywords, title, caption, description, copyright,
            camera_make, camera_model, lens, focal_length, aperture,
            shutter_speed, iso, gps_latitude, gps_longitude, width, height,
            file_size, instagram_posted, instagram_post_date, instagram_url,
            instagram_index, image_hash, analyzed_at, phash, exif, catalog_path)
        VALUES (:key, :id, :filename, :filepath, :date_taken, :rating, :pick,
            :color_label, :keywords, :title, :caption, :description, :copyright,
            :camera_make, :camera_model, :lens, :focal_length, :aperture,
            :shutter_speed, :iso, :gps_latitude, :gps_longitude, :width, :height,
            :file_size, :instagram_posted, :instagram_post_date, :instagram_url,
            :instagram_index, :image_hash, :analyzed_at, :phash, :exif, :catalog_path)
        ON CONFLICT(key) DO UPDATE SET
            id=excluded.id,
            filename=excluded.filename, filepath=excluded.filepath,
            date_taken=excluded.date_taken, rating=excluded.rating,
            pick=excluded.pick, color_label=excluded.color_label,
            keywords=excluded.keywords, title=excluded.title,
            caption=excluded.caption, description=excluded.description,
            copyright=excluded.copyright, camera_make=excluded.camera_make,
            camera_model=excluded.camera_model, lens=excluded.lens,
            focal_length=excluded.focal_length, aperture=excluded.aperture,
            shutter_speed=excluded.shutter_speed, iso=excluded.iso,
            gps_latitude=excluded.gps_latitude, gps_longitude=excluded.gps_longitude,
            width=excluded.width, height=excluded.height,
            file_size=excluded.file_size, image_hash=excluded.image_hash,
            analyzed_at=excluded.analyzed_at, phash=excluded.phash,
            exif=excluded.exif, catalog_path=excluded.catalog_path
    """, params)
    db.commit()
    return key

def store_images_batch(db: sqlite3.Connection, records: list[dict]) -> int:
    """Store multiple records, return count."""
    count = 0
    for record in records:
        store_image(db, record)
        count += 1
    return count

def get_image(db: sqlite3.Connection, key: str) -> dict | None:
    """Get image by key."""
    row = db.execute("SELECT * FROM images WHERE key = ?", (key,)).fetchone()
    return _deserialize_row(row) if row else None

def search_by_keyword(db: sqlite3.Connection, keyword: str) -> list[dict]:
    """Search images by keyword in keywords, filename, title, description."""
    pattern = f'%{keyword}%'
    rows = db.execute("""
        SELECT * FROM images
        WHERE keywords LIKE ? COLLATE NOCASE
           OR filename LIKE ? COLLATE NOCASE
           OR title LIKE ? COLLATE NOCASE
           OR description LIKE ? COLLATE NOCASE
    """, (pattern, pattern, pattern, pattern)).fetchall()
    return [_deserialize_row(r) for r in rows]

def search_by_rating(db: sqlite3.Connection, min_rating: int = 0) -> list[dict]:
    """Search images by minimum rating."""
    rows = db.execute("SELECT * FROM images WHERE rating >= ?", (min_rating,)).fetchall()
    return [_deserialize_row(r) for r in rows]

def search_by_date(db: sqlite3.Connection, start_date: str, end_date: str = None) -> list[dict]:
    """Search images by date range (ISO format)."""
    if end_date:
        rows = db.execute(
            "SELECT * FROM images WHERE date_taken >= ? AND date_taken <= ?",
            (start_date, end_date)
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM images WHERE date_taken >= ?", (start_date,)
        ).fetchall()
    return [_deserialize_row(r) for r in rows]

def search_by_color_label(db: sqlite3.Connection, label: str) -> list[dict]:
    """Search images by color label (case-insensitive)."""
    rows = db.execute(
        "SELECT * FROM images WHERE LOWER(color_label) = LOWER(?)", (label,)
    ).fetchall()
    return [_deserialize_row(r) for r in rows]

def get_all_images(db: sqlite3.Connection) -> list[dict]:
    """Get all images."""
    rows = db.execute("SELECT * FROM images").fetchall()
    return [_deserialize_row(r) for r in rows]

def get_image_count(db: sqlite3.Connection) -> int:
    """Get total image count."""
    return db.execute("SELECT COUNT(*) as cnt FROM images").fetchone()['cnt']

def delete_image(db: sqlite3.Connection, key: str) -> bool:
    """Delete image by key."""
    cursor = db.execute("DELETE FROM images WHERE key = ?", (key,))
    db.commit()
    return cursor.rowcount > 0

def clear_all(db: sqlite3.Connection) -> int:
    """Clear all images. Returns count."""
    count = get_image_count(db)
    db.execute("DELETE FROM images")
    db.commit()
    return count


# ---------------------------------------------------------------------------
# Catalog table helpers (legacy names; aliases for images table)
# ---------------------------------------------------------------------------

def init_catalog_table(db: sqlite3.Connection):
    """No-op: images table is created in init_database."""
    pass


def store_catalog_image(db: sqlite3.Connection, record: dict) -> str:
    """Store catalog image with analysis. Idempotent."""
    key = record.get('key')
    record['analyzed_at'] = datetime.now().isoformat()
    keywords = _serialize_json(record.get('keywords', []))
    exif = _serialize_json(record.get('exif'))

    db.execute("""
        INSERT INTO images (key, filepath, analyzed_at, phash, exif, catalog_path,
            date_taken, filename, rating, keywords, color_label, title, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            analyzed_at=excluded.analyzed_at,
            phash=COALESCE(excluded.phash, images.phash),
            exif=COALESCE(excluded.exif, images.exif),
            catalog_path=COALESCE(excluded.catalog_path, images.catalog_path),
            description=COALESCE(excluded.description, images.description)
    """, (
        key, record.get('filepath'), record['analyzed_at'],
        record.get('phash'), exif, record.get('catalog_path', ''),
        record.get('date_taken', ''), record.get('filename', ''),
        record.get('rating', 0), keywords,
        record.get('color_label', ''), record.get('title', ''),
        record.get('description', ''),
    ))
    db.commit()
    return key


def get_catalog_images_needing_analysis(db: sqlite3.Connection) -> list:
    """Get catalog images without phash."""
    rows = db.execute("SELECT * FROM images WHERE phash IS NULL").fetchall()
    return [_deserialize_row(r) for r in rows]


def get_catalog_images_missing_cache(db: sqlite3.Connection) -> list:
    """Get catalog images without vision cache entries.

    Returns images that either:
    - Don't have a cache entry at all
    - Have a cache entry but the compressed file doesn't exist
    """
    rows = db.execute("""
        SELECT i.* FROM images i
        LEFT JOIN vision_cache vc ON i.key = vc.key
        WHERE vc.key IS NULL OR vc.compressed_path IS NULL
    """).fetchall()

    images = [_deserialize_row(r) for r in rows]

    cached_rows = db.execute("""
        SELECT i.*, vc.compressed_path FROM images i
        INNER JOIN vision_cache vc ON i.key = vc.key
        WHERE vc.compressed_path IS NOT NULL
    """).fetchall()

    for row in cached_rows:
        compressed_path = row.get('compressed_path', '')
        if compressed_path and not os.path.exists(compressed_path):
            images.append(_deserialize_row(row))

    return images


def get_all_catalog_images(db: sqlite3.Connection) -> list:
    """Get all catalog images with resolved file paths."""
    rows = db.execute(
        "SELECT * FROM images ORDER BY date_taken DESC, key DESC"
    ).fetchall()
    images = [_deserialize_row(r) for r in rows]
    for img in images:
        if img.get('filepath'):
            img['filepath'] = resolve_filepath(img['filepath'])
    return images
