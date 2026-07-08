"""Response pins for matches API (read-seam migration guard)."""

import os
import tempfile

from lightroom_tagger.core.database import init_database

_LIST_MATCHES_PIN = {
    "match_groups": [
        {
            "all_rejected": False,
            "best_score": 0.88,
            "candidate_count": 1,
            "candidates": [
                {
                    "catalog_description": None,
                    "catalog_image": {
                        "analyzed_at": None,
                        "aperture": "",
                        "camera_make": "",
                        "camera_model": "",
                        "caption": "",
                        "catalog_path": "",
                        "color_label": "",
                        "copyright": "",
                        "date_taken": "2024-06-15T10:00:00",
                        "description": "",
                        "exif": None,
                        "file_size": None,
                        "filename": "pin.jpg",
                        "filepath": "/fake/pin.jpg",
                        "focal_length": "",
                        "gps_latitude": None,
                        "gps_longitude": None,
                        "height": None,
                        "id": None,
                        "image_hash": None,
                        "instagram_index": 0,
                        "instagram_post_date": None,
                        "instagram_posted": False,
                        "instagram_url": None,
                        "iso": "",
                        "key": "cat_pin",
                        "keywords": [],
                        "lens": "",
                        "phash": None,
                        "pick": 0,
                        "rating": 0,
                        "shutter_speed": "",
                        "title": "",
                        "width": None,
                    },
                    "catalog_key": "cat_pin",
                    "desc_similarity": 0.8,
                    "insta_description": None,
                    "insta_key": "ig/pin",
                    "instagram_image": {
                        "caption": None,
                        "crawled_at": None,
                        "created_at": "2024-06-20T12:00:00",
                        "date_folder": "202406",
                        "description": "",
                        "exif_data": None,
                        "filename": "ig.jpg",
                        "image_hash": None,
                        "image_index": 1,
                        "instagram_folder": "202406",
                        "key": "ig/pin",
                        "local_path": "/fake/ig.jpg",
                        "matched_catalog_key": None,
                        "matched_model": "test-model",
                        "post_url": None,
                        "processed": False,
                        "source_folder": "unknown",
                        "total_in_post": 1,
                    },
                    "instagram_key": "ig/pin",
                    "matched_at": "2024-06-21T08:00:00",
                    "model_used": "test-model",
                    "phash_distance": 2,
                    "phash_score": 0.9,
                    "rank": 1,
                    "score": 0.88,
                    "total_score": 0.88,
                    "validated_at": None,
                    "vision_reasoning": None,
                    "vision_result": "SAME",
                    "vision_score": 0.95,
                }
            ],
            "has_validated": False,
            "instagram_image": {
                "caption": None,
                "crawled_at": None,
                "created_at": "2024-06-20T12:00:00",
                "date_folder": "202406",
                "description": "",
                "exif_data": None,
                "filename": "ig.jpg",
                "image_hash": None,
                "image_index": 1,
                "instagram_folder": "202406",
                "key": "ig/pin",
                "local_path": "/fake/ig.jpg",
                "matched_catalog_key": None,
                "matched_model": "test-model",
                "post_url": None,
                "processed": False,
                "source_folder": "unknown",
                "total_in_post": 1,
            },
            "instagram_key": "ig/pin",
        }
    ],
    "matches": [
        {
            "catalog_description": None,
            "catalog_image": {
                "analyzed_at": None,
                "aperture": "",
                "camera_make": "",
                "camera_model": "",
                "caption": "",
                "catalog_path": "",
                "color_label": "",
                "copyright": "",
                "date_taken": "2024-06-15T10:00:00",
                "description": "",
                "exif": None,
                "file_size": None,
                "filename": "pin.jpg",
                "filepath": "/fake/pin.jpg",
                "focal_length": "",
                "gps_latitude": None,
                "gps_longitude": None,
                "height": None,
                "id": None,
                "image_hash": None,
                "instagram_index": 0,
                "instagram_post_date": None,
                "instagram_posted": False,
                "instagram_url": None,
                "iso": "",
                "key": "cat_pin",
                "keywords": [],
                "lens": "",
                "phash": None,
                "pick": 0,
                "rating": 0,
                "shutter_speed": "",
                "title": "",
                "width": None,
            },
            "catalog_key": "cat_pin",
            "desc_similarity": 0.8,
            "insta_description": None,
            "insta_key": "ig/pin",
            "instagram_image": {
                "caption": None,
                "crawled_at": None,
                "created_at": "2024-06-20T12:00:00",
                "date_folder": "202406",
                "description": "",
                "exif_data": None,
                "filename": "ig.jpg",
                "image_hash": None,
                "image_index": 1,
                "instagram_folder": "202406",
                "key": "ig/pin",
                "local_path": "/fake/ig.jpg",
                "matched_catalog_key": None,
                "matched_model": "test-model",
                "post_url": None,
                "processed": False,
                "source_folder": "unknown",
                "total_in_post": 1,
            },
            "instagram_key": "ig/pin",
            "matched_at": "2024-06-21T08:00:00",
            "model_used": "test-model",
            "phash_distance": 2,
            "phash_score": 0.9,
            "rank": 1,
            "score": 0.88,
            "total_score": 0.88,
            "validated_at": None,
            "vision_reasoning": None,
            "vision_result": "SAME",
            "vision_score": 0.95,
        }
    ],
    "total": 1,
    "total_groups": 1,
    "total_matches": 1,
}


def _make_client(db_path):
    import config
    import utils.db as db_utils

    config.LIBRARY_DB = db_path
    db_utils.LIBRARY_DB = db_path
    from app import create_app

    return create_app().test_client()


def _seed_pin_fixture(db):
    db.execute(
        "INSERT INTO images (key, filename, filepath, date_taken) VALUES (?, ?, ?, ?)",
        ("cat_pin", "pin.jpg", "/fake/pin.jpg", "2024-06-15T10:00:00"),
    )
    db.execute(
        "INSERT INTO instagram_dump_media (media_key, filename, file_path, date_folder, processed, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("ig/pin", "ig.jpg", "/fake/ig.jpg", "202406", 0, "2024-06-20T12:00:00"),
    )
    db.execute(
        "INSERT INTO matches (catalog_key, insta_key, phash_distance, phash_score, desc_similarity, "
        "vision_result, vision_score, total_score, matched_at, rank, model_used) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "cat_pin",
            "ig/pin",
            2,
            0.9,
            0.8,
            "SAME",
            0.95,
            0.88,
            "2024-06-21T08:00:00",
            1,
            "test-model",
        ),
    )
    db.commit()


def test_list_matches_response_pinned():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        db = init_database(db_path)
        _seed_pin_fixture(db)
        db.close()

        client = _make_client(db_path)
        resp = client.get("/api/images/matches?limit=50&offset=0")
        assert resp.status_code == 200
        assert resp.get_json() == _LIST_MATCHES_PIN


def test_validate_match_response_pinned():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        db = init_database(db_path)
        _seed_pin_fixture(db)
        db.close()

        client = _make_client(db_path)
        resp = client.patch("/api/images/matches/cat_pin/ig/pin/validate")
        assert resp.status_code == 200
        assert resp.get_json() == {"validated": True}
        assert resp.data == b'{"validated":true}\n'


def test_reject_match_response_pinned():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        db = init_database(db_path)
        _seed_pin_fixture(db)
        db.close()

        client = _make_client(db_path)
        resp = client.patch("/api/images/matches/cat_pin/ig/pin/reject")
        assert resp.status_code == 200
        assert resp.get_json() == {"rejected": True}
        assert resp.data == b'{"rejected":true}\n'
