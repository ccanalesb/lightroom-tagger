"""Vision comparison pipeline via OpenAI-compat provider stack."""

from __future__ import annotations

import contextlib
import json as _json
import os
from typing import Any

from lightroom_tagger.core.exceptions import ContextLengthError
from lightroom_tagger.core.provider_registry import ProviderRegistry

from .image_prep import RAW_EXTENSIONS, VISION_MAX_DIMENSION, compress_image, get_viewable_path_managed

MAX_TOKENS_ESCALATION = [256, 4096, 32768, 65536]

# Shared across calls so that once a model needs higher max_tokens we
# remember it for subsequent candidates instead of re-discovering every time.
_model_min_tokens: dict[str, int] = {}

# Models where max_tokens escalation was fully exhausted and still fails.
# Keyed by "provider:model" — these are skipped immediately to avoid
# wasting minutes on retries that will never succeed.
_broken_provider_models: set[str] = set()


def _resolve_default_vision_comparison_provider(
    registry: ProviderRegistry,
    model: str | None,
) -> tuple[str | None, str | None]:
    vc_defaults = registry.defaults.get("vision_comparison", {}) or {}
    provider_id: str | None = vc_defaults.get("provider")
    resolved_model = model if model is not None else vc_defaults.get("model")
    if provider_id is None:
        order = registry.fallback_order
        if order:
            provider_id = order[0]
    return provider_id, resolved_model


def compare_with_vision(local_path: str, insta_path: str, log_callback=None,
                        cached_local_path: str | None = None, compressed_insta_path: str | None = None,
                        provider_id: str | None = None, model: str | None = None) -> dict:
    f"""Compare two images using a vision model with compression.

    When *provider_id* is omitted, resolves ``defaults.vision_comparison`` or the
    registry ``fallback_order`` (same path as :func:`_compare_via_provider`).

    Compresses images to max {VISION_MAX_DIMENSION} pixels before comparison
    to reduce bandwidth and processing time. Supports pre-compressed paths
    to avoid redundant compression.

    Args:
        local_path: Original path to catalog image (for error reporting and RAW conversion)
        insta_path: Original path to Instagram image (for error reporting)
        log_callback: Optional callback for logging
        cached_local_path: Pre-compressed catalog image path (optional, uses cache if available)
        compressed_insta_path: Pre-compressed Instagram image path (optional)
        provider_id: Provider to use (``None`` → registry defaults)
        model: Model to use with the selected provider (``None`` → provider default)

    Returns:
        dict with keys ``confidence`` (0-100), ``verdict`` (``SAME`` | ``DIFFERENT`` | ``UNCERTAIN``),
        ``reasoning`` (str), and ``_provider`` / ``_model`` from the provider stack.
    """
    # Track all temp files for cleanup
    temp_files: list[str] = []
    compressed_local: str | None = None
    compressed_insta: str | None = None

    try:
        # Step 1: Handle catalog image (local_path)
        if cached_local_path and os.path.exists(cached_local_path):
            compressed_local = cached_local_path
            if log_callback:
                log_callback('info', f'Using cached compressed image for {os.path.basename(local_path)}')
        else:
            viewable_local, viewable_local_is_temp = get_viewable_path_managed(local_path)
            if viewable_local_is_temp:
                temp_files.append(viewable_local)
                if log_callback:
                    log_callback('info', f'Converted DNG to JPG: {os.path.basename(viewable_local)}')
            elif viewable_local != local_path:
                if log_callback:
                    log_callback('info', f'Using JPG sidecar for {os.path.basename(local_path)}')

            compressed_local = compress_image(viewable_local)
            if compressed_local != viewable_local:
                temp_files.append(compressed_local)

        # Step 2: Handle Instagram image
        if compressed_insta_path and os.path.exists(compressed_insta_path):
            compressed_insta = compressed_insta_path
        else:
            viewable_insta, viewable_insta_is_temp = get_viewable_path_managed(insta_path)
            if viewable_insta_is_temp:
                temp_files.append(viewable_insta)

            compressed_insta = compress_image(viewable_insta)
            if compressed_insta != viewable_insta:
                temp_files.append(compressed_insta)

        # Step 3: Run vision comparison (always via provider registry)
        assert compressed_local is not None and compressed_insta is not None
        resolved_pid = provider_id
        resolved_model = model
        if resolved_pid is None:
            registry = ProviderRegistry()
            resolved_pid, resolved_model = _resolve_default_vision_comparison_provider(
                registry, resolved_model,
            )
        if resolved_pid is None:
            from lightroom_tagger.core.exceptions import ModelUnavailableError
            raise ModelUnavailableError(
                'No provider configured for vision comparison — set defaults.vision_comparison '
                'in providers.json',
                provider=None,
                model=None,
            )
        result = _compare_via_provider(
            compressed_local,
            compressed_insta,
            resolved_pid,
            resolved_model,
            log_callback,
        )
        return result

    finally:
        for temp_file in temp_files:
            if temp_file and os.path.exists(temp_file):
                with contextlib.suppress(Exception):
                    os.unlink(temp_file)


def _compare_via_provider(local_path: str, insta_path: str,
                          provider_id: str, model: str | None,
                          log_callback=None) -> dict:
    """Run vision comparison via the unified provider pipeline.

    Escalates ``max_tokens`` automatically on ``ContextLengthError``
    (e.g. Claude extended-thinking models that require ``max_tokens >
    thinking.budget_tokens``).  Models that succeed at 256 are never
    affected — escalation only triggers after failure.

    Discovered minimums are cached in ``_model_min_tokens`` so later
    candidates skip the failing lower values.
    """
    from lightroom_tagger.core.exceptions import InvalidRequestError
    from lightroom_tagger.core.fallback import FallbackDispatcher
    from lightroom_tagger.core.vision_client import compare_images as _cmp

    registry = ProviderRegistry()
    dispatcher = FallbackDispatcher(registry)

    if model is None:
        models = registry.list_models(provider_id)
        if not models:
            from lightroom_tagger.core.exceptions import ModelUnavailableError
            raise ModelUnavailableError(
                f"No models available for provider '{provider_id}' — check provider config",
                provider=provider_id,
                model=None,
            )
        model = models[0]["id"]

    def fn_factory(client: Any, mdl: str):
        provider_key = f"{provider_id}:{mdl}"
        if provider_key in _broken_provider_models:
            def _skip():
                raise InvalidRequestError(
                    f"{mdl} is broken (max_tokens exhausted in prior call)",
                    provider=provider_id, model=mdl,
                )
            return _skip

        cached_min = _model_min_tokens.get(provider_key, 0)
        start_idx = 0
        for i, val in enumerate(MAX_TOKENS_ESCALATION):
            if val >= cached_min:
                start_idx = i
                break
        state = {"idx": start_idx}

        def _call():
            tokens = MAX_TOKENS_ESCALATION[state["idx"]]
            try:
                return _cmp(client, mdl, local_path, insta_path,
                            log_callback=log_callback, max_tokens=tokens)
            except ContextLengthError:
                if state["idx"] < len(MAX_TOKENS_ESCALATION) - 1:
                    state["idx"] += 1
                    next_val = MAX_TOKENS_ESCALATION[state["idx"]]
                    _model_min_tokens[provider_key] = next_val
                    if log_callback:
                        log_callback(
                            "warning",
                            f"[compare] Escalating max_tokens to "
                            f"{next_val} for {mdl}",
                        )
                else:
                    _broken_provider_models.add(provider_key)
                    if log_callback:
                        log_callback(
                            "warning",
                            f"[compare] max_tokens exhausted at {tokens} "
                            f"for {mdl}, blacklisting for session",
                        )
                raise

        return _call

    result, actual_provider, actual_model = dispatcher.call_with_fallback(
        operation="compare",
        fn_factory=fn_factory,
        provider_id=provider_id,
        model=model,
        log_callback=log_callback,
    )
    result["_provider"] = actual_provider
    result["_model"] = actual_model
    return result


def parse_vision_response(raw: str) -> dict:
    """Parse vision model response into structured result.

    Expects JSON: {"confidence": 0-100, "reasoning": "..."}
    Falls back to legacy SAME/DIFFERENT/UNCERTAIN parsing.
    """
    raw = raw.strip()

    try:
        if raw.startswith('```'):
            raw = raw.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
        data = _json.loads(raw)
        confidence = int(data.get('confidence', 50))
        confidence = max(0, min(100, confidence))
        if confidence >= 70:
            verdict = 'SAME'
        elif confidence <= 30:
            verdict = 'DIFFERENT'
        else:
            verdict = 'UNCERTAIN'
        return {'confidence': confidence, 'verdict': verdict, 'reasoning': data.get('reasoning', '')}
    except (TypeError, ValueError, KeyError, _json.JSONDecodeError):
        pass

    upper = raw.upper()
    if upper.startswith('SAME') and 'DIFFERENT' not in upper[:20]:
        return {'confidence': 100, 'verdict': 'SAME', 'reasoning': ''}
    elif 'DIFFERENT' in upper[:50]:
        return {'confidence': 0, 'verdict': 'DIFFERENT', 'reasoning': ''}
    return {'confidence': 50, 'verdict': 'UNCERTAIN', 'reasoning': ''}


def vision_score(result) -> float:
    """Convert vision result to 0.0-1.0 score.

    Accepts int confidence (0-100) or legacy string ('SAME'/'DIFFERENT'/'UNCERTAIN').
    """
    if isinstance(result, (int, float)):
        return max(0.0, min(1.0, result / 100))
    if isinstance(result, str):
        if result == 'SAME':
            return 1.0
        elif result == 'DIFFERENT':
            return 0.0
        return 0.5
    return 0.5
