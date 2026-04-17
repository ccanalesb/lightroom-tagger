"""FallbackDispatcher — tries selected provider, cascades through fallback
order on retryable failures."""

from __future__ import annotations

from typing import Any, Callable

from lightroom_tagger.core.provider_errors import (
    NOT_RETRYABLE_ERRORS,
    RETRYABLE_ERRORS,
    ModelUnavailableError,
    ProviderError,
)
from lightroom_tagger.core.provider_registry import ProviderRegistry
from lightroom_tagger.core.retry import retry_with_backoff

LogCallback = Callable[[str, str], None] | None


class FallbackDispatcher:
    """Wraps provider calls with retry + automatic cascade."""

    def __init__(self, registry: ProviderRegistry):
        self._registry = registry

    def call_with_fallback(
        self,
        operation: str,
        fn_factory: Callable,
        provider_id: str,
        model: str,
        log_callback: LogCallback = None,
    ) -> tuple[Any, str, str]:
        """Execute *fn_factory(client, model)* with retry and fallback.

        Tries the requested model first, then all other models in the same
        provider (in configured order), then moves on to each fallback provider.

        Parameters
        ----------
        operation:
            Label for logging (``"compare"`` or ``"describe"``).
        fn_factory:
            ``(client, model) -> callable`` — returns a zero-arg callable that
            performs the actual API call.
        provider_id:
            Primary provider to try first.
        model:
            Model to use with the primary provider.
        log_callback:
            Optional ``(level, message)`` logger.

        Returns
        -------
        ``(result, actual_provider_id, actual_model)``
        """
        attempts = self._build_attempts(provider_id, model)
        if not attempts:
            raise ProviderError("No available providers for operation")
        last_error: ProviderError | None = None

        for index, (pid, mid) in enumerate(attempts):
            client = self._registry.get_client(pid)
            retry_config = self._registry.get_retry_config(pid)
            fn = fn_factory(client, mid)

            try:
                result = retry_with_backoff(fn, retry_config, log_callback=log_callback)
                return result, pid, mid
            except tuple(NOT_RETRYABLE_ERRORS | RETRYABLE_ERRORS) as exc:
                last_error = exc  # type: ignore[assignment]
                if log_callback:
                    remaining = attempts[index + 1:]
                    next_label = f"{remaining[0][0]}/{remaining[0][1]}" if remaining else "none"
                    log_callback(
                        "warning",
                        f"[{operation}] {pid}/{mid} failed ({type(exc).__name__}), "
                        f"fallback -> {next_label}",
                    )

        raise last_error  # type: ignore[misc]

    def _build_attempts(self, primary_id: str, primary_model: str) -> list[tuple[str, str]]:
        """Return ordered list of (provider_id, model_id) to try.

        Starts with all vision models in the primary provider (requested model
        first, then the rest in configured order), then the first vision model
        from each fallback provider in fallback order.
        """
        available_ids = {
            entry["id"]
            for entry in self._registry.list_providers()
            if entry.get("available")
        }

        attempts: list[tuple[str, str]] = []

        # Primary provider: requested model first, then remaining vision models
        if primary_id in available_ids:
            all_models = self._registry.list_models(primary_id)
            vision_models = [m["id"] for m in all_models if m.get("vision")]
            # Requested model goes first (even if not in the list)
            ordered = [primary_model] + [m for m in vision_models if m != primary_model]
            for mid in ordered:
                attempts.append((primary_id, mid))

        # Fallback providers: first vision model each
        for pid in self._registry.fallback_order:
            if pid == primary_id or pid not in available_ids:
                continue
            all_models = self._registry.list_models(pid)
            vision_models = [m["id"] for m in all_models if m.get("vision")]
            if vision_models:
                attempts.append((pid, vision_models[0]))

        return attempts
