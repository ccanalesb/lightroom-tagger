"""Contract tests for Catalog pydantic models."""

from __future__ import annotations

import pytest
from app import create_app

from api.images.catalog import _rows_to_catalog_api_images
from api.schemas.catalog import (
    CatalogImage,
    CatalogListResponse,
    CatalogMonthsResponse,
    CatalogSimilarityGroupsResponse,
    ImageView,
    validate_catalog_image,
    validate_image_view,
)
from lightroom_tagger.core.database import init_database, store_image


@pytest.fixture
def catalog_contract_client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "library.db")
    conn = init_database(db_path)
    store_image(
        conn,
        {
            "date_taken": "2024-01-10",
            "filename": "low.jpg",
            "rating": 3,
            "id": "100",
            "instagram_posted": True,
        },
    )
    conn.close()
    monkeypatch.setattr("utils.db.LIBRARY_DB", db_path)
    return create_app().test_client(), db_path


def test_catalog_image_round_trip_from_list_handler(catalog_contract_client):
    client, _db_path = catalog_contract_client
    payload = client.get("/api/images/catalog").get_json()
    assert payload is not None

    validated = CatalogListResponse.model_validate(payload)
    assert validated.total >= 1
    assert len(validated.images) >= 1

    row = validate_catalog_image(payload["images"][0])
    assert CatalogImage.model_validate(row).key


def test_catalog_months_round_trip(catalog_contract_client):
    client, _db_path = catalog_contract_client
    payload = client.get("/api/images/catalog/months").get_json()
    validated = CatalogMonthsResponse.model_validate(payload)
    assert isinstance(validated.months, list)


def test_image_view_round_trip_from_catalog_detail_builder(catalog_contract_client):
    client, _db_path = catalog_contract_client
    list_payload = client.get("/api/images/catalog").get_json()
    image_key = list_payload["images"][0]["key"]
    payload = client.get(f"/api/images/catalog/{image_key}").get_json()
    validated = ImageView.model_validate(validate_image_view(payload))
    assert validated.image_type == "catalog"
    assert validated.key == image_key


def test_catalog_similarity_groups_response_accepts_empty_list(tmp_path, monkeypatch):
    db_path = str(tmp_path / "library.db")
    init_database(db_path)
    monkeypatch.setattr("utils.db.LIBRARY_DB", db_path)
    client = create_app().test_client()
    payload = client.get("/api/images/catalog-similarity-groups").get_json()
    validated = CatalogSimilarityGroupsResponse.model_validate(payload)
    assert validated.total == 0
    assert validated.items == []


def test_rows_to_catalog_api_images_round_trip(catalog_contract_client):
    client, db_path = catalog_contract_client
    from lightroom_tagger.core.database import init_database, query_catalog_images

    conn = init_database(db_path)
    try:
        rows, _total = query_catalog_images(conn)
        images = _rows_to_catalog_api_images(rows, None)
        assert images
        validated = CatalogImage.model_validate(validate_catalog_image(images[0]))
        assert validated.filename
    finally:
        conn.close()


def test_catalog_image_rejects_wrong_shape():
    with pytest.raises(Exception):
        validate_catalog_image({"bogus": 1})


def test_catalog_list_accepts_null_metadata_fields(tmp_path, monkeypatch):
    """Regression: catalog rows with explicit null columns must round-trip."""
    db_path = str(tmp_path / "library.db")
    conn = init_database(db_path)
    store_image(
        conn,
        {
            "date_taken": None,
            "filename": None,
            "rating": None,
            "id": "200",
            "caption": None,
            "title": None,
            "description": None,
            "copyright": None,
            "aperture": None,
            "camera_make": None,
            "camera_model": None,
            "focal_length": None,
            "iso": None,
            "lens": None,
            "shutter_speed": None,
            "catalog_path": None,
        },
    )
    conn.close()
    monkeypatch.setattr("utils.db.LIBRARY_DB", db_path)
    client = create_app().test_client()

    response = client.get("/api/images/catalog")
    assert response.status_code == 200
    payload = response.get_json()
    validated = CatalogListResponse.model_validate(payload)
    null_row = next(img for img in validated.images if img.id == 200)
    assert null_row.caption is None
    assert null_row.filename is None
    assert null_row.aperture is None
