"""Tests for stack suggestion reads, rejections, and accept mutations."""

from __future__ import annotations

import sqlite_vec

from lightroom_tagger.core.database import (
    count_pending_stack_suggestions,
    init_database,
    insert_catalog_similarity_group,
    insert_image_score,
    is_catalog_similarity_pair_rejected,
    library_write,
    list_pending_stack_suggestions,
    reject_catalog_similarity_pair,
    stack_accept_suggestion_pair,
    store_image,
    upsert_image_clip_embedding,
)


def _unit_axis(dim: int) -> bytes:
    v = [0.0] * 512
    v[dim] = 1.0
    return sqlite_vec.serialize_float32(v)


def _score(conn, image_key: str, score: int) -> None:
    insert_image_score(
        conn,
        {
            "image_key": image_key,
            "image_type": "catalog",
            "perspective_slug": "alpha",
            "score": score,
            "rationale": "r",
            "model_used": "m",
            "prompt_version": "v1",
            "scored_at": "2026-01-01T00:00:00+00:00",
            "is_current": 1,
        },
    )
    conn.commit()


def test_pending_stack_suggestions_exclude_rejected_and_blank_frames(tmp_path) -> None:
    db = init_database(str(tmp_path / "library.db"))
    k_good_a = store_image(
        db,
        {"date_taken": "2026-03-20T13:55:40", "filename": "a.jpg", "filepath": "/a.jpg"},
    )
    k_good_b = store_image(
        db,
        {"date_taken": "2026-03-20T13:55:41", "filename": "b.jpg", "filepath": "/b.jpg"},
    )
    k_blank = store_image(
        db,
        {"date_taken": "2026-03-20T13:55:42", "filename": "blank.jpg", "filepath": "/blank.jpg"},
    )
    k_reject = store_image(
        db,
        {"date_taken": "2026-03-20T13:55:43", "filename": "reject.jpg", "filepath": "/reject.jpg"},
    )
    _score(db, k_good_a, 8)
    _score(db, k_good_b, 8)
    _score(db, k_blank, 3)
    _score(db, k_reject, 8)

    insert_catalog_similarity_group(
        db,
        seed_key=k_good_a,
        candidates=[
            {
                "candidate_key": k_good_b,
                "similarity": 0.95,
                "rank": 1,
                "why_matched": "Visual match (95%)",
            }
        ],
    )
    insert_catalog_similarity_group(
        db,
        seed_key=k_good_a,
        candidates=[
            {
                "candidate_key": k_blank,
                "similarity": 0.99,
                "rank": 1,
                "why_matched": "Visual match (99%)",
            }
        ],
    )
    insert_catalog_similarity_group(
        db,
        seed_key=k_good_a,
        candidates=[
            {
                "candidate_key": k_reject,
                "similarity": 0.92,
                "rank": 1,
                "why_matched": "Visual match (92%)",
            }
        ],
    )
    reject_catalog_similarity_pair(db, k_good_a, k_reject)

    assert count_pending_stack_suggestions(db) == 1
    items, total = list_pending_stack_suggestions(db, limit=10, offset=0)
    assert total == 1
    assert len(items) == 1
    assert {items[0]["seed_key"], items[0]["candidate_key"]} == {k_good_a, k_good_b}
    assert is_catalog_similarity_pair_rejected(db, k_good_a, k_reject) is True
    db.close()


def test_reject_survives_similarity_wipe_and_accept_creates_stack(tmp_path) -> None:
    db = init_database(str(tmp_path / "library.db"))
    k_a = store_image(
        db,
        {"date_taken": "2026-03-20T13:55:40", "filename": "a.jpg", "filepath": "/a.jpg"},
    )
    k_b = store_image(
        db,
        {"date_taken": "2026-03-20T13:55:41", "filename": "b.jpg", "filepath": "/b.jpg"},
    )
    k_c = store_image(
        db,
        {"date_taken": "2026-03-20T13:55:42", "filename": "c.jpg", "filepath": "/c.jpg"},
    )
    with library_write(db):
        upsert_image_clip_embedding(db, k_a, _unit_axis(0))
        upsert_image_clip_embedding(db, k_b, _unit_axis(0))
        upsert_image_clip_embedding(db, k_c, _unit_axis(0))

    insert_catalog_similarity_group(
        db,
        seed_key=k_a,
        candidates=[
            {
                "candidate_key": k_b,
                "similarity": 0.95,
                "rank": 1,
                "why_matched": "Visual match (95%)",
            }
        ],
    )
    reject_catalog_similarity_pair(db, k_a, k_c)

    db.execute("DELETE FROM catalog_similarity_candidates")
    db.execute("DELETE FROM catalog_similarity_groups")
    db.commit()

    insert_catalog_similarity_group(
        db,
        seed_key=k_a,
        candidates=[
            {
                "candidate_key": k_b,
                "similarity": 0.95,
                "rank": 1,
                "why_matched": "Visual match (95%)",
            },
            {
                "candidate_key": k_c,
                "similarity": 0.94,
                "rank": 2,
                "why_matched": "Visual match (94%)",
            },
        ],
    )

    assert count_pending_stack_suggestions(db) == 1

    with library_write(db):
        result = stack_accept_suggestion_pair(db, k_a, k_b)
    stack_id = int(result["stack"]["stack_id"])
    members = {
        row["image_key"]
        for row in db.execute(
            "SELECT image_key FROM image_stack_members WHERE stack_id = ?",
            (stack_id,),
        ).fetchall()
    }
    assert members == {k_a, k_b}
    assert count_pending_stack_suggestions(db) == 0
    db.close()
