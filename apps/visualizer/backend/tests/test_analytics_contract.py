"""Contract tests for Analytics pydantic models."""

from __future__ import annotations

import pytest
from app import create_app

from api.schemas.analytics import (
    CaptionStatsResponse,
    PostingFrequencyResponse,
    PostingHeatmapResponse,
    UnpostedCatalogItem,
    UnpostedCatalogResponse,
    validate_unposted_catalog_item,
)
from lightroom_tagger.core.database import init_database, store_image


@pytest.fixture
def analytics_contract_client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "library.db")
    conn = init_database(db_path)
    store_image(
        conn,
        {
            "date_taken": "2024-06-01",
            "filename": "solo.jpg",
            "rating": 3,
            "instagram_posted": False,
        },
    )
    conn.close()
    monkeypatch.setattr("utils.db.LIBRARY_DB", db_path)
    return create_app().test_client(), db_path


def test_posting_frequency_round_trip_from_handler(analytics_contract_client):
    client, _db_path = analytics_contract_client
    payload = client.get(
        "/api/analytics/posting-frequency",
        query_string={
            "date_from": "2024-01-01",
            "date_to": "2024-01-07",
            "granularity": "day",
        },
    ).get_json()
    assert payload is not None

    validated = PostingFrequencyResponse.model_validate(payload)
    assert isinstance(validated.buckets, list)
    assert validated.meta.timezone_assumption == "UTC"


def test_posting_heatmap_round_trip_from_handler(analytics_contract_client):
    client, _db_path = analytics_contract_client
    payload = client.get(
        "/api/analytics/posting-heatmap",
        query_string={
            "date_from": "2024-01-01",
            "date_to": "2024-01-07",
        },
    ).get_json()
    assert payload is not None

    validated = PostingHeatmapResponse.model_validate(payload)
    assert len(validated.cells) == 7 * 24
    assert validated.meta.timezone_assumption == "UTC"


def test_caption_stats_round_trip_from_handler(analytics_contract_client):
    client, _db_path = analytics_contract_client
    payload = client.get(
        "/api/analytics/caption-stats",
        query_string={
            "date_from": "2024-01-01",
            "date_to": "2024-01-07",
        },
    ).get_json()
    assert payload is not None

    validated = CaptionStatsResponse.model_validate(payload)
    assert validated.post_count >= 0
    assert validated.meta.timezone_assumption == "UTC"


def test_unposted_catalog_round_trip_from_handler(analytics_contract_client):
    client, _db_path = analytics_contract_client
    payload = client.get("/api/analytics/unposted-catalog").get_json()
    assert payload is not None

    validated = UnpostedCatalogResponse.model_validate(payload)
    assert validated.total >= 1
    assert len(validated.images) >= 1
    assert validated.pagination.limit is not None

    row = validate_unposted_catalog_item(payload["images"][0])
    assert UnpostedCatalogItem.model_validate(row).filename == "solo.jpg"


def test_unposted_catalog_item_rejects_wrong_shape():
    with pytest.raises(Exception):
        validate_unposted_catalog_item({"bogus": 1})
