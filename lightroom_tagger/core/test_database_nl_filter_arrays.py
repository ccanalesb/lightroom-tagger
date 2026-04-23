"""Tests for ``query_catalog_images`` JSON array filters (dominant_colors, mood_tags)."""

from __future__ import annotations

import os

import pytest

from lightroom_tagger.core.database import (
    init_database,
    query_catalog_images,
    store_image,
    store_image_description,
)


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "nl_filter.db"
    connection = init_database(str(path))
    yield connection
    connection.close()
    bak = str(path) + ".pre-key-migration.bak"
    if os.path.exists(bak):
        os.unlink(bak)


def _seed_two_catalog_images_with_descriptions(db):
    k_a = store_image(
        db,
        {
            "date_taken": "2024-01-15",
            "filename": "a.jpg",
        },
    )
    k_b = store_image(
        db,
        {
            "date_taken": "2024-01-16",
            "filename": "b.jpg",
        },
    )
    store_image_description(
        db,
        {
            "image_key": k_a,
            "image_type": "catalog",
            "summary": "A",
            "dominant_colors": ["blue"],
            "mood_tags": ["moody"],
        },
    )
    store_image_description(
        db,
        {
            "image_key": k_b,
            "image_type": "catalog",
            "summary": "B",
            "dominant_colors": ["red"],
            "mood_tags": ["bright"],
        },
    )
    return k_a, k_b


def test_dominant_colors_filter_matches_single_image(db) -> None:
    k_a, _k_b = _seed_two_catalog_images_with_descriptions(db)
    rows, total = query_catalog_images(db, dominant_colors=["blue"], limit=20, offset=0)
    assert total == 1
    assert len(rows) == 1
    assert rows[0]["key"] == k_a


def test_mood_tags_or_within_list_matches_both_rows(db) -> None:
    _k_a, k_b = _seed_two_catalog_images_with_descriptions(db)
    rows, total = query_catalog_images(
        db,
        mood_tags=["moody", "bright"],
        limit=20,
        offset=0,
    )
    assert total == 2
    assert {r["key"] for r in rows} == {_k_a, k_b}


def test_explicit_none_for_array_filters_same_as_omission(db) -> None:
    _seed_two_catalog_images_with_descriptions(db)
    r1, t1 = query_catalog_images(
        db,
        dominant_colors=None,
        mood_tags=None,
        limit=20,
        offset=0,
    )
    r2, t2 = query_catalog_images(db, limit=20, offset=0)
    assert t1 == t2 == 2
    assert {x["key"] for x in r1} == {x["key"] for x in r2}
