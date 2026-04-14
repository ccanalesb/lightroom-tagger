"""Flask tests for ``/api/identity/*`` routes."""

from __future__ import annotations

import sqlite3

import pytest
from app import create_app

from lightroom_tagger.core.database import init_database, insert_image_score, store_image


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
    assert "total" in data
    assert isinstance(data["total"], int)
    assert "meta" in data
    assert "empty_state" in data


def test_suggestions_offset_changes_first_candidate(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "library.db")
    init_database(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT slug FROM perspectives WHERE active = 1 ORDER BY slug LIMIT 2"
    ).fetchall()
    assert len(rows) >= 2
    s0, s1 = str(rows[0]["slug"]), str(rows[1]["slug"])
    scored_at = "2024-09-01T12:00:00+00:00"
    for i, (day, sc) in enumerate(
        [
            ("2024-09-01", 9),
            ("2024-09-02", 8),
            ("2024-09-03", 7),
        ]
    ):
        k = store_image(
            conn,
            {
                "date_taken": day,
                "filename": f"api{i}.jpg",
                "instagram_posted": False,
            },
        )
        insert_image_score(
            conn,
            {
                "image_key": k,
                "image_type": "catalog",
                "perspective_slug": s0,
                "score": sc,
                "rationale": "",
                "model_used": "test-model",
                "prompt_version": "v-test",
                "scored_at": scored_at,
                "is_current": 1,
            },
        )
        insert_image_score(
            conn,
            {
                "image_key": k,
                "image_type": "catalog",
                "perspective_slug": s1,
                "score": sc,
                "rationale": "",
                "model_used": "test-model",
                "prompt_version": "v-test",
                "scored_at": scored_at,
                "is_current": 1,
            },
        )
    conn.commit()
    conn.close()

    monkeypatch.setattr("utils.db.LIBRARY_DB", db_path)
    app = create_app()
    client = app.test_client()

    r0 = client.get("/api/identity/suggestions?limit=1&offset=0")
    r1 = client.get("/api/identity/suggestions?limit=1&offset=1")
    assert r0.status_code == 200
    assert r1.status_code == 200
    data0 = r0.get_json()
    data1 = r1.get_json()
    assert data0 is not None and data1 is not None
    assert len(data0["candidates"]) == 1
    assert len(data1["candidates"]) == 1
    assert data0["candidates"][0]["image_key"] != data1["candidates"][0]["image_key"]
