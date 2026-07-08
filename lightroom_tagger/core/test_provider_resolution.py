"""Unit tests for provider_resolution.resolve_model precedence ladder."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from lightroom_tagger.core.exceptions import ModelUnavailableError
from lightroom_tagger.core.provider_resolution import ResolvedModel, resolve_model
from lightroom_tagger.core.provider_registry import ProviderRegistry


def _fake_registry(
    *,
    defaults: dict | None = None,
    fallback_order: list[str] | None = None,
    models_by_provider: dict[str, list[dict]] | None = None,
) -> MagicMock:
    registry = MagicMock(spec=ProviderRegistry)
    registry.defaults = defaults or {}
    registry.fallback_order = fallback_order or []
    models_by_provider = models_by_provider or {}

    def list_models(provider_id: str) -> list[dict]:
        return models_by_provider.get(provider_id, [])

    registry.list_models.side_effect = list_models
    return registry


class TestResolveModelPrecedence:
    def test_explicit_args_win_over_all_lower_rungs(self, monkeypatch):
        monkeypatch.setenv("VISION_MODEL", "env-model")
        registry = _fake_registry(
            defaults={"description": {"provider": "p-json", "model": "json-model"}},
            fallback_order=["fallback-p"],
            models_by_provider={"explicit-p": [{"id": "listed-model"}]},
        )
        with patch(
            "lightroom_tagger.core.provider_resolution.get_description_model",
            return_value="config-model",
        ):
            result = resolve_model(
                kind="description",
                provider_id="explicit-p",
                model="explicit-model",
                registry=registry,
            )
        assert result == ResolvedModel("explicit-p", "explicit-model", registry)
        registry.list_models.assert_not_called()

    def test_env_beats_providers_json_and_config(self, monkeypatch):
        monkeypatch.setenv("DESCRIPTION_VISION_MODEL", "env-desc-model")
        registry = _fake_registry(
            defaults={"description": {"provider": "p-json", "model": "json-model"}},
            fallback_order=["fallback-p"],
            models_by_provider={"p-json": [{"id": "listed-model"}]},
        )
        with patch(
            "lightroom_tagger.core.provider_resolution.get_description_model",
            return_value="config-model",
        ):
            result = resolve_model(kind="description", registry=registry)
        assert result.provider_id == "p-json"
        assert result.model == "env-desc-model"
        registry.list_models.assert_not_called()

    def test_vision_comparison_uses_vision_model_env(self, monkeypatch):
        monkeypatch.setenv("VISION_MODEL", "env-vision-model")
        registry = _fake_registry(
            defaults={
                "vision_comparison": {"provider": "vc-p", "model": "json-model"},
            },
            fallback_order=["fallback-p"],
            models_by_provider={"vc-p": [{"id": "listed-model"}]},
        )
        with patch(
            "lightroom_tagger.core.provider_resolution.get_vision_model",
            return_value="config-model",
        ):
            result = resolve_model(kind="vision_comparison", registry=registry)
        assert result.provider_id == "vc-p"
        assert result.model == "env-vision-model"

    def test_description_falls_back_to_vision_model_env(self, monkeypatch):
        monkeypatch.delenv("DESCRIPTION_VISION_MODEL", raising=False)
        monkeypatch.setenv("VISION_MODEL", "shared-env-model")
        registry = _fake_registry(
            defaults={"description": {"provider": "p-json", "model": "json-model"}},
            fallback_order=["fallback-p"],
        )
        with patch(
            "lightroom_tagger.core.provider_resolution.get_description_model",
            return_value="config-model",
        ):
            result = resolve_model(kind="description", registry=registry)
        assert result.model == "shared-env-model"

    def test_providers_json_beats_config_yaml(self, monkeypatch):
        monkeypatch.delenv("DESCRIPTION_VISION_MODEL", raising=False)
        monkeypatch.delenv("VISION_MODEL", raising=False)
        registry = _fake_registry(
            defaults={"description": {"provider": "p-json", "model": "json-model"}},
            fallback_order=["fallback-p"],
            models_by_provider={"p-json": [{"id": "listed-model"}]},
        )
        with patch(
            "lightroom_tagger.core.provider_resolution.get_description_model",
            return_value="config-model",
        ):
            result = resolve_model(kind="description", registry=registry)
        assert result.provider_id == "p-json"
        assert result.model == "json-model"
        registry.list_models.assert_not_called()

    def test_config_yaml_beats_fallback_order_model(self, monkeypatch):
        monkeypatch.delenv("VISION_MODEL", raising=False)
        registry = _fake_registry(
            defaults={"vision_comparison": {"provider": "vc-p", "model": None}},
            fallback_order=["vc-p"],
            models_by_provider={"vc-p": [{"id": "listed-model"}]},
        )
        with patch(
            "lightroom_tagger.core.provider_resolution.get_vision_model",
            return_value="config-model",
        ):
            result = resolve_model(kind="vision_comparison", registry=registry)
        assert result.provider_id == "vc-p"
        assert result.model == "config-model"
        registry.list_models.assert_not_called()

    def test_fallback_order_provider_and_list_models_when_unresolved(self, monkeypatch):
        monkeypatch.delenv("VISION_MODEL", raising=False)
        registry = _fake_registry(
            defaults={},
            fallback_order=["fallback-p"],
            models_by_provider={"fallback-p": [{"id": "first-listed"}]},
        )
        with patch(
            "lightroom_tagger.core.provider_resolution.get_vision_model",
            return_value="",
        ):
            result = resolve_model(kind="vision_comparison", registry=registry)
        assert result.provider_id == "fallback-p"
        assert result.model == "first-listed"
        registry.list_models.assert_called_once_with("fallback-p")

    def test_upper_rung_model_not_validated_against_list_models(self, monkeypatch):
        monkeypatch.delenv("VISION_MODEL", raising=False)
        registry = _fake_registry(
            defaults={"description": {"provider": "p-json", "model": "cloud-only-model"}},
            fallback_order=["p-json"],
            models_by_provider={"p-json": []},
        )
        with patch(
            "lightroom_tagger.core.provider_resolution.get_description_model",
            return_value="",
        ):
            result = resolve_model(kind="description", registry=registry)
        assert result.model == "cloud-only-model"
        registry.list_models.assert_not_called()

    def test_empty_fallback_order_raises_when_no_provider(self, monkeypatch):
        monkeypatch.delenv("VISION_MODEL", raising=False)
        registry = _fake_registry(defaults={}, fallback_order=[])
        with patch(
            "lightroom_tagger.core.provider_resolution.get_vision_model",
            return_value="",
        ):
            with pytest.raises(ModelUnavailableError, match="No provider"):
                resolve_model(kind="vision_comparison", registry=registry)

    def test_provider_with_no_models_raises_when_model_unresolved(self, monkeypatch):
        monkeypatch.delenv("VISION_MODEL", raising=False)
        registry = _fake_registry(
            defaults={},
            fallback_order=["empty-p"],
            models_by_provider={"empty-p": []},
        )
        with patch(
            "lightroom_tagger.core.provider_resolution.get_vision_model",
            return_value="",
        ):
            with pytest.raises(ModelUnavailableError, match="No models"):
                resolve_model(kind="vision_comparison", registry=registry)


class TestResolveModelRegistryConstruction:
    def test_constructs_registry_once_when_not_injected(self):
        with patch(
            "lightroom_tagger.core.provider_resolution.ProviderRegistry"
        ) as mock_cls:
            mock_registry = _fake_registry(
                defaults={"description": {"provider": "p", "model": "m"}},
                fallback_order=["p"],
            )
            mock_cls.return_value = mock_registry
            with patch(
                "lightroom_tagger.core.provider_resolution.get_description_model",
                return_value="",
            ):
                result = resolve_model(kind="description")
        mock_cls.assert_called_once()
        assert result.registry is mock_registry

    def test_injected_registry_is_not_reconstructed(self):
        registry = _fake_registry(
            defaults={"description": {"provider": "p", "model": "m"}},
            fallback_order=["p"],
        )
        with patch(
            "lightroom_tagger.core.provider_resolution.ProviderRegistry"
        ) as mock_cls:
            with patch(
                "lightroom_tagger.core.provider_resolution.get_description_model",
                return_value="",
            ):
                result = resolve_model(kind="description", registry=registry)
        mock_cls.assert_not_called()
        assert result.registry is registry
