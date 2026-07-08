"""Tests for :mod:`lightroom_tagger.core.provider_resolution`."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from lightroom_tagger.core.exceptions import ModelUnavailableError
from lightroom_tagger.core.provider_resolution import resolve_model


def _fake_registry(
    *,
    defaults: dict | None = None,
    fallback_order: list[str] | None = None,
    models: list[dict] | None = None,
) -> MagicMock:
    registry = MagicMock()
    registry.defaults = defaults or {}
    registry.fallback_order = fallback_order if fallback_order is not None else ["ollama"]
    registry.list_models.return_value = models if models is not None else [
        {"id": "listed-model", "vision": True},
    ]
    return registry


def test_explicit_args_win_over_all_other_rungs() -> None:
    registry = _fake_registry(
        defaults={"description": {"provider": "json-prov", "model": "json-model"}},
        fallback_order=["fallback-prov"],
    )
    with (
        patch.dict(os.environ, {"DESCRIPTION_VISION_MODEL": "env-model"}, clear=False),
        patch(
            "lightroom_tagger.core.provider_resolution.get_description_model",
            return_value="yaml-model",
        ),
    ):
        resolved = resolve_model(
            kind="description",
            provider_id="explicit-prov",
            model="explicit-model",
            registry=registry,
        )
    assert resolved.provider_id == "explicit-prov"
    assert resolved.model == "explicit-model"
    assert resolved.registry is registry
    registry.list_models.assert_not_called()


def test_env_beats_providers_json() -> None:
    registry = _fake_registry(
        defaults={"description": {"provider": "json-prov", "model": "json-model"}},
    )
    with (
        patch.dict(os.environ, {"DESCRIPTION_VISION_MODEL": "env-model"}, clear=False),
        patch(
            "lightroom_tagger.core.provider_resolution.get_description_model",
            return_value="yaml-model",
        ),
    ):
        resolved = resolve_model(kind="description", registry=registry)
    assert resolved.provider_id == "json-prov"
    assert resolved.model == "env-model"
    registry.list_models.assert_not_called()


def test_providers_json_beats_config_yaml() -> None:
    registry = _fake_registry(
        defaults={"description": {"provider": "json-prov", "model": "json-model"}},
    )
    with (
        patch.dict(os.environ, {}, clear=True),
        patch(
            "lightroom_tagger.core.provider_resolution.get_description_model",
            return_value="yaml-model",
        ),
    ):
        resolved = resolve_model(kind="description", registry=registry)
    assert resolved.provider_id == "json-prov"
    assert resolved.model == "json-model"
    registry.list_models.assert_not_called()


def test_config_yaml_beats_fallback_order() -> None:
    registry = _fake_registry(
        defaults={"description": {"provider": "json-prov", "model": None}},
        fallback_order=["fallback-prov"],
    )
    with (
        patch.dict(os.environ, {}, clear=True),
        patch(
            "lightroom_tagger.core.provider_resolution.get_description_model",
            return_value="yaml-model",
        ),
    ):
        resolved = resolve_model(kind="description", registry=registry)
    assert resolved.provider_id == "json-prov"
    assert resolved.model == "yaml-model"
    registry.list_models.assert_not_called()


def test_fallback_order_used_when_no_higher_rung_provider() -> None:
    registry = _fake_registry(
        defaults={},
        fallback_order=["fallback-prov"],
        models=[{"id": "listed-model", "vision": True}],
    )
    with (
        patch.dict(os.environ, {}, clear=True),
        patch(
            "lightroom_tagger.core.provider_resolution.get_description_model",
            return_value="",
        ),
        patch(
            "lightroom_tagger.core.provider_resolution.get_vision_model",
            return_value="",
        ),
    ):
        resolved = resolve_model(kind="description", registry=registry)
    assert resolved.provider_id == "fallback-prov"
    assert resolved.model == "listed-model"
    registry.list_models.assert_called_once_with("fallback-prov")


def test_empty_everything_raises_model_unavailable_for_provider() -> None:
    registry = _fake_registry(defaults={}, fallback_order=[])
    with pytest.raises(ModelUnavailableError, match="No provider configured"):
        resolve_model(kind="description", registry=registry)


def test_resolved_provider_with_no_models_raises() -> None:
    registry = _fake_registry(
        defaults={"description": {"provider": "json-prov", "model": None}},
        models=[],
    )
    with (
        patch.dict(os.environ, {}, clear=True),
        patch(
            "lightroom_tagger.core.provider_resolution.get_description_model",
            return_value="",
        ),
    ):
        with pytest.raises(ModelUnavailableError, match="No models available"):
            resolve_model(kind="description", registry=registry)


def test_upper_rung_model_passes_through_without_list_models_validation() -> None:
    registry = _fake_registry(
        defaults={"description": {"provider": "json-prov", "model": "cloud/unknown"}},
        models=[{"id": "listed-model", "vision": True}],
    )
    with patch.dict(os.environ, {}, clear=True):
        resolved = resolve_model(kind="description", registry=registry)
    assert resolved.model == "cloud/unknown"
    registry.list_models.assert_not_called()


def test_vision_comparison_uses_vision_model_env() -> None:
    registry = _fake_registry(
        defaults={"vision_comparison": {"provider": "json-prov", "model": "json-model"}},
    )
    with (
        patch.dict(os.environ, {"VISION_MODEL": "vision-env-model"}, clear=False),
        patch(
            "lightroom_tagger.core.provider_resolution.get_vision_model",
            return_value="yaml-model",
        ),
    ):
        resolved = resolve_model(kind="vision_comparison", registry=registry)
    assert resolved.model == "vision-env-model"


def test_description_falls_back_to_vision_model_env() -> None:
    registry = _fake_registry(
        defaults={"description": {"provider": "json-prov", "model": "json-model"}},
    )
    with (
        patch.dict(os.environ, {"VISION_MODEL": "shared-env-model"}, clear=True),
        patch(
            "lightroom_tagger.core.provider_resolution.get_description_model",
            return_value="yaml-model",
        ),
    ):
        resolved = resolve_model(kind="description", registry=registry)
    assert resolved.model == "shared-env-model"


def test_constructs_registry_when_not_injected() -> None:
    with patch("lightroom_tagger.core.provider_resolution.ProviderRegistry") as mock_cls:
        mock_registry = _fake_registry(
            defaults={"description": {"provider": "ollama", "model": "m"}},
        )
        mock_cls.return_value = mock_registry
        resolved = resolve_model(kind="description", provider_id="ollama", model="m")
    mock_cls.assert_called_once()
    assert resolved.registry is mock_registry
