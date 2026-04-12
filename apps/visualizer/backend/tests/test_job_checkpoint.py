"""Tests for job metadata checkpoint helpers and JobRunner persistence."""

import os
import tempfile

from database import create_job, get_job, init_db
from jobs.checkpoint import (
    CHECKPOINT_VERSION,
    fingerprint_batch_describe,
    fingerprint_batch_score,
)
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
    meta_ps = {**meta, "perspective_slugs": ["street", "documentary"]}
    assert fingerprint_batch_describe(meta_ps, pairs) != a


def test_fingerprint_batch_score_force_and_triples_and_slug_order() -> None:
    meta = {
        "image_type": "both",
        "date_filter": "all",
        "force": False,
        "max_workers": 4,
        "provider_id": None,
        "provider_model": None,
        "perspective_slugs": ["b", "a"],
    }
    triples = [("k1", "catalog", "a"), ("k2", "instagram", "b")]
    base = fingerprint_batch_score(meta, triples)
    assert fingerprint_batch_score(dict(meta), list(triples)) == base
    assert fingerprint_batch_score({**meta, "force": True}, triples) != base
    meta_perm = {**meta, "perspective_slugs": ["a", "b"]}
    assert fingerprint_batch_score(meta_perm, triples) == base
    triples2 = [("k1", "catalog", "a"), ("k3", "catalog", "b")]
    assert fingerprint_batch_score(meta, triples2) != base


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
