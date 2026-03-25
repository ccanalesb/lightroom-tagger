from typing import List, Dict, Any
from tinydb import Query
from lightroom_tagger.core.database import store_match, get_vision_comparison, store_vision_comparison
from lightroom_tagger.core.vision_cache import (
    get_or_create_cached_image,
    get_cached_phash,
    InstagramCache,
)

def query_by_exif(db, insta_exif: dict, date_window_days: int = 7) -> List[dict]:
    """Query catalog by EXIF (camera, lens, date within window)."""
    camera = insta_exif.get('camera')
    lens = insta_exif.get('lens')

    if not camera and not lens:
        return []

    conditions = []
    if camera:
        conditions.append(Query()['exif']['camera'] == camera)
    if lens:
        conditions.append(Query()['exif']['lens'] == lens)

    return db.table('catalog_images').search(conditions[0])

def score_candidates(insta_image: dict, candidates: list, phash_weight: float = 0.5, desc_weight: float = 0.5) -> List[dict]:
    """Score candidates by phash distance + description similarity."""
    from lightroom_tagger.core.phash import hamming_distance

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


def score_candidates_with_vision(db, insta_image: dict, candidates: list,
                                 phash_weight: float = 0.4, desc_weight: float = 0.3,
                                 vision_weight: float = 0.3,
                                 log_callback=None) -> List[dict]:
    """Score candidates including vision comparison (one-by-one).

    Uses vision comparison cache to avoid re-comparing already processed pairs.
    Also uses image compression cache to avoid redundant compression.
    """
    import os as _os
    from lightroom_tagger.core.phash import hamming_distance
    from lightroom_tagger.core.analyzer import compare_with_vision, vision_score, get_vision_model

    results = []
    total_candidates = len(candidates)
    insta_filename = _os.path.basename(insta_image.get('local_path', 'unknown'))

    # Compress Instagram image ONCE before candidate loop
    insta_cache = InstagramCache(db)
    insta_path = insta_image.get('local_path')
    compressed_insta = None
    if insta_path:
        try:
            compressed_insta = insta_cache.compress_instagram_image(insta_path)
            if log_callback:
                log_callback('info', f'[{insta_filename}] Compressed Instagram image once for {total_candidates} candidates')
        except Exception as e:
            if log_callback:
                log_callback('warning', f'[{insta_filename}] Failed to compress Instagram image: {e}')
            compressed_insta = insta_path

    # Count cache usage
    cache_hits = 0
    cache_misses = 0

    if log_callback:
        log_callback('info', f'[{insta_filename}] Starting vision comparison with {total_candidates} candidates')

    for idx, candidate in enumerate(candidates, 1):
        catalog_key = candidate.get('key')
        insta_key = insta_image.get('key')
        local_path = candidate.get('local_path')

        # Use cached pHash if available, otherwise compute or fallback
        cached_phash = get_cached_phash(db, catalog_key)
        if cached_phash is not None:
            phash_dist = hamming_distance(insta_image.get('image_hash', ''), cached_phash)
            cache_hits += 1
        else:
            phash_dist = hamming_distance(insta_image.get('image_hash', ''), candidate.get('image_hash', ''))
            cache_misses += 1

        phash_score_val = max(0, 1 - (phash_dist / 16))

        desc_sim = text_similarity(insta_image.get('description', ''), candidate.get('description', ''))

        # Get or create cached compressed image for catalog
        cached_local_path = None
        if local_path:
            try:
                cached_local_path = get_or_create_cached_image(db, catalog_key, local_path)
            except Exception as e:
                if log_callback and idx <= 5:  # Log first few failures
                    log_callback('warning', f'Cache miss for {catalog_key}, will compress on-demand')

        # Check vision comparison cache
        vision_cached = get_vision_comparison(db, catalog_key, insta_key)

        if vision_cached:
            # Use cached vision comparison result
            vision_result = vision_cached['result']
            vision_score_val = vision_cached['vision_score']
        elif insta_path and local_path:
            # Run vision comparison with cached/prepared paths
            try:
                vision_result = compare_with_vision(
                    local_path, insta_path,
                    log_callback=log_callback,
                    cached_local_path=cached_local_path,
                    compressed_insta_path=compressed_insta
                )
                vision_score_val = vision_score(vision_result)

                # Cache the result
                store_vision_comparison(
                    db, catalog_key, insta_key,
                    vision_result, vision_score_val,
                    get_vision_model()
                )
            except Exception:
                vision_result = 'UNCERTAIN'
                vision_score_val = 0.5
        else:
            vision_result = 'UNCERTAIN'
            vision_score_val = 0.5

        total_score_val = (phash_weight * phash_score_val) + \
                          (desc_weight * desc_sim) + \
                          (vision_weight * vision_score_val)

        results.append({
            'catalog_key': catalog_key,
            'insta_key': insta_key,
            'phash_distance': int(phash_dist),
            'phash_score': phash_score_val,
            'desc_similarity': desc_sim,
            'vision_result': vision_result,
            'vision_score': vision_score_val,
            'total_score': total_score_val
        })

    # Cleanup Instagram temp file
    insta_cache.cleanup()

    # Log summary
    if log_callback:
        log_callback('info', f'[{insta_filename}] Cache summary: {cache_hits} pHash hits, {cache_misses} pHash misses')
        if results:
            best = results[0]
            best_pct = int(best['total_score'] * 100)
            if best['total_score'] >= 0.7:
                log_callback('info', f'[{insta_filename}] Comparison complete - Best match: {best["catalog_key"]} ({best_pct}%)')
            else:
                log_callback('info', f'[{insta_filename}] No match found above threshold (0.7)')

    return sorted(results, key=lambda x: x['total_score'], reverse=True)

def match_image(db, insta_image: dict, threshold: float = 0.7,
                phash_weight: float = 0.4, desc_weight: float = 0.3,
                vision_weight: float = 0.3) -> List[dict]:
    """Match single Instagram image against catalog with vision comparison."""
    insta_exif = insta_image.get('exif', {})

    candidates = query_by_exif(db, insta_exif)

    if not candidates:
        return []

    scored = score_candidates_with_vision(
        db, insta_image, candidates,
        phash_weight, desc_weight, vision_weight
    )

    # Get best match (highest score) if above threshold
    if scored and scored[0]['total_score'] >= threshold:
        match = scored[0] # Already sorted by score descending
        store_match(db, match)
        return [match]

    return []

def match_batch(db, insta_images: list, threshold: float = 0.7,
                phash_weight: float = 0.4, desc_weight: float = 0.3,
                vision_weight: float = 0.3) -> dict:
    """Match multiple Instagram images against catalog."""
    total_matches = 0
    total_candidates = 0

    for insta_image in insta_images:
        matches = match_image(
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


def find_candidates_by_date(db, insta_image: dict, days_before: int = 90) -> list:
    """Find catalog candidates within date window before Instagram posting."""
    from datetime import datetime, timedelta

    date_folder = insta_image.get('date_folder', '')
    if len(date_folder) != 6:
        return []

    post_year = int(date_folder[:4])
    post_month = int(date_folder[4:6])
    post_date = datetime(post_year, post_month, 15)
    window_start = post_date - timedelta(days=days_before)

    candidates = []
    for img in db.table('images').all():
        date_taken = img.get('date_taken', '')
        if not date_taken:
            continue
        try:
            img_date = datetime.fromisoformat(date_taken.replace('Z', '+00:00'))
            if window_start <= img_date <= post_date:
                candidates.append(img)
        except:
            continue

    return candidates
