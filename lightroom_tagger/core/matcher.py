from lightroom_tagger.core.database import (
    _deserialize_row,
    get_vision_comparison,
    store_match,
    store_vision_comparison,
)
from lightroom_tagger.core.vision_cache import (
    InstagramCache,
    get_cached_phash,
    get_or_create_cached_image,
)


def query_by_exif(db, insta_exif: dict, date_window_days: int = 7) -> list[dict]:
    """Query catalog by EXIF (camera, lens, date within window)."""
    camera = insta_exif.get('camera')
    lens = insta_exif.get('lens')

    if not camera and not lens:
        return []

    if camera and lens:
        sql = (
            "SELECT * FROM images WHERE "
            "json_extract(exif, '$.camera') = ? AND json_extract(exif, '$.lens') = ?"
        )
        params = (camera, lens)
    elif camera:
        sql = "SELECT * FROM images WHERE json_extract(exif, '$.camera') = ?"
        params = (camera,)
    else:
        sql = "SELECT * FROM images WHERE json_extract(exif, '$.lens') = ?"
        params = (lens,)

    rows = db.execute(sql, params).fetchall()
    return [_deserialize_row(r) for r in rows]

def score_candidates(insta_image: dict, candidates: list, phash_weight: float = 0.5, desc_weight: float = 0.5) -> list[dict]:
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
                                 threshold: float = 0.7,
                                 log_callback=None,
                                 provider_id: str | None = None,
                                 model: str | None = None,
                                 batch_size: int = 20,
                                 batch_threshold: int = 5) -> list[dict]:
    """Score candidates including vision comparison (one-by-one).

    Uses vision comparison cache to avoid re-comparing already processed pairs.
    Also uses image compression cache to avoid redundant compression.
    """
    import os as _os

    from lightroom_tagger.core.analyzer import compare_with_vision, get_vision_model, vision_score
    from lightroom_tagger.core.phash import hamming_distance
    from lightroom_tagger.core.provider_errors import RateLimitError
    from lightroom_tagger.core.vision_client import compare_images_batch
    from lightroom_tagger.core.provider_registry import ProviderRegistry

    RATE_LIMIT_ABORT_THRESHOLD = 3

    results = []
    total_candidates = len(candidates)
    consecutive_rate_limits = 0
    rate_limited_count = 0
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

    # Use batch API if we have enough candidates and batch processing is enabled
    use_batch = (total_candidates >= batch_threshold and batch_size > 1)
    
    if use_batch:
        if log_callback:
            log_callback('info', f'[{insta_filename}] Using batch API (batch_size={batch_size}, candidates={total_candidates})')
        
        # Prepare batch candidates with numeric IDs
        batch_candidates = []
        for idx, candidate in enumerate(candidates):
            local_path = candidate.get('local_path')
            if not local_path:
                continue
            try:
                cached_local_path = get_or_create_cached_image(db, candidate.get('key'), local_path)
                batch_candidates.append((idx, cached_local_path or local_path))
            except Exception:
                pass
        
        # Call batch API
        batch_results = {}
        if batch_candidates and compressed_insta:
            try:
                registry = ProviderRegistry()
                # Use provided provider_id or fall back to first provider in fallback order
                actual_provider_id = provider_id or registry.fallback_order[0]
                client = registry.get_client(actual_provider_id)
                requested_model = model or get_vision_model()
                batch_results = compare_images_batch(
                    client,
                    requested_model,
                    compressed_insta,
                    batch_candidates,
                    log_callback=log_callback,
                )
            except RateLimitError as e:
                if log_callback:
                    log_callback('warning', f'[{insta_filename}] Batch API rate limited, falling back to sequential')
                use_batch = False
            except Exception as e:
                if log_callback:
                    log_callback('warning', f'[{insta_filename}] Batch API error: {e}, falling back to sequential')
                use_batch = False
    
    if use_batch and batch_results:
        # Process batch results
        for idx, candidate in enumerate(candidates):
            catalog_key = candidate.get('key')
            insta_key = insta_image.get('key')
            
            # Get vision score from batch results
            vision_confidence = batch_results.get(idx, 0.0)
            vision_score_val = vision_score(vision_confidence)
            vision_result = 'SAME' if vision_confidence >= 80 else 'DIFFERENT' if vision_confidence <= 20 else 'UNCERTAIN'
            
            # Compute phash and desc scores
            cached_phash = get_cached_phash(db, catalog_key)
            if cached_phash is not None:
                phash_dist = hamming_distance(insta_image.get('image_hash', ''), cached_phash)
                cache_hits += 1
            else:
                phash_dist = hamming_distance(insta_image.get('image_hash', ''), candidate.get('image_hash', ''))
                cache_misses += 1
            
            phash_score_val = max(0, 1 - (phash_dist / 16))
            desc_sim = text_similarity(insta_image.get('description', ''), candidate.get('description', ''))
            
            # Weight redistribution logic
            insta_hash = insta_image.get('image_hash')
            cand_hash = cached_phash if cached_phash is not None else candidate.get('image_hash')
            phash_available = bool(insta_hash) and bool(cand_hash)
            desc_available = bool((insta_image.get('description') or '').strip()) and bool((candidate.get('description') or '').strip())
            
            active_weights = {}
            if phash_available:
                active_weights['phash'] = phash_weight
            if desc_available:
                active_weights['desc'] = desc_weight
            active_weights['vision'] = vision_weight
            
            weight_sum = sum(active_weights.values()) or 1.0
            w_phash = active_weights.get('phash', 0) / weight_sum
            w_desc = active_weights.get('desc', 0) / weight_sum
            w_vision = active_weights['vision'] / weight_sum
            
            total_score_val = (w_phash * phash_score_val) + (w_desc * desc_sim) + (w_vision * vision_score_val)
            
            model_label = f"{provider_id}:{model}" if provider_id and model else get_vision_model()
            
            # Store result
            store_vision_comparison(db, catalog_key, insta_key, vision_result, vision_score_val, model_label)
            
            results.append({
                'catalog_key': catalog_key,
                'insta_key': insta_key,
                'phash_distance': int(phash_dist),
                'phash_score': phash_score_val,
                'desc_similarity': desc_sim,
                'vision_result': vision_result,
                'vision_score': vision_score_val,
                'vision_reasoning': '',
                'total_score': total_score_val,
                'model_used': model_label,
                'rate_limited': False,
            })
    else:
        # Sequential fallback
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
                except Exception:
                    if log_callback and idx <= 5:  # Log first few failures
                        log_callback('warning', f'Cache miss for {catalog_key}, will compress on-demand')

            # Check vision comparison cache (invalidate if model changed)
            vision_cached = get_vision_comparison(db, catalog_key, insta_key)
            base_vision_model = get_vision_model()
            # Requested label for cache lookup only; pipeline may pick a different default model.
            requested_model_label = (
                f"{provider_id}:{model or base_vision_model}"
                if provider_id
                else base_vision_model
            )
            cache_valid = (
                vision_cached
                and vision_cached.get('model_used') == requested_model_label
            )

            model_label = base_vision_model
            vision_reasoning = ''
            if cache_valid:
                vision_result = vision_cached['result']
                vision_score_val = vision_cached['vision_score']
                model_label = vision_cached.get('model_used', model_label)
                consecutive_rate_limits = 0
            elif consecutive_rate_limits >= RATE_LIMIT_ABORT_THRESHOLD:
                vision_result = 'RATE_LIMITED'
                vision_score_val = 0.0
                rate_limited_count += 1
            elif insta_path and local_path:
                try:
                    vision_data = compare_with_vision(
                        local_path, insta_path,
                        log_callback=log_callback,
                        cached_local_path=cached_local_path,
                        compressed_insta_path=compressed_insta,
                        provider_id=provider_id,
                        model=model,
                    )
                    vision_result = vision_data['verdict']
                    vision_score_val = vision_score(vision_data['confidence'])
                    vision_reasoning = (vision_data.get('reasoning') or '').strip()
                    consecutive_rate_limits = 0

                    if vision_data.get('_provider'):
                        ap = vision_data['_provider']
                        am = vision_data.get('_model')
                        model_label = f"{ap}:{am}" if am is not None else f"{ap}:"

                    store_vision_comparison(
                        db, catalog_key, insta_key,
                        vision_result, vision_score_val,
                        model_label,
                    )
                except RateLimitError as e:
                    consecutive_rate_limits += 1
                    rate_limited_count += 1
                    if log_callback:
                        log_callback('warning', f'[{insta_filename}] Rate limited for {catalog_key} ({consecutive_rate_limits} consecutive)')
                    vision_result = 'RATE_LIMITED'
                    vision_score_val = 0.0
                except Exception as e:
                    consecutive_rate_limits = 0
                    if log_callback:
                        log_callback('error', f'[{insta_filename}] Vision error for {catalog_key}: {e}')
                    vision_result = 'ERROR'
                    vision_score_val = 0.0
            else:
                vision_result = 'UNCERTAIN'
                vision_score_val = 0.5

            # Redistribute weight from unavailable signals to available ones.
            # A signal is unavailable when its inputs are missing (None/empty hashes,
            # empty descriptions), distinct from a genuine low-similarity score.
            insta_hash = insta_image.get('image_hash')
            cand_hash = cached_phash if cached_phash is not None else candidate.get('image_hash')
            phash_available = bool(insta_hash) and bool(cand_hash)
            desc_available = bool((insta_image.get('description') or '').strip()) and bool((candidate.get('description') or '').strip())

            active_weights = {}
            if phash_available:
                active_weights['phash'] = phash_weight
            if desc_available:
                active_weights['desc'] = desc_weight
            active_weights['vision'] = vision_weight

            weight_sum = sum(active_weights.values()) or 1.0
            w_phash = active_weights.get('phash', 0) / weight_sum
            w_desc = active_weights.get('desc', 0) / weight_sum
            w_vision = active_weights['vision'] / weight_sum

            total_score_val = (w_phash * phash_score_val) + \
                              (w_desc * desc_sim) + \
                              (w_vision * vision_score_val)

            if log_callback and vision_result != 'UNCERTAIN':
                log_callback('debug', f'[{insta_filename}] {catalog_key} → {vision_result} (vision={vision_score_val:.2f}, phash={phash_score_val:.2f}, total={total_score_val:.2f})')

            results.append({
                'catalog_key': catalog_key,
                'insta_key': insta_key,
                'phash_distance': int(phash_dist),
                'phash_score': phash_score_val,
                'desc_similarity': desc_sim,
                'vision_result': vision_result,
                'vision_score': vision_score_val,
                'vision_reasoning': vision_reasoning,
                'total_score': total_score_val,
                'model_used': model_label,
                'rate_limited': vision_result == 'RATE_LIMITED',
            })

    # Cleanup Instagram temp file
    insta_cache.cleanup()

    results.sort(key=lambda x: x['total_score'], reverse=True)

    if log_callback:
        log_callback('info', f'[{insta_filename}] Cache summary: {cache_hits} pHash hits, {cache_misses} pHash misses')
        if results:
            best = results[0]
            best_pct = int(best['total_score'] * 100)
            if best['total_score'] >= threshold:
                log_callback('info', f'[{insta_filename}] Comparison complete - Best match: {best["catalog_key"]} ({best_pct}%)')
            else:
                log_callback('info', f'[{insta_filename}] No match found above threshold ({threshold})')

    return results

def match_image(db, insta_image: dict, threshold: float = 0.7,
                phash_weight: float = 0.4, desc_weight: float = 0.3,
                vision_weight: float = 0.3,
                provider_id: str | None = None,
                model: str | None = None) -> list[dict]:
    """Match single Instagram image against catalog with vision comparison."""
    insta_exif = insta_image.get('exif', {})

    candidates = query_by_exif(db, insta_exif)

    if not candidates:
        return []

    scored = score_candidates_with_vision(
        db, insta_image, candidates,
        phash_weight, desc_weight, vision_weight,
        threshold=threshold,
        provider_id=provider_id,
        model=model,
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
    for row in db.execute("SELECT * FROM images").fetchall():
        img = _deserialize_row(row)
        date_taken = img.get('date_taken', '')
        if not date_taken:
            continue
        try:
            img_date = datetime.fromisoformat(date_taken.replace('Z', '+00:00'))
            if window_start <= img_date <= post_date:
                candidates.append(img)
        except Exception:
            continue

    return candidates
