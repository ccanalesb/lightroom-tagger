"""Vision compare_images_batch chunking with payload split and token escalation."""

from __future__ import annotations

from collections.abc import Callable

BATCH_MAX_TOKENS_ESCALATION = [4096, 32768, 65536]


def _build_compressed_batch_entries(
    db,
    candidates: list,
    mount_point: str,
    insta_filename: str,
    log_callback,
    normalize_match_filesystem_path: Callable[[str | None, str], str | None],
    get_or_create_cached_image: Callable[..., str | None],
) -> tuple[list[tuple[int, str]], int, int, int]:
    """Map candidates to compressed local paths suitable for vision batch compares."""
    batch_candidates: list[tuple[int, str]] = []
    failed_count = 0
    skipped_no_path = 0
    skipped_oversized = 0

    for idx, candidate in enumerate(candidates):
        if idx == 0 and log_callback:
            log_callback('debug', f'[{insta_filename}] Candidate keys: {list(candidate.keys())}')

        raw_path = candidate.get('local_path') or candidate.get('filepath')
        local_path = normalize_match_filesystem_path(raw_path, mount_point)
        if local_path is None:
            skipped_no_path += 1
            if log_callback and skipped_no_path <= 2:
                log_callback('debug', f'[{insta_filename}] Candidate {idx} path missing/invalid: {raw_path}')
            continue

        try:
            cached_local_path = get_or_create_cached_image(db, candidate.get('key'), local_path)
            if cached_local_path is None:
                skipped_oversized += 1
                continue
            batch_candidates.append((idx, cached_local_path))
        except Exception as e:
            failed_count += 1
            if log_callback and failed_count <= 3:
                log_callback('error', f'[{insta_filename}] Failed to prepare candidate {idx}: {e}')

    return batch_candidates, skipped_no_path, skipped_oversized, failed_count


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
    from lightroom_tagger.core.exceptions import ContextLengthError, PayloadTooLargeError
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


def _log_comparison_tail(
    insta_filename: str,
    log_callback,
    results: list,
    threshold: float,
    cache_hits: int,
    cache_misses: int,
) -> None:
    if not log_callback:
        return
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
