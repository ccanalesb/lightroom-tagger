"""Database initialization and schema migrations."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import sqlite_vec

from . import library_bootstrap_schema
from .scores import markdown_marks_optional, migrate_legacy_description_scores_to_image_scores
from .db_init_migrations import (
    _backfill_matched_catalog_key_from_validated_matches,
    _library_db_file_path,
    _migrate_add_column,
    _migrate_catalog_similarity,
    _migrate_comparison_pool_snapshots,
    _migrate_image_clip_embeddings_vec0,
    _migrate_image_descriptions_fts,
    _migrate_image_stacks,
    _migrate_image_text_embeddings_vec0,
    _migrate_images_schema,
    _migrate_unified_image_keys,
    migrate_unified_image_keys,
)


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
        optional = 1 if markdown_marks_optional(text) else 0

        conn.execute(
            """
            INSERT INTO perspectives (
                slug, display_name, description, prompt_markdown,
                active, optional, source_filename, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?)
            """,
            (slug, display_name, description, text, optional, source_filename, now, now),
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

    conn.executescript(
        library_bootstrap_schema.BASE_LIBRARY_SCHEMA_SQL
    )

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
    _migrate_add_column(conn, 'perspectives', 'optional', 'INTEGER NOT NULL DEFAULT 0')
    _migrate_add_column(conn, 'image_scores', 'not_attempted', 'INTEGER NOT NULL DEFAULT 0')
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
    migrate_legacy_description_scores_to_image_scores(conn)
    # Stack members reference `images` by key at insert time; `images` is created above.
    _migrate_image_stacks(conn)
    _migrate_catalog_similarity(conn)
    _migrate_comparison_pool_snapshots(conn)
    seed_perspectives_from_prompts_dir(conn)
    conn.commit()
    return conn
