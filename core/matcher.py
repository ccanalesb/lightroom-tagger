from typing import List, Dict, Any
from tinydb import Query
from core.database import store_match

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
    from core.phash import hamming_distance
    
    results = []
    
    for candidate in candidates:
        phash_dist = hamming_distance(insta_image.get('phash', ''), candidate.get('phash', ''))
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

def match_image(db, insta_image: dict, threshold: float = 0.7, phash_weight: float = 0.5, desc_weight: float = 0.5) -> List[dict]:
    """Match single Instagram image against catalog."""
    insta_exif = insta_image.get('exif', {})
    
    candidates = query_by_exif(db, insta_exif)
    
    if not candidates:
        return []
    
    scored = score_candidates(insta_image, candidates, phash_weight, desc_weight)
    
    matches = [m for m in scored if m['total_score'] >= threshold]
    
    for match in matches:
        store_match(db, match)
    
    return matches

def match_batch(db, insta_images: list, threshold: float = 0.7, phash_weight: float = 0.5, desc_weight: float = 0.5) -> dict:
    """Match multiple Instagram images against catalog."""
    total_matches = 0
    total_candidates = 0
    
    for insta_image in insta_images:
        matches = match_image(db, insta_image, threshold, phash_weight, desc_weight)
        if matches:
            total_matches += 1
            total_candidates += len(matches)
    
    return {
        'total_matches': total_matches,
        'total_candidates': total_candidates
    }
