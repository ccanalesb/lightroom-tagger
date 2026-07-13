"""Contract tests for Analytics pydantic models."""

from __future__ import annotations

import pytest

from api.schemas.analytics import (
    CaptionStatsResponse,
    PostingFrequencyResponse,
    PostingHeatmapResponse,
    UnpostedCatalogResponse,
)
from lightroom_tagger.core.database import init_database, store_image
from lightroom_tagger.core.posting_analytics import (
    get_caption_hashtag_stats,
    get_posting_frequency,
    get_posting_time_heatmap,
    query_unposted_catalog,
)


@pytest.fixture
def library_db(tmp_path):
    db_path = tmp_path / "library.db"
    conn = init_database(str(db_path))
    yield conn
    conn.close()


@pytest.fixture
def library_db_seeded(library_db):
    store_image(
        library_db,
        {
            "date_taken": "2024-06-01",
            "filename": "solo.jpg",
            "rating": 3,
            "instagram_posted": False,
        },
    )
    return library_db


def test_posting_frequency_response_round_trip(library_db):
    buckets, meta = get_posting_frequency(
        library_db,
        date_from="2024-01-01",
        date_to="2024-01-07",
        granularity="day",
    )
    validated = PostingFrequencyResponse.model_validate({"buckets": buckets, "meta": meta})

    assert len(validated.buckets) == 7
    assert validated.meta.timezone_assumption == "UTC"
    assert validated.meta.granularity == "day"


def test_posting_heatmap_response_round_trip(library_db):
    cells, meta = get_posting_time_heatmap(
        library_db,
        date_from="2024-01-01",
        date_to="2024-01-07",
    )
    validated = PostingHeatmapResponse.model_validate({"cells": cells, "meta": meta})

    assert len(validated.cells) == 7 * 24
    assert validated.meta.dow_labels is not None
    assert len(validated.meta.dow_labels) == 7


def test_caption_stats_response_round_trip(library_db):
    stats = get_caption_hashtag_stats(
        library_db,
        date_from="2024-01-01",
        date_to="2024-01-31",
    )
    validated = CaptionStatsResponse.model_validate(stats)

    assert validated.post_count == 0
    assert validated.top_hashtags == []
    assert validated.meta.timezone_assumption == "UTC"


def test_unposted_catalog_response_round_trip(library_db_seeded):
    images, total = query_unposted_catalog(library_db_seeded, limit=50, offset=0)
    validated = UnpostedCatalogResponse.model_validate(
        {
            "total": total,
            "images": images,
            "pagination": {
                "offset": 0,
                "limit": 50,
                "current_page": 1,
                "total_pages": 1,
                "has_more": False,
            },
        }
    )

    assert validated.total == 1
    assert len(validated.images) == 1
    assert validated.images[0].filename == "solo.jpg"


def test_posting_frequency_response_rejects_wrong_shape():
    with pytest.raises(Exception):
        PostingFrequencyResponse.model_validate({"buckets": [], "meta": "not-a-meta"})
