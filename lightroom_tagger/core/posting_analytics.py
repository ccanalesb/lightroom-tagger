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
from collections import Counter
from datetime import date, datetime, timedelta
from typing import Literal

from lightroom_tagger.core.database import query_catalog_images

# Full-width number sign (D-34)
_HASHTAG_RE = re.compile(r"[#＃](\w+)", flags=re.UNICODE)

_EN_STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "as",
        "is",
        "was",
        "are",
        "were",
        "be",
        "been",
        "being",
        "it",
        "this",
        "that",
        "these",
        "those",
        "i",
        "you",
        "he",
        "she",
        "we",
        "they",
        "my",
        "your",
        "our",
        "their",
    }
)


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


def _normalize_hashtag_token(raw: str) -> str:
    t = raw.lower().strip()
    return t.rstrip(".,;:!?)")


def _extract_hashtags(caption: str | None) -> list[str]:
    if not caption:
        return []
    found = _HASHTAG_RE.findall(caption)
    out: list[str] = []
    for h in found:
        n = _normalize_hashtag_token(h)
        if n:
            out.append(n)
    return out


def _extract_words(caption: str, hashtag_spans: set[str]) -> list[str]:
    """Whitespace tokens minus hashtags and English stopwords (minimal list)."""
    lowered = caption.lower()
    # Remove hashtag tokens crudely for word stats
    for tag in hashtag_spans:
        lowered = lowered.replace(f"#{tag}", " ")
        lowered = lowered.replace(f"＃{tag}", " ")
    words: list[str] = []
    for raw in re.split(r"\s+", lowered):
        w = raw.strip().strip(".,;:!?()[]\"'")
        if not w or w in _EN_STOPWORDS or len(w) < 2:
            continue
        if w.startswith("#") or w.startswith("＃"):
            continue
        words.append(w)
    return words


def get_caption_hashtag_stats(
    db: sqlite3.Connection,
    *,
    date_from: str,
    date_to: str,
    top_hashtag_limit: int = 30,
    top_word_limit: int = 20,
) -> dict[str, object]:
    """Aggregate caption and hashtag stats for validated posts in the date range."""
    cte = posted_dump_media_cte_sql()
    sql = f"""
    WITH {cte.strip()}
    SELECT p.media_key, p.caption
    FROM posted_dump_media p
    WHERE p.event_iso IS NOT NULL
      AND DATE(p.event_iso) >= DATE(?)
      AND DATE(p.event_iso) <= DATE(?)
    """
    rows = db.execute(sql, (date_from, date_to)).fetchall()

    post_count = len(rows)
    lengths: list[int] = []
    with_caption = 0
    tag_counter: Counter[str] = Counter()
    posts_with_tags = 0
    hashtag_counts_per_post: list[int] = []

    word_counter: Counter[str] = Counter()

    for r in rows:
        cap = r.get("caption")
        cap_s = cap if isinstance(cap, str) else ""
        if cap_s.strip():
            with_caption += 1
        lengths.append(len(cap_s))
        tags = _extract_hashtags(cap_s)
        unique_tags = sorted(set(tags))
        hashtag_counts_per_post.append(len(unique_tags))
        if unique_tags:
            posts_with_tags += 1
        tag_counter.update(unique_tags)
        span_set = set(unique_tags)
        word_counter.update(_extract_words(cap_s, span_set))

    avg_len = sum(lengths) / post_count if post_count else 0.0
    med_len: float | None
    if lengths:
        srt = sorted(lengths)
        mid = len(srt) // 2
        med_len = (
            float(srt[mid]) if len(srt) % 2 == 1 else (srt[mid - 1] + srt[mid]) / 2.0
        )
    else:
        med_len = None

    avg_tags = (
        sum(hashtag_counts_per_post) / post_count if post_count and hashtag_counts_per_post else 0.0
    )

    top_tags = [
        {"tag": tag, "count": cnt}
        for tag, cnt in tag_counter.most_common(top_hashtag_limit)
    ]
    top_words = [
        {"word": w, "count": cnt} for w, cnt in word_counter.most_common(top_word_limit)
    ]

    return {
        "post_count": post_count,
        "with_caption_count": with_caption,
        "avg_caption_len": avg_len,
        "median_caption_len": med_len,
        "top_hashtags": top_tags,
        "posts_with_hashtags": posts_with_tags,
        "avg_hashtags_per_post": float(avg_tags),
        "top_words": top_words,
        "meta": {
            "timezone_assumption": "UTC",
            "hashtag_pattern": r"[#＃][\w]+",
            "timestamp_scope": "same as posting series (validated dump media, event date filter)",
        },
    }


def query_unposted_catalog(
    db: sqlite3.Connection,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    min_rating: int | None = None,
    month: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, object]], int]:
    """Catalog rows with ``instagram_posted = 0`` and optional catalog filters (D-36).

    Returns lightweight dicts ``key``, ``filename``, ``date_taken``, ``rating`` and total.
    """
    rows, total = query_catalog_images(
        db,
        posted=False,
        month=month,
        min_rating=min_rating,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    light: list[dict[str, object]] = []
    for r in rows:
        light.append(
            {
                "key": r.get("key"),
                "filename": r.get("filename"),
                "date_taken": r.get("date_taken"),
                "rating": r.get("rating"),
            }
        )
    return light, total
