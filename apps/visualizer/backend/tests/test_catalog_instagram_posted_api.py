"""PATCH /api/images/catalog/<key>/instagram-posted — manual posted toggle."""

from __future__ import annotations

import os
import tempfile

import pytest
from app import create_app
from lightroom_tagger.core.database import get_image, init_database, store_image


def _make_client(db_path: str):
    import config
    import utils.db as db_utils

    config.LIBRARY_DB = db_path
    db_utils.LIBRARY_DB = db_path
    return create_app().test_client(), db_path


@pytest.fixture
def catalog_posted_client(tmp_path):
    db_path = str(tmp_path / "library.db")
    conn = init_database(db_path)
    store_image(
        conn,
        {
            "date_taken": "2024-06-01",
            "filename": "photo.jpg",
            "instagram_posted": False,
        },
    )
    conn.close()
    client, _ = _make_client(db_path)
    return client, db_path, "2024-06-01_photo.jpg"


def test_patch_instagram_posted_sets_flag(catalog_posted_client):
    client, db_path, key = catalog_posted_client
    resp = client.patch(
        f"/api/images/catalog/{key}/instagram-posted",
        json={"posted": True},
    )
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["key"] == key
    assert payload["instagram_posted"] is True

    db = init_database(db_path)
    img = get_image(db, key)
    db.close()
    assert img is not None
    assert img["instagram_posted"] is True


def test_patch_instagram_posted_clears_flag(catalog_posted_client):
    client, db_path, key = catalog_posted_client
    client.patch(f"/api/images/catalog/{key}/instagram-posted", json={"posted": True})
    resp = client.patch(
        f"/api/images/catalog/{key}/instagram-posted",
        json={"posted": False},
    )
    assert resp.status_code == 200
    assert resp.get_json()["instagram_posted"] is False

    db = init_database(db_path)
    img = get_image(db, key)
    db.close()
    assert img is not None
    assert img["instagram_posted"] is False


def test_patch_instagram_posted_missing_image_returns_404(catalog_posted_client):
    client, _db_path, _key = catalog_posted_client
    resp = client.patch(
        "/api/images/catalog/no-such-key/instagram-posted",
        json={"posted": True},
    )
    assert resp.status_code == 404


def test_patch_instagram_posted_requires_boolean(catalog_posted_client):
    client, _db_path, key = catalog_posted_client
    resp = client.patch(
        f"/api/images/catalog/{key}/instagram-posted",
        json={"posted": "yes"},
    )
    assert resp.status_code == 400


def test_validate_match_still_sets_instagram_posted():
    """Auto-write from match validation remains until the next #218 slice."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        db = init_database(db_path)
        db.execute(
            "INSERT INTO images (key, filename, filepath, date_taken) VALUES (?, ?, ?, ?)",
            ("cat_001", "photo.jpg", "/fake/photo.jpg", "2024-01-15"),
        )
        db.execute(
            "INSERT INTO instagram_dump_media (media_key, filename, file_path, created_at) "
            "VALUES (?, ?, ?, ?)",
            ("ig_001", "insta.jpg", "/fake/insta.jpg", "2024-01-15"),
        )
        db.execute(
            "INSERT INTO matches (catalog_key, insta_key, total_score, vision_result) "
            "VALUES (?, ?, ?, ?)",
            ("cat_001", "ig_001", 0.85, "SAME"),
        )
        db.commit()
        db.close()

        client, _ = _make_client(db_path)
        resp = client.patch("/api/images/matches/cat_001/ig_001/validate")
        assert resp.status_code == 200

        db = init_database(db_path)
        img = get_image(db, "cat_001")
        db.close()
        assert img is not None
        assert img["instagram_posted"] is True
