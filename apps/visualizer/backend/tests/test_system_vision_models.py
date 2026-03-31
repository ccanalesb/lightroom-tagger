import sqlite3
from unittest.mock import MagicMock, patch

import pytest
from app import create_app


@pytest.fixture()
def client():
    app = create_app()
    app.config["TESTING"] = True
    memory_db = sqlite3.connect(":memory:")
    memory_db.row_factory = sqlite3.Row
    memory_db.execute(
        """
        CREATE TABLE provider_models (
            provider_id TEXT NOT NULL,
            model_id TEXT NOT NULL,
            model_name TEXT NOT NULL,
            vision INTEGER DEFAULT 1,
            PRIMARY KEY (provider_id, model_id)
        )
        """
    )
    memory_db.commit()
    app.db = memory_db
    with app.test_client() as test_client:
        yield test_client
    memory_db.close()


class TestVisionModels:
    def test_should_return_models_from_registry(self, client):
        registry_instance = MagicMock()
        registry_instance.defaults = {
            "vision_comparison": {"provider": "ollama", "model": "gemma3:27b"},
        }
        registry_instance.list_providers.return_value = [
            {"id": "ollama", "name": "Ollama", "available": True},
        ]
        registry_instance.list_models.return_value = [
            {
                "id": "gemma3:27b",
                "name": "Gemma 3 27B",
                "vision": True,
                "source": "config",
            },
        ]

        with patch(
            "lightroom_tagger.core.provider_registry.ProviderRegistry",
            return_value=registry_instance,
        ):
            resp = client.get("/api/vision-models")

        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload["fallback"] is False
        models = payload["models"]
        assert len(models) == 1
        entry = models[0]
        assert entry["name"] == "gemma3:27b"
        assert entry["provider_id"] == "ollama"
        assert "default" in entry

    def test_should_mark_default_model(self, client):
        registry_instance = MagicMock()
        registry_instance.defaults = {
            "vision_comparison": {"provider": "ollama", "model": "gemma3:27b"},
        }
        registry_instance.list_providers.return_value = [
            {"id": "ollama", "name": "Ollama", "available": True},
        ]
        registry_instance.list_models.return_value = [
            {
                "id": "gemma3:27b",
                "name": "Gemma",
                "vision": True,
                "source": "config",
            },
            {
                "id": "other-vision",
                "name": "Other",
                "vision": True,
                "source": "config",
            },
        ]

        with patch(
            "lightroom_tagger.core.provider_registry.ProviderRegistry",
            return_value=registry_instance,
        ):
            resp = client.get("/api/vision-models")

        assert resp.status_code == 200
        models = resp.get_json()["models"]
        default_flags = [model["default"] for model in models]
        assert sum(1 for flag in default_flags if flag) == 1

    def test_should_fallback_when_registry_fails(self, client):
        def raise_registry(*args, **kwargs):
            raise RuntimeError("registry unavailable")

        with patch(
            "lightroom_tagger.core.provider_registry.ProviderRegistry",
            side_effect=raise_registry,
        ):
            resp = client.get("/api/vision-models")

        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload["fallback"] is True
        assert payload["models"] == [{"name": "gemma3:27b", "default": True}]
