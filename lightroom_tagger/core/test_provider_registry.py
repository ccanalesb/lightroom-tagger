import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from lightroom_tagger.core.provider_registry import ProviderRegistry

# Pin these tests to the checked-in example config. The real
# ``providers.json`` is a user-editable file and tracks whichever models the
# developer currently has configured — tying the registry test suite to it
# makes these tests flaky whenever someone adds or removes a provider.
# ``providers.example.json`` is the shipped default and is stable.
_EXAMPLE_CONFIG = Path(__file__).parent / "providers.example.json"


@pytest.fixture
def registry_factory():
    """Return a callable that builds a ``ProviderRegistry`` from the shipped
    example config. Tests that used to call ``ProviderRegistry()`` should
    use ``registry_factory()`` instead."""
    def _make():
        return ProviderRegistry(config_path=_EXAMPLE_CONFIG)
    return _make


class TestListProviders:
    def test_should_load_all_providers_from_config(self, registry_factory):
        registry = registry_factory()
        providers = registry.list_providers()
        ids = [p["id"] for p in providers]
        assert "ollama" in ids
        assert "nvidia_nim" in ids
        assert "openrouter" in ids

    def test_should_include_provider_name(self, registry_factory):
        registry = registry_factory()
        providers = {p["id"]: p for p in registry.list_providers()}
        assert providers["ollama"]["name"] == "Ollama (Local)"
        assert providers["nvidia_nim"]["name"] == "NVIDIA NIM"

    def test_should_mark_provider_unavailable_without_api_key(self, registry_factory):
        with patch.dict(os.environ, {}, clear=True):
            registry = registry_factory()
            providers = {p["id"]: p for p in registry.list_providers()}
            assert providers["nvidia_nim"]["available"] is False
            assert providers["openrouter"]["available"] is False

    def test_should_mark_provider_available_with_api_key(self, registry_factory):
        with patch.dict(os.environ, {"NVIDIA_NIM_API_KEY": "test-key"}, clear=False):
            registry = registry_factory()
            providers = {p["id"]: p for p in registry.list_providers()}
            assert providers["nvidia_nim"]["available"] is True

    def test_should_always_mark_ollama_available(self, registry_factory):
        """Ollama uses a static api_key, no env var needed for auth."""
        with patch.dict(os.environ, {}, clear=True):
            registry = registry_factory()
            providers = {p["id"]: p for p in registry.list_providers()}
            assert providers["ollama"]["available"] is True


class TestListModels:
    def test_should_list_static_models_for_nvidia(self, registry_factory):
        registry = registry_factory()
        models = registry.list_models("nvidia_nim")
        model_ids = [m["id"] for m in models]
        # These two models are guaranteed to be in providers.example.json.
        # If the example config legitimately drops one, update the
        # fixture — do not switch back to the user-editable providers.json.
        assert "meta/llama-4-maverick-17b-128e-instruct" in model_ids
        assert "microsoft/phi-4-multimodal-instruct" in model_ids

    def test_should_list_static_models_for_openrouter(self, registry_factory):
        registry = registry_factory()
        models = registry.list_models("openrouter")
        model_ids = [m["id"] for m in models]
        assert "google/gemini-2.5-flash-lite" in model_ids
        assert "openai/gpt-4.1-nano" in model_ids

    def test_should_include_model_source(self, registry_factory):
        registry = registry_factory()
        models = registry.list_models("nvidia_nim")
        assert all(m["source"] == "config" for m in models)

    def test_should_raise_for_unknown_provider(self, registry_factory):
        registry = registry_factory()
        with pytest.raises(KeyError):
            registry.list_models("nonexistent")

    def test_should_auto_discover_ollama_models(self, registry_factory):
        fake_tags = json.dumps({
            "models": [
                {"name": "gemma3:27b", "details": {"family": "gemma"}},
                {"name": "qwen3-vl:235b", "details": {"family": "qwen"}},
            ]
        }).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = fake_tags
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            registry = registry_factory()
            models = registry.list_models("ollama")
            model_ids = [m["id"] for m in models]
            assert "gemma3:27b" in model_ids
            assert "qwen3-vl:235b" in model_ids

    def test_should_mark_discovered_models_source(self, registry_factory):
        fake_tags = json.dumps({
            "models": [{"name": "llava:13b", "details": {}}]
        }).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = fake_tags
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            registry = registry_factory()
            models = registry.list_models("ollama")
            discovered = [m for m in models if m["id"] == "llava:13b"]
            assert len(discovered) == 1
            assert discovered[0]["source"] == "discovered"

    def test_should_gracefully_handle_ollama_unreachable(self, registry_factory):
        with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
            registry = registry_factory()
            models = registry.list_models("ollama")
            assert models == []


class TestGetClient:
    def test_should_return_openai_client_for_provider(self, registry_factory):
        with patch.dict(os.environ, {"NVIDIA_NIM_API_KEY": "test-key"}):
            registry = registry_factory()
            client = registry.get_client("nvidia_nim")
            assert str(client.base_url).rstrip("/").endswith("integrate.api.nvidia.com/v1")

    def test_should_resolve_ollama_base_url_from_env(self, registry_factory):
        with patch.dict(os.environ, {"OLLAMA_HOST": "http://myhost:5000"}):
            registry = registry_factory()
            client = registry.get_client("ollama")
            assert "myhost" in str(client.base_url)

    def test_should_not_append_v1_twice_when_ollama_host_already_has_v1(self, registry_factory):
        with patch.dict(os.environ, {"OLLAMA_HOST": "http://localhost:11434/v1"}):
            registry = registry_factory()
            client = registry.get_client("ollama")
            url = str(client.base_url).rstrip("/")
            assert url.endswith("/v1")
            assert "/v1/v1" not in url

    def test_should_not_append_v1_twice_when_ollama_host_has_trailing_slash_and_v1(self, registry_factory):
        with patch.dict(os.environ, {"OLLAMA_HOST": "http://localhost:11434/v1/"}):
            registry = registry_factory()
            client = registry.get_client("ollama")
            url = str(client.base_url).rstrip("/")
            assert url.endswith("/v1")
            assert "/v1/v1" not in url

    def test_should_use_default_ollama_url_when_env_unset(self, registry_factory):
        with patch.dict(os.environ, {}, clear=True):
            registry = registry_factory()
            client = registry.get_client("ollama")
            assert "localhost:11434" in str(client.base_url)

    def test_should_include_extra_headers_for_openrouter(self, registry_factory):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            registry = registry_factory()
            client = registry.get_client("openrouter")
            assert client._custom_headers.get("HTTP-Referer") == "lightroom-tagger"


class TestRetryConfig:
    def test_should_get_retry_config_with_provider_override(self, registry_factory):
        registry = registry_factory()
        config = registry.get_retry_config("ollama")
        assert config["max_retries"] == 2
        assert config["backoff_seconds"] == [1, 3]

    def test_should_fall_back_to_global_defaults(self, registry_factory):
        registry = registry_factory()
        config = registry.get_retry_config("nvidia_nim")
        assert config["max_retries"] == 3
        assert config["backoff_seconds"] == [2, 8, 32]
        assert config["respect_retry_after"] is True


class TestFallbackOrder:
    def test_should_return_fallback_order_from_config(self, registry_factory):
        registry = registry_factory()
        assert registry.fallback_order == ["ollama", "nvidia_nim", "openrouter"]

    def test_should_return_defaults_from_config(self, registry_factory):
        registry = registry_factory()
        assert registry.defaults["vision_comparison"]["provider"] == "ollama"
        assert registry.defaults["description"]["provider"] == "ollama"
