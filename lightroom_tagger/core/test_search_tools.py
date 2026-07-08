"""Tests for LLM search tool executors (schema introspection contract)."""

from __future__ import annotations

from lightroom_tagger.core.database import (
    init_database,
    insert_image_score,
    store_image,
    store_image_description,
    update_instagram_status,
)
from lightroom_tagger.core.search_tools import execute_tool


def test_get_catalog_schema_seeded_contract(tmp_path) -> None:
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
    db.execute(
        "INSERT INTO perspectives (slug, display_name, description, prompt_markdown) "
        "VALUES ('light', 'Light', '', '')"
    )
    db.commit()
    insert_image_score(
        db,
        {
            "image_key": k1,
            "image_type": "catalog",
            "perspective_slug": "light",
            "score": 8,
            "prompt_version": "v1",
            "scored_at": "2024-02-01T00:00:00+00:00",
            "is_current": 1,
        },
    )
    db.commit()

    result = execute_tool("get_catalog_schema", {}, db)

    assert result == {
        "total_catalog_images": 2,
        "analyzed_images": 2,
        "date_range": {
            "earliest": "2024-01-10",
            "latest": "2024-03-15",
            "note": "Use date_from/date_to (YYYY-MM-DD) or month (YYYYMM) to filter by date.",
        },
        "filters": {
            "description_search": {
                "description": "FTS over AI-generated descriptions. Use visual nouns, NOT genre labels.",
                "indexed_images": 2,
            },
            "mood_tags": {
                "description": "AI mood/atmosphere tags. Pass array of tags; image matches if it has ANY.",
                "images_with_mood_tags": 1,
                "top_40_tags": ["moody", "urban"],
            },
            "dominant_colors": {
                "description": "Hex color codes only (e.g. '#c62828'). Image matches if ANY code present.",
                "images_with_colors": 1,
            },
            "has_repetition": {
                "description": "Visual repetition/patterns/symmetry flag.",
                "images_with_true": 1,
            },
            "color_label": {
                "description": "Lightroom color flag.",
                "available_values_and_counts": {"red": 1, "blue": 1},
            },
            "score_perspective": {
                "description": "Quality score perspective. Use with sort_by_score='desc'.",
                "available_slugs": ["light"],
            },
            "min_rating": {
                "description": "Lightroom star rating 1–5.",
                "images_with_any_rating": 1,
            },
            "posted": {
                "description": "Instagram posted: true=posted, false=not yet posted.",
                "images_posted": 1,
            },
        },
    }
    db.close()


def test_get_catalog_schema_empty_db(tmp_path) -> None:
    db = init_database(str(tmp_path / "library.db"))
    result = execute_tool("get_catalog_schema", {}, db)
    assert result == {
        "total_catalog_images": 0,
        "analyzed_images": 0,
        "date_range": {
            "earliest": "",
            "latest": "",
            "note": "Use date_from/date_to (YYYY-MM-DD) or month (YYYYMM) to filter by date.",
        },
        "filters": {
            "description_search": {
                "description": "FTS over AI-generated descriptions. Use visual nouns, NOT genre labels.",
                "indexed_images": 0,
            },
            "mood_tags": {
                "description": "AI mood/atmosphere tags. Pass array of tags; image matches if it has ANY.",
                "images_with_mood_tags": 0,
                "top_40_tags": [],
            },
            "dominant_colors": {
                "description": "Hex color codes only (e.g. '#c62828'). Image matches if ANY code present.",
                "images_with_colors": 0,
            },
            "has_repetition": {
                "description": "Visual repetition/patterns/symmetry flag.",
                "images_with_true": 0,
            },
            "color_label": {
                "description": "Lightroom color flag.",
                "available_values_and_counts": {},
            },
            "score_perspective": {
                "description": "Quality score perspective. Use with sort_by_score='desc'.",
                "available_slugs": [],
            },
            "min_rating": {
                "description": "Lightroom star rating 1–5.",
                "images_with_any_rating": 0,
            },
            "posted": {
                "description": "Instagram posted: true=posted, false=not yet posted.",
                "images_posted": 0,
            },
        },
    }
    db.close()


def test_get_scoring_perspectives_contract(tmp_path) -> None:
    db = init_database(str(tmp_path / "library.db"))
    k = store_image(db, {"date_taken": "2024-02-01", "filename": "x.jpg"})
    db.execute(
        "INSERT INTO perspectives (slug, display_name, description, prompt_markdown) "
        "VALUES ('alpha', 'Alpha', '', ''), ('beta', 'Beta', '', '')"
    )
    db.commit()
    insert_image_score(
        db,
        {
            "image_key": k,
            "image_type": "catalog",
            "perspective_slug": "beta",
            "score": 7,
            "prompt_version": "v1",
            "scored_at": "2024-02-01T00:00:00+00:00",
            "is_current": 1,
        },
    )
    db.commit()

    assert execute_tool("get_scoring_perspectives", {}, db) == {"perspectives": ["beta"]}
    db.close()
