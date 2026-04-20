"""Configurable retry with exponential backoff for provider calls."""

from __future__ import annotations

import time
from typing import Any, Callable, TypeVar

from lightroom_tagger.core import cancel_scope
from lightroom_tagger.core.provider_errors import (
    NOT_RETRYABLE_ERRORS,
    RETRYABLE_ERRORS,
    ProviderError,
)

T = TypeVar("T")


class CancelledRetryError(Exception):
    """Raised by :func:`retry_with_backoff` when ``cancel_check`` returns truthy
    during a backoff sleep. Callers should treat it as an orderly cancel rather
    than a provider failure (no retry, no fallback).
    """


def _interruptible_sleep(
    total_seconds: float,
    cancel_check: Callable[[], bool] | None,
    step: float = 0.5,
) -> None:
    """Sleep ``total_seconds`` in small slices, aborting early on cancel.

    Without this, ``time.sleep(32)`` inside a retry backoff holds the worker
    for the full duration regardless of ``runner.is_cancelled`` — that is the
    exact failure mode that left job ``b141dbcc`` CPU-pegged for 9 minutes
    after a cancel.
    """
    if cancel_check is None:
        time.sleep(total_seconds)
        return
    remaining = max(0.0, float(total_seconds))
    while remaining > 0:
        if cancel_check():
            raise CancelledRetryError("cancel requested during backoff")
        slice_ = step if remaining > step else remaining
        time.sleep(slice_)
        remaining -= slice_


def retry_with_backoff(
    fn: Callable[[], T],
    retry_config: dict[str, Any],
    log_callback: Callable[[str, str], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> T:
    """Call *fn* with retry on retryable ``ProviderError`` subclasses.

    Parameters
    ----------
    fn:
        Zero-arg callable (bind args with ``functools.partial`` or lambda).
    retry_config:
        ``{"max_retries": int, "backoff_seconds": list[float], "respect_retry_after": bool}``
    log_callback:
        Optional ``(level, message)`` logger.

    Returns the result of *fn* on success.
    Raises the last ``ProviderError`` if all retries are exhausted.
    Raises immediately for non-retryable errors.
    """
    max_retries: int = retry_config.get("max_retries", 3)
    backoff: list[float] = retry_config.get("backoff_seconds", [2, 8, 32])
    respect_retry_after: bool = retry_config.get("respect_retry_after", True)

    # Only opt into the thread-local scope when the current thread has one
    # installed. Otherwise we keep the pre-cancel behaviour exactly —
    # ``time.sleep(wait)`` called once per attempt — so existing tests and
    # timing assumptions stay untouched.
    if cancel_check is None and cancel_scope.has_active_scope():
        cancel_check = cancel_scope.is_cancelled

    last_error: ProviderError | None = None

    for attempt in range(1 + max_retries):
        # Short-circuit before each attempt so a cancel requested while the
        # previous call was in-flight (or during the next backoff) prevents
        # both another call and another sleep.
        if cancel_check is not None and cancel_check():
            raise CancelledRetryError("cancel requested before retry attempt")

        try:
            return fn()
        except tuple(NOT_RETRYABLE_ERRORS) as exc:
            raise
        except tuple(RETRYABLE_ERRORS) as exc:
            last_error = exc  # type: ignore[assignment]

            if attempt >= max_retries:
                break

            wait = backoff[attempt] if attempt < len(backoff) else backoff[-1]

            if (
                respect_retry_after
                and isinstance(exc, ProviderError)
                and getattr(exc, "retry_after", None) is not None
            ):
                wait = exc.retry_after  # type: ignore[assignment]

            if log_callback:
                log_callback(
                    "warning",
                    f"Retry {attempt + 1}/{max_retries} after {type(exc).__name__}: "
                    f"{exc} — waiting {wait}s",
                )

            _interruptible_sleep(wait, cancel_check)

    raise last_error  # type: ignore[misc]
