"""Lightweight perceptual-hash and caption/description similarity scoring."""

from __future__ import annotations

from lightroom_tagger.core.phash import hamming_distance


def text_similarity(text1: str, text2: str) -> float:
    """Simple text similarity using common words."""
    if not text1 or not text2:
        return 0.0

    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())

    if not words1 or not words2:
        return 0.0

    intersection = len(words1 & words2)
    union = len(words1 | words2)

    return intersection / union if union > 0 else 0.0


def score_candidates(insta_image: dict, candidates: list, phash_weight: float = 0.5, desc_weight: float = 0.5) -> list[dict]:
    """Score candidates by phash distance + description similarity."""

    results = []

    for candidate in candidates:
        phash_dist = hamming_distance(insta_image.get('image_hash', ''), candidate.get('image_hash', ''))
        phash_score = max(0, 1 - (phash_dist / 16)) # Normalize to 0-1

        desc_sim = text_similarity(insta_image.get('description', ''), candidate.get('description', ''))

        total_score_val = (phash_weight * phash_score) + (desc_weight * desc_sim)

        results.append({
            'catalog_key': candidate.get('key'),
            'insta_key': insta_image.get('key'),
            'phash_distance': phash_dist,
            'phash_score': phash_score,
            'desc_similarity': desc_sim,
            'total_score': total_score_val
        })

    return sorted(results, key=lambda x: x['total_score'], reverse=True)
