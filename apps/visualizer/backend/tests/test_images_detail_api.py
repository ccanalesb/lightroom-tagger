"""Integration tests for the consolidated image detail endpoint.

``GET /api/images/<image_type>/<image_key>``
"""

from __future__ import annotations

import sqlite3

import pytest
from app import create_app

from lightroom_tagger.core.database import (
    init_database,
    insert_image_score,
    store_image,
    store_image_description,
    store_instagram_dump_media,
)


@pytest.fixture
def detail_client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "library.db")
    init_database(db_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    catalog_key = store_image(
        conn,
        {
            "date_taken": "2024-05-01",
            "filename": "probe.jpg",
            "rating": 4,
            "id": "probe-id",
            "keywords": ["street", "bw"],
            "title": "Probe title",
            "caption": "Probe caption",
            "copyright": "(c) tester",
            "instagram_posted": False,
        },
    )
    store_image_description(
        conn,
        {
            "image_key": catalog_key,
            "image_type": "catalog",
            "summary": "probe-summary",
            "best_perspective": "street",
            "perspectives": {"street": {"score_rationale": "nice"}},
            "composition": {},
            "technical": {},
            "subjects": [],
            "model_used": "test",
            "described_at": "2024-05-01T12:00:00",
        },
    )

    # Pick two active perspective slugs that ship with init_database.
    rows = conn.execute(
        "SELECT slug FROM perspectives WHERE active = 1 ORDER BY slug LIMIT 2"
    ).fetchall()
    assert len(rows) >= 2
    s0, s1 = str(rows[0]["slug"]), str(rows[1]["slug"])
    scored_at = "2024-05-02T12:00:00+00:00"
    for slug, score in ((s0, 8), (s1, 6)):
        insert_image_score(
            conn,
            {
                "image_key": catalog_key,
                "image_type": "catalog",
                "perspective_slug": slug,
                "score": score,
                "rationale": "because",
                "model_used": "test-model",
                "prompt_version": "v-test",
                "scored_at": scored_at,
                "is_current": 1,
            },
        )

    store_instagram_dump_media(
        conn,
        {
            "media_key": "ig-probe",
            "file_path": "/tmp/ig-probe.jpg",
            "filename": "ig-probe.jpg",
            "date_folder": "2024-05",
            "caption": "insta caption",
            "exif_data": None,
            "post_url": "https://example/p/abc",
            "image_hash": "hash",
        },
    )

    conn.commit()
    conn.close()

    monkeypatch.setattr("utils.db.LIBRARY_DB", db_path)
    app = create_app()
    return app.test_client(), catalog_key, s0, s1


def test_detail_catalog_returns_identity_and_available_perspectives(detail_client):
    client, catalog_key, s0, s1 = detail_client

    resp = client.get(f"/api/images/catalog/{catalog_key}")
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()

    assert data["image_type"] == "catalog"
    assert data["key"] == catalog_key
    assert data["filename"] == "probe.jpg"
    assert data["copyright"] == "(c) tester"
    assert data["ai_analyzed"] is True
    assert data["description_summary"] == "probe-summary"
    assert data["description_best_perspective"] == "street"

    # Identity aggregate: equal-weight mean of [8, 6] = 7.0.
    assert data["identity_aggregate_score"] == pytest.approx(7.0)
    assert data["identity_perspectives_covered"] == 2
    assert data["identity_eligible"] is True
    assert {p["perspective_slug"] for p in data["identity_per_perspective"]} == {s0, s1}

    # Perspective slug list sorted and deduped.
    assert data["available_score_perspectives"] == sorted([s0, s1])

    # No score_perspective passed → catalog-score fields null.
    assert data["catalog_perspective_score"] is None
    assert data["catalog_score_perspective"] is None


def test_detail_catalog_with_score_perspective_query(detail_client):
    client, catalog_key, s0, _ = detail_client

    resp = client.get(f"/api/images/catalog/{catalog_key}?score_perspective={s0}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["catalog_score_perspective"] == s0
    assert data["catalog_perspective_score"] == 8


def test_detail_instagram_has_empty_identity(detail_client):
    client, _catalog_key, _s0, _s1 = detail_client

    resp = client.get("/api/images/instagram/ig-probe")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["image_type"] == "instagram"
    assert data["key"] == "ig-probe"
    assert data["identity_aggregate_score"] is None
    assert data["identity_per_perspective"] == []
    assert data["available_score_perspectives"] == []
    assert data["catalog_perspective_score"] is None
    # Parity with ``_enrich_instagram_media`` so the detail modal renders
    # the same folder/source fields list tiles would have.
    assert data["instagram_folder"] == "2024-05"
    assert data["local_path"] == "/tmp/ig-probe.jpg"
    assert "source_folder" in data  # may be None for this fake file_path
    assert data["processed"] is False
    assert data["matched_catalog_key"] is None


def test_detail_404_for_unknown_key(detail_client):
    client, *_ = detail_client
    resp = client.get("/api/images/catalog/does-not-exist")
    assert resp.status_code == 404


def test_detail_400_for_invalid_image_type(detail_client):
    client, catalog_key, *_ = detail_client
    # Image type not in {catalog, instagram}. Because other static routes
    # (``/catalog``, ``/instagram``, ``/matches``, ``/dump-media``) would win
    # as prefixes, we use a two-segment URL with an unknown type.
    resp = client.get(f"/api/images/foo/{catalog_key}")
    assert resp.status_code == 400


def test_detail_400_for_instagram_score_perspective(detail_client):
    client, *_ = detail_client
    resp = client.get("/api/images/instagram/ig-probe?score_perspective=street")
    assert resp.status_code == 400


def test_detail_400_for_invalid_score_perspective_slug(detail_client):
    client, catalog_key, *_ = detail_client
    resp = client.get(f"/api/images/catalog/{catalog_key}?score_perspective=BAD SLUG")
    assert resp.status_code == 400
