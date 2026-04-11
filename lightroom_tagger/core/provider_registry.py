"""Provider registry — loads providers.json, auto-discovers Ollama models,
returns configured openai.OpenAI clients."""

from __future__ import annotations

import json
import os
import shutil
import urllib.request
from pathlib import Path
from typing import Any

import openai

_CONFIG_PATH = Path(__file__).parent / "providers.json"
_EXAMPLE_PATH = Path(__file__).parent / "providers.example.json"


class ProviderRegistry:
    """Central registry of vision/LLM providers and their models."""

    def __init__(self, config_path: Path = _CONFIG_PATH):
        self._config_path = config_path
        if not self._config_path.exists() and _EXAMPLE_PATH.exists():
            shutil.copy2(_EXAMPLE_PATH, self._config_path)
        with open(self._config_path, encoding="utf-8") as f:
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
        for provider_id, provider_config in self._providers.items():
            result.append({
                "id": provider_id,
                "name": provider_config["name"],
                "available": self._is_available(provider_id, provider_config),
            })
        return result

    def list_models(self, provider_id: str) -> list[dict]:
        if provider_id not in self._providers:
            raise KeyError(f"Unknown provider: {provider_id}")

        provider_config = self._providers[provider_id]
        models: list[dict] = []

        for model_entry in provider_config.get("models", []):
            models.append({**model_entry, "source": "config"})

        if provider_config.get("auto_discover"):
            models.extend(self._discover_models(provider_id, provider_config))

        # Apply custom order if it exists
        model_order = provider_config.get("model_order", [])
        if model_order:
            models_by_id = {m["id"]: m for m in models}
            ordered = []
            for model_id in model_order:
                if model_id in models_by_id:
                    ordered.append(models_by_id[model_id])
            # Add any models not in the order (new discoveries)
            for model in models:
                if model["id"] not in model_order:
                    ordered.append(model)
            return ordered

        return models

    def probe_connection(self, provider_id: str) -> tuple[bool, str | None]:
        """Return (True, None) if the provider API responds to a models list call.

        On failure, returns (False, error message) without raising.
        Raises KeyError if ``provider_id`` is not registered.
        """
        if provider_id not in self._providers:
            raise KeyError(provider_id)
        try:
            client = self.get_client(provider_id)
            for _ in client.models.list(timeout=5.0):
                break
            return True, None
        except Exception as exc:
            return False, str(exc)

    def get_client(self, provider_id: str) -> openai.OpenAI:
        provider_config = self._providers[provider_id]
        base_url = self._resolve_base_url(provider_config)
        api_key = self._resolve_api_key(provider_config)
        extra_headers = provider_config.get("extra_headers", {})
        client = openai.OpenAI(
            base_url=base_url,
            api_key=api_key,
            default_headers=extra_headers or None,
        )
        client._provider_id = provider_id  # type: ignore[attr-defined]
        return client

    def get_retry_config(self, provider_id: str) -> dict:
        provider_config = self._providers[provider_id]
        provider_retry = provider_config.get("retry", {})
        merged = {**self._retry_defaults, **provider_retry}
        return merged

    def update_fallback_order(self, order: list[str]) -> None:
        if not order:
            raise ValueError("fallback order must not be empty")
        unknown = [provider_id for provider_id in order if provider_id not in self._providers]
        if unknown:
            raise ValueError(f"Unknown provider id(s): {unknown!r}")
        seen_provider_ids: set[str] = set()
        deduplicated_order: list[str] = []
        for provider_id in order:
            if provider_id not in seen_provider_ids:
                seen_provider_ids.add(provider_id)
                deduplicated_order.append(provider_id)
        self._config["fallback_order"] = deduplicated_order
        self._save_config()

    def update_defaults(self, defaults: dict) -> None:
        allowed_keys = frozenset({"vision_comparison", "description"})
        if not defaults:
            raise ValueError(
                "defaults must include at least one of vision_comparison, description"
            )
        for key, value in defaults.items():
            if key not in allowed_keys:
                raise ValueError(f"Unknown defaults key: {key!r}")
            if not isinstance(value, dict):
                raise ValueError(f"{key} must be an object")
            if "provider" not in value:
                raise ValueError(f"{key} requires provider")
            provider_id = value["provider"]
            if provider_id not in self._providers:
                raise ValueError(f"Unknown provider: {provider_id}")
        merged = {**self._config.get("defaults", {}), **defaults}
        self._config["defaults"] = merged
        self._save_config()

    def remove_model(self, provider_id: str, model_id: str) -> bool:
        """Remove a config model from providers.json. Returns True if removed."""
        if provider_id not in self._providers:
            raise KeyError(f"Unknown provider: {provider_id}")
        models = self._providers[provider_id].get("models", [])
        original_count = len(models)
        self._providers[provider_id]["models"] = [
            model for model in models if model["id"] != model_id
        ]
        if len(self._providers[provider_id]["models"]) == original_count:
            return False
        self._save_config()
        return True

    def reorder_models(self, provider_id: str, model_order: list[str]) -> bool:
        """Reorder models for a provider. model_order is list of model IDs.
        Saves order to model_order field, works for all model types."""
        if provider_id not in self._providers:
            raise KeyError(f"Unknown provider: {provider_id}")

        self._providers[provider_id]["model_order"] = model_order
        self._save_config()
        return True

    def _save_config(self) -> None:
        with open(self._config_path, "w", encoding="utf-8") as f:
            json.dump(self._config, f, indent=2, ensure_ascii=False)
            f.write("\n")

    def _is_available(self, provider_id: str, provider_config: dict) -> bool:
        if "api_key" in provider_config:
            return True
        api_key_env = provider_config.get("api_key_env")
        if api_key_env:
            return bool(os.environ.get(api_key_env))
        return False

    def _resolve_base_url(self, provider_config: dict) -> str:
        if "base_url" in provider_config:
            return provider_config["base_url"]
        env_var = provider_config.get("base_url_env")
        host = os.environ.get(env_var, "") if env_var else ""
        default = provider_config.get("base_url_default", "")
        if host:
            base = host.rstrip("/")
            if not base.endswith("/v1"):
                base = base + "/v1"
            return base
        return default

    def _resolve_api_key(self, provider_config: dict) -> str:
        if "api_key" in provider_config:
            return provider_config["api_key"]
        env_var = provider_config.get("api_key_env")
        return os.environ.get(env_var, "") if env_var else ""

    def _discover_models(self, provider_id: str, provider_config: dict) -> list[dict]:
        if provider_id in self._discovered_cache:
            return self._discovered_cache[provider_id]

        base_url = self._resolve_base_url(provider_config)
        tags_url = base_url.replace("/v1", "/api/tags")

        try:
            with urllib.request.urlopen(tags_url, timeout=5) as resp:
                data = json.loads(resp.read())
        except Exception:
            self._discovered_cache[provider_id] = []
            return []

        models = []
        for discovered_model in data.get("models", []):
            models.append({
                "id": discovered_model["name"],
                "name": discovered_model["name"],
                "vision": True,
                "source": "discovered",
            })

        self._discovered_cache[provider_id] = models
        return models
