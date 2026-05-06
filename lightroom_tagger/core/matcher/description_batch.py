"""Description-only batch scoring via compare_descriptions_batch."""

from lightroom_tagger.core.config import get_vision_model
from lightroom_tagger.core.provider_registry import ProviderRegistry


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
            from lightroom_tagger.core import matcher as _matcher

            raw_map = _matcher.compare_descriptions_batch(
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
