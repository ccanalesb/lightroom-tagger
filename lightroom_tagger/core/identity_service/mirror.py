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
from .ranking import _image_meta_map

_LOW_COVERAGE_THRESHOLD = 0.5
_EXEMPLAR_LIMIT = 12
_DESCRIPTOR_MIN_COUNT = 5
_DESCRIPTOR_LIMIT = 15
_MIN_VOTING_LENSES = 2
_CROWN_ALPHA = 0.05


def _binom_sf(k: int, n: int, p: float) -> float:
    """P(X >= k) for X ~ Binomial(n, p)."""
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    if p <= 0.0:
        return 0.0 if k > 0 else 1.0
    if p >= 1.0:
        return 1.0 if k <= n else 0.0

    mu = n * p
    if n >= 30:
        sigma_sq = n * p * (1.0 - p)
        if sigma_sq <= 0.0:
            return 0.0 if k > mu else 1.0
        z = (k - 0.5 - mu) / math.sqrt(sigma_sq)
        return 0.5 * math.erfc(z / math.sqrt(2.0))

    total = 0.0
    q = 1.0 - p
    for i in range(k, n + 1):
        total += math.comb(n, i) * (p**i) * (q ** (n - i))
    return min(1.0, total)


def _signature_z(votes: int, expected_wins: float, photos_on: int, chance: float) -> float:
    denom = photos_on * chance * (1.0 - chance)
    if denom <= 0.0:
        return 0.0
    return (votes - expected_wins) / math.sqrt(denom)


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
    if not other_percentiles:
        return round(lens_percentile * 100.0, 1)
    return round((lens_percentile - max(other_percentiles)) * 100.0, 1)


def build_mirror(conn: sqlite3.Connection) -> dict[str, Any]:
    """Catalog Mirror: crowned signature lenses, descriptors, and exemplar rails."""
    active_slugs = _active_perspective_slugs(conn)
    slug_set = set(active_slugs)
    display_by_slug: dict[str, str] = {}
    rows = conn.execute(_SCORES_BASE_SQL).fetchall()
    for r in rows:
        slug = str(r["perspective_slug"])
        if slug not in slug_set:
            continue
        display_by_slug.setdefault(slug, str(r["perspective_display_name"] or slug))

    total_catalog = int(conn.execute("SELECT COUNT(*) AS c FROM images").fetchone()["c"])
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

    votes: Counter[str] = Counter()
    photos_on: Counter[str] = Counter()
    expected_wins: dict[str, float] = {s: 0.0 for s in active_slugs}
    voting_population = 0

    for perspectives in by_image.values():
        if len(perspectives) < _MIN_VOTING_LENSES:
            continue
        voting_population += 1
        inv_k = 1.0 / len(perspectives)
        top_pct = max(p["percentile"] for p in perspectives)
        tied = [p for p in perspectives if p["percentile"] == top_pct]
        if len(tied) != 1:
            for p in perspectives:
                photos_on[p["perspective_slug"]] += 1
                expected_wins[p["perspective_slug"]] += inv_k
            continue

        winner_slug = tied[0]["perspective_slug"]
        votes[winner_slug] += 1
        for p in perspectives:
            slug = p["perspective_slug"]
            photos_on[slug] += 1
            expected_wins[slug] += inv_k

    signature_stats: list[dict[str, Any]] = []
    for slug in active_slugs:
        n = photos_on.get(slug, 0)
        if n == 0:
            continue
        v = votes.get(slug, 0)
        expected = expected_wins.get(slug, 0.0)
        chance = expected / n if n else 0.0
        win_rate = v / n if n else 0.0
        z = _signature_z(v, expected, n, chance)
        p_value = _binom_sf(v, n, chance) if 0.0 < chance < 1.0 else 1.0
        crowned = p_value < _CROWN_ALPHA and z > 0
        coverage = n / total_catalog if total_catalog else 0.0
        signature_stats.append(
            {
                "perspective_slug": slug,
                "display_name": display_by_slug.get(slug, slug),
                "votes": v,
                "photos_on": n,
                "win_rate": round(win_rate, 6),
                "expected_wins": round(expected, 4),
                "chance_rate": round(chance, 6),
                "z_score": round(z, 2),
                "p_value": round(p_value, 6),
                "crowned": crowned,
                "coverage": round(coverage, 4),
                "low_coverage": coverage < _LOW_COVERAGE_THRESHOLD,
            }
        )

    crowned_stats = [s for s in signature_stats if s["crowned"]]
    crowned_stats.sort(key=lambda s: (-s["z_score"], s["perspective_slug"]))

    fallback = False
    section_stats = crowned_stats
    if not section_stats and signature_stats:
        fallback = True
        section_stats = [max(signature_stats, key=lambda s: (s["votes"], s["z_score"]))]

    exemplar_keys: list[str] = []
    sections: list[dict[str, Any]] = []
    for stat in section_stats:
        slug = stat["perspective_slug"]
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

        candidates.sort(
            key=lambda row: (
                -row["percentile"],
                -row["purity"],
                row["image_key"],
            )
        )
        top = candidates[:_EXEMPLAR_LIMIT]
        exemplar_keys.extend(str(row["image_key"]) for row in top)

        exemplars: list[dict[str, Any]] = []
        for row in top:
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
            exemplars.append(
                {
                    "image_key": row["image_key"],
                    "score": row["score"],
                    "percentile": round(row["percentile"] * 100.0, 1),
                    "purity": row["purity"],
                    "rationale_preview": _truncate_rationale(row["rationale"]),
                    "per_perspective": per_out,
                }
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
                "exemplars": exemplars,
            }
        )

    meta_map = _image_meta_map(conn, list(dict.fromkeys(exemplar_keys)))
    for section in sections:
        for exemplar in section["exemplars"]:
            im = meta_map.get(str(exemplar["image_key"]), {})
            exemplar["filename"] = im.get("filename") or ""
            exemplar["date_taken"] = im.get("date_taken") or ""
            exemplar["rating"] = int(im.get("rating") or 0)
            exemplar["instagram_posted"] = bool(im.get("instagram_posted"))

    return {
        "population": voting_population,
        "sections": sections,
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
            "exemplar_limit": _EXEMPLAR_LIMIT,
            "descriptor_min_count": _DESCRIPTOR_MIN_COUNT,
            "scores_are_advisory": (
                "Rankings reflect model/rubric versions at time of scoring (is_current rows)."
            ),
            "fallback_active": fallback,
        },
    }
