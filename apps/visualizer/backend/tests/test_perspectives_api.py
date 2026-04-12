"""Tests for ``/api/perspectives`` REST routes."""
from __future__ import annotations

import json

import pytest

from lightroom_tagger.core.database import init_database


@pytest.fixture
def library_db_path(tmp_path, monkeypatch):
    """Temp library DB with seeded perspectives (factory seed from prompts)."""
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


def test_get_perspectives_list_includes_street(client):
    response = client.get("/api/perspectives/")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    slugs = {row["slug"] for row in data}
    assert "street" in slugs
    for row in data:
        assert "prompt_markdown" not in row
        assert set(row.keys()) >= {
            "id",
            "slug",
            "display_name",
            "description",
            "active",
            "source_filename",
            "updated_at",
        }


def test_put_then_get_prompt_markdown_round_trip(client):
    body = {"prompt_markdown": "# test\nbody"}
    put = client.put(
        "/api/perspectives/street",
        data=json.dumps(body),
        content_type="application/json",
    )
    assert put.status_code == 200
    get_one = client.get("/api/perspectives/street")
    assert get_one.status_code == 200
    assert get_one.get_json()["prompt_markdown"] == "# test\nbody"


def test_reset_default_missing_file_returns_404(client, library_db_path):
    conn = init_database(str(library_db_path))
    conn.execute(
        "UPDATE perspectives SET source_filename = ? WHERE slug = ?",
        ("___missing_reset_file___.md", "street"),
    )
    conn.commit()
    conn.close()

    response = client.post("/api/perspectives/street/reset-default")
    assert response.status_code == 404
    assert response.get_json()["error"] == "no default file"
