"""Vision comparison facade — engine dispatch + error policy + batch/sequential strategy."""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from typing import Any

from lightroom_tagger.core import cancel_scope
from lightroom_tagger.core.analyzer.compare import (
    build_compare_batch_op_spec,
    build_compare_op_spec,
)
from lightroom_tagger.core.error_policy import (
    ConsecutiveAbortTracker,
    ContextLengthEscalationPolicy,
    VisionBatchErrorPolicy,
)
from lightroom_tagger.core.exceptions import (
    InvalidRequestError,
    RateLimitError,
)
from lightroom_tagger.core.fallback import LogCallback
from lightroom_tagger.core.provider_registry import ProviderRegistry
from lightroom_tagger.core.retry import CancelledRetryError
from lightroom_tagger.core.vision_op import run_vision_op


class VisionComparator:
    """Thin facade over the vision-op engine for vision compare paths.

    Sequential pair compares and batch compares share one dispatch entry point.
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

    def _run_op(self, spec) -> tuple[Any, str, str]:
        ctx = (
            cancel_scope.install(self._cancel_check)
            if self._cancel_check is not None
            else contextlib.nullcontext()
        )
        with ctx:
            return run_vision_op(spec)

    def compare_pair(
        self,
        local_path: str,
        insta_path: str,
        provider_id: str,
        model: str,
    ) -> dict:
        """Compare one catalog/Instagram pair via ``compare_images``."""
        spec = build_compare_op_spec(
            local_path,
            insta_path,
            provider_id=provider_id,
            model=model,
            log_callback=self._log_callback,
            registry=self._registry,
            error_policy=self._sequential_policy,
            abort_tracker=self._abort_tracker,
        )
        try:
            result, actual_provider, actual_model = self._run_op(spec)
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

        def split_batch(
            left_half: list[tuple[int, str]],
            right_half: list[tuple[int, str]],
            attempt_provider: str,
            mdl: str,
        ) -> dict[int, float]:
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

        spec = build_compare_batch_op_spec(
            reference_path,
            candidates,
            provider_id=provider_id,
            model=model,
            log_callback=self._log_callback,
            registry=self._registry,
            error_policy=self._batch_policy,
            insta_filename=insta_filename,
            chunk_num=chunk_num,
            num_chunks=num_chunks,
            split_batch=split_batch,
            abort_tracker=self._abort_tracker,
        )
        result, _, _ = self._run_op(spec)
        return result
