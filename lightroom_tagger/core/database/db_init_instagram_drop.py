"""Export and drop retired Instagram-matching tables (user_version 6 → 7)."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .db_init_migrations import (
    _column_exists,
    _library_db_file_path,
    _table_exists,
)

INSTAGRAM_MATCHING_EXPORT_FILENAME = "instagram-matching-export.json"

_DROP_TABLES = (
    "comparison_pool_snapshot_candidates",
    "comparison_pool_snapshots",
    "matches",
    "rejected_matches",
    "vision_comparisons",
    "instagram_dump_media",
    "instagram_images",
    "image_text_embeddings",
)


def _scalar_count(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> int:
    row = conn.execute(sql, params).fetchone()
    return int(row["cnt"]) if row else 0


def _export_table_rows(conn: sqlite3.Connection, table: str) -> dict:
    if not _table_exists(conn, table):
        return {"present": False, "row_count": 0, "rows": []}
    rows = [dict(r) for r in conn.execute(f"SELECT * FROM [{table}]").fetchall()]
    return {"present": True, "row_count": len(rows), "rows": rows}


def _write_instagram_matching_export(conn: sqlite3.Connection, payload: dict) -> Path:
    """Atomically write the export artifact next to ``library.db``."""
    db_path = _library_db_file_path(conn)
    export_dir = Path(db_path).resolve().parent
    export_dir.mkdir(parents=True, exist_ok=True)
    final_path = export_dir / INSTAGRAM_MATCHING_EXPORT_FILENAME
    tmp_path = export_dir / f"{INSTAGRAM_MATCHING_EXPORT_FILENAME}.tmp"
    data = json.dumps(payload, indent=2, default=str)
    tmp_path.write_text(data, encoding="utf-8")
    os.replace(tmp_path, final_path)
    if not final_path.is_file() or final_path.stat().st_size == 0:
        raise RuntimeError(
            f"Instagram matching export was not written: {final_path}"
        )
    return final_path


def _migrate_drop_instagram_dead_tables(conn: sqlite3.Connection) -> None:
    """Export irreplaceable Instagram-matching rows, delete orphans, drop dead tables."""
    row = conn.execute("PRAGMA user_version").fetchone()
    current_uv = int(row["user_version"] if row else 0)
    if current_uv >= 7:
        return

    catalog_desc_before = _scalar_count(
        conn,
        "SELECT COUNT(*) AS cnt FROM image_descriptions WHERE image_type = 'catalog'",
    )
    catalog_scores_before = _scalar_count(
        conn,
        "SELECT COUNT(*) AS cnt FROM image_scores WHERE image_type = 'catalog'",
    )

    ig_desc_rows = []
    if _table_exists(conn, "image_descriptions"):
        ig_desc_rows = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM image_descriptions WHERE image_type = 'instagram'"
            ).fetchall()
        ]
    ig_score_rows = []
    if _table_exists(conn, "image_scores"):
        ig_score_rows = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM image_scores WHERE image_type = 'instagram'"
            ).fetchall()
        ]

    payload = {
        "schema_version": 1,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "library_db": _library_db_file_path(conn),
        "tables": {
            "matches": _export_table_rows(conn, "matches"),
            "instagram_dump_media": _export_table_rows(conn, "instagram_dump_media"),
            "rejected_matches": _export_table_rows(conn, "rejected_matches"),
        },
        "image_descriptions_instagram": {
            "row_count": len(ig_desc_rows),
            "rows": ig_desc_rows,
        },
        "image_scores_instagram": {
            "row_count": len(ig_score_rows),
            "rows": ig_score_rows,
        },
        "catalog_counts_verified": {
            "image_descriptions_catalog": {"before": catalog_desc_before},
            "image_scores_catalog": {"before": catalog_scores_before},
        },
    }

    export_path = _write_instagram_matching_export(conn, payload)
    print(f"Wrote Instagram matching export to {export_path}")

    deleted: dict[str, int] = {}
    if _table_exists(conn, "image_scores"):
        cur = conn.execute("DELETE FROM image_scores WHERE image_type = 'instagram'")
        deleted["image_scores_instagram"] = cur.rowcount
    else:
        deleted["image_scores_instagram"] = 0
    if _table_exists(conn, "image_descriptions"):
        cur = conn.execute(
            "DELETE FROM image_descriptions WHERE image_type = 'instagram'"
        )
        deleted["image_descriptions_instagram"] = cur.rowcount
    else:
        deleted["image_descriptions_instagram"] = 0

    for table in _DROP_TABLES:
        conn.execute(f"DROP TABLE IF EXISTS [{table}]")

    if _table_exists(conn, "images"):
        for col in ("instagram_post_date", "instagram_url"):
            if _column_exists(conn, "images", col):
                conn.execute(f"ALTER TABLE images DROP COLUMN {col}")

    catalog_desc_after = _scalar_count(
        conn,
        "SELECT COUNT(*) AS cnt FROM image_descriptions WHERE image_type = 'catalog'",
    )
    catalog_scores_after = _scalar_count(
        conn,
        "SELECT COUNT(*) AS cnt FROM image_scores WHERE image_type = 'catalog'",
    )
    if catalog_desc_after != catalog_desc_before:
        raise RuntimeError(
            "catalog image_descriptions count changed during Instagram drop migration: "
            f"{catalog_desc_before} -> {catalog_desc_after}"
        )
    if catalog_scores_after != catalog_scores_before:
        raise RuntimeError(
            "catalog image_scores count changed during Instagram drop migration: "
            f"{catalog_scores_before} -> {catalog_scores_after}"
        )

    payload["catalog_counts_verified"]["image_descriptions_catalog"]["after"] = (
        catalog_desc_after
    )
    payload["catalog_counts_verified"]["image_scores_catalog"]["after"] = (
        catalog_scores_after
    )
    payload["deleted"] = deleted
    _write_instagram_matching_export(conn, payload)

    print(
        "Instagram dead-table migration: deleted "
        f"{deleted['image_descriptions_instagram']} instagram image_descriptions, "
        f"{deleted['image_scores_instagram']} instagram image_scores; "
        f"catalog descriptions unchanged at {catalog_desc_after}, "
        f"catalog scores unchanged at {catalog_scores_after}"
    )

    conn.execute("PRAGMA user_version = 7")
