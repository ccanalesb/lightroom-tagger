"""Flask tests for ``/api/identity/*`` routes."""

from __future__ import annotations

import pytest
from app import create_app

from lightroom_tagger.core.database import init_database


@pytest.fixture
def identity_client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "library.db")
    init_database(db_path)
    monkeypatch.setattr("utils.db.LIBRARY_DB", db_path)
    app = create_app()
    return app.test_client()


def test_best_photos_200_shape(identity_client) -> None:
    resp = identity_client.get("/api/identity/best-photos")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data is not None
    assert "items" in data
    assert "total" in data
    assert "meta" in data
    assert data["meta"].get("weighting") == "equal"


def test_style_fingerprint_200_shape(identity_client) -> None:
    resp = identity_client.get("/api/identity/style-fingerprint")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data is not None
    assert "per_perspective" in data
    assert "top_rationale_tokens" in data
    assert "meta" in data


def test_suggestions_200_shape(identity_client) -> None:
    resp = identity_client.get("/api/identity/suggestions")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data is not None
    assert "candidates" in data
    assert "meta" in data
    assert "empty_state" in data
