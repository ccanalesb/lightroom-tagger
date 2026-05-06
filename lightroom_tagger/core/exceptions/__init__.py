"""Shared domain exceptions — canonical import surface (ADR-0004)."""

from .provider_errors import (
    AuthenticationError,
    ConnectionError,
    ContextLengthError,
    InvalidRequestError,
    ModelUnavailableError,
    NOT_RETRYABLE_ERRORS,
    PayloadTooLargeError,
    ProviderError,
    RateLimitError,
    RETRYABLE_ERRORS,
    TimeoutError,
)

__all__ = (
    "AuthenticationError",
    "ConnectionError",
    "ContextLengthError",
    "InvalidRequestError",
    "ModelUnavailableError",
    "NOT_RETRYABLE_ERRORS",
    "PayloadTooLargeError",
    "ProviderError",
    "RateLimitError",
    "RETRYABLE_ERRORS",
    "TimeoutError",
)
