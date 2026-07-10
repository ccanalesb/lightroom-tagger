"""Vision comparison pipeline via OpenAI-compat provider stack."""

from __future__ import annotations

import contextlib
import json as _json
import os
from collections.abc import Callable
from typing import Any

from lightroom_tagger.core.error_policy import (
    ConsecutiveAbortTracker,
    ContextLengthEscalationPolicy,
)
from lightroom_tagger.core.exceptions import ContextLengthError
from lightroom_tagger.core.provider_registry import ProviderRegistry
from lightroom_tagger.core.provider_resolution import resolve_model

from .image_prep import RAW_EXTENSIONS, VISION_MAX_DIMENSION, compress_image, get_viewable_path_managed


def compare_with_vision(local_path: str, insta_path: str, log_callback=None,
                        cached_local_path: str | None = None, compressed_insta_path: str | None = None,
                        provider_id: str | None = None, model: str | None = None,
                        error_policy: ContextLengthEscalationPolicy | None = None,
                        cancel_check: Callable[[], bool] | None = None,
                        abort_tracker: ConsecutiveAbortTracker | None = None) -> dict:
    f"""Compare two images using a vision model with compression.

    When *provider_id* / *model* are omitted, resolves via
    :func:`lightroom_tagger.core.provider_resolution.resolve_model`
    (``kind="vision_comparison"``).

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
        error_policy: Per-run escalation policy (``None`` → new instance per call)

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
        r = resolve_model(
            kind="vision_comparison",
            provider_id=provider_id,
            model=model,
        )
        policy = error_policy if error_policy is not None else ContextLengthEscalationPolicy()
        result = _compare_via_provider(
            compressed_local,
            compressed_insta,
            r.provider_id,
            r.model,
            r.registry,
            log_callback,
            error_policy=policy,
            cancel_check=cancel_check,
            abort_tracker=abort_tracker,
        )
        return result

    finally:
        for temp_file in temp_files:
            if temp_file and os.path.exists(temp_file):
                with contextlib.suppress(Exception):
                    os.unlink(temp_file)


def _compare_via_provider(local_path: str, insta_path: str,
                          provider_id: str, model: str,
                          registry: ProviderRegistry,
                          log_callback=None,
                          error_policy: ContextLengthEscalationPolicy | None = None,
                          cancel_check: Callable[[], bool] | None = None,
                          abort_tracker: ConsecutiveAbortTracker | None = None) -> dict:
    """Run vision comparison via the unified provider pipeline.

    Escalates ``max_tokens`` automatically on ``ContextLengthError``
    (e.g. Claude extended-thinking models that require ``max_tokens >
    thinking.budget_tokens``).  Models that succeed at 256 are never
    affected — escalation only triggers after failure.

    Discovered minimums are cached on *error_policy* so later
    candidates skip the failing lower values.
    """
    from lightroom_tagger.core.exceptions import (
        InvalidRequestError,
        RateLimitError,
    )
    from lightroom_tagger.core.fallback import FallbackDispatcher
    from lightroom_tagger.core.retry import CancelledRetryError
    from lightroom_tagger.core.vision_client import compare_images as _cmp

    policy = error_policy if error_policy is not None else ContextLengthEscalationPolicy()
    dispatcher = FallbackDispatcher(registry, error_policy=policy)

    def fn_factory(client: Any, mdl: str):
        if policy.is_broken(provider_id, mdl):
            def _skip():
                raise InvalidRequestError(
                    f"{mdl} is broken (max_tokens exhausted in prior call)",
                    provider=provider_id, model=mdl,
                )
            return _skip

        state: dict[str, Any] = {"token_index": policy.starting_index(provider_id, mdl)}

        def _call():
            tokens = policy.max_tokens_at(state["token_index"])
            try:
                return _cmp(client, mdl, local_path, insta_path,
                            log_callback=log_callback, max_tokens=tokens)
            except ContextLengthError as exc:
                policy.on_escalation_error(
                    exc,
                    provider_id=provider_id,
                    model=mdl,
                    operation="compare",
                    call_state=state,
                )
                if log_callback and state.get("_log_message"):
                    log_callback("warning", state["_log_message"])
                raise

        return _call

    try:
        result, actual_provider, actual_model = dispatcher.call_with_fallback(
            operation="compare",
            fn_factory=fn_factory,
            provider_id=provider_id,
            model=model,
            log_callback=log_callback,
            cancel_check=cancel_check,
            abort_tracker=abort_tracker,
        )
    except RateLimitError:
        return {'confidence': 0, 'verdict': 'RATE_LIMITED', 'reasoning': ''}
    except InvalidRequestError:
        return {'confidence': 0, 'verdict': 'ERROR', 'reasoning': ''}
    except CancelledRetryError:
        raise
    except Exception:
        if abort_tracker is not None:
            abort_tracker.record_transient_error()
        return {'confidence': 0, 'verdict': 'ERROR', 'reasoning': ''}

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
