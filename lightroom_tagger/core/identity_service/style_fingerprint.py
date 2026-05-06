"""Catalog-wide style fingerprint from score patterns."""

from __future__ import annotations

import sqlite3
from collections import Counter
from statistics import median
from typing import Any

from .aggregates import (
    _SCORES_BASE_SQL,
    _active_perspective_slugs,
    _tokenize_rationale,
    compute_image_aggregate_scores,
)


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
