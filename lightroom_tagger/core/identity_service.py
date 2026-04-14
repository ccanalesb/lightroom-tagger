"""Catalog identity aggregation: best-photo ranking, style fingerprint, post-next hints.

Design decisions D-40–D-47 are documented in
``.planning/phases/08-identity-suggestions/08-CONTEXT.md``:
equal-weight aggregate over **active** perspectives and **current** catalog scores
(``is_current = 1``, ``image_type = 'catalog'``), coverage guards (D-41),
rationale token stats without embeddings/NLP (D-43), and suggestion reason codes
(D-44–D-46). Cadence uses the same validated-dump population as
:mod:`lightroom_tagger.core.posting_analytics` (``get_posting_frequency``).
"""

from __future__ import annotations

import re
import sqlite3
from collections import Counter
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Any, cast

from lightroom_tagger.core.posting_analytics import _EN_STOPWORDS, get_posting_frequency

# Current catalog scores only — identity aggregation excludes non-catalog rows (D-40 / phase 10).
_SCORES_BASE_SQL = """
    SELECT
        s.image_key,
        s.image_type,
        s.perspective_slug,
        s.score,
        s.rationale,
        s.model_used,
        s.prompt_version,
        s.scored_at,
        p.display_name AS perspective_display_name
    FROM image_scores s
    INNER JOIN perspectives p
        ON p.slug = s.perspective_slug AND p.active = 1
    WHERE s.is_current = 1
        AND s.image_type = 'catalog'
"""

_WORD_RE = re.compile(r"[\w']+", flags=re.UNICODE)

_RATIONALE_PREVIEW_MAX = 240


def _active_perspective_slugs(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT slug FROM perspectives WHERE active = 1 ORDER BY slug ASC"
    ).fetchall()
    return [str(r["slug"]) for r in rows]


def _default_min_perspectives(active_count: int) -> int:
    """Minimum 1 perspective required for eligibility."""
    return 1


def _tokenize_rationale(text: str | None) -> list[str]:
    """D-43: lowercase word tokens, length >= 3, minimal English stopwords dropped."""
    if not text:
        return []
    out: list[str] = []
    for m in _WORD_RE.finditer(text.lower()):
        w = m.group(0).strip("'")
        if len(w) < 3 or w in _EN_STOPWORDS:
            continue
        out.append(w)
    return out


def _truncate_rationale(text: str | None, max_chars: int = _RATIONALE_PREVIEW_MAX) -> str:
    if not text:
        return ""
    t = text.strip()
    if len(t) <= max_chars:
        return t
    return t[: max_chars - 1].rstrip() + "…"


def compute_image_aggregate_scores(
    conn: sqlite3.Connection,
    *,
    min_perspectives: int | None = None,
    include_ineligible: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build per-image aggregates over active perspectives (equal weights, D-40).

    Returns ``(items, meta)``. Each item includes ``per_perspective`` entries with
    ``rationale_preview`` (truncated). When ``include_ineligible`` is False, only
    eligible rows are returned (used internally for tighter payloads).
    """
    active_slugs = _active_perspective_slugs(conn)
    active_count = len(active_slugs)
    slug_set = set(active_slugs)
    min_used = (
        int(min_perspectives)
        if min_perspectives is not None
        else _default_min_perspectives(active_count)
    )

    total_catalog = int(
        conn.execute("SELECT COUNT(*) AS c FROM images").fetchone()["c"]
    )

    rows = conn.execute(_SCORES_BASE_SQL).fetchall()

    by_key: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        slug = str(r["perspective_slug"])
        if slug not in slug_set:
            continue
        by_key.setdefault(str(r["image_key"]), []).append(
            {
                "perspective_slug": slug,
                "display_name": r["perspective_display_name"] or slug,
                "score": int(r["score"]),
                "rationale": r.get("rationale") or "",
                "model_used": r.get("model_used") or "",
                "prompt_version": r.get("prompt_version") or "",
                "scored_at": r.get("scored_at") or "",
            }
        )

    items: list[dict[str, Any]] = []
    eligible_count = 0
    for image_key, perspectives in by_key.items():
        n = len(perspectives)
        agg = sum(p["score"] for p in perspectives) / n if n else 0.0
        eligible = n >= min_used
        if eligible:
            eligible_count += 1

        per_out: list[dict[str, Any]] = []
        for p in sorted(perspectives, key=lambda x: x["perspective_slug"]):
            per_out.append(
                {
                    "perspective_slug": p["perspective_slug"],
                    "display_name": p["display_name"],
                    "score": p["score"],
                    "prompt_version": p["prompt_version"],
                    "model_used": p["model_used"],
                    "scored_at": p["scored_at"],
                    "rationale_preview": _truncate_rationale(p.get("rationale")),
                }
            )

        row = {
            "image_key": image_key,
            "aggregate_score": round(agg, 4),
            "perspectives_covered": n,
            "eligible": eligible,
            "per_perspective": per_out,
        }
        if include_ineligible or eligible:
            items.append(row)

    scored_any_count = len(by_key)
    coverage_rule = "eligible when perspectives_covered >= min_perspectives (default 1)"
    meta: dict[str, Any] = {
        "active_perspectives": active_slugs,
        "weighting": "equal",
        "min_perspectives_used": min_used,
        "coverage_rule": coverage_rule,
        "total_catalog_images": total_catalog,
        "eligible_count": eligible_count,
        "scored_any_count": scored_any_count,
    }
    if eligible_count == 0 and active_count > 0:
        meta["coverage_note"] = (
            "No images meet the minimum perspective coverage for ranking; "
            "score at least one perspective per image."
        )
    return items, meta


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


def rank_best_photos(
    conn: sqlite3.Connection,
    *,
    limit: int,
    offset: int,
    min_perspectives: int | None = None,
) -> tuple[list[dict[str, Any]], int, dict[str, Any]]:
    """Eligible images only, sorted by aggregate_score DESC, date_taken DESC, key ASC."""
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

    enriched.sort(key=lambda r: r["image_key"])
    enriched.sort(key=lambda r: r.get("date_taken") or "", reverse=True)
    enriched.sort(key=lambda r: r["aggregate_score"], reverse=True)

    total = len(enriched)
    page = enriched[offset : offset + limit]
    return page, total, meta


def _aggregate_histogram(scores: list[float]) -> dict[str, int]:
    """Histogram over eligible aggregate scores (1–3 / 4–6 / 7–10 style buckets)."""
    buckets = {"1-3": 0, "4-6": 0, "7-10": 0}
    for s in scores:
        if s < 4:
            buckets["1-3"] += 1
        elif s < 7:
            buckets["4-6"] += 1
        else:
            buckets["7-10"] += 1
    return buckets


def build_style_fingerprint(conn: sqlite3.Connection) -> dict[str, Any]:
    """Catalog-wide fingerprint: per-perspective stats, histogram, tokens, evidence (D-42)."""
    active_slugs = _active_perspective_slugs(conn)
    rows = conn.execute(_SCORES_BASE_SQL).fetchall()

    slug_scores: dict[str, list[int]] = {s: [] for s in active_slugs}
    token_counter: Counter[str] = Counter()
    for r in rows:
        slug = str(r["perspective_slug"])
        if slug in slug_scores:
            slug_scores[slug].append(int(r["score"]))
        rationale = r.get("rationale")
        if isinstance(rationale, str) and rationale.strip():
            token_counter.update(_tokenize_rationale(rationale))

    per_perspective: list[dict[str, Any]] = []
    for slug in active_slugs:
        vals = slug_scores.get(slug) or []
        per_perspective.append(
            {
                "perspective_slug": slug,
                "mean_score": round(sum(vals) / len(vals), 4) if vals else None,
                "median_score": float(median(vals)) if vals else None,
                "count_scores": len(vals),
            }
        )

    items, _ = compute_image_aggregate_scores(conn, include_ineligible=False)
    eligible_aggs = [float(i["aggregate_score"]) for i in items if i.get("eligible")]
    aggregate_distribution = _aggregate_histogram(eligible_aggs)
    aggregate_distribution_note = (
        "Buckets count only images that meet default coverage (eligible aggregates)."
    )

    top_rationale_tokens = [
        {"token": t, "count": c} for t, c in token_counter.most_common(30)
    ]

    # Evidence: top 3 image_keys per slug by that slug's score among eligible; if no
    # eligible image has a score for that slug, fall back to top scored catalog rows.
    eligible_by_key = {str(i["image_key"]): i for i in items if i.get("eligible")}
    evidence: dict[str, list[str]] = {s: [] for s in active_slugs}

    for slug in active_slugs:
        scored_pairs: list[tuple[str, int]] = []
        for ek, agg_row in eligible_by_key.items():
            for p in agg_row.get("per_perspective") or []:
                if p.get("perspective_slug") == slug:
                    scored_pairs.append((ek, int(p["score"])))
                    break
        if len(scored_pairs) < 3:
            for r in rows:
                if str(r["perspective_slug"]) != slug:
                    continue
                scored_pairs.append((str(r["image_key"]), int(r["score"])))
        scored_pairs.sort(key=lambda x: (-x[1], x[0]))
        seen: set[str] = set()
        top_keys: list[str] = []
        for k, _ in scored_pairs:
            if k in seen:
                continue
            seen.add(k)
            top_keys.append(k)
            if len(top_keys) >= 3:
                break
        evidence[slug] = top_keys

    evidence_note = (
        "Example keys are top scores per perspective among coverage-eligible images "
        "when available; otherwise top current catalog scores for that slug."
    )

    return {
        "per_perspective": per_perspective,
        "aggregate_distribution": aggregate_distribution,
        "aggregate_distribution_note": aggregate_distribution_note,
        "top_rationale_tokens": top_rationale_tokens,
        "evidence": evidence,
        "evidence_note": evidence_note,
        "meta": {
            "tokenization_note": (
                "Unicode word tokens, lowercased, len>=3, minimal English stopwords; "
                "no stemming (D-43)."
            ),
            "perspectives_included": active_slugs,
            "weighting": "equal",
            "scores_are_advisory": (
                "Rankings reflect model/rubric versions at time of scoring (is_current rows)."
            ),
        },
    }


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
) -> dict[str, Any]:
    """Unposted, coverage-eligible catalog images with heuristic reasons (D-44–D-46)."""
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

    candidates_full.sort(key=lambda r: r["image_key"])
    candidates_full.sort(key=lambda r: r.get("date_taken") or "", reverse=True)
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
