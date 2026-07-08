"""Tests for catalog statistics read helpers and schema facets."""

from __future__ import annotations

import sqlite3

from lightroom_tagger.core.database import (
    catalog_schema_facets,
    count_catalog_images_with_descriptions,
    count_catalog_images_with_repetition,
    count_images_with_dominant_colors,
    count_images_with_mood_tags,
    count_rated_catalog_images,
    get_catalog_date_range,
    get_catalog_months,
    get_color_label_statistics,
    get_mood_tags_sample,
    get_posted_images_count,
    init_database,
    insert_image_score,
    store_image,
    store_image_description,
    update_instagram_status,
)


def test_catalog_statistics_empty_db(tmp_path) -> None:
    db = init_database(str(tmp_path / "library.db"))
    assert count_catalog_images_with_descriptions(db) == 0
    assert count_catalog_images_with_repetition(db) == 0
    assert count_rated_catalog_images(db) == 0
    assert get_posted_images_count(db) == 0
    assert count_images_with_mood_tags(db) == 0
    assert count_images_with_dominant_colors(db) == 0
    assert get_color_label_statistics(db) == {}
    assert get_mood_tags_sample(db) == []
    assert get_catalog_date_range(db) == {"earliest": "", "latest": ""}
    assert get_catalog_months(db) == []

    facets = catalog_schema_facets(db)
    assert facets.total == 0
    assert facets.analyzed == 0
    assert facets.has_rep == 0
    assert facets.rated == 0
    assert facets.posted == 0
    assert facets.with_mood == 0
    assert facets.with_colors == 0
    assert facets.color_labels == {}
    assert facets.top_moods == []
    assert facets.date_range == {"earliest": "", "latest": ""}
    assert facets.perspectives == []
    db.close()


def test_catalog_statistics_seeded_counts(tmp_path) -> None:
    db = init_database(str(tmp_path / "library.db"))
    k1 = store_image(
        db,
        {
            "date_taken": "2024-03-15T10:00:00",
            "filename": "a.jpg",
            "rating": 4,
            "color_label": "Red",
        },
    )
    k2 = store_image(
        db,
        {"date_taken": "2024-01-10", "filename": "b.jpg", "rating": 0, "color_label": "blue"},
    )
    update_instagram_status(db, k1, posted=True)
    store_image_description(
        db,
        {
            "image_key": k1,
            "image_type": "catalog",
            "summary": "Moody street",
            "mood_tags": ["moody", "urban"],
            "dominant_colors": ["#112233"],
            "has_repetition": True,
            "model_used": "test",
        },
    )
    store_image_description(
        db,
        {
            "image_key": k2,
            "image_type": "catalog",
            "summary": "Plain",
            "model_used": "test",
        },
    )

    assert count_catalog_images_with_descriptions(db) == 2
    assert count_catalog_images_with_repetition(db) == 1
    assert count_rated_catalog_images(db) == 1
    assert get_posted_images_count(db) == 1
    assert count_images_with_mood_tags(db) == 1
    assert count_images_with_dominant_colors(db) == 1
    assert get_color_label_statistics(db) == {"red": 1, "blue": 1}

    samples = get_mood_tags_sample(db)
    assert len(samples) == 1
    assert "moody" in samples[0]

    date_range = get_catalog_date_range(db)
    assert date_range["earliest"] == "2024-01-10"
    assert date_range["latest"] == "2024-03-15"

    months = get_catalog_months(db)
    assert months == ["202403", "202401"]

    facets = catalog_schema_facets(db)
    assert facets.total == 2
    assert facets.analyzed == 2
    assert facets.has_rep == 1
    assert facets.rated == 1
    assert facets.posted == 1
    assert facets.with_mood == 1
    assert facets.with_colors == 1
    assert "moody" in facets.top_moods
    assert facets.date_range["earliest"] == "2024-01-10"
    db.close()


def test_catalog_schema_facets_includes_perspectives(tmp_path) -> None:
    db = init_database(str(tmp_path / "library.db"))
    k = store_image(db, {"date_taken": "2024-02-01", "filename": "x.jpg"})
    db.execute(
        "INSERT INTO perspectives (slug, display_name, description, prompt_markdown) "
        "VALUES ('light', 'Light', '', '')"
    )
    db.commit()
    insert_image_score(
        db,
        {
            "image_key": k,
            "image_type": "catalog",
            "perspective_slug": "light",
            "score": 8,
            "prompt_version": "v1",
            "scored_at": "2024-02-01T00:00:00+00:00",
            "is_current": 1,
        },
    )
    db.commit()
    facets = catalog_schema_facets(db)
    assert facets.perspectives == ["light"]
    db.close()


def test_read_helpers_return_dicts_not_sqlite_rows(tmp_path) -> None:
    db = init_database(str(tmp_path / "library.db"))
    facets = catalog_schema_facets(db)
    assert not isinstance(facets.color_labels, sqlite3.Row)
    db.close()
