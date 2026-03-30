import os
from unittest.mock import patch

import pytest
from app import create_app


@pytest.fixture()
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestListProviders:
    def test_should_return_all_providers(self, client):
        resp = client.get("/api/providers/")
        assert resp.status_code == 200
        data = resp.get_json()
        ids = [p["id"] for p in data]
        assert "ollama" in ids
        assert "nvidia_nim" in ids
        assert "openrouter" in ids

    def test_should_include_availability_status(self, client):
        resp = client.get("/api/providers/")
        data = resp.get_json()
        provider_map = {p["id"]: p for p in data}
        assert "available" in provider_map["ollama"]


class TestListModels:
    def test_should_return_models_for_nvidia(self, client):
        resp = client.get("/api/providers/nvidia_nim/models")
        assert resp.status_code == 200
        data = resp.get_json()
        model_ids = [m["id"] for m in data]
        assert "meta/llama-4-maverick-17b-128e-instruct" in model_ids

    def test_should_return_404_for_unknown_provider(self, client):
        resp = client.get("/api/providers/nonexistent/models")
        assert resp.status_code == 404


class TestFallbackOrder:
    def test_should_return_fallback_order(self, client):
        resp = client.get("/api/providers/fallback-order")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["order"] == ["ollama", "nvidia_nim", "openrouter"]


class TestDefaults:
    def test_should_return_defaults(self, client):
        resp = client.get("/api/providers/defaults")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["vision_comparison"]["provider"] == "ollama"
        assert data["description"]["provider"] == "ollama"
