"""Pluggable error escalation policies for FallbackDispatcher."""

from __future__ import annotations

from enum import Enum
from typing import Any, Protocol, runtime_checkable

from lightroom_tagger.core.exceptions import (
    ContextLengthError,
    InvalidRequestError,
    PayloadTooLargeError,
    RateLimitError,
)

MAX_TOKENS_ESCALATION = [256, 4096, 32768, 65536]
BATCH_MAX_TOKENS_ESCALATION = [4096, 32768, 65536]

RATE_LIMIT_ABORT_THRESHOLD = 3
FATAL_ABORT_THRESHOLD = 3


class ConsecutiveAbortTracker:
    """Session-level consecutive rate-limit / fatal counters for vision scoring.

    Owned by the dispatcher and consulted before each dispatch.  The scoring
    loop reads ``fatal_abort_reached`` to stop orchestrating candidates; it
    does not re-inspect ``RateLimitError`` / ``InvalidRequestError``.
    """

    def __init__(
        self,
        *,
        rate_limit_threshold: int = RATE_LIMIT_ABORT_THRESHOLD,
        fatal_threshold: int = FATAL_ABORT_THRESHOLD,
    ) -> None:
        self._rate_limit_threshold = rate_limit_threshold
        self._fatal_threshold = fatal_threshold
        self._consecutive_rate_limits = 0
        self._consecutive_fatal = 0

    @property
    def consecutive_rate_limits(self) -> int:
        return self._consecutive_rate_limits

    @property
    def consecutive_fatal(self) -> int:
        return self._consecutive_fatal

    @property
    def rate_limit_abort_reached(self) -> bool:
        return self._consecutive_rate_limits >= self._rate_limit_threshold

    @property
    def fatal_abort_reached(self) -> bool:
        return self._consecutive_fatal >= self._fatal_threshold

    def record_success(self) -> None:
        self._consecutive_rate_limits = 0

    def record_rate_limit(self) -> None:
        self._consecutive_rate_limits += 1
        self._consecutive_fatal = 0

    def record_fatal(self) -> None:
        self._consecutive_rate_limits = 0
        self._consecutive_fatal += 1

    def record_transient_error(self) -> None:
        self._consecutive_rate_limits = 0
        self._consecutive_fatal = 0

    def record_dispatch_outcome(self, exc: Exception | None) -> None:
        """Update counters after a dispatch completes (success or final failure)."""
        if exc is None:
            self.record_success()
        elif isinstance(exc, RateLimitError):
            self.record_rate_limit()
        elif isinstance(exc, InvalidRequestError):
            self.record_fatal()
        else:
            self.record_transient_error()


class EscalationAction(Enum):
    """What to do after an escalation-class error."""

    RETRY = "retry"
    GIVE_UP = "give_up"
    SPLIT = "split"


@runtime_checkable
class ErrorPolicy(Protocol):
    """Hook invoked on retryable escalation-class errors."""

    def on_escalation_error(
        self,
        exc: Exception,
        *,
        provider_id: str,
        model: str,
        operation: str,
        call_state: dict[str, Any],
    ) -> EscalationAction:
        """Decide retry-with-mutation vs give-up.

        Policies may mutate ``call_state`` (and their own instance state)
        before returning ``EscalationAction.RETRY``.
        """


class NoOpErrorPolicy:
    """Default policy — no mutation; normal retry / fallback behaviour."""

    def on_escalation_error(
        self,
        exc: Exception,
        *,
        provider_id: str,
        model: str,
        operation: str,
        call_state: dict[str, Any],
    ) -> EscalationAction:
        return EscalationAction.RETRY


class ContextLengthEscalationPolicy:
    """Vision compare max_tokens ladder with per-run cache and blacklist."""

    def __init__(self, ladder: list[int] | None = None) -> None:
        self._ladder = list(ladder if ladder is not None else MAX_TOKENS_ESCALATION)
        self._model_min_tokens: dict[str, int] = {}
        self._broken_provider_models: set[str] = set()

    @property
    def ladder(self) -> list[int]:
        return list(self._ladder)

    @property
    def model_min_tokens(self) -> dict[str, int]:
        return dict(self._model_min_tokens)

    @property
    def broken_provider_models(self) -> set[str]:
        return set(self._broken_provider_models)

    def provider_key(self, provider_id: str, model: str) -> str:
        return f"{provider_id}:{model}"

    def is_broken(self, provider_id: str, model: str) -> bool:
        return self.provider_key(provider_id, model) in self._broken_provider_models

    def starting_index(self, provider_id: str, model: str) -> int:
        key = self.provider_key(provider_id, model)
        cached_min = self._model_min_tokens.get(key, 0)
        for i, val in enumerate(self._ladder):
            if val >= cached_min:
                return i
        return 0

    def max_tokens_at(self, index: int) -> int:
        return self._ladder[index]

    def on_escalation_error(
        self,
        exc: Exception,
        *,
        provider_id: str,
        model: str,
        operation: str,
        call_state: dict[str, Any],
    ) -> EscalationAction:
        if not isinstance(exc, ContextLengthError):
            return EscalationAction.RETRY

        key = self.provider_key(provider_id, model)
        idx = int(call_state.get("token_index", 0))

        if idx < len(self._ladder) - 1:
            new_idx = idx + 1
            next_val = self._ladder[new_idx]
            self._model_min_tokens[key] = next_val
            call_state["token_index"] = new_idx
            call_state["_log_message"] = (
                f"[{operation}] Escalating max_tokens to {next_val} for {model}"
            )
            return EscalationAction.RETRY

        self._broken_provider_models.add(key)
        call_state["_log_message"] = (
            f"[{operation}] max_tokens exhausted at {self._ladder[idx]} "
            f"for {model}, blacklisting for session"
        )
        return EscalationAction.GIVE_UP


class VisionBatchErrorPolicy:
    """Batch vision: context-length ladder plus payload split on 413."""

    def __init__(
        self,
        token_ladder: list[int] | None = None,
        token_policy: ContextLengthEscalationPolicy | None = None,
    ) -> None:
        ladder = token_ladder if token_ladder is not None else BATCH_MAX_TOKENS_ESCALATION
        self._token_policy = (
            token_policy
            if token_policy is not None
            else ContextLengthEscalationPolicy(ladder=ladder)
        )

    @property
    def ladder(self) -> list[int]:
        return self._token_policy.ladder

    @property
    def model_min_tokens(self) -> dict[str, int]:
        return self._token_policy.model_min_tokens

    @property
    def broken_provider_models(self) -> set[str]:
        return self._token_policy.broken_provider_models

    def provider_key(self, provider_id: str, model: str) -> str:
        return self._token_policy.provider_key(provider_id, model)

    def is_broken(self, provider_id: str, model: str) -> bool:
        return self._token_policy.is_broken(provider_id, model)

    def starting_index(self, provider_id: str, model: str) -> int:
        return self._token_policy.starting_index(provider_id, model)

    def max_tokens_at(self, index: int) -> int:
        return self._token_policy.max_tokens_at(index)

    def on_escalation_error(
        self,
        exc: Exception,
        *,
        provider_id: str,
        model: str,
        operation: str,
        call_state: dict[str, Any],
    ) -> EscalationAction:
        if isinstance(exc, PayloadTooLargeError):
            candidates = call_state.get("candidates") or []
            if len(candidates) <= 1:
                call_state["_log_message"] = (
                    f"[{operation}] single-item chunk still too large, skipping"
                )
                return EscalationAction.GIVE_UP

            half = len(candidates) // 2
            call_state["_split_halves"] = (candidates[:half], candidates[half:])
            call_state["_log_message"] = (
                f"[{operation}] payload too large, splitting "
                f"{len(candidates)} -> {half}+{len(candidates) - half}"
            )
            return EscalationAction.SPLIT

        return self._token_policy.on_escalation_error(
            exc,
            provider_id=provider_id,
            model=model,
            operation=operation,
            call_state=call_state,
        )
