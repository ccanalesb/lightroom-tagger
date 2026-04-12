"""Tests for ``posting_analytics`` (validated dump match population)."""

from __future__ import annotations

from lightroom_tagger.core.database import (
    init_database,
    store_image,
    store_instagram_dump_media,
    store_match,
    validate_match,
)
from lightroom_tagger.core.posting_analytics import (
    get_caption_hashtag_stats,
    get_posting_frequency,
    get_posting_time_heatmap,
    query_unposted_catalog,
)


def _seed_analytics_db(conn) -> None:
    """Three validated posts (two same day) and one unposted catalog row."""
    k1 = store_image(
        conn,
        {
            "date_taken": "2024-01-02T12:00:00",
            "filename": "a.jpg",
            "rating": 5,
            "instagram_posted": True,
        },
    )
    k2 = store_image(
        conn,
        {
            "date_taken": "2024-01-02T14:00:00",
            "filename": "b.jpg",
            "rating": 4,
            "instagram_posted": True,
        },
    )
    k3 = store_image(
        conn,
        {
            "date_taken": "2024-01-03T10:00:00",
            "filename": "c.jpg",
            "rating": 3,
            "instagram_posted": True,
        },
    )
    store_image(
        conn,
        {
            "date_taken": "2024-02-10T10:00:00",
            "filename": "unposted.jpg",
            "rating": 2,
            "instagram_posted": False,
        },
    )
    k5 = store_image(
        conn,
        {
            "date_taken": "2024-02-01T08:00:00",
            "filename": "feb_posted.jpg",
            "rating": 5,
            "instagram_posted": True,
        },
    )

    store_instagram_dump_media(
        conn,
        {
            "media_key": "m1",
            "date_folder": "202401",
            "caption": "Hello #Foo world",
            "created_at": "2024-01-02T15:00:00Z",
        },
    )
    store_instagram_dump_media(
        conn,
        {
            "media_key": "m2",
            "date_folder": "202401",
            "caption": "Other #foo",
            "created_at": "2024-01-02T16:30:00Z",
        },
    )
    store_instagram_dump_media(
        conn,
        {
            "media_key": "m3",
            "date_folder": "202401",
            "caption": "No hashtag",
            "created_at": "2024-01-03T09:00:00Z",
        },
    )
    # Fallback timestamp: no created_at, YYYYMM date_folder → 2024-02-01 UTC
    store_instagram_dump_media(
        conn,
        {
            "media_key": "m4_fallback",
            "date_folder": "202402",
            "caption": "",
            "created_at": None,
        },
    )

    for ck, ik in (
        (k1, "m1"),
        (k2, "m2"),
        (k3, "m3"),
        (k5, "m4_fallback"),
    ):
        store_match(
            conn,
            {
                "catalog_key": ck,
                "insta_key": ik,
                "total_score": 1.0,
            },
            commit=False,
        )
        validate_match(conn, ck, ik)

    conn.commit()


def test_posting_frequency_day_buckets(tmp_path) -> None:
    db_path = tmp_path / "library.db"
    conn = init_database(str(db_path))
    _seed_analytics_db(conn)

    buckets, meta = get_posting_frequency(
        conn,
        date_from="2024-01-01",
        date_to="2024-01-05",
        granularity="day",
    )
    by_day = {b["bucket_start"]: b["count"] for b in buckets}
    assert by_day.get("2024-01-02") == 2
    assert by_day.get("2024-01-03") == 1
    assert meta.get("timezone_assumption") == "UTC"


def test_posting_frequency_includes_date_folder_fallback(tmp_path) -> None:
    db_path = tmp_path / "library.db"
    conn = init_database(str(db_path))
    _seed_analytics_db(conn)

    buckets, _meta = get_posting_frequency(
        conn,
        date_from="2024-02-01",
        date_to="2024-02-29",
        granularity="day",
    )
    by_day = {b["bucket_start"]: b["count"] for b in buckets}
    assert by_day.get("2024-02-01") == 1


def test_heatmap_cell_sum_matches_validated_posts(tmp_path) -> None:
    db_path = tmp_path / "library.db"
    conn = init_database(str(db_path))
    _seed_analytics_db(conn)

    cells, meta = get_posting_time_heatmap(
        conn,
        date_from="2024-01-01",
        date_to="2024-01-05",
    )
    total = sum(c["count"] for c in cells)
    assert total == 3
    assert "timezone_note" in meta


def test_hashtag_aggregation_is_case_insensitive(tmp_path) -> None:
    db_path = tmp_path / "library.db"
    conn = init_database(str(db_path))
    _seed_analytics_db(conn)

    stats = get_caption_hashtag_stats(
        conn,
        date_from="2024-01-01",
        date_to="2024-01-05",
    )
    tags = {t["tag"]: t["count"] for t in stats["top_hashtags"]}
    assert tags.get("foo") == 2


def test_query_unposted_catalog_total_and_filters(tmp_path) -> None:
    db_path = tmp_path / "library.db"
    conn = init_database(str(db_path))
    _seed_analytics_db(conn)

    rows, total = query_unposted_catalog(conn)
    assert total == 1
    assert len(rows) == 1
    assert rows[0].get("filename") == "unposted.jpg"

    _, total_hi = query_unposted_catalog(conn, min_rating=4)
    assert total_hi == 0

    _, total_feb = query_unposted_catalog(conn, month="202402")
    assert total_feb == 1
