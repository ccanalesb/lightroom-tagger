"""Tests for Instagram dead-table export and drop migration (#228)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from lightroom_tagger.core.database import init_database, store_image, store_image_description
from lightroom_tagger.core.database.db_init_instagram_drop import (
    INSTAGRAM_MATCHING_EXPORT_FILENAME,
)

_LEGACY_INSTAGRAM_DDL = """
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
CREATE TABLE IF NOT EXISTS vision_comparisons (
    catalog_key TEXT,
    insta_key TEXT,
    result TEXT,
    vision_score REAL,
    compared_at TEXT,
    model_used TEXT,
    PRIMARY KEY (catalog_key, insta_key)
);
CREATE TABLE IF NOT EXISTS comparison_pool_snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    insta_key TEXT NOT NULL,
    captured_at TEXT NOT NULL DEFAULT (datetime('now')),
    source_job_id TEXT,
    threshold REAL NOT NULL,
    clip_top_k INTEGER NOT NULL,
    weights_json TEXT NOT NULL,
    candidate_count INTEGER NOT NULL DEFAULT 0,
    diagnostics_json TEXT NOT NULL DEFAULT '{}',
    insta_asset_path TEXT
);
CREATE TABLE IF NOT EXISTS comparison_pool_snapshot_candidates (
    snapshot_id INTEGER NOT NULL,
    rank INTEGER NOT NULL,
    catalog_key TEXT NOT NULL,
    total_score REAL,
    PRIMARY KEY (snapshot_id, catalog_key)
);
"""


def _table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    return {r[0] for r in rows}


def test_migration_exports_legacy_rows_and_drops_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "library.db"
    conn = init_database(str(db_path))
    conn.executescript(_LEGACY_INSTAGRAM_DDL)
    catalog_key = store_image(
        conn,
        {"date_taken": "2024-01-01", "filename": "cat.jpg"},
    )
    store_image_description(
        conn,
        {
            "image_key": catalog_key,
            "image_type": "catalog",
            "summary": "catalog summary",
            "model_used": "m",
        },
    )
    store_image_description(
        conn,
        {
            "image_key": "ig-1",
            "image_type": "instagram",
            "summary": "ig summary",
            "model_used": "m",
        },
    )
    conn.execute(
        "INSERT INTO image_scores "
        "(image_key, image_type, perspective_slug, score, rationale, model_used, "
        "prompt_version, scored_at, is_current) "
        "VALUES (?, 'catalog', 'street', 8, '', 'm', 'v1', datetime('now'), 1)",
        (catalog_key,),
    )
    conn.execute(
        "INSERT INTO image_scores "
        "(image_key, image_type, perspective_slug, score, rationale, model_used, "
        "prompt_version, scored_at, is_current) "
        "VALUES ('ig-1', 'instagram', 'street', 5, '', 'm', 'v1', datetime('now'), 1)"
    )
    conn.execute(
        "INSERT INTO instagram_dump_media (media_key, caption, created_at) "
        "VALUES ('ig-1', 'hello', '2024-01-01')"
    )
    conn.execute(
        "INSERT INTO matches (catalog_key, insta_key, total_score) VALUES (?, 'ig-1', 0.9)",
        (catalog_key,),
    )
    conn.execute(
        "INSERT INTO rejected_matches (catalog_key, insta_key, rejected_at) "
        "VALUES (?, 'ig-2', datetime('now'))",
        (catalog_key,),
    )
    conn.execute("PRAGMA user_version = 6")
    conn.commit()
    conn.close()

    init_database(str(db_path))
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    export_path = tmp_path / INSTAGRAM_MATCHING_EXPORT_FILENAME
    assert export_path.is_file()
    payload = json.loads(export_path.read_text(encoding="utf-8"))
    assert payload["tables"]["matches"]["present"] is True
    assert payload["tables"]["matches"]["row_count"] == 1
    assert payload["tables"]["instagram_dump_media"]["row_count"] == 1
    assert payload["image_descriptions_instagram"]["row_count"] == 1
    assert payload["deleted"]["image_descriptions_instagram"] == 1
    assert payload["catalog_counts_verified"]["image_descriptions_catalog"]["before"] == 1
    assert (
        payload["catalog_counts_verified"]["image_descriptions_catalog"]["after"]
        == payload["catalog_counts_verified"]["image_descriptions_catalog"]["before"]
    )

    tables = _table_names(conn)
    for dead in (
        "matches",
        "instagram_dump_media",
        "instagram_images",
        "rejected_matches",
        "vision_comparisons",
        "comparison_pool_snapshots",
        "comparison_pool_snapshot_candidates",
    ):
        assert dead not in tables

    assert conn.execute(
        "SELECT COUNT(*) FROM image_descriptions WHERE image_type = 'catalog'"
    ).fetchone()[0] == 1
    assert conn.execute(
        "SELECT COUNT(*) FROM image_descriptions WHERE image_type = 'instagram'"
    ).fetchone()[0] == 0
    assert int(conn.execute("PRAGMA user_version").fetchone()[0]) == 8
    conn.close()


def test_fresh_database_migration_records_absent_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "library.db"
    init_database(str(db_path))

    export_path = tmp_path / INSTAGRAM_MATCHING_EXPORT_FILENAME
    assert export_path.is_file()
    payload = json.loads(export_path.read_text(encoding="utf-8"))
    assert payload["tables"]["matches"]["present"] is False
    assert payload["tables"]["instagram_dump_media"]["present"] is False
    assert payload["tables"]["rejected_matches"]["present"] is False
    assert payload["image_descriptions_instagram"]["row_count"] == 0

    conn = sqlite3.connect(db_path)
    assert int(conn.execute("PRAGMA user_version").fetchone()[0]) == 8
    conn.close()
