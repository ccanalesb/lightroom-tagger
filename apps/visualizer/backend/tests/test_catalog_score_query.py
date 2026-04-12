"""Tests for GET /api/images/catalog score_perspective / sort_by_score / min_score."""

from datetime import datetime, timezone

import pytest
from app import create_app

from lightroom_tagger.core.database import init_database, insert_image_score, store_image


@pytest.fixture
def empty_catalog_client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "library.db")
    init_database(db_path)
    monkeypatch.setattr("utils.db.LIBRARY_DB", db_path)
    return create_app().test_client()


@pytest.fixture
def catalog_score_ordered_client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "library.db")
    conn = init_database(db_path)

    conn.execute(
        """
        INSERT INTO perspectives (slug, display_name, description, prompt_markdown)
        VALUES ('api_cat_score', 'API cat', '', '')
        """
    )
    conn.commit()

    key_lo = store_image(
        conn,
        {
            "date_taken": "2024-01-01",
            "filename": "lo.jpg",
            "rating": 2,
            "id": "s1",
        },
    )
    key_hi = store_image(
        conn,
        {
            "date_taken": "2024-12-01",
            "filename": "hi.jpg",
            "rating": 5,
            "id": "s2",
        },
    )

    ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    slug = "api_cat_score"
    insert_image_score(
        conn,
        {
            "image_key": key_lo,
            "image_type": "catalog",
            "perspective_slug": slug,
            "score": 2,
            "prompt_version": "v1",
            "scored_at": ts,
            "is_current": 1,
        },
    )
    insert_image_score(
        conn,
        {
            "image_key": key_hi,
            "image_type": "catalog",
            "perspective_slug": slug,
            "score": 9,
            "prompt_version": "v1",
            "scored_at": ts,
            "is_current": 1,
        },
    )
    conn.commit()
    # Ensure WAL is flushed so a new connection in the Flask client sees image_scores rows.
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()

    monkeypatch.setattr("utils.db.LIBRARY_DB", db_path)
    app = create_app()
    return app.test_client(), slug, key_hi, key_lo


def test_sort_by_score_without_perspective_400(empty_catalog_client):
    resp = empty_catalog_client.get("/api/images/catalog?sort_by_score=desc")
    assert resp.status_code == 400
    assert "score_perspective" in resp.get_json().get("error", "").lower()


def test_catalog_score_perspective_sort_desc_matches_db(catalog_score_ordered_client):
    client, slug, key_hi, key_lo = catalog_score_ordered_client
    resp = client.get(
        f"/api/images/catalog?score_perspective={slug}&sort_by_score=desc&limit=50"
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total"] == 2
    keys = [img["key"] for img in data["images"]]
    assert keys == [key_hi, key_lo]
    assert data["images"][0]["catalog_perspective_score"] == 9
    assert data["images"][0]["catalog_score_perspective"] == slug
    assert data["images"][1]["catalog_perspective_score"] == 2
