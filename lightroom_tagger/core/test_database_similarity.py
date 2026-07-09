"""Tests for catalog similarity read helpers."""

from __future__ import annotations

import sqlite3

from lightroom_tagger.core.database import (
    get_catalog_similarity_groups_paginated,
    get_similarity_candidates_for_group,
    get_similarity_groups_count,
    init_database,
    insert_catalog_similarity_group,
    store_image,
)


def test_similarity_read_helpers_empty_db(tmp_path) -> None:
    db = init_database(str(tmp_path / "library.db"))
    assert get_similarity_groups_count(db) == 0
    assert get_catalog_similarity_groups_paginated(db, limit=10, offset=0) == ([], 0)
    db.close()


def test_similarity_read_helpers_pagination_and_candidates(tmp_path) -> None:
    db = init_database(str(tmp_path / "library.db"))
    k_seed = store_image(
        db,
        {"date_taken": "2024-02-01", "filename": "seed.jpg", "filepath": "/seed.jpg"},
    )
    k_cand = store_image(
        db,
        {"date_taken": "2024-01-01", "filename": "cand.jpg", "filepath": "/cand.jpg"},
    )
    gid = insert_catalog_similarity_group(
        db,
        seed_key=k_seed,
        candidates=[
            {
                "candidate_key": k_cand,
                "similarity": 0.91,
                "rank": 1,
                "why_matched": "Visual match (91%)",
            }
        ],
        job_id="job-1",
    )

    assert get_similarity_groups_count(db) == 1
    groups, total = get_catalog_similarity_groups_paginated(db, limit=5, offset=0)
    assert total == 1
    assert len(groups) == 1
    assert groups[0]["seed_key"] == k_seed
    assert not isinstance(groups[0], sqlite3.Row)

    candidates = get_similarity_candidates_for_group(db, gid)
    assert len(candidates) == 1
    assert candidates[0]["candidate_key"] == k_cand
    assert float(candidates[0]["similarity"]) == 0.91
    assert not isinstance(candidates[0], sqlite3.Row)

    groups_page, total_page = get_catalog_similarity_groups_paginated(db, limit=1, offset=1)
    assert groups_page == []
    assert total_page == 1
    db.close()
