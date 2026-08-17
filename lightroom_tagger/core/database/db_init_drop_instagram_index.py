"""Drop vestigial ``instagram_index`` column from ``images`` (user_version 7 → 8)."""

from __future__ import annotations

import sqlite3

from .db_init_migrations import _column_exists, _table_exists


def _migrate_drop_instagram_index(conn: sqlite3.Connection) -> None:
    """Drop ``images.instagram_index`` when present; safe when already absent."""
    row = conn.execute("PRAGMA user_version").fetchone()
    current_uv = int(row["user_version"] if row else 0)
    if current_uv >= 8:
        return

    if _table_exists(conn, "images"):
        if _column_exists(conn, "images", "instagram_index"):
            conn.execute("ALTER TABLE images DROP COLUMN instagram_index")

    conn.execute("PRAGMA user_version = 8")
