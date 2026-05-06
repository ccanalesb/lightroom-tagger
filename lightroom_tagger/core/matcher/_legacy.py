def match_image(db, insta_image: dict, threshold: float = 0.7,
                phash_weight: float = 0.4, desc_weight: float = 0.3,
                vision_weight: float = 0.3,
                provider_id: str | None = None,
                model: str | None = None) -> list[dict]:
    """Match single Instagram image against catalog with vision comparison."""
    from lightroom_tagger.core import matcher as _matcher

    insta_exif = insta_image.get('exif', {})

    candidates = _matcher.query_by_exif(db, insta_exif)

    if not candidates:
        return []

    scored = _matcher.score_candidates_with_vision(
        db, insta_image, candidates,
        phash_weight, desc_weight, vision_weight,
        threshold=threshold,
        provider_id=provider_id,
        model=model,
    )

    # Get best match (highest score) if above threshold
    if scored and scored[0]['total_score'] >= threshold:
        match = scored[0] # Already sorted by score descending
        _matcher.store_match(db, match)
        return [match]

    return []


def match_batch(db, insta_images: list, threshold: float = 0.7,
                phash_weight: float = 0.4, desc_weight: float = 0.3,
                vision_weight: float = 0.3) -> dict:
    """Match multiple Instagram images against catalog."""
    from lightroom_tagger.core import matcher as _matcher

    total_matches = 0
    total_candidates = 0

    for insta_image in insta_images:
        matches = _matcher.match_image(
            db, insta_image, threshold,
            phash_weight, desc_weight, vision_weight
        )
        if matches:
            total_matches += 1
            total_candidates += len(matches)

    return {
        'total_matches': total_matches,
        'total_candidates': total_candidates
    }
