"""Tests for ``/api/scores`` read-only routes."""
from __future__ import annotations

import pytest

from lightroom_tagger.core.database import init_database, insert_image_score


@pytest.fixture
def library_db_path(tmp_path, monkeypatch):
    db_path = tmp_path / "library.db"
    monkeypatch.setattr("utils.db.LIBRARY_DB", str(db_path))
    conn = init_database(str(db_path))
    conn.close()
    return db_path


@pytest.fixture
def client(library_db_path, monkeypatch):
    monkeypatch.setattr("utils.db.LIBRARY_DB", str(library_db_path))
    from app import create_app

    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_current_scores_empty_returns_200_with_empty_list(client):
    r = client.get("/api/scores/some%2Fkey.jpg")
    assert r.status_code == 200
    data = r.get_json()
    assert data["image_key"] == "some/key.jpg"
    assert data["image_type"] == "catalog"
    assert data["current"] == []


def test_current_scores_only_includes_is_current_rows(client, library_db_path):
    image_key = "nested/path/img.jpg"
    conn = init_database(str(library_db_path))
    ts = "2024-01-01T00:00:00+00:00"
    insert_image_score(
        conn,
        {
            "image_key": image_key,
            "image_type": "catalog",
            "perspective_slug": "street",
            "score": 4,
            "prompt_version": "street:v1",
            "scored_at": ts,
            "is_current": 0,
        },
    )
    insert_image_score(
        conn,
        {
            "image_key": image_key,
            "image_type": "catalog",
            "perspective_slug": "street",
            "score": 9,
            "prompt_version": "street:v2",
            "scored_at": ts,
            "is_current": 1,
        },
    )
    conn.commit()
    conn.close()

    enc = "nested%2Fpath%2Fimg.jpg"
    r = client.get(f"/api/scores/{enc}")
    assert r.status_code == 200
    rows = r.get_json()["current"]
    assert len(rows) == 1
    assert rows[0]["score"] == 9
    assert rows[0]["is_current"] is True
    assert rows[0]["prompt_version"] == "street:v2"


def test_history_without_perspective_slug_returns_400(client):
    r = client.get("/api/scores/foo.jpg/history")
    assert r.status_code == 400
    assert "error" in r.get_json()


def test_history_returns_versions_newest_scored_at_first(client, library_db_path):
    image_key = "h.jpg"
    slug = "street"
    conn = init_database(str(library_db_path))
    insert_image_score(
        conn,
        {
            "image_key": image_key,
            "image_type": "catalog",
            "perspective_slug": slug,
            "score": 2,
            "prompt_version": "a",
            "scored_at": "2020-01-01T00:00:00+00:00",
            "is_current": 0,
        },
    )
    insert_image_score(
        conn,
        {
            "image_key": image_key,
            "image_type": "catalog",
            "perspective_slug": slug,
            "score": 7,
            "prompt_version": "b",
            "scored_at": "2025-01-01T00:00:00+00:00",
            "is_current": 1,
        },
    )
    conn.commit()
    conn.close()

    r = client.get(f"/api/scores/{image_key}/history?perspective_slug={slug}")
    assert r.status_code == 200
    data = r.get_json()
    assert data["perspective_slug"] == slug
    hist = data["history"]
    assert len(hist) == 2
    assert hist[0]["prompt_version"] == "b"
    assert hist[0]["scored_at"] == "2025-01-01T00:00:00+00:00"
    assert hist[1]["prompt_version"] == "a"
