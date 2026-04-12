"""Tests for job metadata checkpoint helpers and JobRunner persistence."""

import os
import tempfile

from database import create_job, get_job, init_db
from jobs.checkpoint import CHECKPOINT_VERSION, fingerprint_batch_describe
from jobs.runner import JobRunner


def test_fingerprint_batch_describe_stable_and_force_sensitive() -> None:
    meta = {
        "image_type": "both",
        "date_filter": "all",
        "force": False,
        "max_workers": 4,
        "provider_id": None,
        "provider_model": None,
    }
    pairs = [("k1", "catalog"), ("k2", "instagram")]
    a = fingerprint_batch_describe(meta, pairs)
    b = fingerprint_batch_describe(dict(meta), list(pairs))
    assert a == b
    meta_force = {**meta, "force": True}
    assert fingerprint_batch_describe(meta_force, pairs) != a


def test_persist_checkpoint_round_trip_and_clear() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "jobs.db")
        db = init_db(db_path)
        job_id = create_job(db, "batch_describe", {"foo": 1})
        runner = JobRunner(db)
        runner.persist_checkpoint(
            job_id,
            {
                "job_type": "batch_describe",
                "fingerprint": "abc",
                "processed_pairs": ["k1|catalog"],
                "total_at_start": 5,
            },
        )
        row = get_job(db, job_id)
        assert row is not None
        meta = row["metadata"]
        cp = meta["checkpoint"]
        assert cp["checkpoint_version"] == CHECKPOINT_VERSION
        assert cp["processed_pairs"][0] == "k1|catalog"
        assert meta.get("foo") == 1

        runner.clear_checkpoint(job_id)
        row2 = get_job(db, job_id)
        assert row2 is not None
        assert row2["metadata"].get("checkpoint") is None
