"""Exception hierarchy for vision provider errors.

All errors inherit from ProviderError. RETRYABLE_ERRORS are retried with
backoff then cascaded to fallback providers. NOT_RETRYABLE_ERRORS are surfaced
immediately — no retry, no fallback.
"""


class ProviderError(Exception):
    """Base for all provider errors."""

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        model: str | None = None,
        retry_after: float | None = None,
    ):
        super().__init__(message)
        self.provider = provider
        self.model = model
        self.retry_after = retry_after


class RateLimitError(ProviderError):
    """429 — quota exceeded."""


class TimeoutError(ProviderError):
    """Request timed out."""


class ConnectionError(ProviderError):
    """Can't reach provider (Ollama not running, DNS failure)."""


class ModelUnavailableError(ProviderError):
    """503 — server overloaded or model not loaded."""


class ContextLengthError(ProviderError):
    """Token/context limit exceeded — retry with smaller image or higher max_tokens."""


class PayloadTooLargeError(ProviderError):
    """413 — request body exceeds provider limit (e.g. too many images in batch)."""


class AuthenticationError(ProviderError):
    """401/403 — bad or missing API key."""


class InvalidRequestError(ProviderError):
    """400 — bad model name, unsupported input format."""


RETRYABLE_ERRORS: frozenset[type[ProviderError]] = frozenset({
    RateLimitError,
    TimeoutError,
    ConnectionError,
    ModelUnavailableError,
    ContextLengthError,
    PayloadTooLargeError,
})

NOT_RETRYABLE_ERRORS: frozenset[type[ProviderError]] = frozenset({
    AuthenticationError,
    InvalidRequestError,
})
