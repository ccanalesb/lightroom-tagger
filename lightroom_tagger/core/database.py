import hashlib
import json
import os
import sqlite3
from datetime import datetime, timedelta


def resolve_filepath(path: str) -> str:
    """Resolve UNC/network paths to local mount points.

    Set NAS_PATH_PREFIX and NAS_MOUNT_POINT env vars to configure.
    Falls back to auto-detecting SMB mounts under /Volumes/.
    """
    if not path or not path.startswith('//'):
        return path

    prefix = os.getenv('NAS_PATH_PREFIX', '')
    mount = os.getenv('NAS_MOUNT_POINT', '')

    if not prefix:
        parts = path.lstrip('/').split('/')
        if len(parts) >= 2:
            prefix = f'//{parts[0]}/{parts[1]}'

    if not mount and prefix:
        share_name = prefix.rstrip('/').split('/')[-1]
        try:
            for name in sorted(os.listdir('/Volumes/'), reverse=True):
                if name.startswith(share_name):
                    candidate = os.path.join('/Volumes', name)
                    if os.path.ismount(candidate):
                        mount = candidate
                        break
        except OSError:
            pass

    if mount and prefix and path.startswith(prefix):
        return path.replace(prefix, mount, 1)

    return path


def _dict_factory(cursor, row):
    """Convert sqlite3 rows to dicts."""
    fields = [column[0] for column in cursor.description]
    return dict(zip(fields, row))


def _deserialize_row(row: dict) -> dict:
    """Deserialize JSON columns in a row."""
    if not row:
        return row
    for col in ('keywords', 'exif', 'exif_data', 'logs', 'metadata', 'result'):
        val = row.get(col)
        if isinstance(val, str):
            try:
                row[col] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                pass
    if 'instagram_posted' in row:
        row['instagram_posted'] = bool(row['instagram_posted'])
    if 'processed' in row:
        row['processed'] = bool(row['processed'])
    return row


def _serialize_json(value) -> str | None:
    """Serialize a value to JSON string for storage."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value)


def init_database(db_path: str) -> sqlite3.Connection:
    """Initialize SQLite database with WAL mode and schema."""
    os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else '.', exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = _dict_factory
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS images (
            key TEXT PRIMARY KEY,
            id TEXT,
            filename TEXT,
            filepath TEXT,
            date_taken TEXT,
            rating INTEGER DEFAULT 0,
            pick INTEGER DEFAULT 0,
            color_label TEXT DEFAULT '',
            keywords TEXT DEFAULT '[]',
            title TEXT DEFAULT '',
            caption TEXT DEFAULT '',
            description TEXT DEFAULT '',
            copyright TEXT DEFAULT '',
            camera_make TEXT DEFAULT '',
            camera_model TEXT DEFAULT '',
            lens TEXT DEFAULT '',
            focal_length TEXT DEFAULT '',
            aperture TEXT DEFAULT '',
            shutter_speed TEXT DEFAULT '',
            iso TEXT DEFAULT '',
            gps_latitude REAL,
            gps_longitude REAL,
            width INTEGER,
            height INTEGER,
            file_size INTEGER,
            instagram_posted INTEGER DEFAULT 0,
            instagram_post_date TEXT,
            instagram_url TEXT,
            instagram_index INTEGER DEFAULT 0,
            image_hash TEXT,
            analyzed_at TEXT,
            phash TEXT,
            exif TEXT,
            catalog_path TEXT DEFAULT ''
        );

        CREATE INDEX IF NOT EXISTS idx_images_filepath ON images(filepath);
        CREATE INDEX IF NOT EXISTS idx_images_image_hash ON images(image_hash);
        CREATE INDEX IF NOT EXISTS idx_images_date_taken ON images(date_taken);
        CREATE INDEX IF NOT EXISTS idx_images_instagram_posted ON images(instagram_posted);

        CREATE TABLE IF NOT EXISTS instagram_dump_media (
            media_key TEXT PRIMARY KEY,
            file_path TEXT,
            filename TEXT,
            date_folder TEXT,
            caption TEXT,
            created_at TEXT,
            exif_data TEXT,
            post_url TEXT,
            image_hash TEXT,
            processed INTEGER DEFAULT 0,
            matched_catalog_key TEXT,
            vision_result TEXT,
            vision_score REAL,
            processed_at TEXT,
            last_attempted_at TEXT,
            added_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_dump_media_hash ON instagram_dump_media(image_hash);
        CREATE INDEX IF NOT EXISTS idx_dump_media_date ON instagram_dump_media(date_folder);
        CREATE INDEX IF NOT EXISTS idx_dump_media_processed ON instagram_dump_media(processed);
        CREATE INDEX IF NOT EXISTS idx_dump_media_processed_attempted ON instagram_dump_media(processed, last_attempted_at);

        CREATE TABLE IF NOT EXISTS instagram_images (
            key TEXT PRIMARY KEY,
            local_path TEXT,
            post_url TEXT,
            filename TEXT,
            description TEXT,
            image_hash TEXT,
            instagram_folder TEXT,
            crawled_at TEXT,
            phash TEXT,
            exif TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_insta_images_local_path ON instagram_images(local_path);

        CREATE TABLE IF NOT EXISTS matches (
            catalog_key TEXT,
            insta_key TEXT,
            phash_distance INTEGER,
            phash_score REAL,
            desc_similarity REAL,
            vision_result TEXT,
            vision_score REAL,
            total_score REAL,
            matched_at TEXT,
            PRIMARY KEY (catalog_key, insta_key)
        );

        CREATE TABLE IF NOT EXISTS vision_cache (
            key TEXT PRIMARY KEY,
            compressed_path TEXT,
            phash TEXT,
            compressed_at TEXT,
            original_mtime REAL
        );

        CREATE TABLE IF NOT EXISTS vision_comparisons (
            catalog_key TEXT,
            insta_key TEXT,
            result TEXT,
            vision_score REAL,
            compared_at TEXT,
            model_used TEXT,
            PRIMARY KEY (catalog_key, insta_key)
        );

        CREATE TABLE IF NOT EXISTS image_descriptions (
            image_key TEXT PRIMARY KEY,
            image_type TEXT NOT NULL,
            summary TEXT DEFAULT '',
            composition TEXT DEFAULT '{}',
            perspectives TEXT DEFAULT '{}',
            technical TEXT DEFAULT '{}',
            subjects TEXT DEFAULT '[]',
            best_perspective TEXT DEFAULT '',
            model_used TEXT DEFAULT '',
            described_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_desc_image_type ON image_descriptions(image_type);
    """)

    # Migrations for existing databases
    _migrate_add_column(conn, 'instagram_dump_media', 'last_attempted_at', 'TEXT')
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_dump_media_processed_attempted "
        "ON instagram_dump_media(processed, last_attempted_at)"
    )

    conn.commit()
    return conn


def _migrate_add_column(conn: sqlite3.Connection, table: str, column: str, col_type: str):
    """Add a column if it doesn't already exist. Safe to call repeatedly."""
    cols = {row['name'] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


# ---------------------------------------------------------------------------
# Images (catalog)
# ---------------------------------------------------------------------------

def generate_key(record: dict) -> str:
    """Generate unique key from record: {date_taken}_{filename}"""
    date_taken = record.get('date_taken', 'unknown')
    filename = record.get('filename', 'unknown')
    return f"{date_taken}_{filename}"


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
# Catalog table helpers (aliases for images table)
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


def get_all_catalog_images(db: sqlite3.Connection) -> list:
    """Get all catalog images with resolved file paths."""
    rows = db.execute("SELECT * FROM images").fetchall()
    images = [_deserialize_row(r) for r in rows]
    for img in images:
        if img.get('filepath'):
            img['filepath'] = resolve_filepath(img['filepath'])
    return images


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


def get_unprocessed_dump_media(db: sqlite3.Connection, limit: int = None,
                                run_start: str = None) -> list:
    """Get unprocessed Instagram dump media for matching.

    Args:
        run_start: ISO timestamp; skip images already attempted in this run
                   (last_attempted_at >= run_start).
    """
    where = "processed = 0"
    params: list = []
    if run_start:
        where += " AND (last_attempted_at IS NULL OR last_attempted_at < ?)"
        params.append(run_start)
    sql = f"SELECT * FROM instagram_dump_media WHERE {where}"
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    rows = db.execute(sql, params).fetchall()
    return [_deserialize_row(r) for r in rows]


def get_instagram_by_date_filter(db: sqlite3.Connection, month: str = None,
                                  year: str = None, last_months: int = None,
                                  run_start: str = None) -> list:
    """Get unprocessed Instagram dump media filtered by date.

    Args:
        run_start: ISO timestamp; skip images already attempted in this run.
    """
    where = "processed = 0"
    params: list = []
    if run_start:
        where += " AND (last_attempted_at IS NULL OR last_attempted_at < ?)"
        params.append(run_start)

    if month:
        where += " AND date_folder = ?"
        params.append(month)
    elif year:
        where += " AND date_folder LIKE ?"
        params.append(f'{year}%')
    elif last_months:
        from_date = (datetime.now() - timedelta(days=last_months * 30)).strftime('%Y%m')
        where += " AND date_folder >= ?"
        params.append(from_date)

    rows = db.execute(f"SELECT * FROM instagram_dump_media WHERE {where}", params).fetchall()
    return [_deserialize_row(r) for r in rows]


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


# ---------------------------------------------------------------------------
# Matches
# ---------------------------------------------------------------------------

def init_matches_table(db: sqlite3.Connection):
    """No-op: table is created in init_database."""
    pass


def store_match(db: sqlite3.Connection, record: dict) -> str:
    """Store match between catalog and Instagram image."""
    catalog_key = record.get('catalog_key')
    insta_key = record.get('insta_key')
    record['matched_at'] = datetime.now().isoformat()

    db.execute("""
        INSERT INTO matches (catalog_key, insta_key, phash_distance, phash_score,
            desc_similarity, vision_result, vision_score, total_score, matched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(catalog_key, insta_key) DO UPDATE SET
            phash_distance=excluded.phash_distance, phash_score=excluded.phash_score,
            desc_similarity=excluded.desc_similarity, vision_result=excluded.vision_result,
            vision_score=excluded.vision_score, total_score=excluded.total_score,
            matched_at=excluded.matched_at
    """, (
        catalog_key, insta_key, record.get('phash_distance'),
        record.get('phash_score'), record.get('desc_similarity'),
        record.get('vision_result'), record.get('vision_score'),
        record.get('total_score'), record['matched_at'],
    ))
    db.commit()
    return f"{catalog_key} <-> {insta_key}"


# ---------------------------------------------------------------------------
# Vision cache
# ---------------------------------------------------------------------------

def init_vision_cache_table(db: sqlite3.Connection):
    """No-op: table is created in init_database."""
    pass


def init_vision_comparisons_table(db: sqlite3.Connection):
    """No-op: table is created in init_database."""
    pass


def get_vision_cached_image(db: sqlite3.Connection, catalog_key: str) -> dict | None:
    """Get cached compressed image by catalog key."""
    row = db.execute(
        "SELECT * FROM vision_cache WHERE key = ?", (catalog_key,)
    ).fetchone()
    return dict(row) if row else None


def store_vision_cached_image(db: sqlite3.Connection, catalog_key: str,
                               compressed_path: str, phash: str | None,
                               original_mtime: float) -> bool:
    """Store compressed image info in vision cache."""
    db.execute("""
        INSERT INTO vision_cache (key, compressed_path, phash, compressed_at, original_mtime)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            compressed_path=excluded.compressed_path, phash=excluded.phash,
            compressed_at=excluded.compressed_at, original_mtime=excluded.original_mtime
    """, (catalog_key, compressed_path, phash, datetime.now().isoformat(), original_mtime))
    db.commit()
    return True


def is_vision_cache_valid(db: sqlite3.Connection, catalog_key: str,
                           original_path: str) -> bool:
    """Check if cached image is still valid (mtime unchanged)."""
    cached = get_vision_cached_image(db, catalog_key)
    if not cached or not os.path.exists(cached.get('compressed_path', '')):
        return False
    try:
        current_mtime = os.path.getmtime(original_path)
        return cached.get('original_mtime') == current_mtime
    except OSError:
        return False


def get_cache_stats(db: sqlite3.Connection) -> dict:
    """Get vision cache statistics."""
    total = db.execute("SELECT COUNT(*) as cnt FROM images").fetchone()['cnt']
    cached = db.execute("SELECT COUNT(*) as cnt FROM vision_cache").fetchone()['cnt']

    cache_size_bytes = 0
    rows = db.execute("SELECT compressed_path FROM vision_cache").fetchall()
    for row in rows:
        path = row.get('compressed_path', '')
        if path and os.path.exists(path):
            cache_size_bytes += os.path.getsize(path)

    return {
        'total': total,
        'cached': cached,
        'missing': total - cached,
        'cache_size_mb': cache_size_bytes / (1024 * 1024),
    }


# ---------------------------------------------------------------------------
# Vision comparisons
# ---------------------------------------------------------------------------

def get_vision_comparison(db: sqlite3.Connection, catalog_key: str,
                           insta_key: str) -> dict | None:
    """Get cached vision comparison result."""
    row = db.execute(
        "SELECT * FROM vision_comparisons WHERE catalog_key = ? AND insta_key = ?",
        (catalog_key, insta_key)
    ).fetchone()
    return dict(row) if row else None


def store_vision_comparison(db: sqlite3.Connection, catalog_key: str, insta_key: str,
                            result: str, vision_score: float, model_used: str) -> bool:
    """Store vision comparison result in cache. Never expires."""
    db.execute("""
        INSERT INTO vision_comparisons (catalog_key, insta_key, result, vision_score,
            compared_at, model_used)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(catalog_key, insta_key) DO UPDATE SET
            result=excluded.result, vision_score=excluded.vision_score,
            compared_at=excluded.compared_at, model_used=excluded.model_used
    """, (catalog_key, insta_key, result, vision_score,
          datetime.now().isoformat(), model_used))
    db.commit()
    return True


# ---------------------------------------------------------------------------
# Image descriptions
# ---------------------------------------------------------------------------

def init_image_descriptions_table(db: sqlite3.Connection):
    """No-op: table is created in init_database."""
    pass


def store_image_description(db: sqlite3.Connection, record: dict) -> str:
    """Store image description. Idempotent by image_key."""
    image_key = record.get('image_key')
    if not image_key:
        raise ValueError("image_key is required")

    record['described_at'] = datetime.now().isoformat()

    db.execute("""
        INSERT INTO image_descriptions
            (image_key, image_type, summary, composition, perspectives,
             technical, subjects, best_perspective, model_used, described_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(image_key) DO UPDATE SET
            image_type=excluded.image_type, summary=excluded.summary,
            composition=excluded.composition, perspectives=excluded.perspectives,
            technical=excluded.technical, subjects=excluded.subjects,
            best_perspective=excluded.best_perspective, model_used=excluded.model_used,
            described_at=excluded.described_at
    """, (
        image_key, record.get('image_type', ''),
        record.get('summary', ''),
        _serialize_json(record.get('composition', {})),
        _serialize_json(record.get('perspectives', {})),
        _serialize_json(record.get('technical', {})),
        _serialize_json(record.get('subjects', [])),
        record.get('best_perspective', ''),
        record.get('model_used', ''),
        record['described_at'],
    ))
    db.commit()
    return image_key


def get_image_description(db: sqlite3.Connection, image_key: str) -> dict | None:
    """Get description by image key."""
    row = db.execute(
        "SELECT * FROM image_descriptions WHERE image_key = ?", (image_key,)
    ).fetchone()
    if not row:
        return None
    row = dict(row)
    for col in ('composition', 'perspectives', 'technical', 'subjects'):
        val = row.get(col)
        if isinstance(val, str):
            try:
                row[col] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                pass
    return row


def get_undescribed_catalog_images(db: sqlite3.Connection) -> list[dict]:
    """Get catalog images that don't have descriptions yet."""
    rows = db.execute("""
        SELECT i.* FROM images i
        LEFT JOIN image_descriptions d
            ON i.key = d.image_key AND d.image_type = 'catalog'
        WHERE d.image_key IS NULL
    """).fetchall()
    return [_deserialize_row(r) for r in rows]
