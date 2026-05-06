"""Vision compare_images_batch chunking with payload split and token escalation."""

BATCH_MAX_TOKENS_ESCALATION = [4096, 32768, 65536]


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
