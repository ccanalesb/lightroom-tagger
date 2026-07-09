"""Pluggable error escalation policies for FallbackDispatcher."""

from __future__ import annotations

from enum import Enum
from typing import Any, Protocol, runtime_checkable

from lightroom_tagger.core.exceptions import ContextLengthError

MAX_TOKENS_ESCALATION = [256, 4096, 32768, 65536]


class EscalationAction(Enum):
    """What to do after an escalation-class error."""

    RETRY = "retry"
    GIVE_UP = "give_up"


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
