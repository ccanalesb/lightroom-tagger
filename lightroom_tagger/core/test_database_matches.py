"""Tests for match row persistence and read helpers."""

import sqlite3
from datetime import datetime

from lightroom_tagger.core.database import (
    get_all_matches,
    get_match_validation_status,
    get_matches_model_mapping,
    get_matches_with_scores,
    get_rejected_insta_keys,
    get_validated_catalog_keys,
    has_matches_for_insta_key,
    init_database,
    reject_match,
    store_match,
    validate_match,
)


def test_store_match_with_rank(tmp_path):
    """store_match persists rank column."""
    db = init_database(str(tmp_path / 'test.db'))
    record = {
        'catalog_key': 'cat1', 'insta_key': 'ig1',
        'phash_distance': 5, 'phash_score': 0.8, 'desc_similarity': 0.7,
        'vision_result': 'SAME', 'vision_score': 0.9, 'total_score': 0.85,
        'rank': 2,
    }
    store_match(db, record)
    row = db.execute(
        "SELECT rank FROM matches WHERE catalog_key = ? AND insta_key = ?",
        ('cat1', 'ig1'),
    ).fetchone()
    assert row is not None
    assert row['rank'] == 2
    db.close()


def test_match_read_helpers(tmp_path) -> None:
    db = init_database(str(tmp_path / "library.db"))
    store_match(
        db,
        {
            "catalog_key": "cat_a",
            "insta_key": "ig_1",
            "total_score": 0.7,
            "model_used": "model-a",
            "rank": 1,
        },
    )
    store_match(
        db,
        {
            "catalog_key": "cat_b",
            "insta_key": "ig_1",
            "total_score": 0.9,
            "model_used": "model-b",
            "rank": 2,
        },
    )
    store_match(
        db,
        {
            "catalog_key": "cat_c",
            "insta_key": "ig_2",
            "total_score": 0.5,
            "model_used": "model-c",
        },
    )
    validate_match(db, "cat_c", "ig_2")
    reject_match(db, "cat_x", "ig_9")

    matches = get_all_matches(db)
    assert len(matches) == 3
    assert all(not isinstance(m, sqlite3.Row) for m in matches)
    assert matches[0]["insta_key"] == "ig_1"

    validated = get_validated_catalog_keys(db)
    assert validated == {"cat_c"}

    models = get_matches_model_mapping(db)
    assert models["ig_1"] == "model-b"
    assert models["ig_2"] == "model-c"

    scores = get_matches_with_scores(db)
    assert scores["ig_1"] == 0.9
    assert scores["ig_2"] == 0.5

    assert has_matches_for_insta_key(db, "ig_1") is True
    assert has_matches_for_insta_key(db, "ig_missing") is False

    hit = get_match_validation_status(db, "cat_c", "ig_2")
    assert hit is not None
    assert hit["validated_at"]
    assert get_match_validation_status(db, "cat_a", "ig_1") == {"validated_at": None}

    rejected_keys = get_rejected_insta_keys(db)
    assert rejected_keys == ["ig_9"]
    db.close()


def test_match_read_helpers_empty_db(tmp_path) -> None:
    db = init_database(str(tmp_path / "library.db"))
    assert get_all_matches(db) == []
    assert get_validated_catalog_keys(db) == set()
    assert get_matches_model_mapping(db) == {}
    assert get_matches_with_scores(db) == {}
    assert has_matches_for_insta_key(db, "nope") is False
    assert get_match_validation_status(db, "a", "b") is None
    assert get_rejected_insta_keys(db) == []
    db.close()
