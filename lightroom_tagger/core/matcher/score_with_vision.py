"""Two-stage cascade scoring: description similarity plus optional vision comparisons."""

from collections.abc import Callable

from .score_formula import DEFAULT_WEIGHTS, ScoreWeights, compute_total_score, normalize_phash_score
from .vision_batch import _build_compressed_batch_entries, _log_comparison_tail


def score_candidates_with_vision(db, insta_image: dict, candidates: list,
                                 weights: ScoreWeights = DEFAULT_WEIGHTS,
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

    from lightroom_tagger.core import matcher as _matcher

    from lightroom_tagger.core.analyzer import compare_with_vision, vision_score
    from lightroom_tagger.core.cancel_scope import resolve_cancel_check
    from lightroom_tagger.core.error_policy import (
        ConsecutiveAbortTracker,
        ContextLengthEscalationPolicy,
        FATAL_ABORT_THRESHOLD,
        VisionBatchErrorPolicy,
    )
    from lightroom_tagger.core.exceptions import RateLimitError
    from lightroom_tagger.core.path_utils import normalize_match_filesystem_path
    from lightroom_tagger.core.phash import hamming_distance
    from lightroom_tagger.core.provider_resolution import resolve_model
    from lightroom_tagger.core.retry import CancelledRetryError

    r = resolve_model(kind="vision_comparison", provider_id=provider_id, model=model)
    resolved_provider = r.provider_id
    resolved_model = r.model
    registry = r.registry
    # Selection label: provider-qualified when a provider was requested, else bare model.
    selection_model_label = f"{provider_id}:{resolved_model}" if provider_id else resolved_model

    results = []
    total_candidates = len(candidates)
    insta_filename = _os.path.basename(insta_image.get('local_path', 'unknown'))
    cancel_check = resolve_cancel_check(should_cancel)
    abort_tracker = ConsecutiveAbortTracker()

    desc_scores_by_idx = _matcher._compute_desc_scores_for_candidates(
        insta_image, candidates, batch_size, weights.desc, skip_undescribed,
        provider_id, model, log_callback, registry=registry,
    )

    # Compress Instagram image ONCE before candidate loop (vision stage only)
    insta_cache = _matcher.InstagramCache(db)
    insta_path = insta_image.get('local_path')
    compressed_insta = None
    if weights.vision > 0 and insta_path:
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

    vision_error_policy = ContextLengthEscalationPolicy()
    vision_batch_policy = VisionBatchErrorPolicy()

    if weights.vision == 0:
        insta_key = insta_image.get('key')
        model_label = selection_model_label
        for idx, candidate in enumerate(candidates):
            catalog_key = candidate.get('key')
            cached_phash = _matcher.get_cached_phash(db, catalog_key)
            if cached_phash is not None:
                phash_dist = hamming_distance(insta_image.get('image_hash', ''), cached_phash)
                cache_hits += 1
            else:
                phash_dist = hamming_distance(insta_image.get('image_hash', ''), candidate.get('image_hash', ''))
                cache_misses += 1
            phash_score_val = normalize_phash_score(phash_dist)
            desc_sim_01 = desc_scores_by_idx.get(idx, 0.0) if weights.desc > 0 else 0.0
            capt_sim = _matcher.text_similarity(insta_image.get('description', ''), candidate.get('description', ''))
            desc_sim_display = desc_sim_01 if weights.desc > 0 else capt_sim
            vision_score_val = 0.0
            total_score_val = compute_total_score(
                phash_score_val, desc_sim_01, vision_score_val,
                weights,
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
        _log_comparison_tail(insta_filename, log_callback, results, threshold, cache_hits, cache_misses)
        return results

    # Use batch API if we have enough candidates and batch processing is enabled
    use_batch = (total_candidates >= batch_threshold and batch_size > 1)

    if use_batch:
        if log_callback:
            log_callback('info', f'[{insta_filename}] Using batch API (batch_size={batch_size}, candidates={total_candidates})')

        from lightroom_tagger.core.config import load_config

        config = load_config()
        mount_point = config.mount_point

        batch_candidates, skipped_no_path, skipped_oversized, failed_count = _build_compressed_batch_entries(
            db,
            candidates,
            mount_point,
            insta_filename,
            log_callback,
            normalize_match_filesystem_path,
            _matcher.get_or_create_cached_image,
        )

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
        model_label = selection_model_label

        def _score_and_store(chunk_results: dict[int, float]):
            """Score chunk results immediately: write to DB and append to results."""
            for cid, vision_confidence in chunk_results.items():
                candidate = candidate_by_idx.get(cid)
                if candidate is None:
                    continue
                catalog_key = candidate.get('key')

                vision_score_val = vision_score(vision_confidence)
                vision_result = 'SAME' if vision_confidence >= 80 else 'DIFFERENT' if vision_confidence <= 20 else 'UNCERTAIN'

                cached_phash = _matcher.get_cached_phash(db, catalog_key)
                if cached_phash is not None:
                    phash_dist = hamming_distance(insta_image.get('image_hash', ''), cached_phash)
                    nonlocal cache_hits
                    cache_hits += 1
                else:
                    phash_dist = hamming_distance(insta_image.get('image_hash', ''), candidate.get('image_hash', ''))
                    nonlocal cache_misses
                    cache_misses += 1

                phash_score_val = normalize_phash_score(phash_dist)
                desc_sim_01 = desc_scores_by_idx.get(cid, 0.0) if weights.desc > 0 else 0.0
                capt_sim = _matcher.text_similarity(insta_image.get('description', ''), candidate.get('description', ''))
                desc_sim_display = desc_sim_01 if weights.desc > 0 else capt_sim

                total_score_val = compute_total_score(
                    phash_score_val, desc_sim_01, vision_score_val,
                    weights,
                )

                _matcher.store_vision_comparison(db, catalog_key, insta_key, vision_result, vision_score_val, model_label)

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
                actual_provider_id = resolved_provider
                requested_model = resolved_model

                for chunk_start in range(0, len(batch_candidates), batch_size):
                    if cancel_check is not None and cancel_check():
                        break
                    chunk = batch_candidates[chunk_start:chunk_start + batch_size]
                    chunk_num = chunk_start // batch_size + 1
                    current_chunk_size = len(chunk)

                    if log_callback:
                        log_callback('debug', f'[{insta_filename}] Batch {chunk_num}/{num_chunks}: {current_chunk_size} candidates')

                    try:
                        chunk_results = _matcher._call_batch_chunk(
                            registry, actual_provider_id, requested_model,
                            compressed_insta, chunk, log_callback, insta_filename,
                            chunk_num, num_chunks, error_policy=vision_batch_policy,
                            cancel_check=cancel_check,
                            abort_tracker=abort_tracker,
                        )
                    except CancelledRetryError:
                        break
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

    if cancel_check is not None and cancel_check():
        return results

    if not use_batch:
        # Sequential fallback
        for idx0, candidate in enumerate(candidates):
            idx = idx0 + 1
            if cancel_check is not None and cancel_check():
                break
            if abort_tracker.fatal_abort_reached:
                if log_callback:
                    log_callback('warning', f'[{insta_filename}] Aborting remaining {len(candidates) - idx + 1} candidates after {FATAL_ABORT_THRESHOLD} consecutive fatal errors')
                break
            catalog_key = candidate.get('key')
            insta_key = insta_image.get('key')
            local_path = candidate.get('local_path')

            # Use cached pHash if available, otherwise compute or fallback
            cached_phash = _matcher.get_cached_phash(db, catalog_key)
            if cached_phash is not None:
                phash_dist = hamming_distance(insta_image.get('image_hash', ''), cached_phash)
                cache_hits += 1
            else:
                phash_dist = hamming_distance(insta_image.get('image_hash', ''), candidate.get('image_hash', ''))
                cache_misses += 1

            phash_score_val = normalize_phash_score(phash_dist)

            desc_sim_01 = desc_scores_by_idx.get(idx0, 0.0) if weights.desc > 0 else 0.0
            capt_sim = _matcher.text_similarity(insta_image.get('description', ''), candidate.get('description', ''))
            desc_sim_display = desc_sim_01 if weights.desc > 0 else capt_sim

            # Get or create cached compressed image for catalog
            cached_local_path = None
            if local_path:
                try:
                    cached_local_path = _matcher.get_or_create_cached_image(db, catalog_key, local_path)
                except Exception:
                    if log_callback and idx <= 5:  # Log first few failures
                        log_callback('warning', f'Cache miss for {catalog_key}, will compress on-demand')

            # Check vision comparison cache (invalidate if model changed)
            vision_cached = _matcher.get_vision_comparison(db, catalog_key, insta_key)
            # Requested label for cache lookup only; pipeline may pick a different default model.
            requested_model_label = selection_model_label
            cache_valid = (
                vision_cached
                and vision_cached.get('model_used') == requested_model_label
            )

            model_label = resolved_model
            vision_reasoning = ''
            if cache_valid:
                vision_result = vision_cached['result']
                vision_score_val = vision_cached['vision_score']
                model_label = vision_cached.get('model_used', model_label)
                abort_tracker.record_success()
            elif weights.vision > 0 and insta_path and local_path:
                try:
                    vision_data = compare_with_vision(
                        local_path, insta_path,
                        log_callback=log_callback,
                        cached_local_path=cached_local_path,
                        compressed_insta_path=compressed_insta,
                        provider_id=provider_id,
                        model=model,
                        error_policy=vision_error_policy,
                        cancel_check=cancel_check,
                        abort_tracker=abort_tracker,
                    )
                except CancelledRetryError:
                    break
                except Exception:
                    if log_callback:
                        log_callback('error', f'[{insta_filename}] Vision error for {catalog_key}')
                    vision_result = 'ERROR'
                    vision_score_val = 0.0
                    vision_reasoning = ''
                else:
                    vision_result = vision_data['verdict']
                    vision_score_val = vision_score(vision_data['confidence'])
                    vision_reasoning = (vision_data.get('reasoning') or '').strip()

                    if vision_result == 'RATE_LIMITED' and log_callback:
                        log_callback(
                            'warning',
                            f'[{insta_filename}] Rate limited for {catalog_key} '
                            f'({abort_tracker.consecutive_rate_limits} consecutive)',
                        )
                    elif vision_result == 'ERROR' and log_callback:
                        log_callback('error', f'[{insta_filename}] Vision error for {catalog_key}')

                    if vision_result not in ('RATE_LIMITED', 'ERROR'):
                        if vision_data.get('_provider'):
                            ap = vision_data['_provider']
                            am = vision_data.get('_model')
                            model_label = f"{ap}:{am}" if am is not None else f"{ap}:"

                        _matcher.store_vision_comparison(
                            db, catalog_key, insta_key,
                            vision_result, vision_score_val,
                            model_label,
                        )
            else:
                vision_result = 'UNCERTAIN'
                vision_score_val = 0.5

            total_score_val = compute_total_score(
                phash_score_val, desc_sim_01, vision_score_val,
                weights,
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

    insta_cache.cleanup()
    results.sort(key=lambda x: x['total_score'], reverse=True)
    _log_comparison_tail(insta_filename, log_callback, results, threshold, cache_hits, cache_misses)

    return results
