"""Mirror signature + exemplars from within-perspective percentile ranks."""

from __future__ import annotations

import math
import sqlite3
from collections import Counter, defaultdict
from typing import Any

from .aggregates import (
    _SCORES_BASE_SQL,
    _active_perspective_slugs,
    _tokenize_rationale,
    _truncate_rationale,
)
from .percentiles import compute_within_perspective_percentile_lookup
from .ranking import (
    _image_meta_map,
    _stack_fields_for_image_keys,
    _stack_non_representative_keys,
)
from .signature import (
    _CROWN_ALPHA,
    _LOW_COVERAGE_THRESHOLD,
    _MIN_VOTING_LENSES,
    MirrorScan,
    compute_signature_stats,
)

_EXEMPLAR_INITIAL_LIMIT = 24
_EXEMPLAR_PAGE_SIZE = 12
_DESCRIPTOR_MIN_COUNT = 5
_DESCRIPTOR_LIMIT = 15


def _strength_label(*, z_score: float, crowned: bool, leading_not_distinctive: bool) -> str:
    if leading_not_distinctive:
        return "Leading, but not strongly distinctive"
    if z_score >= 6.0:
        return "A defining strength"
    if z_score >= 3.0:
        return "A clear strength"
    if crowned:
        return "A strength"
    return "Leading, but not strongly distinctive"


def _distinctive_descriptors(
    lens_rationales: list[str],
    corpus_rationales: list[str],
    *,
    min_count: int = _DESCRIPTOR_MIN_COUNT,
    limit: int = _DESCRIPTOR_LIMIT,
) -> list[dict[str, Any]]:
    lens_tokens: Counter[str] = Counter()
    corpus_tokens: Counter[str] = Counter()
    for text in lens_rationales:
        lens_tokens.update(_tokenize_rationale(text))
    for text in corpus_rationales:
        corpus_tokens.update(_tokenize_rationale(text))

    lens_total = sum(lens_tokens.values()) or 1
    corpus_total = sum(corpus_tokens.values()) or 1

    scored: list[tuple[str, float, int]] = []
    for token, lens_count in lens_tokens.items():
        if lens_count < min_count:
            continue
        corpus_count = corpus_tokens.get(token, 0)
        p_lens = lens_count / lens_total
        p_corpus = max(corpus_count, 0.5) / corpus_total
        if p_lens <= 0.0:
            continue
        log_odds = math.log(p_lens / p_corpus)
        scored.append((token, log_odds, lens_count))

    scored.sort(key=lambda row: (-row[1], -row[2], row[0]))
    return [
        {"token": token, "log_odds": round(log_odds, 4), "count": count}
        for token, log_odds, count in scored[:limit]
    ]


def _purity(lens_percentile: float, other_percentiles: list[float]) -> float:
    # Purity is a *separation*: how far this lens's percentile leads the image's
    # next-strongest lens (spec #207: "X-percentile - next-highest-percentile").
    # An image scored on only this lens has no other lens to separate from, so its
    # purity is undefined — report 0.0 (no demonstrated concentration) rather than
    # the raw percentile, which would let single-lens images out-rank genuinely
    # distinctive multi-lens ones in the exemplar tiebreak.
    if not other_percentiles:
        return 0.0
    return round((lens_percentile - max(other_percentiles)) * 100.0, 1)


def build_mirror_scan(conn: sqlite3.Connection) -> MirrorScan:
    active_slugs = _active_perspective_slugs(conn)
    slug_set = set(active_slugs)
    display_by_slug: dict[str, str] = {}
    rows = conn.execute(_SCORES_BASE_SQL).fetchall()
    for r in rows:
        slug = str(r["perspective_slug"])
        if slug not in slug_set:
            continue
        display_by_slug.setdefault(slug, str(r["perspective_display_name"] or slug))

    percentile_lookup = compute_within_perspective_percentile_lookup(conn)

    by_image: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rationales_by_slug: dict[str, list[str]] = {s: [] for s in active_slugs}
    corpus_rationales: list[str] = []

    for r in rows:
        slug = str(r["perspective_slug"])
        if slug not in slug_set:
            continue
        image_key = str(r["image_key"])
        percentile = percentile_lookup[(image_key, slug)]
        rationale = r.get("rationale") or ""
        if isinstance(rationale, str) and rationale.strip():
            rationales_by_slug[slug].append(rationale)
            corpus_rationales.append(rationale)
        by_image[image_key].append(
            {
                "perspective_slug": slug,
                "display_name": display_by_slug.get(slug, slug),
                "score": int(r["score"]),
                "percentile": percentile,
                "rationale": rationale,
            }
        )

    return MirrorScan(
        active_slugs=active_slugs,
        slug_set=slug_set,
        display_by_slug=display_by_slug,
        by_image=dict(by_image),
        rationales_by_slug=rationales_by_slug,
        corpus_rationales=corpus_rationales,
        percentile_lookup=percentile_lookup,
    )


def _lens_exemplar_candidates(
    slug: str,
    by_image: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for image_key, perspectives in by_image.items():
        match = next((p for p in perspectives if p["perspective_slug"] == slug), None)
        if match is None:
            continue
        others = [p["percentile"] for p in perspectives if p["perspective_slug"] != slug]
        candidates.append(
            {
                "image_key": image_key,
                "score": match["score"],
                "percentile": match["percentile"],
                "purity": _purity(match["percentile"], others),
                "rationale": match.get("rationale") or "",
                "per_perspective": perspectives,
            }
        )
    return candidates


def _format_exemplar_rows(
    conn: sqlite3.Connection,
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not rows:
        return []

    keys = [str(row["image_key"]) for row in rows]
    meta_map = _image_meta_map(conn, keys)
    stack_by_key = _stack_fields_for_image_keys(conn, keys)

    exemplars: list[dict[str, Any]] = []
    for row in rows:
        image_key = str(row["image_key"])
        per_out = []
        for p in sorted(row["per_perspective"], key=lambda x: x["perspective_slug"]):
            per_out.append(
                {
                    "perspective_slug": p["perspective_slug"],
                    "display_name": p["display_name"],
                    "score": p["score"],
                    "percentile": round(p["percentile"], 6),
                }
            )
        im = meta_map.get(image_key, {})
        stack = stack_by_key.get(image_key, {})
        exemplars.append(
            {
                "image_key": image_key,
                "score": row["score"],
                "percentile": round(row["percentile"] * 100.0, 1),
                "purity": row["purity"],
                "rationale_preview": _truncate_rationale(row["rationale"]),
                "per_perspective": per_out,
                "filename": im.get("filename") or "",
                "date_taken": im.get("date_taken") or "",
                "rating": int(im.get("rating") or 0),
                "instagram_posted": bool(im.get("instagram_posted")),
                "stack_id": stack.get("stack_id"),
                "stack_size": stack.get("stack_member_count"),
            }
        )
    return exemplars


def build_lens_exemplars(
    conn: sqlite3.Connection,
    slug: str,
    *,
    offset: int = 0,
    limit: int = _EXEMPLAR_INITIAL_LIMIT,
    scan: MirrorScan | None = None,
    drop_keys: set[str] | None = None,
) -> dict[str, Any]:
    """Ranked exemplars for one lens; collapses burst stacks to representatives."""
    if scan is None:
        scan = build_mirror_scan(conn)

    if slug not in scan.active_slugs:
        raise ValueError(f"unknown or inactive perspective slug: {slug}")

    candidates = _lens_exemplar_candidates(slug, scan.by_image)
    if drop_keys is None:
        candidate_keys = [str(c["image_key"]) for c in candidates]
        drop_keys = _stack_non_representative_keys(conn, candidate_keys)
    candidates = [c for c in candidates if str(c["image_key"]) not in drop_keys]

    candidates.sort(
        key=lambda row: (
            -row["percentile"],
            -row["purity"],
            row["image_key"],
        )
    )

    total = len(candidates)
    page = candidates[offset : offset + limit] if limit > 0 else []
    items = _format_exemplar_rows(conn, page)
    return {"items": items, "total": total}


def build_mirror(conn: sqlite3.Connection) -> dict[str, Any]:
    """Catalog Mirror: crowned signature lenses, descriptors, and exemplar rails."""
    scan = build_mirror_scan(conn)
    active_slugs = scan.active_slugs
    rationales_by_slug = scan.rationales_by_slug
    corpus_rationales = scan.corpus_rationales

    total_catalog = int(conn.execute("SELECT COUNT(*) AS c FROM images").fetchone()["c"])

    signature_stats = compute_signature_stats(scan, total_catalog=total_catalog)
    voting_population = sum(
        1 for perspectives in scan.by_image.values() if len(perspectives) >= _MIN_VOTING_LENSES
    )

    drop_keys = _stack_non_representative_keys(conn, list(scan.by_image.keys()))

    crowned_stats = [s for s in signature_stats if s["crowned"]]
    crowned_stats.sort(key=lambda s: (-s["z_score"], s["perspective_slug"]))

    fallback = False
    section_stats = crowned_stats
    if not section_stats and signature_stats:
        fallback = True
        section_stats = [max(signature_stats, key=lambda s: (s["votes"], s["z_score"]))]

    section_slugs = {s["perspective_slug"] for s in section_stats}
    sections: list[dict[str, Any]] = []
    for stat in section_stats:
        slug = stat["perspective_slug"]
        exemplar_payload = build_lens_exemplars(
            conn,
            slug,
            offset=0,
            limit=_EXEMPLAR_INITIAL_LIMIT,
            scan=scan,
            drop_keys=drop_keys,
        )

        leading_not_distinctive = fallback
        sections.append(
            {
                "perspective_slug": slug,
                "display_name": stat["display_name"],
                "strength_label": _strength_label(
                    z_score=stat["z_score"],
                    crowned=stat["crowned"],
                    leading_not_distinctive=leading_not_distinctive,
                ),
                "leading_not_distinctive": leading_not_distinctive,
                "crowned": stat["crowned"],
                "win_rate": stat["win_rate"],
                "chance_rate": stat["chance_rate"],
                "z_score": stat["z_score"],
                "votes": stat["votes"],
                "photos_on": stat["photos_on"],
                "coverage": stat["coverage"],
                "low_coverage": stat["low_coverage"],
                "descriptors": _distinctive_descriptors(
                    rationales_by_slug.get(slug, []),
                    corpus_rationales,
                ),
                "exemplars": exemplar_payload["items"],
                "exemplar_total": exemplar_payload["total"],
            }
        )

    other_lenses: list[dict[str, Any]] = []
    for stat in signature_stats:
        slug = stat["perspective_slug"]
        if slug in section_slugs:
            continue
        exemplar_total = build_lens_exemplars(
            conn,
            slug,
            offset=0,
            limit=0,
            scan=scan,
            drop_keys=drop_keys,
        )["total"]
        other_lenses.append(
            {
                "perspective_slug": slug,
                "display_name": stat["display_name"],
                "strength_label": _strength_label(
                    z_score=stat["z_score"],
                    crowned=stat["crowned"],
                    leading_not_distinctive=False,
                ),
                "win_rate": stat["win_rate"],
                "chance_rate": stat["chance_rate"],
                "z_score": stat["z_score"],
                "coverage": stat["coverage"],
                "low_coverage": stat["low_coverage"],
                "votes": stat["votes"],
                "photos_on": stat["photos_on"],
                "exemplar_total": exemplar_total,
            }
        )

    return {
        "population": voting_population,
        "sections": sections,
        "other_lenses": other_lenses,
        "meta": {
            "active_perspectives": active_slugs,
            "total_catalog_images": total_catalog,
            "voting_rule": (
                "strict argmax on within-perspective percentile among images scored on "
                f">= {_MIN_VOTING_LENSES} lenses"
            ),
            "crowning_rule": (
                f"one-sided binomial test p < {_CROWN_ALPHA} on coverage-corrected win rate"
            ),
            "low_coverage_threshold": _LOW_COVERAGE_THRESHOLD,
            "exemplar_initial_limit": _EXEMPLAR_INITIAL_LIMIT,
            "exemplar_page_size": _EXEMPLAR_PAGE_SIZE,
            "descriptor_min_count": _DESCRIPTOR_MIN_COUNT,
            "scores_are_advisory": (
                "Rankings reflect model/rubric versions at time of scoring (is_current rows)."
            ),
            "fallback_active": fallback,
        },
    }
