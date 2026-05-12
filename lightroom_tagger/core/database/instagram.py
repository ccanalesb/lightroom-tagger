"""Instagram-related library DB accessors (dump pipeline, hashed images)."""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timedelta

from .db_init import _deserialize_row, _serialize_json


def update_instagram_status(db: sqlite3.Connection, key: str, posted: bool = True,
                            post_date: str = None, url: str = None, index: int = 0) -> bool:
    """Update Instagram status for an image."""
    cursor = db.execute("""
        UPDATE images SET instagram_posted = ?, instagram_post_date = ?,
            instagram_url = ?, instagram_index = ?
        WHERE key = ?
    """, (int(posted), post_date, url, index, key))
    db.commit()
    return cursor.rowcount > 0


def search_by_instagram_posted(db: sqlite3.Connection, posted: bool = True) -> list[dict]:
    """Search images by Instagram posted status."""
    rows = db.execute(
        "SELECT * FROM images WHERE instagram_posted = ?", (int(posted),)
    ).fetchall()
    return [_deserialize_row(r) for r in rows]


def get_images_without_hash(db: sqlite3.Connection) -> list[dict]:
    """Get all images that don't have a computed hash yet."""
    rows = db.execute(
        "SELECT * FROM images WHERE image_hash IS NULL"
    ).fetchall()
    return [_deserialize_row(r) for r in rows]


def update_image_hash(db: sqlite3.Connection, key: str, image_hash: str) -> bool:
    """Update the image hash for an image."""
    cursor = db.execute(
        "UPDATE images SET image_hash = ? WHERE key = ?", (image_hash, key)
    )
    db.commit()
    return cursor.rowcount > 0


def batch_update_hashes(db: sqlite3.Connection, updates: list[dict]) -> int:
    """Batch update image hashes."""
    count = 0
    for update in updates:
        key = update.get('key')
        image_hash = update.get('image_hash')
        if key and image_hash and update_image_hash(db, key, image_hash):
            count += 1
    return count



# ---------------------------------------------------------------------------
# Instagram dump media
# ---------------------------------------------------------------------------

def init_instagram_dump_table(db: sqlite3.Connection):
    """No-op: table is created in init_database."""
    pass


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


def get_dump_media_by_hash(db: sqlite3.Connection, image_hash: str) -> list:
    """Get Instagram dump media by image hash."""
    rows = db.execute(
        "SELECT * FROM instagram_dump_media WHERE image_hash = ?", (image_hash,)
    ).fetchall()
    return [_deserialize_row(r) for r in rows]


_VIDEO_EXTENSIONS_CLAUSE = (
    "LOWER(file_path) NOT LIKE '%.mp4' AND "
    "LOWER(file_path) NOT LIKE '%.mov' AND "
    "LOWER(file_path) NOT LIKE '%.avi' AND "
    "LOWER(file_path) NOT LIKE '%.mkv'"
)

# Same exclusions as :data:`_VIDEO_EXTENSIONS_CLAUSE` for ``instagram_dump_media``
# queries that alias the table as ``m``.
_INSTAGRAM_DUMP_CLIP_VIDEO_GUARD = _VIDEO_EXTENSIONS_CLAUSE.replace(
    "file_path", "m.file_path"
)


def get_unprocessed_dump_media(db: sqlite3.Connection, limit: int = None,
                                run_start: str = None,
                                include_processed: bool = False) -> list:
    """Get Instagram dump media for matching.

    Args:
        run_start: ISO timestamp; skip images already attempted in this run
                   (last_attempted_at >= run_start).
        include_processed: If True, also return already-processed rows.
    """
    clauses: list[str] = [_VIDEO_EXTENSIONS_CLAUSE]
    params: list = []
    if not include_processed:
        clauses.append("processed = 0")
        clauses.append(
            "media_key NOT IN "
            "(SELECT insta_key FROM matches WHERE validated_at IS NOT NULL)"
        )
    if run_start:
        clauses.append("(last_attempted_at IS NULL OR last_attempted_at < ?)")
        params.append(run_start)
    where = " AND ".join(clauses) if clauses else "1=1"
    sql = f"SELECT * FROM instagram_dump_media WHERE {where} ORDER BY date_folder DESC, media_key DESC"
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    rows = db.execute(sql, params).fetchall()
    return [_deserialize_row(r) for r in rows]


def get_instagram_by_date_filter(db: sqlite3.Connection, month: str = None,
                                  year: str = None, last_months: int = None,
                                  run_start: str = None,
                                  include_processed: bool = False) -> list:
    """Get Instagram dump media filtered by date.

    Args:
        run_start: ISO timestamp; skip images already attempted in this run.
        include_processed: If True, also return already-processed rows.
    """
    clauses: list[str] = [_VIDEO_EXTENSIONS_CLAUSE]
    params: list = []
    if not include_processed:
        clauses.append("processed = 0")
        clauses.append(
            "media_key NOT IN "
            "(SELECT insta_key FROM matches WHERE validated_at IS NOT NULL)"
        )
    if run_start:
        clauses.append("(last_attempted_at IS NULL OR last_attempted_at < ?)")
        params.append(run_start)

    if month:
        clauses.append("date_folder = ?")
        params.append(month)
    elif year:
        clauses.append("date_folder LIKE ?")
        params.append(f'{year}%')
    elif last_months:
        from_date = (datetime.now() - timedelta(days=last_months * 30)).strftime('%Y%m')
        clauses.append("date_folder >= ?")
        params.append(from_date)

    where = " AND ".join(clauses) if clauses else "1=1"
    rows = db.execute(f"SELECT * FROM instagram_dump_media WHERE {where} ORDER BY date_folder DESC, media_key DESC", params).fetchall()
    return [_deserialize_row(r) for r in rows]


def list_comparison_pool_report_targets(
    db: sqlite3.Connection,
    *,
    month: str | None = None,
    job_id: str | None = None,
    media_key: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Unmatched attempted dump rows eligible for comparison-pool reports."""
    clauses = [
        "processed = 0",
        "last_attempted_at IS NOT NULL",
    ]
    params: dict[str, object] = {}
    if month is not None:
        clauses.append("date_folder = :month")
        params["month"] = month
    if media_key is not None:
        clauses.append("media_key = :media_key")
        params["media_key"] = media_key
    if job_id is not None:
        clauses.append(
            "media_key IN ("
            "SELECT DISTINCT insta_key "
            "FROM comparison_pool_snapshots "
            "WHERE source_job_id = :job_id"
            ")"
        )
        params["job_id"] = job_id

    sql = (
        "SELECT * FROM instagram_dump_media "
        f"WHERE {' AND '.join(clauses)} "
        "ORDER BY last_attempted_at DESC"
    )
    if limit is not None:
        sql += " LIMIT :limit"
        params["limit"] = int(limit)

    rows = db.execute(sql, params).fetchall()
    return [_deserialize_row(dict(r)) for r in rows]


def mark_dump_media_processed(db: sqlite3.Connection, media_key: str,
                               matched_catalog_key: str = None,
                               vision_result: str = None,
                               vision_score: float = None) -> bool:
    """Mark Instagram dump media as processed with match results."""
    cursor = db.execute("""
        UPDATE instagram_dump_media SET
            processed = 1, matched_catalog_key = ?, vision_result = ?,
            vision_score = ?, processed_at = ?
        WHERE media_key = ?
    """, (matched_catalog_key, vision_result, vision_score,
          datetime.now().isoformat(), media_key))
    db.commit()
    return cursor.rowcount > 0


def mark_dump_media_attempted(db: sqlite3.Connection, media_key: str,
                               vision_result: str = None,
                               vision_score: float = None) -> bool:
    """Record an attempt without marking as permanently processed.

    Stores the best vision result for debugging and sets last_attempted_at
    so the current run can skip it. Does NOT set processed=1.
    """
    cursor = db.execute("""
        UPDATE instagram_dump_media SET
            last_attempted_at = ?,
            vision_result = COALESCE(?, vision_result),
            vision_score = COALESCE(?, vision_score)
        WHERE media_key = ?
    """, (datetime.now().isoformat(), vision_result, vision_score, media_key))
    db.commit()
    return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# Instagram images (legacy crawled)
# ---------------------------------------------------------------------------

def init_instagram_table(db: sqlite3.Connection):
    """No-op: table is created in init_database."""
    pass


def _instagram_row_key(local_path: str | None, post_url: str, filename: str) -> str:
    """Stable primary key for instagram_images (new rows)."""
    basis = (local_path or "").strip() or f"{post_url}|{filename}"
    return "insta_" + hashlib.sha256(basis.encode("utf-8", errors="replace")).hexdigest()


def store_instagram_image(db: sqlite3.Connection, record: dict) -> str:
    """Store Instagram image with analysis. Idempotent by local_path."""
    local_path = record.get('local_path')
    post_url = record.get('post_url', '')
    filename = record.get('filename', '')
    key = None
    if local_path:
        row = db.execute(
            "SELECT key FROM instagram_images WHERE local_path = ? LIMIT 1",
            (local_path,),
        ).fetchone()
        if row:
            key = row["key"]
    if key is None:
        key = _instagram_row_key(local_path, post_url, filename)
    record['key'] = key
    record['crawled_at'] = datetime.now().isoformat()

    exif = _serialize_json(record.get('exif'))

    db.execute("""
        INSERT INTO instagram_images (key, local_path, post_url, filename, description,
            image_hash, instagram_folder, crawled_at, phash, exif)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            local_path=excluded.local_path, post_url=excluded.post_url,
            filename=excluded.filename, description=excluded.description,
            image_hash=excluded.image_hash, instagram_folder=excluded.instagram_folder,
            crawled_at=excluded.crawled_at,
            phash=COALESCE(excluded.phash, instagram_images.phash),
            exif=COALESCE(excluded.exif, instagram_images.exif)
    """, (
        key, local_path, post_url, filename, record.get('description'),
        record.get('image_hash'), record.get('instagram_folder'),
        record['crawled_at'], record.get('phash'), exif,
    ))
    db.commit()
    return key


def get_instagram_images_needing_analysis(db: sqlite3.Connection) -> list:
    """Get Instagram images without phash."""
    rows = db.execute(
        "SELECT * FROM instagram_images WHERE phash IS NULL"
    ).fetchall()
    return [_deserialize_row(r) for r in rows]
