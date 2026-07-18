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
            "optional",
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


def test_list_and_detail_expose_optional(client):
    lst = client.get("/api/perspectives/")
    assert lst.status_code == 200
    for row in lst.get_json():
        assert "optional" in row
        assert isinstance(row["optional"], bool)

    detail = client.get("/api/perspectives/street")
    assert detail.status_code == 200
    assert "optional" in detail.get_json()


def test_create_derives_optional_from_markdown_marker(client):
    body = {
        "slug": "excusable_lens",
        "display_name": "Excusable Lens",
        "prompt_markdown": "<!-- optional: true -->\n# Lens\nEvaluate.",
    }
    resp = client.post(
        "/api/perspectives/",
        data=json.dumps(body),
        content_type="application/json",
    )
    assert resp.status_code == 201
    assert resp.get_json()["optional"] is True


def test_create_hyphenated_slug(client):
    body = {
        "slug": "fresh-kebab-case-slug",
        "display_name": "Fresh Kebab",
        "prompt_markdown": "# Env\nEvaluate.",
    }
    resp = client.post(
        "/api/perspectives/",
        data=json.dumps(body),
        content_type="application/json",
    )
    assert resp.status_code == 201
    assert resp.get_json()["slug"] == "fresh-kebab-case-slug"


def test_edit_markdown_marker_flips_optional(client):
    # Adding the marker via an edit flips optional on...
    put = client.put(
        "/api/perspectives/street",
        data=json.dumps({"prompt_markdown": "<!-- optional: true -->\n# Street"}),
        content_type="application/json",
    )
    assert put.status_code == 200
    assert put.get_json()["optional"] is True

    # ...and removing it flips optional back off.
    put2 = client.put(
        "/api/perspectives/street",
        data=json.dumps({"prompt_markdown": "# Street\nno marker"}),
        content_type="application/json",
    )
    assert put2.status_code == 200
    assert put2.get_json()["optional"] is False


def test_reset_default_re_derives_optional_from_file_marker(
    client, library_db_path, tmp_path, monkeypatch
):
    # A default file that carries the optional marker.
    fake_root = tmp_path / "repo"
    persp_dir = fake_root / "prompts" / "perspectives"
    persp_dir.mkdir(parents=True)
    (persp_dir / "street.md").write_text(
        "<!-- optional: true -->\n# Street\nEvaluate geometry.\n", encoding="utf-8"
    )
    monkeypatch.setattr("api.perspectives._REPO_ROOT", str(fake_root))

    resp = client.post("/api/perspectives/street/reset-default")
    assert resp.status_code == 200
    assert resp.get_json()["optional"] is True


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
