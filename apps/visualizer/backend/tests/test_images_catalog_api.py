"""Integration tests for GET /api/images/catalog query parameters."""

import sqlite3

import pytest

from app import create_app
from lightroom_tagger.core.database import (
    init_database,
    store_image,
    store_image_description,
)


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
            "instagram_posted": True,
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


@pytest.fixture
def catalog_analyzed_client(tmp_path, monkeypatch):
    """Single catalog image with AI description row (image_type=catalog)."""
    db_path = str(tmp_path / "library.db")
    conn = init_database(db_path)
    image_key = store_image(
        conn,
        {
            "date_taken": "2024-03-01",
            "filename": "probe.jpg",
            "rating": 4,
            "id": "probe-id",
        },
    )
    store_image_description(
        conn,
        {
            "image_key": image_key,
            "image_type": "catalog",
            "summary": "probe-summary",
            "best_perspective": "street",
            "perspectives": {},
            "composition": {},
            "technical": {},
            "subjects": [],
            "model_used": "test",
            "described_at": "2024-03-01T12:00:00",
        },
    )
    conn.close()

    monkeypatch.setattr("utils.db.LIBRARY_DB", db_path)
    app = create_app()
    return app.test_client(), image_key


def test_catalog_analyzed_filter_and_embedded_description(catalog_analyzed_client):
    client, image_key = catalog_analyzed_client

    resp = client.get("/api/images/catalog?analyzed=true")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total"] >= 1
    keys = {img["key"] for img in data["images"]}
    assert image_key in keys
    probe = next(img for img in data["images"] if img["key"] == image_key)
    assert probe["ai_analyzed"] is True
    assert probe["description_summary"] == "probe-summary"

    resp = client.get("/api/images/catalog?analyzed=false")
    assert resp.status_code == 200
    data = resp.get_json()
    assert all(img["key"] != image_key for img in data["images"])

    resp = client.get("/api/images/catalog")
    assert resp.status_code == 200
    data = resp.get_json()
    probe = next(img for img in data["images"] if img["key"] == image_key)
    assert probe["ai_analyzed"] is True
    assert probe["description_summary"] == "probe-summary"


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


def test_catalog_posted_filter_true(catalog_client):
    resp = catalog_client.get("/api/images/catalog?posted=true")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total"] == 1
    assert len(data["images"]) == 1
    assert data["images"][0]["instagram_posted"] is True
    assert data["images"][0]["filename"] == "low.jpg"


def test_catalog_posted_filter_false(catalog_client):
    resp = catalog_client.get("/api/images/catalog?posted=false")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total"] == 1
    assert len(data["images"]) == 1
    assert data["images"][0]["instagram_posted"] is False
    assert data["images"][0]["filename"] == "high.jpg"


@pytest.fixture
def legacy_catalog_client(tmp_path, monkeypatch):
    """Library DB with an older `images` table missing catalog-query columns."""
    db_path = str(tmp_path / "legacy_library.db")
    raw = sqlite3.connect(db_path)
    raw.execute(
        """
        CREATE TABLE images (
            key TEXT PRIMARY KEY,
            id TEXT,
            filename TEXT,
            filepath TEXT,
            date_taken TEXT,
            rating INTEGER DEFAULT 0
        )
        """
    )
    raw.execute(
        """
        CREATE TABLE image_descriptions (
            image_key TEXT PRIMARY KEY,
            image_type TEXT NOT NULL,
            summary TEXT DEFAULT '',
            composition TEXT DEFAULT '{}',
            perspectives TEXT DEFAULT '{}',
            technical TEXT DEFAULT '{}',
            subjects TEXT DEFAULT '[]',
            best_perspective TEXT DEFAULT '',
            model_used TEXT DEFAULT '',
            described_at TEXT
        )
        """
    )
    raw.execute(
        "INSERT INTO images (key, id, filename, filepath, date_taken, rating) VALUES (?,?,?,?,?,?)",
        ("2024-01-10_x.jpg", "1", "x.jpg", "/tmp/x.jpg", "2024-01-10T12:00:00", 4),
    )
    raw.commit()
    raw.close()

    monkeypatch.setattr("utils.db.LIBRARY_DB", db_path)
    app = create_app()
    return app.test_client()


def test_catalog_legacy_db_missing_columns_returns_200(legacy_catalog_client):
    """Regression: query_catalog_images must not 500 when legacy rows lack new columns."""
    resp = legacy_catalog_client.get("/api/images/catalog?limit=50&offset=0")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total"] == 1
    assert len(data["images"]) == 1
    assert data["images"][0]["filename"] == "x.jpg"
