"""Single seam for provider/model resolution (ADR-0007)."""

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


def _nonempty(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    return value


def _env_model_for_kind(kind: Kind) -> str | None:
    if kind == "description":
        if "DESCRIPTION_VISION_MODEL" in os.environ:
            return os.environ["DESCRIPTION_VISION_MODEL"]
        if "VISION_MODEL" in os.environ:
            return os.environ["VISION_MODEL"]
        return None
    if "VISION_MODEL" in os.environ:
        return os.environ["VISION_MODEL"]
    return None


def _config_model_for_kind(kind: Kind) -> str:
    if kind == "description":
        return get_description_model()
    return get_vision_model()


def resolve_model(
    *,
    kind: Kind = "description",
    provider_id: str | None = None,
    model: str | None = None,
    registry: ProviderRegistry | None = None,
) -> ResolvedModel:
    """Resolve provider and model using the ADR-0007 precedence ladder."""
    if registry is None:
        registry = ProviderRegistry()

    resolved_provider = _nonempty(provider_id)
    resolved_model = _nonempty(model)

    if resolved_model is None:
        resolved_model = _nonempty(_env_model_for_kind(kind))

    defaults = registry.defaults.get(kind, {}) or {}
    if resolved_provider is None:
        resolved_provider = _nonempty(defaults.get("provider"))
    if resolved_model is None:
        resolved_model = _nonempty(defaults.get("model"))

    if resolved_model is None:
        resolved_model = _nonempty(_config_model_for_kind(kind))

    if resolved_provider is None:
        if registry.fallback_order:
            resolved_provider = registry.fallback_order[0]

    if resolved_provider is None:
        raise ModelUnavailableError(
            f"No provider configured for {kind} — set defaults.{kind} in providers.json",
            provider=None,
            model=None,
        )

    if resolved_model is None:
        models = registry.list_models(resolved_provider)
        if not models:
            raise ModelUnavailableError(
                f"No models available for provider '{resolved_provider}' — check provider config",
                provider=resolved_provider,
                model=None,
            )
        resolved_model = models[0]["id"]

    return ResolvedModel(
        provider_id=resolved_provider,
        model=resolved_model,
        registry=registry,
    )


__all__ = ["Kind", "ResolvedModel", "resolve_model"]
