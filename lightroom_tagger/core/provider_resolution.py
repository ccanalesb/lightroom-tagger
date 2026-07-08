"""Single provider/model resolution seam — one precedence ladder per kind."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from lightroom_tagger.core.config import get_description_model, get_vision_model
from lightroom_tagger.core.exceptions import ModelUnavailableError
from lightroom_tagger.core.provider_registry import ProviderRegistry

Kind = Literal["description", "vision_comparison"]


@dataclass(frozen=True)
class ResolvedModel:
    provider_id: str
    model: str
    registry: ProviderRegistry


def _model_from_env(kind: Kind) -> str | None:
    if kind == "vision_comparison":
        value = os.environ.get("VISION_MODEL")
        return value if value else None
    if "DESCRIPTION_VISION_MODEL" in os.environ:
        return os.environ["DESCRIPTION_VISION_MODEL"]
    value = os.environ.get("VISION_MODEL")
    return value if value else None


def _model_from_config(kind: Kind) -> str | None:
    if kind == "vision_comparison":
        value = get_vision_model()
    else:
        value = get_description_model()
    return value if value else None


def _resolve_provider(
    registry: ProviderRegistry,
    kind: Kind,
    provider_id: str | None,
) -> str | None:
    if provider_id:
        return provider_id
    defaults = registry.defaults.get(kind, {}) or {}
    provider = defaults.get("provider")
    if provider:
        return provider
    order = registry.fallback_order
    if order:
        return order[0]
    return None


def _resolve_model(
    registry: ProviderRegistry,
    kind: Kind,
    provider_id: str,
    model: str | None,
) -> str:
    if model:
        return model
    env_model = _model_from_env(kind)
    if env_model:
        return env_model
    defaults = registry.defaults.get(kind, {}) or {}
    default_model = defaults.get("model")
    if default_model:
        return default_model
    config_model = _model_from_config(kind)
    if config_model:
        return config_model
    models = registry.list_models(provider_id)
    if not models:
        raise ModelUnavailableError(
            f"No models available for provider {provider_id!r}",
            provider=provider_id,
            model=None,
        )
    return models[0]["id"]


def resolve_model(
    *,
    kind: Kind = "description",
    provider_id: str | None = None,
    model: str | None = None,
    registry: ProviderRegistry | None = None,
) -> ResolvedModel:
    """Resolve provider and model using the documented precedence ladder."""
    if registry is None:
        registry = ProviderRegistry()

    resolved_provider = _resolve_provider(registry, kind, provider_id)
    if resolved_provider is None:
        raise ModelUnavailableError(
            "No provider configured — set defaults or fallback_order in providers.json",
            provider=None,
            model=None,
        )

    resolved_model = _resolve_model(registry, kind, resolved_provider, model)
    return ResolvedModel(
        provider_id=resolved_provider,
        model=resolved_model,
        registry=registry,
    )
