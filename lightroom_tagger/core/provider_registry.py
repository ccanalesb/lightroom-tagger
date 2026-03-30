"""Provider registry — loads providers.json, auto-discovers Ollama models,
returns configured openai.OpenAI clients."""

from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path
from typing import Any

import openai

_CONFIG_PATH = Path(__file__).parent / "providers.json"


class ProviderRegistry:
    """Central registry of vision/LLM providers and their models."""

    def __init__(self, config_path: Path = _CONFIG_PATH):
        with open(config_path) as f:
            self._config: dict[str, Any] = json.load(f)
        self._providers: dict[str, dict] = self._config["providers"]
        self._retry_defaults: dict = self._config.get("retry_defaults", {})
        self._discovered_cache: dict[str, list[dict]] = {}

    @property
    def fallback_order(self) -> list[str]:
        return self._config.get("fallback_order", list(self._providers.keys()))

    @property
    def defaults(self) -> dict[str, dict]:
        return self._config.get("defaults", {})

    def list_providers(self) -> list[dict]:
        result = []
        for pid, pconfig in self._providers.items():
            result.append({
                "id": pid,
                "name": pconfig["name"],
                "available": self._is_available(pid, pconfig),
            })
        return result

    def list_models(self, provider_id: str) -> list[dict]:
        if provider_id not in self._providers:
            raise KeyError(f"Unknown provider: {provider_id}")

        pconfig = self._providers[provider_id]
        models: list[dict] = []

        for m in pconfig.get("models", []):
            models.append({**m, "source": "config"})

        if pconfig.get("auto_discover"):
            models.extend(self._discover_models(provider_id, pconfig))

        return models

    def get_client(self, provider_id: str) -> openai.OpenAI:
        pconfig = self._providers[provider_id]
        base_url = self._resolve_base_url(pconfig)
        api_key = self._resolve_api_key(pconfig)
        extra_headers = pconfig.get("extra_headers", {})
        return openai.OpenAI(
            base_url=base_url,
            api_key=api_key,
            default_headers=extra_headers or None,
        )

    def get_retry_config(self, provider_id: str) -> dict:
        pconfig = self._providers[provider_id]
        provider_retry = pconfig.get("retry", {})
        merged = {**self._retry_defaults, **provider_retry}
        return merged

    def _is_available(self, provider_id: str, pconfig: dict) -> bool:
        if "api_key" in pconfig:
            return True
        api_key_env = pconfig.get("api_key_env")
        if api_key_env:
            return bool(os.environ.get(api_key_env))
        return False

    def _resolve_base_url(self, pconfig: dict) -> str:
        if "base_url" in pconfig:
            return pconfig["base_url"]
        env_var = pconfig.get("base_url_env")
        host = os.environ.get(env_var, "") if env_var else ""
        default = pconfig.get("base_url_default", "")
        if host:
            return host.rstrip("/") + "/v1"
        return default

    def _resolve_api_key(self, pconfig: dict) -> str:
        if "api_key" in pconfig:
            return pconfig["api_key"]
        env_var = pconfig.get("api_key_env")
        return os.environ.get(env_var, "") if env_var else ""

    def _discover_models(self, provider_id: str, pconfig: dict) -> list[dict]:
        if provider_id in self._discovered_cache:
            return self._discovered_cache[provider_id]

        base_url = self._resolve_base_url(pconfig)
        tags_url = base_url.replace("/v1", "/api/tags")

        try:
            with urllib.request.urlopen(tags_url, timeout=5) as resp:
                data = json.loads(resp.read())
        except Exception:
            self._discovered_cache[provider_id] = []
            return []

        models = []
        for m in data.get("models", []):
            models.append({
                "id": m["name"],
                "name": m["name"],
                "vision": True,
                "source": "discovered",
            })

        self._discovered_cache[provider_id] = models
        return models
