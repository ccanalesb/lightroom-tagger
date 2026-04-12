"""Flask tests for ``/api/analytics/*`` routes."""

from __future__ import annotations

import pytest
from app import create_app

from lightroom_tagger.core.database import init_database, store_image


@pytest.fixture
def analytics_client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "library.db")
    init_database(db_path)
    monkeypatch.setattr("utils.db.LIBRARY_DB", db_path)
    app = create_app()
    return app.test_client()


@pytest.fixture
def analytics_client_seeded(tmp_path, monkeypatch):
    db_path = str(tmp_path / "library.db")
    conn = init_database(db_path)
    store_image(
        conn,
        {
            "date_taken": "2024-06-01",
            "filename": "solo.jpg",
            "rating": 3,
            "instagram_posted": False,
        },
    )
    conn.close()
    monkeypatch.setattr("utils.db.LIBRARY_DB", db_path)
    app = create_app()
    return app.test_client()


def test_posting_frequency_200_and_meta(analytics_client) -> None:
    resp = analytics_client.get(
        "/api/analytics/posting-frequency",
        query_string={
            "date_from": "2024-01-01",
            "date_to": "2024-01-07",
            "granularity": "day",
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data is not None
    assert "buckets" in data
    assert "meta" in data
    assert data["meta"].get("timezone_assumption") == "UTC"


def test_posting_frequency_rejects_bad_granularity(analytics_client) -> None:
    resp = analytics_client.get(
        "/api/analytics/posting-frequency",
        query_string={
            "date_from": "2024-01-01",
            "date_to": "2024-01-07",
            "granularity": "hour",
        },
    )
    assert resp.status_code == 400


def test_unposted_catalog_200_shape(analytics_client) -> None:
    resp = analytics_client.get("/api/analytics/unposted-catalog")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data is not None
    assert "total" in data
    assert "images" in data
    assert "pagination" in data
    assert data["pagination"].get("limit") is not None


def test_unposted_catalog_lists_unposted_rows(analytics_client_seeded) -> None:
    resp = analytics_client_seeded.get("/api/analytics/unposted-catalog")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total"] == 1
    assert len(data["images"]) == 1
    assert data["images"][0].get("filename") == "solo.jpg"
