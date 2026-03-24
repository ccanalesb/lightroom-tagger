from typing import List, Dict, Any
from tinydb import Query
from lightroom_tagger.core.database import store_match, get_vision_comparison, store_vision_comparison

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
        phash_score = max(0, 1 - (phash_dist / 16))  # Normalize to 0-1
        
        desc_sim = text_similarity(insta_image.get('description', ''), candidate.get('description', ''))
        
        total = (phash_weight * phash_score) + (desc_weight * desc_sim)
        
        results.append({
            'catalog_key': candidate.get('key'),
            'insta_key': insta_image.get('key'),
            'phash_distance': phash_dist,
            'phash_score': phash_score,
            'desc_similarity': desc_sim,
            'total_score': total
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
                                 vision_weight: float = 0.3) -> List[dict]:
    """Score candidates including vision comparison (one-by-one).

    Uses vision comparison cache to avoid re-comparing already processed pairs.
    """
    from lightroom_tagger.core.phash import hamming_distance
    from lightroom_tagger.core.analyzer import compare_with_vision, vision_score, get_vision_model

    results = []

    for candidate in candidates:
        phash_dist = hamming_distance(insta_image.get('image_hash', ''), candidate.get('image_hash', ''))
        phash_score_val = max(0, 1 - (phash_dist / 16))

        desc_sim = text_similarity(insta_image.get('description', ''), candidate.get('description', ''))

        catalog_key = candidate.get('key')
        insta_key = insta_image.get('key')
        insta_path = insta_image.get('local_path')
        local_path = candidate.get('local_path')

        # Check cache first
        cached = get_vision_comparison(db, catalog_key, insta_key)

        if cached:
            # Use cached result (never expires by design)
            vision_result = cached['result']
            vision_score_val = cached['vision_score']
        elif insta_path and local_path:
            # Run vision comparison
            try:
                vision_result = compare_with_vision(local_path, insta_path)
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

        total = (phash_weight * phash_score_val) + \
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
            'total_score': total
        })

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
        match = scored[0]  # Already sorted by score descending
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
