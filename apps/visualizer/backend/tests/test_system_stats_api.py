"""Tests for ``GET /api/stats`` library-DB statistics contract."""

from __future__ import annotations

from app import create_app
from lightroom_tagger.core.database import (
    init_database,
    store_image,
    store_instagram_dump_media,
    store_match,
    update_instagram_status,
)


def _client_for_library(tmp_path, monkeypatch):
    import config
    import utils.db as db_utils

    db_path = tmp_path / "library.db"
    lib = init_database(str(db_path))
    k1 = store_image(lib, {"date_taken": "2024-01-01", "filename": "a.jpg"})
    store_image(lib, {"date_taken": "2024-02-01", "filename": "b.jpg"})
    update_instagram_status(lib, k1, posted=True)
    store_instagram_dump_media(
        lib,
        {
            "media_key": "202401/111",
            "file_path": "/tmp/111.jpg",
            "date_folder": "202401",
        },
    )
    store_instagram_dump_media(
        lib,
        {
            "media_key": "202401/222",
            "file_path": "/tmp/222.jpg",
            "date_folder": "202401",
        },
    )
    store_match(
        lib,
        {"catalog_key": k1, "insta_key": "202401/111", "total_score": 0.8},
    )
    lib.close()

    monkeypatch.setattr(config, "LIBRARY_DB", str(db_path))
    monkeypatch.setattr(db_utils, "LIBRARY_DB", str(db_path))

    app = create_app()
    app.config["TESTING"] = True
    return app.test_client(), str(db_path)


def test_stats_returns_seeded_counts(tmp_path, monkeypatch) -> None:
    client, db_path = _client_for_library(tmp_path, monkeypatch)
    resp = client.get("/api/stats")
    assert resp.status_code == 200
    assert resp.json == {
        "catalog_images": 2,
        "instagram_images": 2,
        "posted_to_instagram": 1,
        "matches_found": 1,
        "db_path": db_path,
    }


def test_stats_404_when_library_missing(tmp_path, monkeypatch) -> None:
    import config
    import utils.db as db_utils

    missing = tmp_path / "missing.db"
    monkeypatch.setattr(config, "LIBRARY_DB", str(missing))
    monkeypatch.setattr(db_utils, "LIBRARY_DB", str(missing))

    app = create_app()
    app.config["TESTING"] = True
    resp = app.test_client().get("/api/stats")
    assert resp.status_code == 404
    assert resp.json == {"error": "Library database not found"}
