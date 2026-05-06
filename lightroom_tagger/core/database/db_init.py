"""Database initialization and schema migrations."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import sqlite_vec


def _dict_factory(cursor, row):
    """Convert sqlite3 rows to dicts."""
    fields = [column[0] for column in cursor.description]
    return dict(zip(fields, row))


def _ensure_sqlite_vec_loaded(conn: sqlite3.Connection) -> None:
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)


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
    if 'is_stack_representative' in row and row.get('is_stack_representative') is not None:
        row['is_stack_representative'] = bool(row['is_stack_representative'])
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
    module's path: ``Path(__file__).resolve().parents[3] / "prompts" / "perspectives"``
    (repo root → ``prompts`` → ``perspectives``). That matches editable installs where the
    package lives under the project root; callers may pass an absolute path when bundling.

    If ``SELECT COUNT(*) FROM perspectives`` is greater than zero, returns ``0`` without
    reading files (factory seed runs once; DB remains authoritative afterward).

    Returns the number of rows inserted.
    """
    if prompts_dir is None:
        prompts_dir = str(
            Path(__file__).resolve().parents[3] / "prompts" / "perspectives"
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
    _ensure_sqlite_vec_loaded(conn)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    # WAL allows only one writer at a time — every other writer blocks on
    # the write lock. Under the parallel score/describe passes (4 workers,
    # each doing UPDATE + INSERT + commit after a slow vision call), the
    # previous 5s timeout was too aggressive: ~15-20% of writes failed
    # with "database is locked" on busy jobs. 30s lets a contended writer
    # wait through a handful of slow commits without giving up. We also
    # set ``synchronous=NORMAL`` which is safe on WAL and materially
    # reduces the writer's fsync time (the #1 driver of lock contention).
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA wal_autocheckpoint=1000")

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
            exif TEXT,
            created_at TEXT
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
            described_at TEXT,
            dominant_colors TEXT,
            mood_tags TEXT,
            has_repetition INTEGER,
            description_search_document TEXT
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
    _migrate_add_column(conn, 'instagram_images', 'created_at', 'TEXT')
    _migrate_add_column(conn, 'matches', 'model_used', 'TEXT')
    _migrate_add_column(conn, 'matches', 'validated_at', 'TEXT')
    _migrate_add_column(conn, 'matches', 'rank', 'INTEGER DEFAULT 1')
    _migrate_add_column(conn, 'matches', 'vision_reasoning', 'TEXT')
    _migrate_add_column(conn, 'image_descriptions', 'dominant_colors', 'TEXT')
    _migrate_add_column(conn, 'image_descriptions', 'mood_tags', 'TEXT')
    _migrate_add_column(conn, 'image_descriptions', 'has_repetition', 'INTEGER')
    _migrate_add_column(conn, 'image_descriptions', 'description_search_document', 'TEXT')
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
    _backfill_matched_catalog_key_from_validated_matches(conn)
    _migrate_image_descriptions_fts(conn)
    _migrate_image_text_embeddings_vec0(conn)
    _migrate_image_clip_embeddings_vec0(conn)
    # Stack members reference `images` by key at insert time; `images` is created above.
    _migrate_image_stacks(conn)
    _migrate_catalog_similarity(conn)
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


def _backfill_matched_catalog_key_from_validated_matches(conn: sqlite3.Connection) -> None:
    """One-time sync: for every validated row in ``matches``, mirror the
    pairing onto ``instagram_dump_media.matched_catalog_key`` so the
    Instagram tab "matched" badge reflects on-demand validations too.

    Gated on ``PRAGMA user_version`` (bump: 1 → 2) so the UPDATE runs exactly
    once per DB file. Still idempotent if it does run: only overwrites rows
    whose ``matched_catalog_key`` is NULL (we never stomp a value written by
    the bulk matcher).
    """
    row = conn.execute("PRAGMA user_version").fetchone()
    current_uv = int(row["user_version"] if row else 0)
    if current_uv >= 2:
        return
    try:
        conn.execute(
            "UPDATE instagram_dump_media "
            "SET matched_catalog_key = ("
            "    SELECT m.catalog_key FROM matches m "
            "    WHERE m.insta_key = instagram_dump_media.media_key "
            "      AND m.validated_at IS NOT NULL "
            "    ORDER BY m.validated_at DESC LIMIT 1"
            ") "
            "WHERE matched_catalog_key IS NULL "
            "  AND EXISTS ("
            "    SELECT 1 FROM matches m "
            "    WHERE m.insta_key = instagram_dump_media.media_key "
            "      AND m.validated_at IS NOT NULL"
            ")"
        )
    except sqlite3.OperationalError:
        # `matches` may not exist yet on very fresh DBs — safe to skip and
        # leave user_version unchanged so the next init retries.
        return
    conn.execute("PRAGMA user_version = 2")


def _migrate_image_descriptions_fts(conn: sqlite3.Connection) -> None:
    """Backfill description_search_document, add standalone FTS5, and index existing rows (D-05). Runs once (user_version 2 → 3)."""
    from .descriptions import build_description_search_document

    row = conn.execute("PRAGMA user_version").fetchone()
    current_uv = int(row["user_version"] if row else 0)
    if current_uv >= 3:
        return
    try:
        conn.execute("DROP TABLE IF EXISTS image_descriptions_fts")
        conn.execute(
            """
            CREATE VIRTUAL TABLE image_descriptions_fts USING fts5(
                description_search_document,
                tokenize='porter unicode61'
            )
            """
        )
        rows = conn.execute(
            "SELECT image_key, summary, subjects FROM image_descriptions "
            "WHERE description_search_document IS NULL AND image_type = 'catalog'"
        ).fetchall()
        for r in rows:
            doc = build_description_search_document(
                r.get("summary") or "",
                r.get("subjects") if r.get("subjects") is not None else "[]",
            )
            conn.execute(
                "UPDATE image_descriptions SET description_search_document = ? "
                "WHERE image_key = ?",
                (doc if doc else None, r["image_key"]),
            )
        # D-05: index all catalog search documents (no external `rebuild` — standalone table).
        inserted = conn.execute(
            "SELECT rowid, description_search_document FROM image_descriptions "
            "WHERE image_type = 'catalog' AND description_search_document IS NOT NULL "
            "AND TRIM(description_search_document) != ''"
        ).fetchall()
        for ins in inserted:
            conn.execute(
                "INSERT INTO image_descriptions_fts(rowid, description_search_document) "
                "VALUES(?, ?)",
                (ins["rowid"], ins["description_search_document"]),
            )
    except sqlite3.OperationalError:
        return
    conn.execute("PRAGMA user_version = 3")


def _migrate_image_text_embeddings_vec0(conn: sqlite3.Connection) -> None:
    """Create sqlite-vec vec0 table for catalog text embeddings (user_version 3 → 4)."""
    row = conn.execute("PRAGMA user_version").fetchone()
    current_uv = int(row["user_version"] if row else 0)
    if current_uv >= 4:
        return
    try:
        conn.execute("DROP TABLE IF EXISTS image_text_embeddings")
        conn.execute(
            """
            CREATE VIRTUAL TABLE image_text_embeddings USING vec0(
              embedding float[768] distance_metric=cosine,
              image_key TEXT
            );
            """
        )
    except sqlite3.OperationalError:
        return
    conn.execute("PRAGMA user_version = 4")


def _migrate_image_clip_embeddings_vec0(conn: sqlite3.Connection) -> None:
    """Create sqlite-vec vec0 table for catalog CLIP embeddings (user_version 4 → 5)."""
    row = conn.execute("PRAGMA user_version").fetchone()
    current_uv = int(row["user_version"] if row else 0)
    if current_uv >= 5:
        return
    try:
        conn.execute("DROP TABLE IF EXISTS image_clip_embeddings")
        conn.execute(
            """
            CREATE VIRTUAL TABLE image_clip_embeddings USING vec0(
              embedding float[512] distance_metric=cosine,
              image_key TEXT
            );
            """
        )
    except sqlite3.OperationalError:
        return
    conn.execute("PRAGMA user_version = 5")


# Stack mutations from batch jobs must use library_write(context manager).
def _migrate_image_stacks(conn: sqlite3.Connection) -> None:
    """Idempotent stack tables; core ``images`` must exist (satisfied by init)."""
    # Runs after _migrate_image_text_embeddings_vec0; no user_version — IF NOT EXISTS only.
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS image_stacks (
            stack_id INTEGER PRIMARY KEY AUTOINCREMENT,
            representative_key TEXT NOT NULL,
            stack_size INTEGER NOT NULL DEFAULT 0, -- maintained on split/merge/set_representative; drift vs members theoretical; stack_metadata_for_api authoritative for live counts
            user_modified INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE UNIQUE INDEX IF NOT EXISTS uq_image_stacks_representative
            ON image_stacks(representative_key);

        CREATE TABLE IF NOT EXISTS image_stack_members (
            stack_id INTEGER NOT NULL
                REFERENCES image_stacks(stack_id) ON DELETE CASCADE,
            image_key TEXT NOT NULL,
            PRIMARY KEY (stack_id, image_key)
        );

        CREATE UNIQUE INDEX IF NOT EXISTS uq_image_stack_members_image_key
            ON image_stack_members(image_key);
        """
    )


def _migrate_catalog_similarity(conn: sqlite3.Connection) -> None:
    """Idempotent derived tables for job-driven catalog visual similarity."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS catalog_similarity_groups (
            group_id INTEGER PRIMARY KEY AUTOINCREMENT,
            seed_key TEXT NOT NULL,
            candidate_count INTEGER NOT NULL DEFAULT 0,
            best_similarity REAL NOT NULL DEFAULT 0,
            job_id TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_catalog_similarity_groups_created
            ON catalog_similarity_groups(created_at DESC, group_id DESC);
        CREATE INDEX IF NOT EXISTS idx_catalog_similarity_groups_seed
            ON catalog_similarity_groups(seed_key);

        CREATE TABLE IF NOT EXISTS catalog_similarity_candidates (
            group_id INTEGER NOT NULL
                REFERENCES catalog_similarity_groups(group_id) ON DELETE CASCADE,
            candidate_key TEXT NOT NULL,
            similarity REAL NOT NULL,
            rank INTEGER NOT NULL,
            why_matched TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (group_id, candidate_key)
        );

        CREATE INDEX IF NOT EXISTS idx_catalog_similarity_candidates_group_rank
            ON catalog_similarity_candidates(group_id, rank);
        """
    )


def _migrate_unified_image_keys(conn: sqlite3.Connection) -> None:
    """Remap legacy composite keys to date-truncated form; idempotent via user_version."""
    from .catalog import generate_key

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
