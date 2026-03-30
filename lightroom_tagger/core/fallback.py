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
        primary_id = provider_id
        order = self._build_order(primary_id)
        if not order:
            raise ProviderError("No available providers for operation")
        last_error: ProviderError | None = None

        for index, provider_id in enumerate(order):
            client = self._registry.get_client(provider_id)
            retry_config = self._registry.get_retry_config(provider_id)

            current_model = model if provider_id == primary_id else self._pick_fallback_model(provider_id)

            fn = fn_factory(client, current_model)

            try:
                result = retry_with_backoff(fn, retry_config, log_callback=log_callback)
                return result, provider_id, current_model
            except tuple(NOT_RETRYABLE_ERRORS):
                raise
            except tuple(RETRYABLE_ERRORS) as exc:
                last_error = exc  # type: ignore[assignment]
                if log_callback:
                    remaining = order[index + 1:]
                    next_label = remaining[0] if remaining else "none"
                    log_callback(
                        "warning",
                        f"[{operation}] {provider_id} failed ({type(exc).__name__}), "
                        f"fallback -> {next_label}",
                    )

        raise last_error  # type: ignore[misc]

    def _build_order(self, primary: str) -> list[str]:
        """Return [primary] + remaining fallback order (excluding primary).

        Only includes providers that are available (e.g. API key present).
        """
        available_ids = {
            entry["id"]
            for entry in self._registry.list_providers()
            if entry.get("available")
        }
        full_order = [primary] + [
            provider_id
            for provider_id in self._registry.fallback_order
            if provider_id != primary
        ]
        return [provider_id for provider_id in full_order if provider_id in available_ids]

    def _pick_fallback_model(self, provider_id: str) -> str:
        """Pick the first vision model for a fallback provider."""
        models = self._registry.list_models(provider_id)
        if not models:
            raise ModelUnavailableError(
                f"No models available for fallback provider '{provider_id}'.",
                provider=provider_id,
            )
        vision_models = [m for m in models if m.get("vision")]
        return vision_models[0]["id"] if vision_models else models[0]["id"]
