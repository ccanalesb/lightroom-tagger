"""Read/write helpers for ``instagram_dump_media`` rows (describe/score paths only)."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from .db_init import _deserialize_row, _serialize_json


def store_instagram_dump_media(db: sqlite3.Connection, record: dict) -> str:
    """Store Instagram dump media record. Idempotent by media_key."""
    media_key = record.get('media_key')
    if not media_key:
        raise ValueError("media_key is required")

    record.setdefault('processed', False)
    record.setdefault('matched_catalog_key', None)
    record.setdefault('vision_result', None)
    record.setdefault('vision_score', None)
    record.setdefault('processed_at', None)
    record.setdefault('added_at', datetime.now().isoformat())
    record.setdefault('exif_data', None)
    record.setdefault('post_url', None)
    record.setdefault('image_hash', None)

    exif_data = _serialize_json(record.get('exif_data'))

    db.execute("""
        INSERT INTO instagram_dump_media
            (media_key, file_path, filename, date_folder, caption, created_at,
             exif_data, post_url, image_hash, processed, matched_catalog_key,
             vision_result, vision_score, processed_at, added_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(media_key) DO UPDATE SET
            file_path=COALESCE(excluded.file_path, instagram_dump_media.file_path),
            filename=COALESCE(excluded.filename, instagram_dump_media.filename),
            date_folder=COALESCE(excluded.date_folder, instagram_dump_media.date_folder),
            caption=COALESCE(excluded.caption, instagram_dump_media.caption),
            exif_data=COALESCE(excluded.exif_data, instagram_dump_media.exif_data),
            post_url=COALESCE(excluded.post_url, instagram_dump_media.post_url),
            image_hash=COALESCE(excluded.image_hash, instagram_dump_media.image_hash)
    """, (
        media_key, record.get('file_path'), record.get('filename'),
        record.get('date_folder'), record.get('caption'),
        record.get('created_at'), exif_data, record.get('post_url'),
        record.get('image_hash'), int(bool(record.get('processed', False))),
        record.get('matched_catalog_key'), record.get('vision_result'),
        record.get('vision_score'), record.get('processed_at'),
        record.get('added_at'),
    ))
    db.commit()
    return media_key


def get_instagram_dump_media(db: sqlite3.Connection, media_key: str) -> dict | None:
    """Get Instagram dump media by key."""
    row = db.execute(
        "SELECT * FROM instagram_dump_media WHERE media_key = ?", (media_key,)
    ).fetchone()
    return _deserialize_row(row) if row else None


def get_instagram_dump_media_filtered(
    db: sqlite3.Connection,
    *,
    processed: bool | None = None,
    matched: bool | None = None,
) -> list[dict]:
    """Dump-media rows with optional ``processed`` / ``matched_catalog_key`` filters."""
    clauses: list[str] = []
    params: list = []
    if processed is True:
        clauses.append("processed = 1")
    elif processed is False:
        clauses.append("processed = 0")
    if matched is True:
        clauses.append("matched_catalog_key IS NOT NULL")
    elif matched is False:
        clauses.append("matched_catalog_key IS NULL")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.execute(f"SELECT * FROM instagram_dump_media {where}", params).fetchall()
    return [_deserialize_row(r) for r in rows]
