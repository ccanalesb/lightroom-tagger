"""Integration tests for Instagram image API endpoints (read-seam migration pins)."""

from __future__ import annotations

import json

import pytest
from app import create_app

from lightroom_tagger.core.database import (
    init_database,
    store_image_description,
    store_instagram_dump_media,
    store_match,
)


def _seed_instagram_library(conn) -> None:
    store_instagram_dump_media(
        conn,
        {
            "media_key": "202405/aaa",
            "file_path": "/dump/media/posts/202405/aaa.jpg",
            "filename": "aaa.jpg",
            "date_folder": "202405",
            "caption": "cap-a",
            "created_at": "2024-05-01T10:00:00",
            "added_at": "2024-05-02T11:00:00",
            "post_url": "https://example/p/a",
            "image_hash": "hash-a",
            "processed": False,
            "exif_data": {"Make": "Test"},
        },
    )
    store_instagram_dump_media(
        conn,
        {
            "media_key": "202406/bbb",
            "file_path": "/dump/media/archived_posts/202406/bbb.jpg",
            "filename": "bbb.jpg",
            "date_folder": "202406",
            "caption": "cap-b",
            "created_at": "2024-06-01T10:00:00",
            "added_at": "2024-06-02T11:00:00",
            "post_url": "https://example/p/b",
            "image_hash": "hash-b",
            "processed": True,
            "matched_catalog_key": "cat-b",
            "exif_data": None,
        },
    )
    store_image_description(
        conn,
        {
            "image_key": "202405/aaa",
            "image_type": "instagram",
            "summary": "ai-summary-a",
            "best_perspective": "street",
            "perspectives": {},
            "composition": {},
            "technical": {},
            "subjects": [],
            "model_used": "test",
            "described_at": "2024-05-03T12:00:00",
        },
    )
    store_match(
        conn,
        {
            "catalog_key": "cat-x",
            "insta_key": "202405/aaa",
            "total_score": 0.6,
            "model_used": "model-a",
        },
    )
    store_match(
        conn,
        {
            "catalog_key": "cat-y",
            "insta_key": "202405/aaa",
            "total_score": 0.85,
            "model_used": "model-b",
        },
    )
    conn.commit()


@pytest.fixture
def instagram_client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "library.db")
    conn = init_database(db_path)
    _seed_instagram_library(conn)
    conn.close()

    monkeypatch.setattr("utils.db.LIBRARY_DB", db_path)
    app = create_app()
    return app.test_client()


def test_list_instagram_images_response_pin(instagram_client):
    resp = instagram_client.get("/api/images/instagram?limit=50&offset=0")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total"] == 2
    assert data["pagination"] == {
        "offset": 0,
        "limit": 50,
        "current_page": 1,
        "total_pages": 1,
        "has_more": False,
    }

    by_key = {img["key"]: img for img in data["images"]}
    assert set(by_key) == {"202405/aaa", "202406/bbb"}

    a = by_key["202405/aaa"]
    assert a["instagram_folder"] == "202405"
    assert a["source_folder"] == "posts"
    assert a["description"] == "ai-summary-a"
    # Pins pre-seam behavior: the old blueprint's matches query referenced a
    # non-existent ``score`` column, always raised OperationalError, and was
    # swallowed -> model/score always empty. Migration preserves this.
    assert a["matched_model"] is None
    assert a["match_score"] is None
    assert a["processed"] is False
    assert a["exif_data"] == {"Make": "Test"}

    b = by_key["202406/bbb"]
    assert b["instagram_folder"] == "202406"
    assert b["source_folder"] == "archived_posts"
    assert b["description"] == ""
    assert b["matched_model"] is None
    assert b["match_score"] is None
    assert b["processed"] is True
    assert b["matched_catalog_key"] == "cat-b"


def test_list_instagram_images_date_folder_filter(instagram_client):
    resp = instagram_client.get("/api/images/instagram?date_folder=202405")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total"] == 1
    assert data["images"][0]["key"] == "202405/aaa"


def test_list_instagram_images_sort_oldest(instagram_client):
    resp = instagram_client.get("/api/images/instagram?sort_by_date=oldest")
    assert resp.status_code == 200
    keys = [img["key"] for img in resp.get_json()["images"]]
    assert keys == ["202405/aaa", "202406/bbb"]


def test_get_instagram_months(instagram_client):
    resp = instagram_client.get("/api/images/instagram/months")
    assert resp.status_code == 200
    assert resp.get_json() == {"months": ["202406", "202405"]}


def test_list_dump_media_unfiltered(instagram_client):
    resp = instagram_client.get("/api/images/dump-media")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total"] == 2
    by_key = {row["media_key"]: row for row in data["media"]}
    assert by_key["202405/aaa"]["processed"] == 0
    assert by_key["202406/bbb"]["processed"] == 1
    assert isinstance(by_key["202405/aaa"]["exif_data"], str)
    assert json.loads(by_key["202405/aaa"]["exif_data"]) == {"Make": "Test"}


@pytest.mark.parametrize(
    ("query", "expected_keys"),
    [
        ("processed=true", ["202406/bbb"]),
        ("processed=false", ["202405/aaa"]),
        ("matched=true", ["202406/bbb"]),
        ("matched=false", ["202405/aaa"]),
    ],
)
def test_list_dump_media_filters(instagram_client, query, expected_keys):
    resp = instagram_client.get(f"/api/images/dump-media?{query}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total"] == len(expected_keys)
    assert [row["media_key"] for row in data["media"]] == expected_keys


def test_get_instagram_image_detail(instagram_client):
    resp = instagram_client.get("/api/images/instagram/202405/aaa")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["image_type"] == "instagram"
    assert data["key"] == "202405/aaa"
    assert data["ai_analyzed"] is True
    assert data["description_summary"] == "ai-summary-a"
    assert data["instagram_folder"] == "202405"
    assert data["source_folder"] == "posts"


def test_get_instagram_image_detail_not_found(instagram_client):
    resp = instagram_client.get("/api/images/instagram/missing-key")
    assert resp.status_code == 404
