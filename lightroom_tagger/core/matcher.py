import os
from collections.abc import Callable

from lightroom_tagger.core.database import (
    _deserialize_row,
    get_vision_comparison,
    store_match,
    store_vision_comparison,
)
from lightroom_tagger.core.provider_registry import ProviderRegistry
from lightroom_tagger.core.vision_cache import (
    InstagramCache,
    get_cached_phash,
    get_or_create_cached_image,
)
from lightroom_tagger.core.vision_client import compare_descriptions_batch


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


BATCH_MAX_TOKENS_ESCALATION = [4096, 32768, 65536]


def _compute_desc_scores_for_candidates(
    insta_image: dict,
    candidates: list,
    batch_size: int,
    desc_weight: float,
    skip_undescribed: bool,
    provider_id: str | None,
    model: str | None,
    log_callback,
) -> dict[int, float]:
    """Map candidate index -> description similarity 0–1 via compare_descriptions_batch."""
    if desc_weight <= 0:
        return {}

    from lightroom_tagger.core.analyzer import get_vision_model

    reference_text = (insta_image.get('ai_summary') or '').strip()
    desc_scores: dict[int, float] = {}
    if not reference_text:
        for idx in range(len(candidates)):
            desc_scores[idx] = 0.0
        return desc_scores

    registry = ProviderRegistry()
    actual_provider_id = provider_id or registry.fallback_order[0]
    client = registry.get_client(actual_provider_id)
    requested_model = model or get_vision_model()

    for chunk_start in range(0, len(candidates), batch_size):
        chunk_indices = list(range(chunk_start, min(chunk_start + batch_size, len(candidates))))
        text_candidates: list[tuple[int, str]] = []
        for idx in chunk_indices:
            cand = candidates[idx]
            summary = (cand.get('ai_summary') or '').strip()
            if skip_undescribed and not summary:
                desc_scores[idx] = 0.0
            else:
                text_candidates.append((idx, cand.get('ai_summary') or ''))
        if not text_candidates:
            continue
        try:
            raw_map = compare_descriptions_batch(
                client,
                requested_model,
                reference_text,
                text_candidates,
                log_callback=log_callback,
                max_tokens=4096,
            )
        except Exception as e:
            if log_callback:
                log_callback('warning', f'[desc_batch] batch failed: {e}')
            for idx, _ in text_candidates:
                desc_scores[idx] = 0.0
            continue
        for cid, conf in raw_map.items():
            desc_scores[int(cid)] = max(0.0, min(1.0, float(conf) / 100.0))
        for idx, _ in text_candidates:
            desc_scores.setdefault(idx, 0.0)

    return desc_scores


def _call_batch_chunk(
    client,
    model: str,
    reference_path: str,
    chunk: list[tuple[int, str]],
    log_callback,
    insta_filename: str,
    chunk_num: int,
    num_chunks: int,
    max_tokens_idx: int = 0,
) -> dict[int, float]:
    """Call compare_images_batch for a single chunk with adaptive recovery.

    - On PayloadTooLargeError: halve the chunk and retry both halves.
    - On ContextLengthError: escalate max_tokens and retry the same chunk.
      If all escalation levels are exhausted, re-raise so the caller can
      fall back to sequential processing.
    """
    from lightroom_tagger.core.provider_errors import ContextLengthError, PayloadTooLargeError
    from lightroom_tagger.core.vision_client import compare_images_batch

    current_tokens = BATCH_MAX_TOKENS_ESCALATION[max_tokens_idx]

    try:
        return compare_images_batch(
            client, model, reference_path, chunk,
            log_callback=log_callback, max_tokens=current_tokens,
        )
    except PayloadTooLargeError:
        if len(chunk) <= 1:
            if log_callback:
                log_callback('warning', f'[{insta_filename}] Batch {chunk_num}/{num_chunks}: single-item chunk still too large, skipping')
            return {}
        half = len(chunk) // 2
        if log_callback:
            log_callback('warning', f'[{insta_filename}] Batch {chunk_num}/{num_chunks}: 413 payload too large, splitting {len(chunk)} -> {half}+{len(chunk)-half}')
        left = _call_batch_chunk(client, model, reference_path, chunk[:half], log_callback, insta_filename, chunk_num, num_chunks, max_tokens_idx)
        right = _call_batch_chunk(client, model, reference_path, chunk[half:], log_callback, insta_filename, chunk_num, num_chunks, max_tokens_idx)
        left.update(right)
        return left
    except ContextLengthError:
        if max_tokens_idx < len(BATCH_MAX_TOKENS_ESCALATION) - 1:
            next_idx = max_tokens_idx + 1
            next_tokens = BATCH_MAX_TOKENS_ESCALATION[next_idx]
            if log_callback:
                log_callback('warning', f'[{insta_filename}] Batch {chunk_num}/{num_chunks}: escalating max_tokens {current_tokens} -> {next_tokens}')
            return _call_batch_chunk(client, model, reference_path, chunk, log_callback, insta_filename, chunk_num, num_chunks, next_idx)
        raise


def score_candidates_with_vision(db, insta_image: dict, candidates: list,
                                 phash_weight: float = 0.4, desc_weight: float = 0.3,
                                 vision_weight: float = 0.3,
                                 threshold: float = 0.7,
                                 log_callback=None,
                                 provider_id: str | None = None,
                                 model: str | None = None,
                                 batch_size: int = 10,
                                 batch_threshold: int = 5,
                                 skip_undescribed: bool = True,
                                 should_cancel: Callable[[], bool] | None = None,
                                 batch_progress_callback: Callable[[int, int], None] | None = None) -> list[dict]:
    """Score candidates including vision comparison (one-by-one).

    Uses vision comparison cache to avoid re-comparing already processed pairs.
    Also uses image compression cache to avoid redundant compression.
    """
    import os as _os

    from lightroom_tagger.core.analyzer import compare_with_vision, get_vision_model, vision_score
    from lightroom_tagger.core.phash import hamming_distance
    from lightroom_tagger.core.provider_errors import InvalidRequestError, PayloadTooLargeError, RateLimitError

    RATE_LIMIT_ABORT_THRESHOLD = 3

    results = []
    total_candidates = len(candidates)
    consecutive_rate_limits = 0
    rate_limited_count = 0
    insta_filename = _os.path.basename(insta_image.get('local_path', 'unknown'))

    desc_scores_by_idx = _compute_desc_scores_for_candidates(
        insta_image,
        candidates,
        batch_size,
        desc_weight,
        skip_undescribed,
        provider_id,
        model,
        log_callback,
    )

    # Compress Instagram image ONCE before candidate loop (vision stage only)
    insta_cache = InstagramCache(db)
    insta_path = insta_image.get('local_path')
    compressed_insta = None
    if vision_weight > 0 and insta_path:
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

    if vision_weight == 0:
        insta_key = insta_image.get('key')
        model_label = f"{provider_id}:{model}" if provider_id and model else get_vision_model()
        for idx, candidate in enumerate(candidates):
            catalog_key = candidate.get('key')
            cached_phash = get_cached_phash(db, catalog_key)
            if cached_phash is not None:
                phash_dist = hamming_distance(insta_image.get('image_hash', ''), cached_phash)
                cache_hits += 1
            else:
                phash_dist = hamming_distance(insta_image.get('image_hash', ''), candidate.get('image_hash', ''))
                cache_misses += 1
            phash_score_val = max(0, 1 - (phash_dist / 16))
            desc_sim_01 = desc_scores_by_idx.get(idx, 0.0) if desc_weight > 0 else 0.0
            capt_sim = text_similarity(insta_image.get('description', ''), candidate.get('description', ''))
            desc_sim_display = desc_sim_01 if desc_weight > 0 else capt_sim
            vision_score_val = 0.0
            total_score_val = (
                (phash_weight * phash_score_val)
                + (desc_weight * desc_sim_01)
                + (vision_weight * vision_score_val)
            )
            if batch_progress_callback:
                batch_progress_callback(idx + 1, total_candidates)
            results.append({
                'catalog_key': catalog_key,
                'insta_key': insta_key,
                'phash_distance': int(phash_dist),
                'phash_score': phash_score_val,
                'desc_similarity': desc_sim_display,
                'vision_result': 'UNCERTAIN',
                'vision_score': vision_score_val,
                'vision_reasoning': '',
                'total_score': total_score_val,
                'model_used': model_label,
                'rate_limited': False,
            })
        insta_cache.cleanup()
        results.sort(key=lambda x: x['total_score'], reverse=True)
        if log_callback:
            log_callback('info', f'[{insta_filename}] Cache summary: {cache_hits} pHash hits, {cache_misses} pHash misses')
            above = [r for r in results if r['total_score'] >= threshold]
            log_callback('debug', f'[{insta_filename}] {len(results)} results, {len(above)} above threshold ({threshold})')
            if above:
                for r in above[:5]:
                    log_callback('info', f'[{insta_filename}] Above threshold: {r["catalog_key"]} total={r["total_score"]:.4f} vision={r["vision_score"]:.4f}')
            if results:
                best = results[0]
                best_pct = int(best['total_score'] * 100)
                if best['total_score'] >= threshold:
                    log_callback('info', f'[{insta_filename}] Comparison complete - Best match: {best["catalog_key"]} ({best_pct}%)')
                else:
                    log_callback('info', f'[{insta_filename}] No match found above threshold ({threshold})')
                    log_callback('debug', f'[{insta_filename}] Best result: {best["catalog_key"]} total={best["total_score"]:.4f} vision={best["vision_score"]:.4f}')
        return results

    # Use batch API if we have enough candidates and batch processing is enabled
    use_batch = (total_candidates >= batch_threshold and batch_size > 1)
    
    if use_batch:
        if log_callback:
            log_callback('info', f'[{insta_filename}] Using batch API (batch_size={batch_size}, candidates={total_candidates})')
        
        # Prepare batch candidates with numeric IDs
        batch_candidates = []
        failed_count = 0
        skipped_no_path = 0
        skipped_oversized = 0
        
        # Get mount_point from config for resolving paths
        from lightroom_tagger.core.config import load_config
        config = load_config()
        mount_point = config.mount_point
        
        for idx, candidate in enumerate(candidates):
            # DEBUG: Log candidate keys for first one
            if idx == 0 and log_callback:
                log_callback('debug', f'[{insta_filename}] Candidate keys: {list(candidate.keys())}')
            
            # Get path from candidate (may be 'local_path' or 'filepath')
            local_path = candidate.get('local_path') or candidate.get('filepath')
            
            # Convert Windows UNC paths to Unix mount points
            # e.g., //NAS/ccanales/... -> /Volumes/ccanales/...
            if local_path and local_path.startswith('//'):
                parts = local_path[2:].split('/', 2)  # Skip // and split into [server, share, rest]
                if len(parts) >= 3:
                    # For //NAS/ccanales/..., we want /Volumes/ccanales/...
                    local_path = f'/Volumes/{parts[1]}/{parts[2]}'
            
            # Resolve path with mount_point if needed (for relative paths)
            elif local_path and not _os.path.isabs(local_path):
                local_path = _os.path.join(mount_point, local_path)
            
            if not local_path or not _os.path.exists(local_path):
                skipped_no_path += 1
                if log_callback and skipped_no_path <= 2:  # Log first 2
                    log_callback('debug', f'[{insta_filename}] Candidate {idx} path missing/invalid: {local_path}')
                continue
                
            try:
                cached_local_path = get_or_create_cached_image(db, candidate.get('key'), local_path)
                if cached_local_path is None:
                    skipped_oversized += 1
                    continue
                batch_candidates.append((idx, cached_local_path))
            except Exception as e:
                failed_count += 1
                if log_callback and failed_count <= 3:  # Log first 3 failures
                    log_callback('error', f'[{insta_filename}] Failed to prepare candidate {idx}: {e}')
                pass
        
        if log_callback:
            if skipped_no_path > 0:
                log_callback('debug', f'[{insta_filename}] Skipped {skipped_no_path} candidates with missing/invalid paths')
            if skipped_oversized > 0:
                log_callback('info', f'[{insta_filename}] Skipped {skipped_oversized} oversized candidates')
            if failed_count > 0:
                log_callback('warning', f'[{insta_filename}] Failed to prepare {failed_count} candidates for batch processing')
        
        # Build idx->candidate lookup for immediate scoring after each chunk
        candidate_by_idx = {idx: candidate for idx, candidate in enumerate(candidates)}
        insta_key = insta_image.get('key')
        model_label = f"{provider_id}:{model}" if provider_id and model else get_vision_model()

        def _score_and_store(chunk_results: dict[int, float]):
            """Score chunk results immediately: write to DB and append to results."""
            for cid, vision_confidence in chunk_results.items():
                candidate = candidate_by_idx.get(cid)
                if candidate is None:
                    continue
                catalog_key = candidate.get('key')

                vision_score_val = vision_score(vision_confidence)
                vision_result = 'SAME' if vision_confidence >= 80 else 'DIFFERENT' if vision_confidence <= 20 else 'UNCERTAIN'

                cached_phash = get_cached_phash(db, catalog_key)
                if cached_phash is not None:
                    phash_dist = hamming_distance(insta_image.get('image_hash', ''), cached_phash)
                    nonlocal cache_hits
                    cache_hits += 1
                else:
                    phash_dist = hamming_distance(insta_image.get('image_hash', ''), candidate.get('image_hash', ''))
                    nonlocal cache_misses
                    cache_misses += 1

                phash_score_val = max(0, 1 - (phash_dist / 16))
                desc_sim_01 = desc_scores_by_idx.get(cid, 0.0) if desc_weight > 0 else 0.0
                capt_sim = text_similarity(insta_image.get('description', ''), candidate.get('description', ''))
                desc_sim_display = desc_sim_01 if desc_weight > 0 else capt_sim

                total_score_val = (
                    (phash_weight * phash_score_val)
                    + (desc_weight * desc_sim_01)
                    + (vision_weight * vision_score_val)
                )

                store_vision_comparison(db, catalog_key, insta_key, vision_result, vision_score_val, model_label)

                results.append({
                    'catalog_key': catalog_key,
                    'insta_key': insta_key,
                    'phash_distance': int(phash_dist),
                    'phash_score': phash_score_val,
                    'desc_similarity': desc_sim_display,
                    'vision_result': vision_result,
                    'vision_score': vision_score_val,
                    'vision_reasoning': '',
                    'total_score': total_score_val,
                    'model_used': model_label,
                    'rate_limited': False,
                })

        # Call batch API in chunks, scoring each chunk immediately
        if log_callback:
            log_callback('debug', f'[{insta_filename}] Batch check: batch_candidates={len(batch_candidates)}, compressed_insta={"present" if compressed_insta else "missing"}')
        
        if batch_candidates and compressed_insta:
            num_chunks = (len(batch_candidates) + batch_size - 1) // batch_size
            if log_callback:
                log_callback('info', f'[{insta_filename}] Processing {len(batch_candidates)} candidates in {num_chunks} batches of {batch_size}')
            try:
                registry = ProviderRegistry()
                actual_provider_id = provider_id or registry.fallback_order[0]
                client = registry.get_client(actual_provider_id)
                requested_model = model or get_vision_model()

                for chunk_start in range(0, len(batch_candidates), batch_size):
                    if should_cancel is not None and should_cancel():
                        break
                    chunk = batch_candidates[chunk_start:chunk_start + batch_size]
                    chunk_num = chunk_start // batch_size + 1
                    current_chunk_size = len(chunk)

                    if log_callback:
                        log_callback('debug', f'[{insta_filename}] Batch {chunk_num}/{num_chunks}: {current_chunk_size} candidates')

                    chunk_results = _call_batch_chunk(
                        client, requested_model, compressed_insta, chunk,
                        log_callback, insta_filename, chunk_num, num_chunks,
                    )
                    _score_and_store(chunk_results)
                    if batch_progress_callback:
                        batch_progress_callback(chunk_num, num_chunks)

                if log_callback:
                    log_callback('debug', f'[{insta_filename}] Batch API scored {len(results)} total results')
            except RateLimitError:
                if log_callback:
                    log_callback('warning', f'[{insta_filename}] Batch API rate limited, falling back to sequential')
                use_batch = False
            except Exception as e:
                if log_callback:
                    log_callback('warning', f'[{insta_filename}] Batch API error: {e}, falling back to sequential')
                use_batch = False
        else:
            if log_callback:
                log_callback('warning', f'[{insta_filename}] Batch API SKIPPED (batch_candidates={len(batch_candidates)}, compressed_insta={"present" if compressed_insta else "missing"})')

        # Score candidates that were skipped (no valid path) with 0.0
        scored_ids = {r['catalog_key'] for r in results}
        for idx, candidate in enumerate(candidates):
            catalog_key = candidate.get('key')
            if catalog_key not in scored_ids:
                _score_and_store({idx: 0.0})
    
    if should_cancel is not None and should_cancel():
        return results

    if not use_batch:
        # Sequential fallback
        consecutive_fatal = 0
        FATAL_ABORT_THRESHOLD = 3
        for idx0, candidate in enumerate(candidates):
            idx = idx0 + 1
            if should_cancel is not None and should_cancel():
                break
            if consecutive_fatal >= FATAL_ABORT_THRESHOLD:
                if log_callback:
                    log_callback('warning', f'[{insta_filename}] Aborting remaining {len(candidates) - idx + 1} candidates after {FATAL_ABORT_THRESHOLD} consecutive fatal errors')
                break
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

            desc_sim_01 = desc_scores_by_idx.get(idx0, 0.0) if desc_weight > 0 else 0.0
            capt_sim = text_similarity(insta_image.get('description', ''), candidate.get('description', ''))
            desc_sim_display = desc_sim_01 if desc_weight > 0 else capt_sim

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
            elif vision_weight > 0 and insta_path and local_path:
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
                    consecutive_fatal = 0
                    rate_limited_count += 1
                    if log_callback:
                        log_callback('warning', f'[{insta_filename}] Rate limited for {catalog_key} ({consecutive_rate_limits} consecutive)')
                    vision_result = 'RATE_LIMITED'
                    vision_score_val = 0.0
                except InvalidRequestError as e:
                    consecutive_rate_limits = 0
                    consecutive_fatal += 1
                    if log_callback:
                        log_callback('error', f'[{insta_filename}] Fatal vision error for {catalog_key}: {e}')
                    vision_result = 'ERROR'
                    vision_score_val = 0.0
                except Exception as e:
                    consecutive_rate_limits = 0
                    consecutive_fatal = 0
                    if log_callback:
                        log_callback('error', f'[{insta_filename}] Vision error for {catalog_key}: {e}')
                    vision_result = 'ERROR'
                    vision_score_val = 0.0
            else:
                vision_result = 'UNCERTAIN'
                vision_score_val = 0.5

            total_score_val = (
                (phash_weight * phash_score_val)
                + (desc_weight * desc_sim_01)
                + (vision_weight * vision_score_val)
            )

            if log_callback and vision_result != 'UNCERTAIN':
                log_callback('debug', f'[{insta_filename}] {catalog_key} → {vision_result} (vision={vision_score_val:.2f}, phash={phash_score_val:.2f}, total={total_score_val:.2f})')

            results.append({
                'catalog_key': catalog_key,
                'insta_key': insta_key,
                'phash_distance': int(phash_dist),
                'phash_score': phash_score_val,
                'desc_similarity': desc_sim_display,
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
        above = [r for r in results if r['total_score'] >= threshold]
        log_callback('debug', f'[{insta_filename}] {len(results)} results, {len(above)} above threshold ({threshold})')
        if above:
            for r in above[:5]:
                log_callback('info', f'[{insta_filename}] Above threshold: {r["catalog_key"]} total={r["total_score"]:.4f} vision={r["vision_score"]:.4f}')
        if results:
            best = results[0]
            best_pct = int(best['total_score'] * 100)
            if best['total_score'] >= threshold:
                log_callback('info', f'[{insta_filename}] Comparison complete - Best match: {best["catalog_key"]} ({best_pct}%)')
            else:
                log_callback('info', f'[{insta_filename}] No match found above threshold ({threshold})')
                log_callback('debug', f'[{insta_filename}] Best result: {best["catalog_key"]} total={best["total_score"]:.4f} vision={best["vision_score"]:.4f}')

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
    from lightroom_tagger.core.analyzer import VIDEO_EXTENSIONS

    date_folder = insta_image.get('date_folder', '')
    if len(date_folder) != 6:
        return []

    post_year = int(date_folder[:4])
    post_month = int(date_folder[4:6])
    post_date = datetime(post_year, post_month, 15)
    window_start = post_date - timedelta(days=days_before)

    candidates = []
    sql = (
        "SELECT i.*, COALESCE(d.summary, '') AS ai_summary "
        "FROM images i "
        "LEFT JOIN image_descriptions d ON i.key = d.image_key AND d.image_type = 'catalog' "
        "WHERE i.instagram_posted = 0"
    )
    for row in db.execute(sql).fetchall():
        row_dict = dict(row)
        img = _deserialize_row(row_dict)
        img["ai_summary"] = str(row_dict.get("ai_summary") or "")
        filepath = img.get('filepath', '')
        if filepath:
            ext = os.path.splitext(filepath)[1].lower()
            if ext in VIDEO_EXTENSIONS:
                continue
        date_taken = img.get('date_taken', '')
        if not date_taken:
            continue
        try:
            img_date = datetime.fromisoformat(date_taken.replace('Z', '+00:00'))
            if window_start <= img_date <= post_date:
                candidates.append(img)
        except Exception:
            continue

    candidates.sort(key=lambda c: c.get('date_taken', ''), reverse=True)
    return candidates
