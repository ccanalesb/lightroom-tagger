"""Vision compare_images_batch chunking with payload split and token escalation."""

from __future__ import annotations

from collections.abc import Callable

from lightroom_tagger.core.error_policy import (
    ConsecutiveAbortTracker,
    VisionBatchErrorPolicy,
)
from lightroom_tagger.core.provider_registry import ProviderRegistry


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
    registry: ProviderRegistry,
    provider_id: str,
    model: str,
    reference_path: str,
    chunk: list[tuple[int, str]],
    log_callback,
    insta_filename: str,
    chunk_num: int,
    num_chunks: int,
    error_policy: VisionBatchErrorPolicy | None = None,
    cancel_check: Callable[[], bool] | None = None,
    abort_tracker: ConsecutiveAbortTracker | None = None,
) -> dict[int, float]:
    """Call compare_images_batch for a single chunk via :class:`VisionComparator`."""
    from lightroom_tagger.core.vision_comparator import VisionComparator

    comparator = VisionComparator(
        registry,
        log_callback=log_callback,
        cancel_check=cancel_check,
        abort_tracker=abort_tracker,
        batch_policy=error_policy,
    )
    return comparator.compare_batch(
        reference_path,
        chunk,
        provider_id,
        model,
        insta_filename=insta_filename,
        chunk_num=chunk_num,
        num_chunks=num_chunks,
    )


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
