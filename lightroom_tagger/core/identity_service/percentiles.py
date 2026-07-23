"""Within-perspective percentile ranks over the eligible identity population."""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from typing import Any

from .aggregates import (
    _SCORES_BASE_SQL,
    _active_perspective_slugs,
    _default_min_perspectives,
    _truncate_rationale,
)


def _midrank_percentile_ranks(scores: list[int]) -> dict[int, float]:
    """Map each distinct raw score to a percentile rank in [0, 1] (midrank ties)."""
    n = len(scores)
    if n == 0:
        return {}
    if n == 1:
        return {scores[0]: 1.0}

    counts: dict[int, int] = defaultdict(int)
    for s in scores:
        counts[s] += 1

    out: dict[int, float] = {}
    below = 0
    for score in sorted(counts):
        tied = counts[score]
        # 1-based average rank for tied values.
        midrank = below + (tied + 1) / 2.0
        out[score] = (midrank - 1) / (n - 1)
        below += tied
    return out


def compute_within_perspective_percentile_lookup(
    conn: sqlite3.Connection,
) -> dict[tuple[str, str], float]:
    """Percentile rank in [0, 1] for each (image_key, perspective_slug) score cell.

  Computed once over the eligible population from :data:`_SCORES_BASE_SQL`
  (``is_current=1``, ``image_type='catalog'``, ``not_attempted=0``, active
  perspectives), with midrank tie handling within each perspective.
    """
    rows = conn.execute(_SCORES_BASE_SQL).fetchall()
    scores_by_perspective: dict[str, list[int]] = defaultdict(list)
    cells: list[tuple[str, str, int]] = []

    for r in rows:
        image_key = str(r["image_key"])
        slug = str(r["perspective_slug"])
        score = int(r["score"])
        scores_by_perspective[slug].append(score)
        cells.append((image_key, slug, score))

    score_percentile_by_perspective = {
        slug: _midrank_percentile_ranks(scores)
        for slug, scores in scores_by_perspective.items()
    }

    lookup: dict[tuple[str, str], float] = {}
    for image_key, slug, score in cells:
        lookup[(image_key, slug)] = score_percentile_by_perspective[slug][score]
    return lookup


def compute_image_peak_percentile_scores(
    conn: sqlite3.Connection,
    *,
    min_perspectives: int | None = None,
    include_ineligible: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Per-image peak within-perspective percentile plus per-perspective detail.

    Returns ``(items, meta)``. Each item includes ``peak_percentile`` (max
    percentile across the image's scored lenses), ``perspectives_covered``,
  ``eligible``, and ``per_perspective`` entries with ``percentile``.
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

    percentile_lookup = compute_within_perspective_percentile_lookup(conn)
    rows = conn.execute(_SCORES_BASE_SQL).fetchall()

    by_key: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        slug = str(r["perspective_slug"])
        if slug not in slug_set:
            continue
        image_key = str(r["image_key"])
        score = int(r["score"])
        percentile = percentile_lookup[(image_key, slug)]
        by_key.setdefault(image_key, []).append(
            {
                "perspective_slug": slug,
                "display_name": r["perspective_display_name"] or slug,
                "score": score,
                "percentile": round(percentile, 6),
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
        peak = max(p["percentile"] for p in perspectives) if perspectives else 0.0
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
                    "percentile": p["percentile"],
                    "prompt_version": p["prompt_version"],
                    "model_used": p["model_used"],
                    "scored_at": p["scored_at"],
                    "rationale_preview": _truncate_rationale(p.get("rationale")),
                }
            )

        row = {
            "image_key": image_key,
            "peak_percentile": round(peak, 6),
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
        "weighting": "peak_within_perspective_percentile",
        "ranking_key": "peak_percentile",
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
