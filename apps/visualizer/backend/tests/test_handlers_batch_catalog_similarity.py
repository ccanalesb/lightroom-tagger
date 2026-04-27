"""Tests for job-driven catalog visual similarity results."""

from __future__ import annotations

import sqlite_vec

from database import create_job, get_job, init_db
from jobs.runner import JobRunner
from lightroom_tagger.core.database import (
    init_database,
    library_write,
    store_image,
    upsert_image_clip_embedding,
)


def _unit_axis(dim: int) -> bytes:
    v = [0.0] * 512
    v[dim] = 1.0
    return sqlite_vec.serialize_float32(v)


def test_batch_catalog_similarity_materializes_group(tmp_path, monkeypatch) -> None:
    from jobs.handlers import handle_batch_catalog_similarity

    jobs_path = tmp_path / "jobs.db"
    lib_path = tmp_path / "library.db"
    jobs_db = init_db(str(jobs_path))
    job_id = create_job(jobs_db, "batch_catalog_similarity", {})

    lib = init_database(str(lib_path))
    k_seed = store_image(
        lib,
        {
            "date_taken": "2026-03-20T13:55:41",
            "filename": "new.dng",
            "filepath": "/new.dng",
        },
    )
    k_match = store_image(
        lib,
        {
            "date_taken": "2026-03-20T13:55:40",
            "filename": "old.dng",
            "filepath": "/old.dng",
        },
    )
    with library_write(lib):
        upsert_image_clip_embedding(lib, k_seed, _unit_axis(0))
        upsert_image_clip_embedding(lib, k_match, _unit_axis(0))
    lib.close()

    monkeypatch.setenv("LIBRARY_DB", str(lib_path))
    runner = JobRunner(jobs_db)
    handle_batch_catalog_similarity(
        runner,
        job_id,
        {"min_similarity": 0.9, "limit_per_seed": 5},
    )

    job = get_job(jobs_db, job_id)
    assert job["status"] == "completed"
    assert job["result"]["groups_created"] == 1
    assert job["result"]["candidates_created"] == 1

    check = init_database(str(lib_path))
    try:
        group = check.execute("SELECT * FROM catalog_similarity_groups").fetchone()
        assert group is not None
        assert group["seed_key"] == k_seed
        candidate = check.execute("SELECT * FROM catalog_similarity_candidates").fetchone()
        assert candidate is not None
        assert candidate["candidate_key"] == k_match
        assert float(candidate["similarity"]) >= 0.9
    finally:
        check.close()
