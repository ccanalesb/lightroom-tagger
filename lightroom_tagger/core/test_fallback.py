from unittest.mock import MagicMock, patch

import pytest

from lightroom_tagger.core.provider_errors import (
    AuthenticationError,
    ConnectionError,
    RateLimitError,
)
from lightroom_tagger.core.fallback import FallbackDispatcher


def _mock_registry(available_providers=None):
    """Build a mock ProviderRegistry."""
    if available_providers is None:
        available_providers = ["ollama", "nvidia_nim", "openrouter"]

    registry = MagicMock()
    registry.fallback_order = available_providers
    registry.get_client.return_value = MagicMock()
    registry.get_retry_config.return_value = {
        "max_retries": 0,
        "backoff_seconds": [],
        "respect_retry_after": False,
    }
    registry.list_models.return_value = [{"id": "test-model", "vision": True, "source": "config"}]
    return registry


class TestPrimarySuccess:
    def test_should_return_result_from_primary_provider(self):
        registry = _mock_registry()
        dispatcher = FallbackDispatcher(registry)

        result, provider, model = dispatcher.call_with_fallback(
            operation="compare",
            fn_factory=lambda client, model: lambda: {"verdict": "SAME"},
            provider_id="ollama",
            model="gemma3:27b",
        )
        assert result == {"verdict": "SAME"}
        assert provider == "ollama"
        assert model == "gemma3:27b"

    def test_should_not_try_fallback_on_success(self):
        registry = _mock_registry()
        dispatcher = FallbackDispatcher(registry)

        dispatcher.call_with_fallback(
            operation="compare",
            fn_factory=lambda client, model: lambda: "ok",
            provider_id="ollama",
            model="gemma3:27b",
        )
        registry.get_client.assert_called_once_with("ollama")


class TestFallbackCascade:
    @patch("time.sleep")
    def test_should_cascade_to_next_provider_on_failure(self, mock_sleep):
        registry = _mock_registry()
        dispatcher = FallbackDispatcher(registry)

        call_count = {"n": 0}

        def fn_factory(client, model):
            def fn():
                call_count["n"] += 1
                if call_count["n"] == 1:
                    raise RateLimitError("429")
                return "from_fallback"
            return fn

        result, provider, model = dispatcher.call_with_fallback(
            operation="compare",
            fn_factory=fn_factory,
            provider_id="ollama",
            model="gemma3:27b",
        )
        assert result == "from_fallback"
        assert provider == "nvidia_nim"

    @patch("time.sleep")
    def test_should_try_all_providers_before_raising(self, mock_sleep):
        registry = _mock_registry()
        dispatcher = FallbackDispatcher(registry)

        def fn_factory(client, model):
            return lambda: (_ for _ in ()).throw(ConnectionError("down"))

        with pytest.raises(ConnectionError):
            dispatcher.call_with_fallback(
                operation="compare",
                fn_factory=fn_factory,
                provider_id="ollama",
                model="gemma3:27b",
            )
        assert registry.get_client.call_count == 3

    @patch("time.sleep")
    def test_should_use_default_model_for_fallback_providers(self, mock_sleep):
        registry = _mock_registry()
        dispatcher = FallbackDispatcher(registry)

        models_used = []

        def fn_factory(client, model):
            models_used.append(model)
            def fn():
                if len(models_used) == 1:
                    raise RateLimitError("429")
                return "ok"
            return fn

        dispatcher.call_with_fallback(
            operation="compare",
            fn_factory=fn_factory,
            provider_id="ollama",
            model="gemma3:27b",
        )
        assert models_used[0] == "gemma3:27b"
        assert models_used[1] == "test-model"


class TestNonRetryableSkipsFallback:
    def test_should_raise_immediately_on_auth_error(self):
        registry = _mock_registry()
        dispatcher = FallbackDispatcher(registry)

        def fn_factory(client, model):
            return lambda: (_ for _ in ()).throw(AuthenticationError("bad key"))

        with pytest.raises(AuthenticationError):
            dispatcher.call_with_fallback(
                operation="compare",
                fn_factory=fn_factory,
                provider_id="ollama",
                model="gemma3:27b",
            )
        registry.get_client.assert_called_once()


class TestLogCallback:
    @patch("time.sleep")
    def test_should_log_fallback_transitions(self, mock_sleep):
        registry = _mock_registry()
        dispatcher = FallbackDispatcher(registry)
        log = MagicMock()

        call_count = {"n": 0}
        def fn_factory(client, model):
            def fn():
                call_count["n"] += 1
                if call_count["n"] == 1:
                    raise RateLimitError("429")
                return "ok"
            return fn

        dispatcher.call_with_fallback(
            operation="compare",
            fn_factory=fn_factory,
            provider_id="ollama",
            model="gemma3:27b",
            log_callback=log,
        )
        log_messages = " ".join(str(c) for c in log.call_args_list)
        assert "fallback" in log_messages.lower() or "nvidia_nim" in log_messages
