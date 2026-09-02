"""Tests for job-driven catalog visual similarity results."""

from __future__ import annotations

import sqlite_vec

from database import create_job, get_job, init_db
from jobs.runner import JobRunner
from lightroom_tagger.core.database import (
    init_database,
    insert_frame_substance_override,
    insert_frame_substance_run,
    insert_image_score,
    library_write,
    store_image,
    upsert_frame_substance_verdict,
    upsert_image_clip_embedding,
)
from lightroom_tagger.core.frame_substance_detector import detector_version


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


def _seed_verdict(
    conn,
    image_key: str,
    verdict: str,
    *,
    override: bool = False,
) -> None:
    run_id = insert_frame_substance_run(conn, detector_version=detector_version())
    upsert_frame_substance_verdict(
        conn,
        image_key=image_key,
        verdict=verdict,
        unknown_reason="",
        black_frac_25=0.0,
        blown_frac_235=0.0,
        lap_var=1.0,
        tile_max=10.0,
        entropy=5.0,
        detector_version=detector_version(),
        run_id=run_id,
    )
    if override:
        insert_frame_substance_override(conn, image_key)
    conn.commit()


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


def test_batch_catalog_similarity_skips_flagged_seed(tmp_path, monkeypatch) -> None:
    from jobs.handlers import handle_batch_catalog_similarity

    jobs_path = tmp_path / "jobs.db"
    lib_path = tmp_path / "library.db"
    jobs_db = init_db(str(jobs_path))
    job_id = create_job(jobs_db, "batch_catalog_similarity", {})

    lib = init_database(str(lib_path))
    k_void = store_image(
        lib,
        {"date_taken": "2026-03-20T13:55:42", "filename": "void.dng", "filepath": "/void.dng"},
    )
    k_good = store_image(
        lib,
        {"date_taken": "2026-03-20T13:55:40", "filename": "good.dng", "filepath": "/good.dng"},
    )
    _seed_verdict(lib, k_void, "void")
    with library_write(lib):
        upsert_image_clip_embedding(lib, k_void, _unit_axis(0))
        upsert_image_clip_embedding(lib, k_good, _unit_axis(0))
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
    assert job["result"]["skipped_flagged_frame"] == 2
    assert job["result"]["groups_created"] == 0


def test_batch_catalog_similarity_skips_flagged_candidate_and_includes_low_score(
    tmp_path, monkeypatch
) -> None:
    from jobs.handlers import handle_batch_catalog_similarity

    jobs_path = tmp_path / "jobs.db"
    lib_path = tmp_path / "library.db"
    jobs_db = init_db(str(jobs_path))
    job_id = create_job(jobs_db, "batch_catalog_similarity", {})

    lib = init_database(str(lib_path))
    k_good = store_image(
        lib,
        {"date_taken": "2026-03-20T13:55:43", "filename": "good.dng", "filepath": "/good.dng"},
    )
    k_void = store_image(
        lib,
        {"date_taken": "2026-03-20T13:55:42", "filename": "void.dng", "filepath": "/void.dng"},
    )
    k_low = store_image(
        lib,
        {"date_taken": "2026-03-20T13:55:40", "filename": "low.dng", "filepath": "/low.dng"},
    )
    _score(lib, k_low, 4)
    _seed_verdict(lib, k_void, "void")
    with library_write(lib):
        upsert_image_clip_embedding(lib, k_good, _unit_axis(0))
        upsert_image_clip_embedding(lib, k_void, _unit_axis(0))
        upsert_image_clip_embedding(lib, k_low, _unit_axis(0))
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
    assert job["result"]["skipped_flagged_frame"] >= 2
    assert job["result"]["groups_created"] == 1
    assert job["result"]["candidates_created"] == 1

    check = init_database(str(lib_path))
    try:
        group = check.execute("SELECT * FROM catalog_similarity_groups").fetchone()
        assert group is not None
        assert group["seed_key"] == k_good
        candidate = check.execute("SELECT * FROM catalog_similarity_candidates").fetchone()
        assert candidate is not None
        assert candidate["candidate_key"] == k_low
    finally:
        check.close()


def test_batch_catalog_similarity_does_not_skip_overridden_flagged(tmp_path, monkeypatch) -> None:
    from jobs.handlers import handle_batch_catalog_similarity

    jobs_path = tmp_path / "jobs.db"
    lib_path = tmp_path / "library.db"
    jobs_db = init_db(str(jobs_path))
    job_id = create_job(jobs_db, "batch_catalog_similarity", {})

    lib = init_database(str(lib_path))
    k_void = store_image(
        lib,
        {"date_taken": "2026-03-20T13:55:40", "filename": "void.dng", "filepath": "/void.dng"},
    )
    k_match = store_image(
        lib,
        {"date_taken": "2026-03-20T13:55:41", "filename": "match.dng", "filepath": "/match.dng"},
    )
    _seed_verdict(lib, k_void, "void", override=True)
    with library_write(lib):
        upsert_image_clip_embedding(lib, k_void, _unit_axis(0))
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
    assert job["result"]["skipped_flagged_frame"] == 0
    assert job["result"]["groups_created"] == 1
    assert job["result"]["candidates_created"] == 1
