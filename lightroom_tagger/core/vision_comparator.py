"""Vision comparison facade — dispatcher + error policy + batch/sequential strategy."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from lightroom_tagger.core.error_policy import (
    ConsecutiveAbortTracker,
    ContextLengthEscalationPolicy,
    EscalationAction,
    VisionBatchErrorPolicy,
)
from lightroom_tagger.core.exceptions import (
    ContextLengthError,
    InvalidRequestError,
    PayloadTooLargeError,
    RateLimitError,
)
from lightroom_tagger.core.fallback import FallbackDispatcher, LogCallback
from lightroom_tagger.core.provider_registry import ProviderRegistry
from lightroom_tagger.core.retry import CancelledRetryError
from lightroom_tagger.core.vision_client import compare_images, compare_images_batch


class VisionComparator:
    """Thin facade over :class:`FallbackDispatcher` for vision compare paths.

    Sequential pair compares and batch compares share one dispatcher entry point.
    A single candidate batch is handled as a batch of one — callers do not fork
    retry/fallback logic.
    """

    def __init__(
        self,
        registry: ProviderRegistry,
        *,
        log_callback: LogCallback = None,
        cancel_check: Callable[[], bool] | None = None,
        abort_tracker: ConsecutiveAbortTracker | None = None,
        sequential_policy: ContextLengthEscalationPolicy | None = None,
        batch_policy: VisionBatchErrorPolicy | None = None,
    ) -> None:
        self._registry = registry
        self._log_callback = log_callback
        self._cancel_check = cancel_check
        self._abort_tracker = abort_tracker
        self._sequential_policy = (
            sequential_policy if sequential_policy is not None else ContextLengthEscalationPolicy()
        )
        self._batch_policy = (
            batch_policy if batch_policy is not None else VisionBatchErrorPolicy()
        )

    def compare_pair(
        self,
        local_path: str,
        insta_path: str,
        provider_id: str,
        model: str,
    ) -> dict:
        """Compare one catalog/Instagram pair via ``compare_images``."""
        policy = self._sequential_policy
        dispatcher = FallbackDispatcher(self._registry, error_policy=policy)

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
                        log_callback=self._log_callback,
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
                    if self._log_callback and state.get("_log_message"):
                        self._log_callback("warning", state["_log_message"])
                    raise

            return _call

        try:
            result, actual_provider, actual_model = dispatcher.call_with_fallback(
                operation="compare",
                fn_factory=fn_factory,
                provider_id=provider_id,
                model=model,
                log_callback=self._log_callback,
                cancel_check=self._cancel_check,
                abort_tracker=self._abort_tracker,
            )
        except RateLimitError:
            return {"confidence": 0, "verdict": "RATE_LIMITED", "reasoning": ""}
        except InvalidRequestError:
            return {"confidence": 0, "verdict": "ERROR", "reasoning": ""}
        except CancelledRetryError:
            raise
        except Exception:
            if self._abort_tracker is not None:
                self._abort_tracker.record_transient_error()
            return {"confidence": 0, "verdict": "ERROR", "reasoning": ""}

        result["_provider"] = actual_provider
        result["_model"] = actual_model
        return result

    def compare_batch(
        self,
        reference_path: str,
        candidates: list[tuple[int, str]],
        provider_id: str,
        model: str,
        *,
        insta_filename: str = "",
        chunk_num: int = 1,
        num_chunks: int = 1,
    ) -> dict[int, float]:
        """Compare reference image against candidate paths (batch of one when ``len==1``)."""
        if not candidates:
            return {}

        policy = self._batch_policy
        dispatcher = FallbackDispatcher(self._registry, error_policy=policy)

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
                        log_callback=self._log_callback,
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
                    if self._log_callback and call_state.get("_log_message"):
                        prefix = f"[{insta_filename}] Batch {chunk_num}/{num_chunks}: "
                        self._log_callback("warning", prefix + call_state["_log_message"])

                    if isinstance(exc, PayloadTooLargeError):
                        if action == EscalationAction.SPLIT:
                            left_half, right_half = call_state["_split_halves"]
                            left = self.compare_batch(
                                reference_path,
                                left_half,
                                attempt_provider,
                                mdl,
                                insta_filename=insta_filename,
                                chunk_num=chunk_num,
                                num_chunks=num_chunks,
                            )
                            right = self.compare_batch(
                                reference_path,
                                right_half,
                                attempt_provider,
                                mdl,
                                insta_filename=insta_filename,
                                chunk_num=chunk_num,
                                num_chunks=num_chunks,
                            )
                            left.update(right)
                            return left
                        if action == EscalationAction.GIVE_UP:
                            return {}

                    if action == EscalationAction.GIVE_UP:
                        raise
                    if action == EscalationAction.RETRY:
                        return _call()
                    raise

            return _call

        result, _, _ = dispatcher.call_with_fallback(
            operation="compare_batch",
            fn_factory=fn_factory,
            provider_id=provider_id,
            model=model,
            log_callback=self._log_callback,
            cancel_check=self._cancel_check,
            abort_tracker=self._abort_tracker,
        )
        return result
