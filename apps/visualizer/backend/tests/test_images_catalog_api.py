"""Integration tests for GET /api/images/catalog query parameters."""

import pytest

from app import create_app
from lightroom_tagger.core.database import init_database, store_image


@pytest.fixture
def catalog_client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "library.db")
    conn = init_database(db_path)
    store_image(
        conn,
        {
            "date_taken": "2024-01-10",
            "filename": "low.jpg",
            "rating": 3,
            "id": "100",
        },
    )
    store_image(
        conn,
        {
            "date_taken": "2024-06-15",
            "filename": "high.jpg",
            "rating": 5,
            "id": "200",
        },
    )
    conn.close()

    monkeypatch.setattr("utils.db.LIBRARY_DB", db_path)
    app = create_app()
    return app.test_client()


def test_catalog_pagination_total_and_limit(catalog_client):
    resp = catalog_client.get("/api/images/catalog?limit=1&offset=0")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total"] == 2
    assert len(data["images"]) <= 1
    assert len(data["images"]) == 1


def test_catalog_min_rating_filter(catalog_client):
    resp = catalog_client.get("/api/images/catalog?min_rating=5")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total"] == 1
    assert len(data["images"]) == 1
    assert data["images"][0]["rating"] >= 5
    assert data["images"][0]["filename"] == "high.jpg"
