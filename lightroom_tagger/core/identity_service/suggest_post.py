"""Post-next suggestions from coverage-eligible catalog gaps."""

from __future__ import annotations

import sqlite3
from collections import Counter
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Any, cast

from lightroom_tagger.core.posting_analytics import get_posting_frequency

from .aggregates import _SCORES_BASE_SQL, _tokenize_rationale, compute_image_aggregate_scores
from .ranking import _image_meta_map


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
