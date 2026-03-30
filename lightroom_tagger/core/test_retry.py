from unittest.mock import MagicMock, patch

import pytest

from lightroom_tagger.core.provider_errors import (
    AuthenticationError,
    ConnectionError,
    InvalidRequestError,
    RateLimitError,
    TimeoutError,
)
from lightroom_tagger.core.retry import retry_with_backoff

DEFAULT_CONFIG = {"max_retries": 3, "backoff_seconds": [1, 2, 4], "respect_retry_after": True}


class TestRetrySuccess:
    def test_should_return_result_on_first_success(self):
        fn = MagicMock(return_value="ok")
        result = retry_with_backoff(fn, DEFAULT_CONFIG)
        assert result == "ok"
        assert fn.call_count == 1

    @patch("time.sleep")
    def test_should_succeed_after_transient_failure(self, mock_sleep):
        fn = MagicMock(side_effect=[RateLimitError("429"), "ok"])
        result = retry_with_backoff(fn, DEFAULT_CONFIG)
        assert result == "ok"
        assert fn.call_count == 2
        mock_sleep.assert_called_once_with(1)

    @patch("time.sleep")
    def test_should_succeed_after_multiple_transient_failures(self, mock_sleep):
        fn = MagicMock(side_effect=[
            TimeoutError("timeout"),
            ConnectionError("conn"),
            "ok",
        ])
        result = retry_with_backoff(fn, DEFAULT_CONFIG)
        assert result == "ok"
        assert fn.call_count == 3


class TestRetryExhaustion:
    @patch("time.sleep")
    def test_should_raise_after_all_retries_exhausted(self, mock_sleep):
        fn = MagicMock(side_effect=RateLimitError("429"))
        with pytest.raises(RateLimitError):
            retry_with_backoff(fn, DEFAULT_CONFIG)
        assert fn.call_count == 4  # 1 initial + 3 retries

    @patch("time.sleep")
    def test_should_use_configured_backoff_times(self, mock_sleep):
        fn = MagicMock(side_effect=RateLimitError("429"))
        with pytest.raises(RateLimitError):
            retry_with_backoff(fn, DEFAULT_CONFIG)
        sleep_times = [c.args[0] for c in mock_sleep.call_args_list]
        assert sleep_times == [1, 2, 4]


class TestNonRetryable:
    def test_should_raise_immediately_on_auth_error(self):
        fn = MagicMock(side_effect=AuthenticationError("401"))
        with pytest.raises(AuthenticationError):
            retry_with_backoff(fn, DEFAULT_CONFIG)
        assert fn.call_count == 1

    def test_should_raise_immediately_on_invalid_request(self):
        fn = MagicMock(side_effect=InvalidRequestError("400"))
        with pytest.raises(InvalidRequestError):
            retry_with_backoff(fn, DEFAULT_CONFIG)
        assert fn.call_count == 1


class TestRetryAfterHeader:
    @patch("time.sleep")
    def test_should_respect_retry_after_when_configured(self, mock_sleep):
        err = RateLimitError("429", retry_after=30)
        fn = MagicMock(side_effect=[err, "ok"])
        result = retry_with_backoff(fn, DEFAULT_CONFIG)
        assert result == "ok"
        mock_sleep.assert_called_once_with(30)

    @patch("time.sleep")
    def test_should_ignore_retry_after_when_disabled(self, mock_sleep):
        err = RateLimitError("429", retry_after=30)
        config = {**DEFAULT_CONFIG, "respect_retry_after": False}
        fn = MagicMock(side_effect=[err, "ok"])
        result = retry_with_backoff(fn, config)
        assert result == "ok"
        mock_sleep.assert_called_once_with(1)


class TestLogCallback:
    @patch("time.sleep")
    def test_should_log_retries(self, mock_sleep):
        fn = MagicMock(side_effect=[RateLimitError("429"), "ok"])
        log = MagicMock()
        retry_with_backoff(fn, DEFAULT_CONFIG, log_callback=log)
        log.assert_called()
        log_msg = log.call_args_list[0].args[1]
        assert "retry" in log_msg.lower() or "Retry" in log_msg
