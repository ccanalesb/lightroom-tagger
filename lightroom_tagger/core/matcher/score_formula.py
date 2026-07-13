"""Pure matcher score arithmetic — no I/O, DB, or vision."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScoreWeights:
    phash: float
    desc: float
    vision: float

    @classmethod
    def from_dict(cls, d: dict) -> ScoreWeights:
        return cls(
            phash=d.get('phash', 0.4),
            desc=d.get('description', 0.3),
            vision=d.get('vision', 0.3),
        )


DEFAULT_WEIGHTS = ScoreWeights(0.4, 0.3, 0.3)


def normalize_phash_score(distance: int | float) -> float:
    """Map Hamming distance to a 0–1 score (16-bit hash, clamped at zero)."""
    return max(0, 1 - (distance / 16))


def compute_total_score(
    phash: float,
    desc: float,
    vision: float,
    weights: ScoreWeights,
) -> float:
    """Weighted blend of phash, description, and vision component scores."""
    return (
        (weights.phash * phash)
        + (weights.desc * desc)
        + (weights.vision * vision)
    )
