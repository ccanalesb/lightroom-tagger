from lightroom_tagger.core.provider_errors import (
    ProviderError,
    RateLimitError,
    TimeoutError,
    ConnectionError,
    ModelUnavailableError,
    ContextLengthError,
    AuthenticationError,
    InvalidRequestError,
    RETRYABLE_ERRORS,
    NOT_RETRYABLE_ERRORS,
)

import pytest


class TestProviderErrorHierarchy:
    @pytest.mark.parametrize("cls", [
        RateLimitError, TimeoutError, ConnectionError,
        ModelUnavailableError, ContextLengthError,
        AuthenticationError, InvalidRequestError,
    ])
    def test_should_inherit_from_provider_error(self, cls):
        assert issubclass(cls, ProviderError)

    def test_should_include_retryable_errors(self):
        for cls in (RateLimitError, TimeoutError, ConnectionError,
                    ModelUnavailableError, ContextLengthError):
            assert cls in RETRYABLE_ERRORS

    def test_should_exclude_non_retryable_from_retryable_set(self):
        assert AuthenticationError not in RETRYABLE_ERRORS
        assert InvalidRequestError not in RETRYABLE_ERRORS

    def test_should_include_non_retryable_errors(self):
        assert AuthenticationError in NOT_RETRYABLE_ERRORS
        assert InvalidRequestError in NOT_RETRYABLE_ERRORS

    def test_should_exclude_retryable_from_non_retryable_set(self):
        assert RateLimitError not in NOT_RETRYABLE_ERRORS
        assert TimeoutError not in NOT_RETRYABLE_ERRORS

    def test_should_carry_provider_and_model_context(self):
        err = RateLimitError("too fast", provider="ollama", model="gemma3:27b")
        assert err.provider == "ollama"
        assert err.model == "gemma3:27b"
        assert "too fast" in str(err)

    def test_should_default_context_to_none(self):
        err = ProviderError("generic")
        assert err.provider is None
        assert err.model is None

    def test_should_carry_retry_after(self):
        err = RateLimitError("too fast", provider="openrouter", retry_after=30)
        assert err.retry_after == 30

    def test_should_default_retry_after_to_none(self):
        err = RateLimitError("too fast")
        assert err.retry_after is None
