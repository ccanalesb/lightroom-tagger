"""Caption statistics and lightweight unposted-catalog listing."""

from __future__ import annotations

import re
import sqlite3
from collections import Counter

from lightroom_tagger.core.database import query_catalog_images

from lightroom_tagger.core.posting_analytics import _EN_STOPWORDS, _HASHTAG_RE


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
    from lightroom_tagger.core.posting_analytics import posted_dump_media_cte_sql

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
