"""Request-scoped Mirror scan value object + crowning statistics primitive.

Split out of ``mirror.py`` to keep that module within the core file-size budget
(docs/architecture.md). ``build_mirror_scan`` stays in ``mirror.py`` because its
DB dependencies (``_active_perspective_slugs``,
``compute_within_perspective_percentile_lookup``) are monkeypatched there by the
call-count spy tests; only the pure value object and stats math live here.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import Any

_LOW_COVERAGE_THRESHOLD = 0.5
_MIN_VOTING_LENSES = 2
_CROWN_ALPHA = 0.05


@dataclass(frozen=True)
class MirrorScan:
    active_slugs: list[str]
    slug_set: frozenset[str]
    display_by_slug: dict[str, str]
    by_image: dict[str, list[dict[str, Any]]]
    rationales_by_slug: dict[str, list[str]]
    corpus_rationales: list[str]
    percentile_lookup: dict[tuple[str, str], float]
    total_catalog: int


@dataclass(frozen=True)
class SignatureStats:
    """Per-lens crowning stats plus the voting population they were computed over.

    ``voting_population`` is returned here so callers don't re-derive the same
    ``_MIN_VOTING_LENSES`` threshold that this primitive already applies.
    """

    stats: list[dict[str, Any]]
    voting_population: int


def _binom_sf(k: int, n: int, p: float) -> float:
    """P(X >= k) for X ~ Binomial(n, p).

    Exact for n < 30; for n >= 30 (the real-catalog regime) uses the
    continuity-corrected normal approximation, which is accurate deep in the
    upper tail where crowning decisions actually sit. A lens sitting right at
    p ~ 0.05 could differ marginally from the exact test; distinctive lenses
    (large z) are unaffected. No scipy/numpy dependency, so this is hand-rolled.
    """
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
    # Each photo's win probability is 1/k_i (k_i = lenses it was scored on), so the
    # vote count is Poisson-binomial. We approximate it with a homogeneous
    # Binomial(photos_on, chance) using the mean per-photo chance. Because the true
    # variance sum_i p_i(1-p_i) <= n*chance*(1-chance) (Jensen), this denominator is
    # an upper bound, so z is conservative (understated) — crowning never over-fires.
    denom = photos_on * chance * (1.0 - chance)
    if denom <= 0.0:
        return 0.0
    return (votes - expected_wins) / math.sqrt(denom)


def compute_signature_stats(scan: MirrorScan) -> SignatureStats:
    """Per-lens vote counts, z-scores, p-values, and crowning flags.

    Coverage is computed against ``scan.total_catalog`` (always populated by
    ``build_mirror_scan``), and the voting population is returned alongside the
    stats so callers don't re-apply the ``_MIN_VOTING_LENSES`` threshold.
    """
    active_slugs = scan.active_slugs
    display_by_slug = scan.display_by_slug
    by_image = scan.by_image
    catalog = scan.total_catalog

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
        coverage = n / catalog if catalog else 0.0
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
    return SignatureStats(stats=signature_stats, voting_population=voting_population)
