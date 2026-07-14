"""Vision compare operations (pair + batch) routed through the vision-op engine."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from lightroom_tagger.core.error_policy import (
    ContextLengthEscalationPolicy,
    EscalationAction,
    VisionBatchErrorPolicy,
)
from lightroom_tagger.core.exceptions import (
    ContextLengthError,
    InvalidRequestError,
    PayloadTooLargeError,
)
from lightroom_tagger.core.provider_registry import ProviderRegistry
from lightroom_tagger.core.vision_client import compare_images, compare_images_batch

SplitBatchFn = Callable[
    [list[tuple[int, str]], list[tuple[int, str]], str, str],
    dict[int, float],
]


def parse_compare_vision_response(raw: Any) -> Any:
    """Pass through compare client output (already parsed by ``compare_images``)."""
    return raw


def build_compare_op_spec(
    local_path: str,
    insta_path: str,
    *,
    provider_id: str | None = None,
    model: str | None = None,
    log_callback=None,
    registry: ProviderRegistry | None = None,
    error_policy: ContextLengthEscalationPolicy | None = None,
    abort_tracker=None,
):
    """Build a :class:`VisionOpSpec` for a single pair compare."""
    from lightroom_tagger.core.vision_op import VisionOpSpec

    policy = error_policy if error_policy is not None else ContextLengthEscalationPolicy()

    def prepare_fn_factory():
        def fn_factory(client: Any, mdl: str):
            if policy.is_broken(provider_id, mdl):
                def _skip():
                    raise InvalidRequestError(
                        f"{mdl} is broken (max_tokens exhausted in prior call)",
                        provider=provider_id,
                        model=mdl,
                    )

                return _skip

            state: dict[str, Any] = {"token_index": policy.starting_index(provider_id, mdl)}

            def _call():
                tokens = policy.max_tokens_at(state["token_index"])
                try:
                    return compare_images(
                        client,
                        mdl,
                        local_path,
                        insta_path,
                        log_callback=log_callback,
                        max_tokens=tokens,
                    )
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

        return fn_factory

    return VisionOpSpec(
        resolve_kind="vision_comparison",
        operation="compare",
        provider_id=provider_id,
        model=model,
        fn_factory=prepare_fn_factory,
        parse_response=parse_compare_vision_response,
        log_callback=log_callback,
        registry=registry,
        error_policy=policy,
        abort_tracker=abort_tracker,
    )


def build_compare_batch_op_spec(
    reference_path: str,
    candidates: list[tuple[int, str]],
    *,
    provider_id: str | None = None,
    model: str | None = None,
    log_callback=None,
    registry: ProviderRegistry | None = None,
    error_policy: VisionBatchErrorPolicy | None = None,
    insta_filename: str = "",
    chunk_num: int = 1,
    num_chunks: int = 1,
    split_batch: SplitBatchFn | None = None,
    abort_tracker=None,
):
    """Build a :class:`VisionOpSpec` for one batch compare attempt."""
    from lightroom_tagger.core.vision_op import VisionOpSpec

    policy = error_policy if error_policy is not None else VisionBatchErrorPolicy()

    def prepare_fn_factory():
        def fn_factory(client, mdl):
            attempt_provider = getattr(client, "_provider_id", None) or provider_id
            call_state: dict[str, Any] = {
                "candidates": candidates,
                "token_index": policy.starting_index(attempt_provider, mdl),
            }

            def _call():
                if policy.is_broken(attempt_provider, mdl):
                    raise InvalidRequestError(
                        f"{mdl} is broken (max_tokens exhausted in prior call)",
                        provider=attempt_provider,
                        model=mdl,
                    )

                tokens = policy.max_tokens_at(call_state["token_index"])
                try:
                    return compare_images_batch(
                        client,
                        mdl,
                        reference_path,
                        call_state["candidates"],
                        log_callback=log_callback,
                        max_tokens=tokens,
                    )
                except (ContextLengthError, PayloadTooLargeError) as exc:
                    action = policy.on_escalation_error(
                        exc,
                        provider_id=attempt_provider,
                        model=mdl,
                        operation="compare_batch",
                        call_state=call_state,
                    )
                    if log_callback and call_state.get("_log_message"):
                        prefix = f"[{insta_filename}] Batch {chunk_num}/{num_chunks}: "
                        log_callback("warning", prefix + call_state["_log_message"])

                    if isinstance(exc, PayloadTooLargeError):
                        if action == EscalationAction.SPLIT:
                            left_half, right_half = call_state["_split_halves"]
                            if split_batch is None:
                                raise RuntimeError("split_batch callback required for SPLIT") from exc
                            return split_batch(left_half, right_half, attempt_provider, mdl)
                        if action == EscalationAction.GIVE_UP:
                            return {}

                    if action == EscalationAction.GIVE_UP:
                        raise
                    if action == EscalationAction.RETRY:
                        return _call()
                    raise

            return _call

        return fn_factory

    return VisionOpSpec(
        resolve_kind="vision_comparison",
        operation="compare_batch",
        provider_id=provider_id,
        model=model,
        fn_factory=prepare_fn_factory,
        parse_response=parse_compare_vision_response,
        log_callback=log_callback,
        registry=registry,
        error_policy=policy,
        abort_tracker=abort_tracker,
    )
