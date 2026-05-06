"""Temporary identity_service slice: ranking + suggestions (removed in 15-06-T03)."""

from __future__ import annotations

import sqlite3
from collections import Counter
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Any, cast

from lightroom_tagger.core.posting_analytics import get_posting_frequency

from .aggregates import _SCORES_BASE_SQL, _tokenize_rationale, compute_image_aggregate_scores


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
    """Eligible images only, sorted by aggregate_score DESC, date_taken, key ASC.

    ``sort_by_date`` (``newest`` / ``oldest``) only controls the date tiebreaker;
    score remains the primary sort key.
    """
    if sort_by_date is not None and sort_by_date not in ("newest", "oldest"):
        raise ValueError("sort_by_date must be 'newest' or 'oldest'")

    items, meta = compute_image_aggregate_scores(
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
    enriched.sort(key=lambda r: r["aggregate_score"], reverse=True)

    if posted is True:
        enriched = [r for r in enriched if bool(r.get("instagram_posted")) is True]
    elif posted is False:
        enriched = [r for r in enriched if bool(r.get("instagram_posted")) is False]

    total = len(enriched)
    page = enriched[offset : offset + limit]
    return page, total, meta


def _posted_catalog_keys_sql() -> str:
    """Catalog keys treated as posted: flag or validated dump match (aligned with Phase 7)."""
    return """
        SELECT DISTINCT i.key AS image_key
        FROM images i
        WHERE i.instagram_posted = 1
        UNION
        SELECT DISTINCT m.catalog_key AS image_key
        FROM matches m
        WHERE m.validated_at IS NOT NULL
    """


def suggest_what_to_post_next(
    conn: sqlite3.Connection,
    *,
    limit: int,
    offset: int = 0,
    lookback_days_recent: int = 30,
    lookback_days_baseline: int = 90,
    sort_by_date: str | None = None,
) -> dict[str, Any]:
    """Unposted, coverage-eligible catalog images with heuristic reasons (D-44–D-46).

    ``sort_by_date`` (``newest`` / ``oldest``) only controls the date tiebreaker;
    aggregate score remains the primary sort key.
    """
    if sort_by_date is not None and sort_by_date not in ("newest", "oldest"):
        raise ValueError("sort_by_date must be 'newest' or 'oldest'")

    items, agg_meta = compute_image_aggregate_scores(conn, include_ineligible=False)
    keys = [str(i["image_key"]) for i in items if i.get("eligible")]
    img_meta = _image_meta_map(conn, keys)

    candidates_full: list[dict[str, Any]] = []
    for i in items:
        if not i.get("eligible"):
            continue
        k = str(i["image_key"])
        im = img_meta.get(k, {})
        if im.get("instagram_posted"):
            continue
        candidates_full.append({**i, **im})

    date_reverse = sort_by_date != "oldest"
    candidates_full.sort(key=lambda r: r["image_key"])
    candidates_full.sort(key=lambda r: r.get("date_taken") or "", reverse=date_reverse)
    candidates_full.sort(key=lambda r: r["aggregate_score"], reverse=True)

    unposted_aggs = [float(c["aggregate_score"]) for c in candidates_full]
    if unposted_aggs:
        sorted_aggs = sorted(unposted_aggs)
        idx = max(0, int(round(0.9 * (len(sorted_aggs) - 1))))
        p90 = sorted_aggs[idx]
    else:
        p90 = 10.0

    # Posted rationale tokens (D-46): current catalog scores for posted keys.
    posted_keys_rows = conn.execute(_posted_catalog_keys_sql()).fetchall()
    posted_key_set = {str(r["image_key"]) for r in posted_keys_rows}
    posted_token_counter: Counter[str] = Counter()
    for r in conn.execute(_SCORES_BASE_SQL).fetchall():
        if str(r["image_key"]) not in posted_key_set:
            continue
        rat = r.get("rationale")
        if isinstance(rat, str) and rat.strip():
            posted_token_counter.update(_tokenize_rationale(rat))

    posted_top = [t for t, c in posted_token_counter.most_common(25) if c >= 2]

    # Cadence (D-45): compare recent vs older window using validated posts.
    suggestions_meta: dict[str, Any] = {
        "weighting": agg_meta.get("weighting"),
        "min_perspectives_used": agg_meta.get("min_perspectives_used"),
        "coverage_rule": agg_meta.get("coverage_rule"),
        "timezone_assumption": "UTC",
        "high_score_rule": (
            "reason code high_score_unposted when aggregate_score >= p90 of eligible "
            "unposted images' aggregate scores."
        ),
        "posted_semantics": (
            "Posted set for theme heuristic: instagram_posted=1 OR validated match "
            "on catalog_key (same population family as posting_analytics)."
        ),
    }

    today = datetime.now(timezone.utc).date()
    recent_start = today - timedelta(days=max(1, lookback_days_recent) - 1)
    recent_end = today
    baseline_end = today - timedelta(days=lookback_days_recent)
    baseline_start = today - timedelta(
        days=lookback_days_recent + max(1, lookback_days_baseline) - 1
    )

    cadence_note: str | None = None
    try:
        buckets_r, _ = get_posting_frequency(
            conn,
            date_from=recent_start.isoformat(),
            date_to=recent_end.isoformat(),
            granularity="day",
        )
        buckets_b, _ = get_posting_frequency(
            conn,
            date_from=baseline_start.isoformat(),
            date_to=baseline_end.isoformat(),
            granularity="day",
        )
        recent_total = sum(cast(int, b["count"]) for b in buckets_r)
        base_total = sum(cast(int, b["count"]) for b in buckets_b)
        days_r = max(1, lookback_days_recent)
        days_b = max(1, lookback_days_baseline)
        rate_r = recent_total / days_r
        rate_b = base_total / days_b if base_total else 0.0
        # Below half the baseline daily rate → global cadence hint (only if baseline had posts).
        if base_total > 0 and rate_r < 0.5 * rate_b:
            cadence_note = (
                "Recent posting rate is below half the prior-window daily average "
                f"(validated dump posts: last {lookback_days_recent}d vs preceding "
                f"{lookback_days_baseline}d)."
            )
            suggestions_meta["cadence_gap"] = True
    except Exception:
        cadence_note = None

    if cadence_note:
        suggestions_meta["cadence_note"] = cadence_note

    mid = median(unposted_aggs) if unposted_aggs else 0.0

    total_candidates = len(candidates_full)
    lim = max(0, limit)
    page = candidates_full[offset : offset + lim]

    out_candidates: list[dict[str, Any]] = []
    for cand in page:
        reasons: list[str] = []
        codes: list[str] = []
        agg = float(cand["aggregate_score"])
        if agg >= p90:
            reasons.append(
                "Strong aggregate score among scored, unposted catalog images "
                f"(aggregate={agg:.2f})."
            )
            codes.append("high_score_unposted")

        if cadence_note and agg >= mid:
            reasons.append(
                "Posting cadence has slowed versus your earlier window; "
                "this image remains a strong candidate."
            )
            codes.append("cadence_gap")

        cand_tokens: Counter[str] = Counter()
        for p in cand.get("per_perspective") or []:
            prev = p.get("rationale_preview") or ""
            cand_tokens.update(_tokenize_rationale(prev))
        for tok in posted_top:
            posted_c = posted_token_counter.get(tok, 0)
            if posted_c < 2:
                continue
            if cand_tokens.get(tok, 0) == 0:
                reasons.append(
                    f"Theme '{tok}' appears often in posted-image score rationales "
                    "but not in this image's rationale snippets — possible variety gap."
                )
                codes.append("underrepresented_theme")
                break

        if not reasons:
            reasons.append(
                "Unposted catalog image with sufficient perspective coverage; "
                "ranked by aggregate score among eligible candidates."
            )
            codes.append("eligible_unposted")

        out_candidates.append(
            {
                "image_key": cand["image_key"],
                "filename": cand.get("filename", ""),
                "date_taken": cand.get("date_taken", ""),
                "rating": cand.get("rating", 0),
                "aggregate_score": cand["aggregate_score"],
                "perspectives_covered": cand["perspectives_covered"],
                "per_perspective": cand.get("per_perspective", []),
                "reasons": reasons,
                "reason_codes": codes,
            }
        )

    empty_state: str | None = None
    if not out_candidates:
        empty_state = (
            "No unposted catalog images meet perspective coverage with current scores."
        )

    return {
        "candidates": out_candidates,
        "total": total_candidates,
        "meta": suggestions_meta,
        "empty_state": empty_state,
    }
