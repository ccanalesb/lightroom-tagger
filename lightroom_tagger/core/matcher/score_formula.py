"""Pure matcher score arithmetic — no I/O, DB, or vision."""

from __future__ import annotations


def normalize_phash_score(distance: int | float) -> float:
    """Map Hamming distance to a 0–1 score (16-bit hash, clamped at zero)."""
    return max(0, 1 - (distance / 16))


def compute_total_score(
    phash: float,
    desc: float,
    vision: float,
    phash_weight: float,
    desc_weight: float,
    vision_weight: float,
) -> float:
    """Weighted blend of phash, description, and vision component scores."""
    return (
        (phash_weight * phash)
        + (desc_weight * desc)
        + (vision_weight * vision)
    )
