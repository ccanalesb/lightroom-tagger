import hashlib
import json
import os
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


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
            # Match found - construct path: /mount/rest
            if rest_of_path:
                return os.path.join(mount, rest_of_path)
            else:
                return mount

    # Auto-detect mount if not configured
    if not mount:
        try:
            for name in sorted(os.listdir('/Volumes/'), reverse=True):
                if name.startswith(share_name):
                    candidate = os.path.join('/Volumes', name)
                    if os.path.ismount(candidate):
                        mount = candidate
                        if rest_of_path:
                            return os.path.join(mount, rest_of_path)
                        else:
                            return mount
        except OSError:
            pass

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


def _perspective_seed_description(markdown: str) -> str:
    """First body line for ``perspectives.description`` when seeding from disk."""
    lines = markdown.splitlines()
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i >= len(lines):
        return ""
    first = lines[i].strip()
    if first.startswith("# ") and not first.startswith("##"):
        i += 1
        while i < len(lines) and not lines[i].strip():
            i += 1
        if i >= len(lines):
            return first.lstrip("#").strip()
        return lines[i].strip()
    return first


def seed_perspectives_from_prompts_dir(
    conn: sqlite3.Connection, prompts_dir: str | None = None
) -> int:
    """Insert default perspective rows from ``prompts/perspectives/*.md`` when the table is empty.

    Default *prompts_dir* is the repo's ``prompts/perspectives`` directory, resolved from this
    module's path: ``Path(__file__).resolve().parents[2] / "prompts" / "perspectives"``
    (repo root → ``prompts`` → ``perspectives``). That matches editable installs where the
    package lives under the project root; callers may pass an absolute path when bundling.

    If ``SELECT COUNT(*) FROM perspectives`` is greater than zero, returns ``0`` without
    reading files (factory seed runs once; DB remains authoritative afterward).

    Returns the number of rows inserted.
    """
    if prompts_dir is None:
        prompts_dir = str(
            Path(__file__).resolve().parents[2] / "prompts" / "perspectives"
        )

    row = conn.execute("SELECT COUNT(*) AS cnt FROM perspectives").fetchone()
    if row is not None and int(row["cnt"]) > 0:
        return 0

    base = Path(prompts_dir)
    if not base.is_dir():
        return 0

    base_resolved = base.resolve()
    inserted = 0
    now = datetime.now(timezone.utc).isoformat()

    for entry in sorted(base_resolved.iterdir(), key=lambda p: p.name):
        if not entry.is_file() or entry.suffix.lower() != ".md":
            continue
        try:
            entry.resolve().relative_to(base_resolved)
        except ValueError:
            continue

        slug = entry.stem
        source_filename = entry.name
        text = entry.read_text(encoding="utf-8")
        display_name = slug.replace("_", " ").title()
        description = _perspective_seed_description(text)

        conn.execute(
            """
            INSERT INTO perspectives (
                slug, display_name, description, prompt_markdown,
                active, source_filename, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 1, ?, ?, ?)
            """,
            (slug, display_name, description, text, source_filename, now, now),
        )
        inserted += 1

    return inserted


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
            model_used TEXT,
            validated_at TEXT,
            rank INTEGER DEFAULT 1,
            PRIMARY KEY (catalog_key, insta_key)
        );

        CREATE TABLE IF NOT EXISTS rejected_matches (
            catalog_key TEXT,
            insta_key TEXT,
            rejected_at TEXT,
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

        CREATE TABLE IF NOT EXISTS perspectives (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            prompt_markdown TEXT NOT NULL DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1,
            source_filename TEXT,
            updated_at TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS image_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_key TEXT NOT NULL,
            image_type TEXT NOT NULL DEFAULT 'catalog',
            perspective_slug TEXT NOT NULL,
            score INTEGER NOT NULL CHECK (score BETWEEN 1 AND 10),
            rationale TEXT NOT NULL DEFAULT '',
            model_used TEXT NOT NULL DEFAULT '',
            prompt_version TEXT NOT NULL DEFAULT '',
            scored_at TEXT NOT NULL,
            is_current INTEGER NOT NULL DEFAULT 1,
            repaired_from_malformed INTEGER NOT NULL DEFAULT 0,
            CONSTRAINT uq_image_scores_versioned
                UNIQUE (image_key, image_type, perspective_slug, prompt_version)
        );

        CREATE INDEX IF NOT EXISTS idx_image_scores_perspective_score
            ON image_scores(perspective_slug, score);
        CREATE INDEX IF NOT EXISTS idx_image_scores_image
            ON image_scores(image_key, image_type);
        CREATE INDEX IF NOT EXISTS idx_image_scores_current
            ON image_scores(image_key, image_type, perspective_slug, is_current);
    """)

    # Migrations for existing databases
    _migrate_add_column(conn, 'instagram_dump_media', 'last_attempted_at', 'TEXT')
    _migrate_add_column(conn, 'matches', 'model_used', 'TEXT')
    _migrate_add_column(conn, 'matches', 'validated_at', 'TEXT')
    _migrate_add_column(conn, 'matches', 'rank', 'INTEGER DEFAULT 1')
    _migrate_add_column(conn, 'matches', 'vision_reasoning', 'TEXT')
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_dump_media_processed_attempted "
        "ON instagram_dump_media(processed, last_attempted_at)"
    )

    # Legacy library DBs: existing `images` tables are not upgraded by
    # CREATE TABLE IF NOT EXISTS — add any columns missing vs current schema.
    _migrate_images_schema(conn)

    # Indexes on `images` must run after column migration (legacy tables may
    # lack e.g. image_hash until _migrate_images_schema).
    conn.executescript("""
        CREATE INDEX IF NOT EXISTS idx_images_filepath ON images(filepath);
        CREATE INDEX IF NOT EXISTS idx_images_image_hash ON images(image_hash);
        CREATE INDEX IF NOT EXISTS idx_images_date_taken ON images(date_taken);
        CREATE INDEX IF NOT EXISTS idx_images_instagram_posted ON images(instagram_posted);
    """)

    _migrate_unified_image_keys(conn)
    seed_perspectives_from_prompts_dir(conn)
    conn.commit()
    return conn


def _migrate_add_column(conn: sqlite3.Connection, table: str, column: str, col_type: str):
    """Add a column if it doesn't already exist. Safe to call repeatedly."""
    cols = {row['name'] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


def _migrate_images_schema(conn: sqlite3.Connection) -> None:
    """Ensure `images` has every column used by catalog queries and upserts."""
    for column, col_type in (
        ("id", "TEXT"),
        ("filename", "TEXT"),
        ("filepath", "TEXT"),
        ("date_taken", "TEXT"),
        ("rating", "INTEGER DEFAULT 0"),
        ("pick", "INTEGER DEFAULT 0"),
        ("color_label", "TEXT DEFAULT ''"),
        ("keywords", "TEXT DEFAULT '[]'"),
        ("title", "TEXT DEFAULT ''"),
        ("caption", "TEXT DEFAULT ''"),
        ("description", "TEXT DEFAULT ''"),
        ("copyright", "TEXT DEFAULT ''"),
        ("camera_make", "TEXT DEFAULT ''"),
        ("camera_model", "TEXT DEFAULT ''"),
        ("lens", "TEXT DEFAULT ''"),
        ("focal_length", "TEXT DEFAULT ''"),
        ("aperture", "TEXT DEFAULT ''"),
        ("shutter_speed", "TEXT DEFAULT ''"),
        ("iso", "TEXT DEFAULT ''"),
        ("gps_latitude", "REAL"),
        ("gps_longitude", "REAL"),
        ("width", "INTEGER"),
        ("height", "INTEGER"),
        ("file_size", "INTEGER"),
        ("instagram_posted", "INTEGER DEFAULT 0"),
        ("instagram_post_date", "TEXT"),
        ("instagram_url", "TEXT"),
        ("instagram_index", "INTEGER DEFAULT 0"),
        ("image_hash", "TEXT"),
        ("analyzed_at", "TEXT"),
        ("phash", "TEXT"),
        ("exif", "TEXT"),
        ("catalog_path", "TEXT DEFAULT ''"),
    ):
        _migrate_add_column(conn, "images", column, col_type)


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


def _library_db_file_path(conn: sqlite3.Connection) -> str:
    """Resolve the on-disk path of the main attached database."""
    for row in conn.execute("PRAGMA database_list").fetchall():
        if row.get("name") == "main":
            path = (row.get("file") or "").strip()
            if path:
                return path
    raise RuntimeError(
        "migrate_unified_image_keys: could not resolve main database file path"
    )


def _migrate_unified_image_keys(conn: sqlite3.Connection) -> None:
    """Remap legacy composite keys to date-truncated form; idempotent via user_version."""
    row = conn.execute("PRAGMA user_version").fetchone()
    current_uv = int(row["user_version"] if row else 0)
    if current_uv >= 1:
        return

    db_path = _library_db_file_path(conn)
    bak_path = db_path + ".pre-key-migration.bak"
    if not os.path.exists(bak_path):
        try:
            shutil.copy2(db_path, bak_path)
            print(f"Backed up {db_path} before key migration")
        except OSError as exc:
            print(
                f"Warning: could not back up {db_path} before key migration "
                f"({exc}); continuing without backup"
            )

    rows = conn.execute("SELECT * FROM images").fetchall()
    by_new_key: dict[str, list[dict]] = {}
    for row in rows:
        new_key = generate_key(row)
        by_new_key.setdefault(new_key, []).append(row)

    # Resolve collisions: multiple old keys map to the same unified key.
    # Keep the row with the most data (non-null columns), delete the rest.
    # For tables with unique key constraints (vision_cache, image_descriptions),
    # delete the loser's row when the survivor already has one — UPDATE would
    # violate UNIQUE.  For non-unique FK columns (matches, etc.) remap safely.
    duplicates_to_delete: list[str] = []
    for new_key, colliding_rows in by_new_key.items():
        if len(colliding_rows) <= 1:
            continue
        def _non_null_count(r: dict) -> int:
            return sum(1 for v in r.values() if v is not None and v != "" and v != 0)
        colliding_rows.sort(key=_non_null_count, reverse=True)
        survivor = colliding_rows[0]
        for loser in colliding_rows[1:]:
            loser_key = loser["key"]
            survivor_key = survivor["key"]

            # Tables with non-unique FK columns: safe to remap
            for stmt in (
                "UPDATE matches SET catalog_key = ? WHERE catalog_key = ?",
                "UPDATE rejected_matches SET catalog_key = ? WHERE catalog_key = ?",
                "UPDATE vision_comparisons SET catalog_key = ? WHERE catalog_key = ?",
                "UPDATE instagram_dump_media SET matched_catalog_key = ? WHERE matched_catalog_key = ?",
            ):
                conn.execute(stmt, (survivor_key, loser_key))

            # Tables with unique key constraints: delete loser row if survivor
            # already owns one, otherwise remap.
            for del_stmt, upd_stmt in (
                (
                    "DELETE FROM vision_cache WHERE key = ? AND EXISTS (SELECT 1 FROM vision_cache WHERE key = ?)",
                    "UPDATE vision_cache SET key = ? WHERE key = ?",
                ),
                (
                    "DELETE FROM image_descriptions WHERE image_key = ? AND image_type = 'catalog' AND EXISTS (SELECT 1 FROM image_descriptions WHERE image_key = ? AND image_type = 'catalog')",
                    "UPDATE image_descriptions SET image_key = ? WHERE image_key = ? AND image_type = 'catalog'",
                ),
            ):
                conn.execute(del_stmt, (loser_key, survivor_key))
                conn.execute(upd_stmt, (survivor_key, loser_key))

            duplicates_to_delete.append(loser_key)
            print(
                f"migrate_unified_image_keys: merged duplicate "
                f"{loser_key!r} into {survivor_key!r} (unified: {new_key!r})"
            )

    for dup_key in duplicates_to_delete:
        conn.execute("DELETE FROM images WHERE key = ?", (dup_key,))

    remaps: list[tuple[str, str]] = []
    for row in rows:
        old_key = row["key"]
        if old_key in duplicates_to_delete:
            continue
        new_key = generate_key(row)
        if old_key != new_key:
            remaps.append((old_key, new_key))

    for old_key, new_key in remaps:
        conn.execute(
            "UPDATE matches SET catalog_key = ? WHERE catalog_key = ?",
            (new_key, old_key),
        )
        conn.execute(
            "UPDATE rejected_matches SET catalog_key = ? WHERE catalog_key = ?",
            (new_key, old_key),
        )
        conn.execute(
            "UPDATE vision_cache SET key = ? WHERE key = ?",
            (new_key, old_key),
        )
        conn.execute(
            "UPDATE vision_comparisons SET catalog_key = ? WHERE catalog_key = ?",
            (new_key, old_key),
        )
        conn.execute(
            "UPDATE image_descriptions SET image_key = ? "
            "WHERE image_key = ? AND image_type = 'catalog'",
            (new_key, old_key),
        )
        conn.execute(
            "UPDATE instagram_dump_media SET matched_catalog_key = ? "
            "WHERE matched_catalog_key = ?",
            (new_key, old_key),
        )
        conn.execute(
            "UPDATE images SET key = ? WHERE key = ?",
            (new_key, old_key),
        )

    conn.execute("PRAGMA user_version = 1")


def migrate_unified_image_keys(conn: sqlite3.Connection) -> None:
    """Public entry point for the unified composite key migration."""
    _migrate_unified_image_keys(conn)


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


def query_catalog_images(
    db: sqlite3.Connection,
    *,
    posted: bool | None = None,
    month: str | None = None,
    keyword: str | None = None,
    min_rating: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    color_label: str | None = None,
    analyzed: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """List catalog images with AND-combined filters, SQL pagination, and total count."""
    clauses: list[str] = ["1=1"]
    bindings: list = []

    if posted is True:
        clauses.append("i.instagram_posted = 1")
    elif posted is False:
        clauses.append("i.instagram_posted = 0")

    if month and len(month) == 6 and month.isdigit():
        clauses.append("strftime('%Y%m', i.date_taken) = ?")
        bindings.append(month)

    kw = (keyword or "").strip()
    if kw:
        pattern = f"%{kw}%"
        clauses.append(
            "("
            "i.keywords LIKE ? COLLATE NOCASE OR "
            "i.filename LIKE ? COLLATE NOCASE OR "
            "i.title LIKE ? COLLATE NOCASE OR "
            "i.description LIKE ? COLLATE NOCASE"
            ")"
        )
        bindings.extend([pattern, pattern, pattern, pattern])

    if min_rating is not None:
        clauses.append("i.rating >= ?")
        bindings.append(min_rating)

    if date_from:
        clauses.append("i.date_taken >= ?")
        bindings.append(date_from)

    if date_to:
        clauses.append("i.date_taken <= ?")
        bindings.append(date_to)

    cl = (color_label or "").strip()
    if cl:
        clauses.append("LOWER(i.color_label) = LOWER(?)")
        bindings.append(cl)

    if analyzed is True:
        clauses.append("d.image_key IS NOT NULL")
    elif analyzed is False:
        clauses.append("d.image_key IS NULL")

    where_sql = "WHERE " + " AND ".join(clauses)
    join_sql = (
        "FROM images i "
        "LEFT JOIN image_descriptions d ON i.key = d.image_key AND d.image_type = 'catalog' "
    )

    count_row = db.execute(
        f"SELECT COUNT(*) AS cnt {join_sql} {where_sql}",
        bindings,
    ).fetchone()
    total_count = int(count_row["cnt"])

    select_params = list(bindings) + [limit, offset]
    rows = db.execute(
        f"SELECT i.*, d.summary AS description_summary, "
        f"d.best_perspective AS description_best_perspective, "
        f"d.perspectives AS description_perspectives_json "
        f"{join_sql} {where_sql} ORDER BY i.date_taken DESC LIMIT ? OFFSET ?",
        select_params,
    ).fetchall()
    return [_deserialize_row(r) for r in rows], total_count


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
    
    # Also check if cached files actually exist on disk
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
                                run_start: str = None,
                                include_processed: bool = False) -> list:
    """Get Instagram dump media for matching.

    Args:
        run_start: ISO timestamp; skip images already attempted in this run
                   (last_attempted_at >= run_start).
        include_processed: If True, also return already-processed rows.
    """
    clauses: list[str] = []
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
    clauses: list[str] = []
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


def delete_matches_for_insta_key(db: sqlite3.Connection, insta_key: str,
                                  commit: bool = True) -> None:
    """Remove all match rows for an Instagram key (e.g. before replacing candidate set)."""
    db.execute("DELETE FROM matches WHERE insta_key = ?", (insta_key,))
    if commit:
        db.commit()


def store_match(db: sqlite3.Connection, record: dict, commit: bool = True) -> str:
    """Store match between catalog and Instagram image."""
    catalog_key = record.get('catalog_key')
    insta_key = record.get('insta_key')
    record['matched_at'] = datetime.now().isoformat()

    db.execute("""
        INSERT INTO matches (catalog_key, insta_key, phash_distance, phash_score,
            desc_similarity, vision_result, vision_score, total_score, matched_at,
            model_used, rank, vision_reasoning)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(catalog_key, insta_key) DO UPDATE SET
            phash_distance=excluded.phash_distance, phash_score=excluded.phash_score,
            desc_similarity=excluded.desc_similarity, vision_result=excluded.vision_result,
            vision_score=excluded.vision_score, total_score=excluded.total_score,
            matched_at=excluded.matched_at, model_used=excluded.model_used,
            rank=excluded.rank, vision_reasoning=excluded.vision_reasoning
    """, (
        catalog_key, insta_key, record.get('phash_distance'),
        record.get('phash_score'), record.get('desc_similarity'),
        record.get('vision_result'), record.get('vision_score'),
        record.get('total_score'), record['matched_at'],
        record.get('model_used'), record.get('rank', 1),
        record.get('vision_reasoning'),
    ))
    if commit:
        db.commit()
    return f"{catalog_key} <-> {insta_key}"


def validate_match(db: sqlite3.Connection, catalog_key: str, insta_key: str) -> bool:
    """Stamp a match as human-validated."""
    cursor = db.execute(
        "UPDATE matches SET validated_at = ? WHERE catalog_key = ? AND insta_key = ?",
        (datetime.now().isoformat(), catalog_key, insta_key),
    )
    db.commit()
    return cursor.rowcount > 0


def unvalidate_match(db: sqlite3.Connection, catalog_key: str, insta_key: str) -> bool:
    """Remove human validation (undo validate, not reject)."""
    cursor = db.execute(
        "UPDATE matches SET validated_at = NULL WHERE catalog_key = ? AND insta_key = ?",
        (catalog_key, insta_key),
    )
    db.commit()
    return cursor.rowcount > 0


def reject_match(db: sqlite3.Connection, catalog_key: str, insta_key: str) -> bool:
    """Delete match row and add pair to rejected blocklist.

    Also resets the instagram image's processed flag so it can match other
    catalog candidates in future runs.
    """
    db.execute(
        "DELETE FROM matches WHERE catalog_key = ? AND insta_key = ?",
        (catalog_key, insta_key),
    )
    db.execute(
        "INSERT OR REPLACE INTO rejected_matches (catalog_key, insta_key, rejected_at) "
        "VALUES (?, ?, ?)",
        (catalog_key, insta_key, datetime.now().isoformat()),
    )
    db.execute(
        "UPDATE instagram_dump_media SET processed = 0, matched_catalog_key = NULL "
        "WHERE media_key = ?",
        (insta_key,),
    )
    # Reset instagram_posted on the catalog image if no other matches reference it
    remaining = db.execute(
        "SELECT 1 FROM matches WHERE catalog_key = ? LIMIT 1", (catalog_key,)
    ).fetchone()
    if not remaining:
        db.execute(
            "UPDATE images SET instagram_posted = 0 WHERE key = ?",
            (catalog_key,),
        )
    db.commit()
    return True


def get_rejected_pairs(db: sqlite3.Connection) -> set[tuple[str, str]]:
    """Return set of (catalog_key, insta_key) pairs in the blocklist."""
    rows = db.execute("SELECT catalog_key, insta_key FROM rejected_matches").fetchall()
    return {(r['catalog_key'], r['insta_key']) for r in rows}


# ---------------------------------------------------------------------------
# Vision cache
# ---------------------------------------------------------------------------

VISION_CACHE_OVERSIZED_SENTINEL = "__oversized__"


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
    if not cached:
        return False
    comp = cached.get('compressed_path') or ''

    from lightroom_tagger.core.analyzer import RAW_EXTENSIONS, VIDEO_EXTENSIONS

    ext = os.path.splitext(original_path)[1].lower()
    if ext in VIDEO_EXTENSIONS:
        return False

    if ext in RAW_EXTENSIONS:
        if comp == original_path:
            return False
        if comp == VISION_CACHE_OVERSIZED_SENTINEL:
            return False

    if comp == VISION_CACHE_OVERSIZED_SENTINEL:
        try:
            current_mtime = os.path.getmtime(original_path)
            return cached.get('original_mtime') == current_mtime
        except OSError:
            return False

    if not comp or not os.path.exists(comp):
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


def get_undescribed_catalog_images(
    db: sqlite3.Connection, months: int | None = None, min_rating: int | None = None
) -> list[dict]:
    """Get catalog images that don't have descriptions yet."""
    sql = """
        SELECT i.* FROM images i
        LEFT JOIN image_descriptions d
            ON i.key = d.image_key AND d.image_type = 'catalog'
        WHERE d.image_key IS NULL
    """
    params: list = []
    if months:
        sql += " AND i.date_taken >= date('now', ?)"
        params.append(f'-{months} months')
    if min_rating is not None:
        sql += " AND i.rating >= ?"
        params.append(min_rating)
    rows = db.execute(sql, params).fetchall()
    return [_deserialize_row(r) for r in rows]


def get_undescribed_instagram_images(db: sqlite3.Connection, months: int = None) -> list[dict]:
    """Get Instagram dump media that don't have descriptions yet."""
    sql = """
        SELECT m.* FROM instagram_dump_media m
        LEFT JOIN image_descriptions d
            ON m.media_key = d.image_key AND d.image_type = 'instagram'
        WHERE d.image_key IS NULL
    """
    params: list = []
    if months:
        sql += " AND m.created_at >= date('now', ?)"
        params.append(f'-{months} months')
    rows = db.execute(sql, params).fetchall()
    return [_deserialize_row(r) for r in rows]


def get_all_images_with_descriptions(db: sqlite3.Connection,
                                     image_type: str = None,
                                     described_only: bool = False,
                                     limit: int = 50,
                                     offset: int = 0) -> tuple[list[dict], int]:
    """Get images joined with their descriptions for the descriptions page.

    Returns (items, total_count).
    """
    parts = []
    params: list = []

    if image_type != 'instagram':
        parts.append("""
            SELECT i.key AS image_key, 'catalog' AS image_type,
                   i.filename, i.date_taken AS date_ref,
                   d.summary, d.best_perspective, d.model_used AS desc_model,
                   d.described_at,
                   CASE WHEN d.image_key IS NOT NULL THEN 1 ELSE 0 END AS has_description
            FROM images i
            LEFT JOIN image_descriptions d
                ON i.key = d.image_key AND d.image_type = 'catalog'
        """)

    if image_type != 'catalog':
        parts.append("""
            SELECT m.media_key AS image_key, 'instagram' AS image_type,
                   m.filename, m.created_at AS date_ref,
                   d.summary, d.best_perspective, d.model_used AS desc_model,
                   d.described_at,
                   CASE WHEN d.image_key IS NOT NULL THEN 1 ELSE 0 END AS has_description
            FROM instagram_dump_media m
            LEFT JOIN image_descriptions d
                ON m.media_key = d.image_key AND d.image_type = 'instagram'
        """)

    union_sql = " UNION ALL ".join(parts)

    if described_only:
        wrapper = f"SELECT * FROM ({union_sql}) t WHERE t.has_description = 1"
    else:
        wrapper = f"SELECT * FROM ({union_sql}) t"

    count_sql = f"SELECT COUNT(*) AS cnt FROM ({wrapper})"
    total = db.execute(count_sql, params * len(parts)).fetchone()['cnt']

    page_sql = (
        f"{wrapper} ORDER BY CASE WHEN t.described_at IS NULL THEN 1 ELSE 0 END, "
        f"t.described_at DESC, t.date_ref DESC LIMIT ? OFFSET ?"
    )
    all_params = params * len(parts) + [limit, offset]
    rows = db.execute(page_sql, all_params).fetchall()

    return [_deserialize_row(r) for r in rows], total


# ---------------------------------------------------------------------------
# Perspectives & image scores (structured scoring)
# ---------------------------------------------------------------------------
#
# ## Queryable score fields (image_scores)
#
# - **id**: Surrogate primary key for this score row.
# - **image_key**: Library image identity (e.g. ``YYYY-MM-DD_filename.jpg``).
# - **image_type**: ``catalog`` vs ``instagram`` (dump media keys).
# - **perspective_slug**: Stable key matching ``perspectives.slug``.
# - **score**: Integer rubric score 1–10.
# - **rationale**: Short text justification from the model.
# - **model_used**: Provider/model identifier for the scoring call.
# - **prompt_version**: Rubric/prompt revision label; unique per image+type+slug.
# - **scored_at**: ISO-8601 timestamp when the score was recorded.
# - **is_current**: 1 if this row is the active score for this image+type+slug.
# - **repaired_from_malformed**: 1 if the row was persisted after output repair.
#
# Join ``image_scores`` with ``LEFT JOIN`` from catalog/dump rows: **no matching
# row means that image has not been scored yet** for that perspective (and type).


def list_perspectives(
    conn: sqlite3.Connection, *, active_only: bool = False
) -> list[dict]:
    """Return perspective rows as dicts ordered by ``slug``."""
    sql = "SELECT * FROM perspectives"
    if active_only:
        sql += " WHERE active = 1"
    sql += " ORDER BY slug ASC"
    rows = conn.execute(sql).fetchall()
    return [dict(r) for r in rows]


def get_perspective_by_slug(conn: sqlite3.Connection, slug: str) -> dict | None:
    """Return one perspective row by ``slug``, or ``None``."""
    row = conn.execute(
        "SELECT * FROM perspectives WHERE slug = ? LIMIT 1", (slug,)
    ).fetchone()
    return dict(row) if row else None


def insert_perspective(
    conn: sqlite3.Connection,
    *,
    slug: str,
    display_name: str,
    prompt_markdown: str,
    description: str = "",
    active: bool = True,
    source_filename: str | None = None,
) -> None:
    """Insert a ``perspectives`` row. Caller commits."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO perspectives (
            slug, display_name, description, prompt_markdown,
            active, source_filename, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            slug,
            display_name,
            description,
            prompt_markdown,
            1 if active else 0,
            source_filename,
            now,
            now,
        ),
    )


def update_perspective(
    conn: sqlite3.Connection,
    slug: str,
    *,
    display_name: str | None = None,
    description: str | None = None,
    prompt_markdown: str | None = None,
    active: bool | None = None,
) -> bool:
    """Partially update a perspective by ``slug``. Returns whether a row was updated."""
    fields: list[str] = []
    values: list = []
    if display_name is not None:
        fields.append("display_name = ?")
        values.append(display_name)
    if description is not None:
        fields.append("description = ?")
        values.append(description)
    if prompt_markdown is not None:
        fields.append("prompt_markdown = ?")
        values.append(prompt_markdown)
    if active is not None:
        fields.append("active = ?")
        values.append(1 if active else 0)
    if not fields:
        return False
    now = datetime.now(timezone.utc).isoformat()
    fields.append("updated_at = ?")
    values.append(now)
    values.append(slug)
    cur = conn.execute(
        f"UPDATE perspectives SET {', '.join(fields)} WHERE slug = ?",
        tuple(values),
    )
    if cur.rowcount > 0:
        return True
    return get_perspective_by_slug(conn, slug) is not None


def delete_perspective(conn: sqlite3.Connection, slug: str) -> bool:
    """Delete a perspective by ``slug``. Returns whether a row was removed."""
    cur = conn.execute("DELETE FROM perspectives WHERE slug = ?", (slug,))
    return cur.rowcount > 0


def insert_image_score(conn: sqlite3.Connection, row: dict) -> int:
    """Insert one ``image_scores`` row; return ``lastrowid``.

    Caller manages transactions and coordinating ``is_current`` / supersede calls.
    """
    cursor = conn.execute(
        """
        INSERT INTO image_scores (
            image_key, image_type, perspective_slug, score, rationale,
            model_used, prompt_version, scored_at, is_current,
            repaired_from_malformed
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row["image_key"],
            row.get("image_type", "catalog"),
            row["perspective_slug"],
            row["score"],
            row.get("rationale", ""),
            row.get("model_used", ""),
            row.get("prompt_version", ""),
            row["scored_at"],
            int(row.get("is_current", 1)),
            int(row.get("repaired_from_malformed", 0)),
        ),
    )
    last = cursor.lastrowid
    assert last is not None
    return int(last)


def supersede_previous_current_scores(
    conn: sqlite3.Connection,
    image_key: str,
    image_type: str,
    perspective_slug: str,
    new_prompt_version: str,
) -> None:
    """Set ``is_current = 0`` for rows matching key, type, and slug whose
    ``prompt_version`` is not ``new_prompt_version``.

    Call before inserting a new current row for the same image+type+slug so only
    the new version remains ``is_current = 1``.
    """
    conn.execute(
        """
        UPDATE image_scores
        SET is_current = 0
        WHERE image_key = ?
          AND image_type = ?
          AND perspective_slug = ?
          AND prompt_version != ?
        """,
        (image_key, image_type, perspective_slug, new_prompt_version),
    )


def get_current_scores_for_image(
    conn: sqlite3.Connection, image_key: str, image_type: str = "catalog"
) -> list[dict]:
    """Return all ``image_scores`` rows for this image with ``is_current = 1``."""
    rows = conn.execute(
        """
        SELECT * FROM image_scores
        WHERE image_key = ? AND image_type = ? AND is_current = 1
        ORDER BY perspective_slug ASC
        """,
        (image_key, image_type),
    ).fetchall()
    return [dict(r) for r in rows]
