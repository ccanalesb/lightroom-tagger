"""FallbackDispatcher — tries selected provider, cascades through fallback
order on retryable failures."""

from __future__ import annotations

from typing import Any, Callable

from lightroom_tagger.core.cancel_scope import resolve_cancel_check
from lightroom_tagger.core.error_policy import (
    ConsecutiveAbortTracker,
    ErrorPolicy,
    NoOpErrorPolicy,
)
from lightroom_tagger.core.exceptions import (
    RETRYABLE_ERRORS,
    ConnectionError,
    InvalidRequestError,
    ModelUnavailableError,
    ProviderError,
    RateLimitError,
)
from lightroom_tagger.core.provider_registry import ProviderRegistry
from lightroom_tagger.core.retry import CancelledRetryError, retry_with_backoff

LogCallback = Callable[[str, str], None] | None


def _log_cascade(
    log_callback: LogCallback,
    operation: str,
    pid: str,
    mid: str,
    exc: Exception,
    attempts: list[tuple[str, str]],
    index: int,
) -> None:
    """Emit a single, uniform log line when a provider attempt falls through."""
    if not log_callback:
        return
    remaining = attempts[index + 1:]
    next_label = f"{remaining[0][0]}/{remaining[0][1]}" if remaining else "none"
    log_callback(
        "warning",
        f"[{operation}] {pid}/{mid} failed ({type(exc).__name__}), "
        f"fallback -> {next_label}",
    )


class FallbackDispatcher:
    """Wraps provider calls with retry + automatic cascade."""

    def __init__(
        self,
        registry: ProviderRegistry,
        error_policy: ErrorPolicy | None = None,
    ):
        self._registry = registry
        self._error_policy = (
            error_policy if error_policy is not None else NoOpErrorPolicy()
        )

    @property
    def error_policy(self) -> ErrorPolicy:
        return self._error_policy

    def call_with_fallback(
        self,
        operation: str,
        fn_factory: Callable,
        provider_id: str,
        model: str,
        log_callback: LogCallback = None,
        cancel_check: Callable[[], bool] | None = None,
        abort_tracker: ConsecutiveAbortTracker | None = None,
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
        attempts, empty_fallbacks = self._build_attempts(provider_id, model)
        if not attempts:
            raise ProviderError("No available providers for operation")
        last_error: ProviderError | None = None

        cancel_check = resolve_cancel_check(cancel_check)

        for index, (pid, mid) in enumerate(attempts):
            # Cancel between providers: without this, a cancel during the
            # primary provider's retries would still trigger the full
            # fallback cascade (another 3-4 × 42s of work) before the
            # worker checked in again.
            if cancel_check is not None and cancel_check():
                raise CancelledRetryError("cancel requested before fallback attempt")

            if abort_tracker is not None and abort_tracker.rate_limit_abort_reached:
                raise RateLimitError("consecutive rate-limit abort threshold reached")

            client = self._registry.get_client(pid)
            retry_config = self._registry.get_retry_config(pid)
            fn = fn_factory(client, mid)

            try:
                result = retry_with_backoff(
                    fn,
                    retry_config,
                    log_callback=log_callback,
                    cancel_check=cancel_check,
                )
                if abort_tracker is not None:
                    abort_tracker.record_success()
                return result, pid, mid
            except CancelledRetryError:
                # Surface cancellation directly — do NOT fall through to
                # the next provider. ``raise`` keeps the original frame.
                raise
            except InvalidRequestError as exc:
                if abort_tracker is not None:
                    abort_tracker.record_fatal()
                raise
            except tuple(RETRYABLE_ERRORS) as exc:
                last_error = exc  # type: ignore[assignment]
                _log_cascade(log_callback, operation, pid, mid, exc, attempts, index)
            except ConnectionError as exc:
                # ``ConnectionError`` is NOT_RETRYABLE (see commit 5b0763a —
                # "connection refused / DNS failure is permanent for that
                # provider") but it IS a provider-specific failure that
                # should cascade to the next available provider instead of
                # surfacing to the caller. Other NOT_RETRYABLE errors
                # (``AuthenticationError``, ``InvalidRequestError``) are
                # global and propagate below.
                last_error = exc
                _log_cascade(log_callback, operation, pid, mid, exc, attempts, index)

        # All attempts exhausted. If any advertised fallback provider had no
        # vision models we surface that as the *actionable* error — the
        # caller can configure or enable a model — instead of whatever
        # transient error the last working provider happened to throw.
        if empty_fallbacks:
            raise ModelUnavailableError(
                f"No models available for fallback provider(s): "
                f"{', '.join(empty_fallbacks)}"
            )
        if abort_tracker is not None and last_error is not None:
            abort_tracker.record_dispatch_outcome(last_error)
        raise last_error  # type: ignore[misc]

    def _build_attempts(
        self, primary_id: str, primary_model: str
    ) -> tuple[list[tuple[str, str]], list[str]]:
        """Return ordered list of (provider_id, model_id) to try.

        Starts with all vision models in the primary provider (requested model
        first, then the rest in configured order), then the first vision model
        from each fallback provider in fallback order.

        Also returns the list of fallback provider IDs that advertised no
        vision models — used by ``call_with_fallback`` to surface a
        ``ModelUnavailableError`` with an actionable message when the
        cascade exhausts.
        """
        available_ids = {
            entry["id"]
            for entry in self._registry.list_providers()
            if entry.get("available")
        }

        attempts: list[tuple[str, str]] = []
        empty_fallbacks: list[str] = []

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
            else:
                empty_fallbacks.append(pid)

        return attempts, empty_fallbacks
