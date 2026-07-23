"""Best-photo ranking with stack enrichment."""

from __future__ import annotations

import sqlite3
from typing import Any

from .percentiles import compute_image_peak_percentile_scores


def _image_meta_map(conn: sqlite3.Connection, keys: list[str]) -> dict[str, dict[str, Any]]:
    if not keys:
        return {}
    placeholders = ",".join("?" * len(keys))
    out: dict[str, dict[str, Any]] = {}
    # Catalog images
    rows = conn.execute(
        f"SELECT key, filename, date_taken, rating, instagram_posted FROM images "
        f"WHERE key IN ({placeholders})",
        keys,
    ).fetchall()
    for r in rows:
        out[str(r["key"])] = {
            "filename": r.get("filename") or "",
            "date_taken": r.get("date_taken") or "",
            "rating": int(r["rating"] or 0),
            "instagram_posted": bool(r.get("instagram_posted")),
            "image_type": "catalog",
        }
    # Instagram images (keys not already resolved above)
    missing = [k for k in keys if k not in out]
    if missing:
        ig_placeholders = ",".join("?" * len(missing))
        ig_rows = conn.execute(
            f"SELECT media_key, filename, created_at FROM instagram_dump_media "
            f"WHERE media_key IN ({ig_placeholders})",
            missing,
        ).fetchall()
        for r in ig_rows:
            out[str(r["media_key"])] = {
                "filename": r.get("filename") or r.get("media_key") or "",
                "date_taken": r.get("created_at") or "",
                "rating": 0,
                "instagram_posted": True,
                "image_type": "instagram",
            }
    return out


def _stack_non_representative_keys(conn: sqlite3.Connection, keys: list[str]) -> set[str]:
    """Image keys that are stack members but not the stack representative."""
    if not keys:
        return set()
    placeholders = ",".join("?" * len(keys))
    rows = conn.execute(
        f"""
        SELECT m.image_key FROM image_stack_members m
        INNER JOIN image_stacks s ON s.stack_id = m.stack_id
        WHERE m.image_key IN ({placeholders}) AND m.image_key <> s.representative_key
        """,
        keys,
    ).fetchall()
    return {str(r["image_key"]) for r in rows}


def _stack_fields_for_image_keys(
    conn: sqlite3.Connection, keys: list[str]
) -> dict[str, dict[str, Any]]:
    """``stack_id``, ``stack_member_count`` (``image_stacks.stack_size``), ``is_stack_representative``."""
    if not keys:
        return {}
    placeholders = ",".join("?" * len(keys))
    rows = conn.execute(
        f"""
        SELECT m.image_key, s.stack_id, s.representative_key, s.stack_size
        FROM image_stack_members m
        INNER JOIN image_stacks s ON s.stack_id = m.stack_id
        WHERE m.image_key IN ({placeholders})
        """,
        keys,
    ).fetchall()
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        k = str(r["image_key"])
        rep = str(r["representative_key"])
        out[k] = {
            "stack_id": int(r["stack_id"]),
            "stack_member_count": int(r["stack_size"]),
            "is_stack_representative": k == rep,
        }
    return out


def rank_best_photos(
    conn: sqlite3.Connection,
    *,
    limit: int,
    offset: int,
    min_perspectives: int | None = None,
    sort_by_date: str | None = None,
    posted: bool | None = None,
) -> tuple[list[dict[str, Any]], int, dict[str, Any]]:
    """Eligible images only, sorted by peak_percentile DESC, date_taken, key ASC.

    ``sort_by_date`` (``newest`` / ``oldest``) only controls the date tiebreaker;
    peak within-perspective percentile remains the primary sort key.
    """
    if sort_by_date is not None and sort_by_date not in ("newest", "oldest"):
        raise ValueError("sort_by_date must be 'newest' or 'oldest'")

    items, meta = compute_image_peak_percentile_scores(
        conn, min_perspectives=min_perspectives, include_ineligible=False
    )
    eligible = [i for i in items if i.get("eligible")]
    keys = [str(i["image_key"]) for i in eligible]
    img_meta = _image_meta_map(conn, keys)

    enriched: list[dict[str, Any]] = []
    for i in eligible:
        k = str(i["image_key"])
        im = img_meta.get(k, {})
        enriched.append({**i, **im})

    ekeys = [str(r["image_key"]) for r in enriched]
    drop_keys = _stack_non_representative_keys(conn, ekeys)
    enriched = [r for r in enriched if str(r["image_key"]) not in drop_keys]

    if enriched:
        skeys = [str(r["image_key"]) for r in enriched]
        stack_by_key = _stack_fields_for_image_keys(conn, skeys)
        for r in enriched:
            k = str(r["image_key"])
            if k in stack_by_key:
                r.update(stack_by_key[k])
            else:
                r["stack_id"] = None
                r["stack_member_count"] = None
                r["is_stack_representative"] = False

    date_reverse = sort_by_date != "oldest"
    enriched.sort(key=lambda r: r["image_key"])
    enriched.sort(key=lambda r: r.get("date_taken") or "", reverse=date_reverse)
    enriched.sort(key=lambda r: r["peak_percentile"], reverse=True)

    if posted is True:
        enriched = [r for r in enriched if bool(r.get("instagram_posted")) is True]
    elif posted is False:
        enriched = [r for r in enriched if bool(r.get("instagram_posted")) is False]

    total = len(enriched)
    page = enriched[offset : offset + limit]
    return page, total, meta
