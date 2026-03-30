"""Configurable retry with exponential backoff for provider calls."""

from __future__ import annotations

import time
from typing import Any, Callable, TypeVar

from lightroom_tagger.core.provider_errors import (
    NOT_RETRYABLE_ERRORS,
    RETRYABLE_ERRORS,
    ProviderError,
)

T = TypeVar("T")


def retry_with_backoff(
    fn: Callable[[], T],
    retry_config: dict[str, Any],
    log_callback: Callable[[str, str], None] | None = None,
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

    last_error: ProviderError | None = None

    for attempt in range(1 + max_retries):
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

            time.sleep(wait)

    raise last_error  # type: ignore[misc]
