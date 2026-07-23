"""Post-next suggestions from coverage-eligible catalog gaps."""

from __future__ import annotations

import sqlite3
from typing import Any

from .mirror import build_mirror_scan, compute_signature_stats
from .percentiles import compute_image_peak_percentile_scores
from .ranking import _image_meta_map


def _peak_perspective(per_perspective: list[dict[str, Any]]) -> dict[str, Any]:
    return sorted(
        per_perspective,
        key=lambda p: (-float(p.get("percentile") or 0.0), str(p.get("perspective_slug") or "")),
    )[0]


def suggest_what_to_post_next(
    conn: sqlite3.Connection,
    *,
    limit: int,
    offset: int = 0,
    sort_by_date: str | None = None,
) -> dict[str, Any]:
    """Unposted, coverage-eligible catalog images with heuristic reasons (D-44–D-46).

    ``sort_by_date`` (``newest`` / ``oldest``) only controls the date tiebreaker;
    peak within-perspective percentile remains the primary sort key.
    """
    if sort_by_date is not None and sort_by_date not in ("newest", "oldest"):
        raise ValueError("sort_by_date must be 'newest' or 'oldest'")

    scan = build_mirror_scan(conn)
    items, peak_meta = compute_image_peak_percentile_scores(
        conn,
        include_ineligible=False,
        percentile_lookup=scan.percentile_lookup,
    )
    crowned = {s["perspective_slug"] for s in compute_signature_stats(scan) if s["crowned"]}
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
        per = list(i.get("per_perspective") or [])
        peak_lens = _peak_perspective(per) if per else {}
        slug = str(peak_lens.get("perspective_slug") or "")
        candidates_full.append(
            {
                **i,
                **im,
                "peak_perspective_slug": slug,
                "peak_perspective_display_name": str(
                    peak_lens.get("display_name") or slug
                ),
                "is_signature": slug in crowned if slug else False,
            }
        )

    date_reverse = sort_by_date != "oldest"
    candidates_full.sort(key=lambda r: r["image_key"])
    candidates_full.sort(key=lambda r: r.get("date_taken") or "", reverse=date_reverse)
    candidates_full.sort(key=lambda r: r["peak_percentile"], reverse=True)

    unposted_peaks = [float(c["peak_percentile"]) for c in candidates_full]
    if unposted_peaks:
        sorted_peaks = sorted(unposted_peaks)
        idx = max(0, int(round(0.9 * (len(sorted_peaks) - 1))))
        p90 = sorted_peaks[idx]
    else:
        p90 = 1.0

    suggestions_meta: dict[str, Any] = {
        "weighting": peak_meta.get("weighting"),
        "ranking_key": peak_meta.get("ranking_key"),
        "min_perspectives_used": peak_meta.get("min_perspectives_used"),
        "coverage_rule": peak_meta.get("coverage_rule"),
        "high_score_rule": (
            "reason code high_score_unposted when peak_percentile >= p90 of eligible "
            "unposted images' peak within-perspective percentiles."
        ),
    }

    total_candidates = len(candidates_full)
    lim = max(0, limit)
    page = candidates_full[offset : offset + lim]

    out_candidates: list[dict[str, Any]] = []
    for cand in page:
        reasons: list[str] = []
        codes: list[str] = []
        peak = float(cand["peak_percentile"])
        lens_name = str(cand.get("peak_perspective_display_name") or "")
        is_sig = bool(cand.get("is_signature"))
        if peak >= p90:
            reasons.append(
                "Strong peak percentile among scored, unposted catalog images "
                f"(peak_percentile={peak:.4f})."
            )
            codes.append("high_score_unposted")

        if lens_name:
            if is_sig:
                reasons.append(
                    f"Peak lens is {lens_name}, one of your crowned signature techniques."
                )
            else:
                reasons.append(f"Peak lens is {lens_name}.")

        if not codes:
            reasons.append(
                "Unposted catalog image with sufficient perspective coverage; "
                "ranked by peak within-perspective percentile among eligible candidates."
            )
            codes.append("eligible_unposted")

        out_candidates.append(
            {
                "image_key": cand["image_key"],
                "filename": cand.get("filename", ""),
                "date_taken": cand.get("date_taken", ""),
                "rating": cand.get("rating", 0),
                "peak_percentile": cand["peak_percentile"],
                "peak_perspective_slug": cand.get("peak_perspective_slug", ""),
                "peak_perspective_display_name": cand.get("peak_perspective_display_name", ""),
                "is_signature": is_sig,
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
