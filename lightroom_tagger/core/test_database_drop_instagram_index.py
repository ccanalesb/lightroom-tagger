"""Tests for dropping vestigial ``instagram_index`` column (#256)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from lightroom_tagger.core.database import init_database, store_image


def _column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def test_migration_drops_instagram_index_from_legacy_db(tmp_path: Path) -> None:
    db_path = tmp_path / "library.db"
    conn = init_database(str(db_path))
    conn.execute("ALTER TABLE images ADD COLUMN instagram_index INTEGER DEFAULT 0")
    conn.execute("PRAGMA user_version = 7")
    conn.commit()
    conn.close()

    init_database(str(db_path))
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    cols = _column_names(conn, "images")
    assert "instagram_index" not in cols
    assert "instagram_posted" in cols
    assert int(conn.execute("PRAGMA user_version").fetchone()[0]) == 8
    conn.close()


def test_fresh_database_has_no_instagram_index(tmp_path: Path) -> None:
    db_path = tmp_path / "library.db"
    init_database(str(db_path))

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cols = _column_names(conn, "images")
    assert "instagram_index" not in cols
    assert "instagram_posted" in cols
    assert int(conn.execute("PRAGMA user_version").fetchone()[0]) == 8
    conn.close()


def test_store_image_does_not_write_instagram_index(tmp_path: Path) -> None:
    db_path = tmp_path / "library.db"
    conn = init_database(str(db_path))
    key = store_image(
        conn,
        {
            "date_taken": "2024-06-01",
            "filename": "no-index.jpg",
            "instagram_posted": True,
        },
    )
    row = conn.execute("SELECT * FROM images WHERE key = ?", (key,)).fetchone()
    assert dict(row)["instagram_posted"] == 1
    assert "instagram_index" not in dict(row)
    conn.close()
