"""Tests for job metadata checkpoint helpers and JobRunner persistence."""

import json
import os
import tempfile

from database import create_job, get_job, init_db
from jobs.checkpoint import (
    CHECKPOINT_VERSION,
    build_batch_describe_checkpoint_body,
    build_batch_embed_image_checkpoint_body,
    build_batch_score_checkpoint_body,
    build_batch_stack_detect_checkpoint_body,
    build_batch_text_embed_checkpoint_body,
    build_enrich_catalog_checkpoint_body,
    build_prepare_catalog_checkpoint_body,
    build_vision_match_checkpoint_body,
    fingerprint_batch_describe,
    fingerprint_batch_score,
    fingerprint_batch_stack_detect,
    fingerprint_batch_text_embed,
    load_resume_state,
    job_type_entry,
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
    meta_backfill = {**meta, "backfill_visual_tags": True}
    assert fingerprint_batch_describe(meta_backfill, pairs) != a
    assert (
        fingerprint_batch_describe({**meta, "backfill_visual_tags": True}, pairs)
        == fingerprint_batch_describe(dict(meta_backfill), list(pairs))
    )
    meta_ps = {**meta, "perspective_slugs": ["street", "documentary"]}
    assert fingerprint_batch_describe(meta_ps, pairs) != a


def test_fingerprint_batch_stack_detect_permutation_invariant_and_delta_force_sensitive() -> None:
    meta: dict = {}
    keys = ["a", "b"]
    base = fingerprint_batch_stack_detect(
        meta, keys, resolved_delta_ms=2000, force_mode="incremental"
    )
    assert fingerprint_batch_stack_detect(
        dict(meta), list(reversed(keys)), resolved_delta_ms=2000, force_mode="incremental"
    ) == base
    assert (
        fingerprint_batch_stack_detect(
            meta, ["b", "a"], resolved_delta_ms=2000, force_mode="incremental"
        )
        == base
    )
    assert (
        fingerprint_batch_stack_detect(
            meta, keys, resolved_delta_ms=3000, force_mode="incremental"
        )
        != base
    )
    assert (
        fingerprint_batch_stack_detect(meta, keys, resolved_delta_ms=2000, force_mode="full")
        != base
    )
    fp_full = fingerprint_batch_stack_detect(
        meta, keys, resolved_delta_ms=2000, force_mode="full"
    )
    fp_preserve = fingerprint_batch_stack_detect(
        meta, keys, resolved_delta_ms=2000, force_mode="preserve_edited"
    )
    assert fp_full != fp_preserve


def test_fingerprint_batch_text_embed_stable_and_force_sensitive() -> None:
    meta = {
        "image_type": "catalog",
        "date_filter": "all",
        "force": False,
        "min_rating": None,
    }
    pairs = [("k2", "catalog"), ("k1", "catalog")]
    a = fingerprint_batch_text_embed(meta, pairs)
    b = fingerprint_batch_text_embed(dict(meta), list(pairs))
    assert a == b
    perm = [("k1", "catalog"), ("k2", "catalog")]
    assert fingerprint_batch_text_embed(meta, perm) == a
    meta_force = {**meta, "force": True}
    assert fingerprint_batch_text_embed(meta_force, pairs) != a


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


def _checkpoint_metadata(job_type: str, fingerprint: str, **fields) -> dict:
    return {
        "checkpoint": {
            "checkpoint_version": CHECKPOINT_VERSION,
            "job_type": job_type,
            "fingerprint": fingerprint,
            **fields,
        }
    }


def test_load_resume_state_returns_processed_set_on_match() -> None:
    logs: list[str] = []
    meta = _checkpoint_metadata(
        "batch_describe",
        "fp-ok",
        processed_pairs=["k1|catalog", "k2|instagram"],
        total_at_start=2,
    )
    result = load_resume_state(
        "batch_describe",
        meta,
        "fp-ok",
        logs.append,
    )
    assert result == {"k1|catalog", "k2|instagram"}
    assert logs == []


def test_load_resume_state_version_mismatch_returns_empty() -> None:
    logs: list[str] = []
    meta = {
        "checkpoint": {
            "checkpoint_version": 0,
            "job_type": "batch_describe",
            "fingerprint": "fp-ok",
            "processed_pairs": ["k1|catalog"],
        }
    }
    assert load_resume_state("batch_describe", meta, "fp-ok", logs.append) == set()
    assert logs == []


def test_load_resume_state_job_type_mismatch_returns_empty() -> None:
    logs: list[str] = []
    meta = _checkpoint_metadata(
        "batch_score",
        "fp-ok",
        processed_triplets=["k1|catalog|slug"],
        total_at_start=1,
    )
    assert load_resume_state("batch_describe", meta, "fp-ok", logs.append) == set()
    assert logs == []


def test_load_resume_state_fingerprint_drift_logs_per_handler_message() -> None:
    cases = [
        (
            "vision_match",
            {"processed_media_keys": ["mk1"]},
            "checkpoint mismatch: vision_match fingerprint changed, starting fresh",
        ),
        (
            "enrich_catalog",
            {"processed_image_keys": ["ik1"]},
            "checkpoint mismatch: enrich_catalog fingerprint changed, starting fresh",
        ),
        (
            "prepare_catalog",
            {"processed_image_keys": ["ik1"]},
            "checkpoint mismatch: prepare_catalog fingerprint changed, starting fresh",
        ),
        (
            "batch_describe",
            {"processed_pairs": ["k1|catalog"], "total_at_start": 1},
            "checkpoint mismatch: batch_describe fingerprint changed, starting fresh",
        ),
        (
            "batch_score",
            {"processed_triplets": ["k1|catalog|slug"], "total_at_start": 1},
            "checkpoint mismatch: batch_score fingerprint changed, starting fresh",
        ),
        (
            "batch_text_embed",
            {"processed_pairs": ["k1|catalog"], "total_at_start": 1},
            "checkpoint mismatch: batch_text_embed fingerprint changed, starting fresh",
        ),
        (
            "batch_embed_image",
            {"processed_pairs": ["k1"], "total_at_start": 1},
            "checkpoint mismatch: batch_embed_image fingerprint changed, starting fresh",
        ),
        (
            "batch_stack_detect",
            {"processed_image_keys": ["k1"], "total_at_start": 1},
            "checkpoint mismatch: batch_stack_detect fingerprint changed, starting fresh",
        ),
    ]
    for job_type, extra, expected_msg in cases:
        logs: list[str] = []
        meta = _checkpoint_metadata(job_type, "fp-stale", **extra)
        assert load_resume_state(job_type, meta, "fp-current", logs.append) == set()
        assert logs == [expected_msg], f"{job_type}: {logs!r}"


def test_load_resume_state_nested_batch_analyze_describe() -> None:
    logs: list[str] = []
    meta = {
        "checkpoint": {
            "checkpoint_version": CHECKPOINT_VERSION,
            "job_type": "batch_analyze",
            "stage": "describe",
            "describe": {
                "fingerprint": "fp-stale",
                "processed_pairs": ["k1|catalog"],
                "total_at_start": 1,
            },
            "score": {},
        }
    }
    assert (
        load_resume_state(
            "batch_describe",
            meta,
            "fp-current",
            logs.append,
            nested_sub_key="describe",
            nested_root_job_type="batch_analyze",
            mismatch_message=(
                "checkpoint mismatch: batch_analyze describe fingerprint changed, "
                "starting describe fresh"
            ),
        )
        == set()
    )
    assert logs == [
        "checkpoint mismatch: batch_analyze describe fingerprint changed, starting describe fresh"
    ]


def test_build_checkpoint_body_matches_hand_rolled_payloads() -> None:
    fp = "abc123"
    processed = {"b", "a"}
    total = 7
    cases = [
        (
            build_vision_match_checkpoint_body,
            {
                "job_type": "vision_match",
                "fingerprint": fp,
                "processed_media_keys": ["a", "b"],
            },
            {"fingerprint": fp, "processed": processed},
        ),
        (
            build_enrich_catalog_checkpoint_body,
            {
                "job_type": "enrich_catalog",
                "fingerprint": fp,
                "processed_image_keys": ["a", "b"],
            },
            {"fingerprint": fp, "processed": processed},
        ),
        (
            build_prepare_catalog_checkpoint_body,
            {
                "job_type": "prepare_catalog",
                "fingerprint": fp,
                "processed_image_keys": ["a", "b"],
            },
            {"fingerprint": fp, "processed": processed},
        ),
        (
            build_batch_describe_checkpoint_body,
            {
                "job_type": "batch_describe",
                "fingerprint": fp,
                "processed_pairs": ["a", "b"],
                "total_at_start": total,
            },
            {"fingerprint": fp, "processed": processed, "total_at_start": total},
        ),
        (
            build_batch_score_checkpoint_body,
            {
                "job_type": "batch_score",
                "fingerprint": fp,
                "processed_triplets": ["a", "b"],
                "total_at_start": total,
            },
            {"fingerprint": fp, "processed": processed, "total_at_start": total},
        ),
        (
            build_batch_text_embed_checkpoint_body,
            {
                "job_type": "batch_text_embed",
                "fingerprint": fp,
                "processed_pairs": ["a", "b"],
                "total_at_start": total,
            },
            {"fingerprint": fp, "processed": processed, "total_at_start": total},
        ),
        (
            build_batch_embed_image_checkpoint_body,
            {
                "job_type": "batch_embed_image",
                "fingerprint": fp,
                "processed_pairs": ["a", "b"],
                "total_at_start": total,
            },
            {"fingerprint": fp, "processed": processed, "total_at_start": total},
        ),
        (
            build_batch_stack_detect_checkpoint_body,
            {
                "job_type": "batch_stack_detect",
                "fingerprint": fp,
                "processed_image_keys": ["a", "b"],
                "total_at_start": total,
            },
            {"fingerprint": fp, "processed": processed, "total_at_start": total},
        ),
    ]
    for builder, expected, kwargs in cases:
        built = builder(**kwargs)
        assert built == expected
        assert json.dumps(built, sort_keys=True) == json.dumps(expected, sort_keys=True)


def test_registry_build_checkpoint_body_delegates_to_helpers() -> None:
    fp = "fp"
    processed = {"x"}
    jt = job_type_entry("batch_describe")
    assert jt.build_checkpoint_body(
        fingerprint=fp,
        processed=processed,
        total_at_start=3,
    ) == {
        "job_type": "batch_describe",
        "fingerprint": fp,
        "processed_pairs": ["x"],
        "total_at_start": 3,
    }
