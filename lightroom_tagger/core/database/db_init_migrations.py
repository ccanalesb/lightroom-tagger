"""Post-bootstrap migrations (user_version gates)."""

from __future__ import annotations

import os
import shutil
import sqlite3


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cols = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    return column in cols


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


def _migrate_image_clip_embeddings_vec0(conn: sqlite3.Connection) -> None:
    """Create sqlite-vec vec0 table for catalog CLIP embeddings (user_version 3 → 5)."""
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
    # Runs after CLIP vec0 migration; no user_version — IF NOT EXISTS only.
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


def _migrate_catalog_similarity_rejections(conn: sqlite3.Connection) -> None:
    """Persist user rejections for catalog similarity pairs across batch wipes."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS catalog_similarity_rejections (
            key_a TEXT NOT NULL,
            key_b TEXT NOT NULL,
            rejected_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (key_a, key_b),
            CHECK (key_a < key_b)
        );

        CREATE INDEX IF NOT EXISTS idx_catalog_similarity_rejections_rejected_at
            ON catalog_similarity_rejections(rejected_at DESC);
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

            # Tables with non-unique FK columns: safe to remap (guarded — tables
            # may already be absent if the 0→1 remap and 6→7 drop run together).
            for table, column in (
                ("matches", "catalog_key"),
                ("rejected_matches", "catalog_key"),
                ("vision_comparisons", "catalog_key"),
                ("instagram_dump_media", "matched_catalog_key"),
            ):
                if _table_exists(conn, table) and _column_exists(conn, table, column):
                    conn.execute(
                        f"UPDATE [{table}] SET {column} = ? WHERE {column} = ?",
                        (survivor_key, loser_key),
                    )

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
        for table, column in (
            ("matches", "catalog_key"),
            ("rejected_matches", "catalog_key"),
            ("vision_comparisons", "catalog_key"),
            ("instagram_dump_media", "matched_catalog_key"),
        ):
            if _table_exists(conn, table) and _column_exists(conn, table, column):
                conn.execute(
                    f"UPDATE [{table}] SET {column} = ? WHERE {column} = ?",
                    (new_key, old_key),
                )
        conn.execute(
            "UPDATE vision_cache SET key = ? WHERE key = ?",
            (new_key, old_key),
        )
        conn.execute(
            "UPDATE image_descriptions SET image_key = ? "
            "WHERE image_key = ? AND image_type = 'catalog'",
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
