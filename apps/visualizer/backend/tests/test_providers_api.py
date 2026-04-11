import sqlite3
from unittest.mock import PropertyMock, patch

import pytest
from app import create_app
from lightroom_tagger.core.provider_registry import ProviderRegistry


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


class TestListProviders:
    def test_should_return_all_providers(self, client):
        resp = client.get("/api/providers/")
        assert resp.status_code == 200
        data = resp.get_json()
        ids = {provider["id"] for provider in data}
        assert ids == {p["id"] for p in ProviderRegistry().list_providers()}

    def test_should_include_availability_status(self, client):
        resp = client.get("/api/providers/")
        data = resp.get_json()
        provider_map = {provider["id"]: provider for provider in data}
        assert "available" in provider_map["ollama"]


class TestListModels:
    def test_should_return_models_for_provider_with_config_models(self, client):
        resp = client.get("/api/providers/github_copilot/models")
        assert resp.status_code == 200
        data = resp.get_json()
        model_ids = [model["id"] for model in data]
        assert "gpt-4o" in model_ids

    def test_should_return_404_for_unknown_provider(self, client):
        resp = client.get("/api/providers/nonexistent/models")
        assert resp.status_code == 404


class TestFallbackOrder:
    def test_should_return_fallback_order(self, client):
        resp = client.get("/api/providers/fallback-order")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["order"] == ProviderRegistry().fallback_order

    def test_put_fallback_order_should_update_order(self, client):
        from lightroom_tagger.core.provider_registry import ProviderRegistry

        expected_order = ["nvidia_nim", "ollama", "openrouter"]

        def capture_order(new_order):
            shared_order[:] = list(new_order)

        shared_order = list(expected_order)

        with patch.object(
            ProviderRegistry,
            "fallback_order",
            new_callable=PropertyMock,
            return_value=shared_order,
        ):
            with patch.object(
                ProviderRegistry, "update_fallback_order", side_effect=capture_order
            ):
                resp = client.put(
                    "/api/providers/fallback-order",
                    json={"order": expected_order},
                )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["order"] == expected_order

    def test_put_fallback_order_should_reject_empty_body(self, client):
        resp = client.put("/api/providers/fallback-order", json={})
        assert resp.status_code == 400

    def test_put_fallback_order_should_reject_unknown_providers(self, client):
        from lightroom_tagger.core.provider_registry import ProviderRegistry

        with patch.object(
            ProviderRegistry,
            "update_fallback_order",
            side_effect=ValueError("Unknown provider id(s): ['not_a_provider']"),
        ):
            resp = client.put(
                "/api/providers/fallback-order",
                json={"order": ["not_a_provider"]},
            )
        assert resp.status_code == 400


class TestDefaults:
    def test_should_return_defaults(self, client):
        resp = client.get("/api/providers/defaults")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["vision_comparison"]["provider"] == "ollama"
        assert data["description"]["provider"] == "ollama"

    def test_put_defaults_should_update_defaults(self, client):
        from lightroom_tagger.core.provider_registry import ProviderRegistry

        merged_defaults = {
            "vision_comparison": {"provider": "ollama", "model": "gemma3:27b"},
            "description": {"provider": "ollama"},
        }

        def merge_defaults(incoming: dict) -> None:
            merged_defaults.update(incoming)

        with patch.object(
            ProviderRegistry,
            "defaults",
            new_callable=PropertyMock,
            return_value=merged_defaults,
        ):
            with patch.object(
                ProviderRegistry, "update_defaults", side_effect=merge_defaults
            ):
                resp = client.put(
                    "/api/providers/defaults",
                    json={
                        "vision_comparison": {
                            "provider": "ollama",
                            "model": "gemma3:27b",
                        }
                    },
                )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["vision_comparison"]["provider"] == "ollama"
        assert data["vision_comparison"]["model"] == "gemma3:27b"

    def test_put_defaults_should_reject_empty_body(self, client):
        resp = client.put("/api/providers/defaults", json={})
        assert resp.status_code == 400
        resp_null_json = client.put(
            "/api/providers/defaults",
            data="null",
            content_type="application/json",
        )
        assert resp_null_json.status_code == 400

    def test_put_defaults_should_reject_invalid_key(self, client):
        from lightroom_tagger.core.provider_registry import ProviderRegistry

        with patch.object(
            ProviderRegistry,
            "update_defaults",
            side_effect=ValueError("Unknown defaults key: 'bad_key'"),
        ):
            resp = client.put(
                "/api/providers/defaults",
                json={"bad_key": {"provider": "ollama"}},
            )
        assert resp.status_code == 400


class TestProviderHealth:
    def test_health_reachable(self, client):
        with patch.object(
            ProviderRegistry, "probe_connection", return_value=(True, None)
        ):
            resp = client.get("/api/providers/ollama/health")
        assert resp.status_code == 200
        assert resp.get_json() == {"reachable": True}

    def test_health_unreachable(self, client):
        with patch.object(
            ProviderRegistry, "probe_connection", return_value=(False, "boom")
        ):
            resp = client.get("/api/providers/ollama/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["reachable"] is False
        assert "boom" in (data.get("error") or "")


class TestUserModels:
    def test_post_model_should_create_user_model(self, client):
        with patch("api.providers.add_user_model") as add_user_model_mock:
            resp = client.post(
                "/api/providers/ollama/models",
                json={
                    "id": "test-model",
                    "name": "Test Model",
                    "vision": True,
                },
            )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["id"] == "test-model"
        assert data["name"] == "Test Model"
        assert data["vision"] is True
        assert data["source"] == "user"
        add_user_model_mock.assert_called_once()

    def test_post_model_should_reject_missing_fields(self, client):
        resp = client.post(
            "/api/providers/ollama/models",
            json={"name": "No Id Model"},
        )
        assert resp.status_code == 400

    def test_post_model_should_reject_duplicate(self, client):
        with patch("api.providers.add_user_model") as add_user_model_mock:
            add_user_model_mock.side_effect = sqlite3.IntegrityError("UNIQUE constraint")
            resp = client.post(
                "/api/providers/ollama/models",
                json={
                    "id": "dup",
                    "name": "Dup",
                    "vision": True,
                },
            )
        assert resp.status_code == 409

    def test_delete_model_should_remove_user_model(self, client):
        with patch("api.providers.delete_user_model", return_value=True) as delete_mock:
            resp = client.delete("/api/providers/ollama/models/test-model")
        assert resp.status_code == 200
        assert resp.get_json() == {"deleted": True}
        delete_mock.assert_called_once()

    def test_delete_model_should_return_404_for_missing(self, client):
        with patch("api.providers.delete_user_model", return_value=False):
            resp = client.delete("/api/providers/ollama/models/missing-model")
        assert resp.status_code == 404
