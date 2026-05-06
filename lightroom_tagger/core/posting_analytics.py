"""Posting analytics over the library DB (validated Instagram dump matches).

Population (D-30): rows are **confirmed posts** — ``instagram_dump_media`` joined to
``matches`` where ``matches.insta_key = instagram_dump_media.media_key`` and
``matches.validated_at IS NOT NULL``. One row per ``media_key`` (``SELECT DISTINCT``)
so carousel / duplicate keys are not double-counted if multiple catalog keys were ever
validated for the same media key (an abnormal case; DISTINCT still collapses per media).

Event time (D-31): ``COALESCE(NULLIF(trim(created_at), ''), synthetic UTC midnight from
date_folder)``. When ``created_at`` is missing, ``date_folder`` is treated as
``YYYYMM`` when ``length(trim(date_folder)) >= 6``: first day of that month at
``00:00:00Z``. Rows with neither a usable ``created_at`` nor ``date_folder`` are
excluded from time-bounded queries.

All SQL uses bound parameters only (no string-built predicates from user input).
"""

from __future__ import annotations

import re
import sqlite3
from datetime import date, datetime, timedelta
from typing import Literal

from lightroom_tagger.core.text_constants import EN_STOPWORDS

# Full-width number sign (D-34)
_HASHTAG_RE = re.compile(r"[#＃](\w+)", flags=re.UNICODE)

_EN_STOPWORDS: frozenset[str] = EN_STOPWORDS


def posted_dump_media_cte_sql() -> str:
    """Return the shared ``posted_dump_media`` CTE body (no leading ``WITH``).

    Joins ``instagram_dump_media`` to ``matches`` with ``validated_at IS NOT NULL``.
    """
    return """
    posted_dump_media AS (
        SELECT DISTINCT
            m.media_key,
            m.caption,
            COALESCE(
                NULLIF(TRIM(m.created_at), ''),
                CASE
                    WHEN LENGTH(TRIM(COALESCE(m.date_folder, ''))) >= 6
                    THEN
                        SUBSTR(TRIM(m.date_folder), 1, 4)
                        || '-'
                        || SUBSTR(TRIM(m.date_folder), 5, 2)
                        || '-01T00:00:00Z'
                END
            ) AS event_iso
        FROM instagram_dump_media m
        INNER JOIN matches mat
            ON mat.insta_key = m.media_key
            AND mat.validated_at IS NOT NULL
    )
    """


def _parse_iso_date(value: str) -> date:
    return datetime.strptime(value[:10], "%Y-%m-%d").date()


def _daterange_inclusive(d0: date, d1: date) -> list[date]:
    out: list[date] = []
    cur = d0
    while cur <= d1:
        out.append(cur)
        cur += timedelta(days=1)
    return out


def _week_start_sunday(d: date) -> date:
    """Calendar week starting Sunday (aligns with SQLite ``strftime('%%w', ...)``)."""
    return d - timedelta(days=(d.weekday() + 1) % 7)


def _next_month(d: date) -> date:
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)


def _iter_month_starts(d0: date, d1: date) -> list[date]:
    cur = date(d0.year, d0.month, 1)
    end = date(d1.year, d1.month, 1)
    out: list[date] = []
    while cur <= end:
        out.append(cur)
        cur = _next_month(cur)
    return out


def get_posting_frequency(
    db: sqlite3.Connection,
    *,
    date_from: str,
    date_to: str,
    granularity: Literal["day", "week", "month"],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Bucket counts of validated posts between ``date_from`` and ``date_to`` (inclusive).

    Returns ``(buckets, meta)`` where each bucket is
    ``{"bucket_start": "<ISO date string>", "count": int}`` sorted ascending.
    Missing buckets are zero-filled (D-32).
    """
    d0 = _parse_iso_date(date_from)
    d1 = _parse_iso_date(date_to)

    cte = posted_dump_media_cte_sql()
    if granularity == "day":
        bucket_expr = "DATE(p.event_iso)"
        sql = f"""
        WITH {cte.strip()}
        SELECT DATE(p.event_iso) AS bucket_start, COUNT(*) AS cnt
        FROM posted_dump_media p
        WHERE p.event_iso IS NOT NULL
          AND DATE(p.event_iso) >= DATE(?)
          AND DATE(p.event_iso) <= DATE(?)
        GROUP BY bucket_start
        """
    elif granularity == "week":
        # Sunday-based week start in SQLite: weekday 0 = Sunday
        bucket_expr = "DATE(DATETIME(p.event_iso), 'weekday 0')"
        sql = f"""
        WITH {cte.strip()}
        SELECT DATE(DATETIME(p.event_iso), 'weekday 0') AS bucket_start, COUNT(*) AS cnt
        FROM posted_dump_media p
        WHERE p.event_iso IS NOT NULL
          AND DATE(p.event_iso) >= DATE(?)
          AND DATE(p.event_iso) <= DATE(?)
        GROUP BY bucket_start
        """
    elif granularity == "month":
        bucket_expr = "SUBSTR(DATE(p.event_iso), 1, 7) || '-01'"
        sql = f"""
        WITH {cte.strip()}
        SELECT (SUBSTR(DATE(p.event_iso), 1, 7) || '-01') AS bucket_start, COUNT(*) AS cnt
        FROM posted_dump_media p
        WHERE p.event_iso IS NOT NULL
          AND DATE(p.event_iso) >= DATE(?)
          AND DATE(p.event_iso) <= DATE(?)
        GROUP BY bucket_start
        """
    else:
        raise ValueError(f"unsupported granularity: {granularity}")

    rows = db.execute(sql, (date_from, date_to)).fetchall()
    counts: dict[str, int] = {}
    for r in rows:
        key = r["bucket_start"]
        if key is None:
            continue
        counts[str(key)] = int(r["cnt"])

    if granularity == "day":
        bucket_keys = [d.isoformat() for d in _daterange_inclusive(d0, d1)]
    elif granularity == "week":
        ws0 = _week_start_sunday(d0)
        ws1 = _week_start_sunday(d1)
        bucket_keys = []
        cur = ws0
        while cur <= ws1:
            bucket_keys.append(cur.isoformat())
            cur += timedelta(days=7)
    else:
        bucket_keys = [d.isoformat() for d in _iter_month_starts(d0, d1)]

    if granularity == "week":
        counts_norm: dict[str, int] = {}
        for k, v in counts.items():
            try:
                kd = _parse_iso_date(str(k))
                norm = _week_start_sunday(kd).isoformat()
                counts_norm[norm] = counts_norm.get(norm, 0) + int(v)
            except ValueError:
                counts_norm[str(k)] = counts_norm.get(str(k), 0) + int(v)
        counts = counts_norm

    buckets = [{"bucket_start": bk, "count": int(counts.get(bk, 0))} for bk in bucket_keys]

    meta: dict[str, object] = {
        "timestamp_source": "coalesce(created_at, date_folder_month_start_utc)",
        "granularity": granularity,
        "timezone_assumption": "UTC",
        "date_from": date_from,
        "date_to": date_to,
        "bucket_expression": bucket_expr,
    }
    return buckets, meta


def get_posting_time_heatmap(
    db: sqlite3.Connection,
    *,
    date_from: str,
    date_to: str,
) -> tuple[list[dict[str, int]], dict[str, object]]:
    """Day-of-week (0=Sunday) × hour (0–23) counts in UTC (D-33)."""
    cte = posted_dump_media_cte_sql()
    sql = f"""
    WITH {cte.strip()}
    SELECT
        CAST(STRFTIME('%w', DATETIME(p.event_iso)) AS INTEGER) AS dow,
        CAST(STRFTIME('%H', DATETIME(p.event_iso)) AS INTEGER) AS hour,
        COUNT(*) AS cnt
    FROM posted_dump_media p
    WHERE p.event_iso IS NOT NULL
      AND DATE(p.event_iso) >= DATE(?)
      AND DATE(p.event_iso) <= DATE(?)
    GROUP BY dow, hour
    """
    rows = db.execute(sql, (date_from, date_to)).fetchall()
    grid: dict[tuple[int, int], int] = {}
    for r in rows:
        dow = int(r["dow"])
        hour = int(r["hour"])
        grid[(dow, hour)] = int(r["cnt"])

    cells: list[dict[str, int]] = []
    for dow in range(7):
        for hour in range(24):
            cells.append({"dow": dow, "hour": hour, "count": int(grid.get((dow, hour), 0))})

    meta: dict[str, object] = {
        "dow_labels": ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
        "timezone_assumption": "UTC",
        "timezone_note": (
            "dow/hour are from DATETIME(event_iso) in SQLite (UTC Z suffix when present; "
            "date_folder fallback uses month-start midnight UTC)."
        ),
        "date_from": date_from,
        "date_to": date_to,
    }
    return cells, meta


from lightroom_tagger.core.posting_analytics_captions import (
    get_caption_hashtag_stats,
    query_unposted_catalog,
)
