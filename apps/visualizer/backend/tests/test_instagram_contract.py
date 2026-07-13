"""Contract tests for Instagram pydantic models."""

from __future__ import annotations

import pytest
from app import create_app

from api.schemas.instagram import (
    InstagramImage,
    InstagramListResponse,
    InstagramMonthsResponse,
    validate_instagram_image,
)
from lightroom_tagger.core.database import init_database, store_instagram_dump_media


@pytest.fixture
def instagram_contract_client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "library.db")
    conn = init_database(db_path)
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
    conn.close()
    monkeypatch.setattr("utils.db.LIBRARY_DB", db_path)
    return create_app().test_client(), db_path


def test_instagram_list_response_round_trip(instagram_contract_client):
    client, _db_path = instagram_contract_client
    payload = client.get("/api/images/instagram").get_json()
    validated = InstagramListResponse.model_validate(payload)
    assert validated.total == 1
    assert validated.images[0].key == "202405/aaa"


def test_instagram_months_round_trip(instagram_contract_client):
    client, _db_path = instagram_contract_client
    payload = client.get("/api/images/instagram/months").get_json()
    validated = InstagramMonthsResponse.model_validate(payload)
    assert "202405" in validated.months


def test_instagram_image_round_trip_from_enricher(instagram_contract_client):
    client, _db_path = instagram_contract_client
    payload = client.get("/api/images/instagram").get_json()
    row = validate_instagram_image(payload["images"][0])
    validated = InstagramImage.model_validate(row)
    assert validated.instagram_folder == "202405"


def test_image_view_round_trip_from_instagram_detail_builder(instagram_contract_client):
    client, _db_path = instagram_contract_client
    from api.schemas.catalog import ImageView, validate_image_view

    payload = client.get("/api/images/instagram/202405/aaa").get_json()
    validated = ImageView.model_validate(validate_image_view(payload))
    assert validated.image_type == "instagram"
    assert validated.key == "202405/aaa"


def test_instagram_image_rejects_wrong_shape():
    with pytest.raises(Exception):
        validate_instagram_image({"key": "only-key"})
