import json
import os
from unittest.mock import patch, MagicMock

import pytest

from lightroom_tagger.core.provider_registry import ProviderRegistry


class TestListProviders:
    def test_should_load_all_providers_from_config(self):
        registry = ProviderRegistry()
        providers = registry.list_providers()
        ids = [p["id"] for p in providers]
        assert "ollama" in ids
        assert "nvidia_nim" in ids
        assert "openrouter" in ids

    def test_should_include_provider_name(self):
        registry = ProviderRegistry()
        providers = {p["id"]: p for p in registry.list_providers()}
        assert providers["ollama"]["name"] == "Ollama (Local)"
        assert providers["nvidia_nim"]["name"] == "NVIDIA NIM"

    def test_should_mark_provider_unavailable_without_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            registry = ProviderRegistry()
            providers = {p["id"]: p for p in registry.list_providers()}
            assert providers["nvidia_nim"]["available"] is False
            assert providers["openrouter"]["available"] is False

    def test_should_mark_provider_available_with_api_key(self):
        with patch.dict(os.environ, {"NVIDIA_NIM_API_KEY": "test-key"}, clear=False):
            registry = ProviderRegistry()
            providers = {p["id"]: p for p in registry.list_providers()}
            assert providers["nvidia_nim"]["available"] is True

    def test_should_always_mark_ollama_available(self):
        """Ollama uses a static api_key, no env var needed for auth."""
        with patch.dict(os.environ, {}, clear=True):
            registry = ProviderRegistry()
            providers = {p["id"]: p for p in registry.list_providers()}
            assert providers["ollama"]["available"] is True


class TestListModels:
    def test_should_list_static_models_for_nvidia(self):
        registry = ProviderRegistry()
        models = registry.list_models("nvidia_nim")
        model_ids = [m["id"] for m in models]
        assert "meta/llama-4-maverick-17b-128e-instruct" in model_ids
        assert "google/paligemma" in model_ids

    def test_should_list_static_models_for_openrouter(self):
        registry = ProviderRegistry()
        models = registry.list_models("openrouter")
        model_ids = [m["id"] for m in models]
        assert "anthropic/claude-sonnet-4" in model_ids
        assert "openai/gpt-4.1" in model_ids

    def test_should_include_model_source(self):
        registry = ProviderRegistry()
        models = registry.list_models("nvidia_nim")
        assert all(m["source"] == "config" for m in models)

    def test_should_raise_for_unknown_provider(self):
        registry = ProviderRegistry()
        with pytest.raises(KeyError):
            registry.list_models("nonexistent")

    def test_should_auto_discover_ollama_models(self):
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
            registry = ProviderRegistry()
            models = registry.list_models("ollama")
            model_ids = [m["id"] for m in models]
            assert "gemma3:27b" in model_ids
            assert "qwen3-vl:235b" in model_ids

    def test_should_mark_discovered_models_source(self):
        fake_tags = json.dumps({
            "models": [{"name": "llava:13b", "details": {}}]
        }).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = fake_tags
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            registry = ProviderRegistry()
            models = registry.list_models("ollama")
            discovered = [m for m in models if m["id"] == "llava:13b"]
            assert len(discovered) == 1
            assert discovered[0]["source"] == "discovered"

    def test_should_gracefully_handle_ollama_unreachable(self):
        with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
            registry = ProviderRegistry()
            models = registry.list_models("ollama")
            assert models == []


class TestGetClient:
    def test_should_return_openai_client_for_provider(self):
        with patch.dict(os.environ, {"NVIDIA_NIM_API_KEY": "test-key"}):
            registry = ProviderRegistry()
            client = registry.get_client("nvidia_nim")
            assert str(client.base_url).rstrip("/").endswith("integrate.api.nvidia.com/v1")

    def test_should_resolve_ollama_base_url_from_env(self):
        with patch.dict(os.environ, {"OLLAMA_HOST": "http://myhost:5000"}):
            registry = ProviderRegistry()
            client = registry.get_client("ollama")
            assert "myhost" in str(client.base_url)

    def test_should_not_append_v1_twice_when_ollama_host_already_has_v1(self):
        with patch.dict(os.environ, {"OLLAMA_HOST": "http://localhost:11434/v1"}):
            registry = ProviderRegistry()
            client = registry.get_client("ollama")
            url = str(client.base_url).rstrip("/")
            assert url.endswith("/v1")
            assert "/v1/v1" not in url

    def test_should_not_append_v1_twice_when_ollama_host_has_trailing_slash_and_v1(self):
        with patch.dict(os.environ, {"OLLAMA_HOST": "http://localhost:11434/v1/"}):
            registry = ProviderRegistry()
            client = registry.get_client("ollama")
            url = str(client.base_url).rstrip("/")
            assert url.endswith("/v1")
            assert "/v1/v1" not in url

    def test_should_use_default_ollama_url_when_env_unset(self):
        with patch.dict(os.environ, {}, clear=True):
            registry = ProviderRegistry()
            client = registry.get_client("ollama")
            assert "localhost:11434" in str(client.base_url)

    def test_should_include_extra_headers_for_openrouter(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            registry = ProviderRegistry()
            client = registry.get_client("openrouter")
            assert client._custom_headers.get("HTTP-Referer") == "lightroom-tagger"


class TestRetryConfig:
    def test_should_get_retry_config_with_provider_override(self):
        registry = ProviderRegistry()
        config = registry.get_retry_config("ollama")
        assert config["max_retries"] == 2
        assert config["backoff_seconds"] == [1, 3]

    def test_should_fall_back_to_global_defaults(self):
        registry = ProviderRegistry()
        config = registry.get_retry_config("nvidia_nim")
        assert config["max_retries"] == 3
        assert config["backoff_seconds"] == [2, 8, 32]
        assert config["respect_retry_after"] is True


class TestFallbackOrder:
    def test_should_return_fallback_order_from_config(self):
        registry = ProviderRegistry()
        assert registry.fallback_order == ["ollama", "nvidia_nim", "openrouter"]

    def test_should_return_defaults_from_config(self):
        registry = ProviderRegistry()
        assert registry.defaults["vision_comparison"]["provider"] == "ollama"
        assert registry.defaults["description"]["provider"] == "ollama"
