"""Contract tests for Providers pydantic models."""

from __future__ import annotations

from pathlib import Path

import pytest

from api.schemas.providers import (
    DescriptionModelsResponse,
    FallbackOrderResponse,
    ProviderDefaults,
    ProviderListResponse,
    ProviderModel,
    ProviderModelsListResponse,
)
from lightroom_tagger.core.provider_registry import ProviderRegistry

_EXAMPLE_CONFIG = Path(__file__).resolve().parents[4] / "lightroom_tagger" / "core" / "providers.example.json"


@pytest.fixture
def registry():
    return ProviderRegistry(config_path=_EXAMPLE_CONFIG)


def test_provider_list_round_trip(registry):
    payload = registry.list_providers()
    validated = ProviderListResponse.model_validate(payload)

    ids = {provider.id for provider in validated.root}
    assert "nvidia_nim" in ids
    assert all(isinstance(provider.available, bool) for provider in validated.root)


def test_provider_model_round_trip_from_config_models(registry):
    payload = registry.list_models("nvidia_nim")
    validated = ProviderModelsListResponse.model_validate(payload)

    assert len(validated.root) >= 1
    first = validated.root[0]
    assert first.source == "config"
    assert isinstance(first.id, str)


def test_provider_defaults_round_trip(registry):
    validated = ProviderDefaults.model_validate(registry.defaults)

    assert validated.vision_comparison.provider
    assert validated.description.provider


def test_fallback_order_round_trip(registry):
    validated = FallbackOrderResponse.model_validate({"order": registry.fallback_order})
    assert "ollama" in validated.order


def test_description_models_response_round_trip(registry):
    providers = registry.list_providers()
    result = []
    for provider in providers:
        pid = provider["id"]
        for model in registry.list_models(pid):
            result.append({
                "provider_id": pid,
                "provider_name": provider["name"],
                "model_id": model["id"],
                "model_name": model.get("name", model["id"]),
                "tool_calling": bool(provider.get("tool_calling", False)),
            })
    defaults = registry.defaults.get("description", {}) or {}
    payload = {
        "models": result,
        "default_provider": defaults.get("provider"),
        "default_model": defaults.get("model"),
    }
    validated = DescriptionModelsResponse.model_validate(payload)
    assert isinstance(validated.models, list)


def test_provider_model_rejects_wrong_shape():
    with pytest.raises(Exception):
        ProviderModel.model_validate({"id": "only-id"})
