"""Tests for batch_embed_image job handler (real library SQLite, mocked CLIP encode)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
from PIL import Image

import sqlite_vec
from database import create_job, get_job, init_db, update_job_field
import jobs.handlers as job_handlers
from jobs.checkpoint import CHECKPOINT_VERSION, fingerprint_batch_embed_image
from jobs.runner import JobRunner
from lightroom_tagger.core.database import (
    init_database,
    library_write,
    list_instagram_dump_keys_needing_clip_embedding,
    store_image,
    store_instagram_dump_media,
    store_vision_cached_image,
    upsert_image_clip_embedding,
)


def _write_min_jpg(path) -> None:
    img = Image.new("RGB", (2, 2), (0, 0, 0))
    img.save(path, "JPEG")


def _make_runner() -> MagicMock:
    runner = MagicMock()
    runner.db = MagicMock()
    runner.is_cancelled.return_value = False
    return runner


def test_fingerprint_batch_embed_image_differs_catalog_vs_catalog_and_instagram() -> None:
    keys = ["2024-01-01_a.jpg", "2024-01-02_b.jpg"]
    meta_cat = {"image_type": "catalog", "force": False}
    meta_union = {"image_type": "catalog_and_instagram", "force": False}
    fp_cat = fingerprint_batch_embed_image(
        meta_cat, keys, resolved_months=None, resolved_year=None
    )
    fp_union = fingerprint_batch_embed_image(
        meta_union, keys, resolved_months=None, resolved_year=None
    )
    assert fp_cat != fp_union


def test_instagram_dump_keys_needing_clip_embedding_excludes_existing_vec(
    tmp_path,
) -> None:
    """Dump keys missing vec rows are listed; keys already embedded are omitted."""
    db_path = tmp_path / "library.db"
    conn = init_database(str(db_path))
    store_instagram_dump_media(
        conn,
        {
            "media_key": "ig_embedded",
            "file_path": "/fake/a.jpg",
            "filename": "a.jpg",
            "date_folder": "202601",
        },
    )
    store_instagram_dump_media(
        conn,
        {
            "media_key": "ig_need_vec",
            "file_path": "/fake/b.jpg",
            "filename": "b.jpg",
            "date_folder": "202602",
        },
    )
    blob = sqlite_vec.serialize_float32([0.0] * 512)
    with library_write(conn):
        upsert_image_clip_embedding(conn, "ig_embedded", blob)
    conn.close()

    conn = init_database(str(db_path))
    try:
        keys = list_instagram_dump_keys_needing_clip_embedding(
            conn,
            months=None,
            year=None,
            min_rating=None,
        )
    finally:
        conn.close()

    assert keys == ["ig_need_vec"]


@patch("jobs.handlers.add_job_log")
@patch("jobs.handlers.load_config")
def test_batch_embed_image_zero_work_completes(
    mock_load_config, _mock_add_log, tmp_path, monkeypatch
) -> None:
    from jobs.handlers import handle_batch_embed_image

    mock_enc = MagicMock()
    monkeypatch.setattr(job_handlers, "encode_images", mock_enc)

    db_path = tmp_path / "library.db"
    init_database(str(db_path)).close()
    monkeypatch.setenv("LIBRARY_DB", str(db_path))
    mock_load_config.return_value = MagicMock(db_path=str(db_path))

    runner = _make_runner()
    handle_batch_embed_image(runner, "job-zero", {"image_type": "catalog"})

    runner.complete_job.assert_called_once()
    result = runner.complete_job.call_args[0][1]
    assert result["embedded"] == 0
    assert result["total"] == 0
    mock_enc.assert_not_called()


@patch("jobs.handlers.add_job_log")
@patch("jobs.handlers.load_config")
def test_batch_embed_image_writes_clip_row(
    mock_load_config, mock_add_log, tmp_path, monkeypatch
) -> None:
    from jobs.handlers import handle_batch_embed_image

    jpg = tmp_path / "x.jpg"
    _write_min_jpg(jpg)

    db_path = tmp_path / "library.db"
    conn = init_database(str(db_path))
    store_image(
        conn,
        {
            "date_taken": "2024-05-01",
            "filename": "x.jpg",
            "filepath": str(jpg),
            "rating": 2,
        },
    )
    conn.close()

    mock_enc = MagicMock(
        return_value=np.ones((1, 512), dtype=np.float32)
    )
    monkeypatch.setattr(job_handlers, "encode_images", mock_enc)

    monkeypatch.setenv("LIBRARY_DB", str(db_path))
    mock_load_config.return_value = MagicMock(db_path=str(db_path))

    runner = _make_runner()
    handle_batch_embed_image(runner, "job-clip", {"image_type": "catalog"})

    runner.complete_job.assert_called_once()
    result = runner.complete_job.call_args[0][1]
    assert result["embedded"] == 1
    messages = [str(c.args[3]) for c in mock_add_log.call_args_list if len(c.args) > 3]
    assert any("builds similarity index only" in msg for msg in messages)

    verify = init_database(str(db_path))
    try:
        n = int(
            verify.execute("SELECT COUNT(*) AS c FROM image_clip_embeddings")
            .fetchone()["c"]
        )
        assert n == 1
    finally:
        verify.close()


@patch("jobs.handlers.add_job_log")
@patch("jobs.handlers.load_config")
def test_batch_embed_image_catalog_and_instagram_embeds_instagram_dump_row(
    mock_load_config, _mock_add_log, tmp_path, monkeypatch
) -> None:
    from jobs.handlers import handle_batch_embed_image

    ig_jpg = tmp_path / "ig.jpg"
    _write_min_jpg(ig_jpg)

    db_path = tmp_path / "library.db"
    conn = init_database(str(db_path))
    store_instagram_dump_media(
        conn,
        {
            "media_key": "ig_dump_mk",
            "file_path": str(ig_jpg),
            "filename": "ig.jpg",
            "date_folder": "202604",
        },
    )
    conn.close()

    mock_enc = MagicMock(
        return_value=np.ones((1, 512), dtype=np.float32)
    )
    monkeypatch.setattr(job_handlers, "encode_images", mock_enc)
    monkeypatch.setattr(
        job_handlers,
        "get_or_create_cached_image",
        lambda _db, _k, path: path,
    )

    monkeypatch.setenv("LIBRARY_DB", str(db_path))
    mock_load_config.return_value = MagicMock(db_path=str(db_path))

    runner = _make_runner()
    handle_batch_embed_image(
        runner,
        "job-cat-ig",
        {"image_type": "catalog_and_instagram"},
    )

    runner.complete_job.assert_called_once()
    result = runner.complete_job.call_args[0][1]
    assert result["embedded"] == 1
    assert result["total"] == 1

    verify = init_database(str(db_path))
    try:
        row = verify.execute(
            "SELECT 1 FROM image_clip_embeddings WHERE image_key = ?",
            ("ig_dump_mk",),
        ).fetchone()
        assert row is not None
    finally:
        verify.close()


@patch("jobs.handlers.add_job_log")
@patch("jobs.handlers.load_config")
def test_batch_embed_image_incremental_skips_existing(
    mock_load_config, _mock_add_log, tmp_path, monkeypatch
) -> None:
    from jobs.handlers import handle_batch_embed_image

    a = tmp_path / "a.jpg"
    b = tmp_path / "b.jpg"
    _write_min_jpg(a)
    _write_min_jpg(b)

    db_path = tmp_path / "library.db"
    conn = init_database(str(db_path))
    store_image(
        conn,
        {
            "date_taken": "2024-01-10",
            "filename": "a.jpg",
            "filepath": str(a),
            "rating": 1,
        },
    )
    store_image(
        conn,
        {
            "date_taken": "2024-01-11",
            "filename": "b.jpg",
            "filepath": str(b),
            "rating": 1,
        },
    )
    blob = sqlite_vec.serialize_float32([0.0] * 512)
    with library_write(conn):
        upsert_image_clip_embedding(
            conn, "2024-01-10_a.jpg", blob
        )
    conn.close()

    calls: list[tuple[list[str], int]] = []

    def _encode(paths, batch_size=8):
        calls.append((list(paths), batch_size))
        return np.ones((len(paths), 512), dtype=np.float32)

    monkeypatch.setattr(job_handlers, "encode_images", _encode)
    monkeypatch.setattr(
        job_handlers,
        "get_or_create_cached_image",
        lambda _db, _k, path: path,
    )

    monkeypatch.setenv("LIBRARY_DB", str(db_path))
    mock_load_config.return_value = MagicMock(db_path=str(db_path))

    runner = _make_runner()
    handle_batch_embed_image(runner, "job-inc", {"image_type": "catalog"})

    assert len(calls) == 1
    assert len(calls[0][0]) == 1
    assert calls[0][0][0] == str(b)
    res = runner.complete_job.call_args[0][1]
    assert res["embedded"] == 1


@patch("jobs.handlers.add_job_log")
@patch("jobs.handlers.load_config")
def test_batch_embed_image_force_reprocesses(
    mock_load_config, _mock_add_log, tmp_path, monkeypatch
) -> None:
    from jobs.handlers import handle_batch_embed_image

    a = tmp_path / "a.jpg"
    b = tmp_path / "b.jpg"
    _write_min_jpg(a)
    _write_min_jpg(b)

    db_path = tmp_path / "library.db"
    conn = init_database(str(db_path))
    store_image(
        conn,
        {
            "date_taken": "2024-01-10",
            "filename": "a.jpg",
            "filepath": str(a),
            "rating": 1,
        },
    )
    store_image(
        conn,
        {
            "date_taken": "2024-01-11",
            "filename": "b.jpg",
            "filepath": str(b),
            "rating": 1,
        },
    )
    blob = sqlite_vec.serialize_float32([0.0] * 512)
    with library_write(conn):
        upsert_image_clip_embedding(
            conn, "2024-01-10_a.jpg", blob
        )
        upsert_image_clip_embedding(
            conn, "2024-01-11_b.jpg", blob
        )
    conn.close()

    calls: list[tuple[list[str], int]] = []

    def _encode(paths, batch_size=8):
        calls.append((list(paths), batch_size))
        return np.ones((len(paths), 512), dtype=np.float32)

    monkeypatch.setattr(job_handlers, "encode_images", _encode)
    monkeypatch.setattr(
        job_handlers,
        "get_or_create_cached_image",
        lambda _db, _k, path: path,
    )

    monkeypatch.setenv("LIBRARY_DB", str(db_path))
    mock_load_config.return_value = MagicMock(db_path=str(db_path))

    runner = _make_runner()
    handle_batch_embed_image(
        runner, "job-f", {"image_type": "catalog", "force": True}
    )

    res = runner.complete_job.call_args[0][1]
    assert res["embedded"] == 2
    assert len(calls) == 1
    assert len(calls[0][0]) == 2
    assert calls[0][0] == [str(b), str(a)]

    verify = init_database(str(db_path))
    try:
        n = int(
            verify.execute("SELECT COUNT(*) AS c FROM image_clip_embeddings")
            .fetchone()["c"]
        )
        assert n == 2
    finally:
        verify.close()


@patch("jobs.handlers.add_job_log")
@patch("jobs.handlers.load_config")
def test_batch_embed_image_checkpoint_resume(
    mock_load_config, _mock_add_log, tmp_path, monkeypatch
) -> None:
    """Seeded checkpoint marks first key done; only second image is embedded."""
    from jobs.handlers import handle_batch_embed_image

    jobs_path = tmp_path / "jobs.db"
    lib_path = tmp_path / "library.db"
    jdb = init_db(str(jobs_path))
    job_id = create_job(jdb, "batch_embed_image", {"image_type": "catalog"})

    a = tmp_path / "a.jpg"
    b = tmp_path / "b.jpg"
    _write_min_jpg(a)
    _write_min_jpg(b)

    conn = init_database(str(lib_path))
    k1 = store_image(
        conn,
        {
            "date_taken": "2024-01-10",
            "filename": "a.jpg",
            "filepath": str(a),
            "rating": 1,
        },
    )
    k2 = store_image(
        conn,
        {
            "date_taken": "2024-01-11",
            "filename": "b.jpg",
            "filepath": str(b),
            "rating": 1,
        },
    )
    conn.close()

    keys_sorted = sorted([k1, k2])
    fp = fingerprint_batch_embed_image({"image_type": "catalog"}, keys_sorted)
    row = get_job(jdb, job_id)
    assert row is not None
    meta = dict(row.get("metadata") or {})
    meta["checkpoint"] = {
        "checkpoint_version": CHECKPOINT_VERSION,
        "job_type": "batch_embed_image",
        "fingerprint": fp,
        "processed_pairs": [k1],
        "total_at_start": 2,
    }
    update_job_field(jdb, job_id, "metadata", meta)

    calls: list[tuple[list[str], int]] = []

    def _encode(paths, batch_size=8):
        calls.append((list(paths), batch_size))
        return np.ones((len(paths), 512), dtype=np.float32)

    monkeypatch.setattr(job_handlers, "encode_images", _encode)
    monkeypatch.setattr(
        job_handlers,
        "get_or_create_cached_image",
        lambda _db, _k, path: path,
    )

    monkeypatch.setenv("LIBRARY_DB", str(lib_path))
    mock_load_config.return_value = MagicMock(db_path=str(lib_path))

    runner = JobRunner(jdb)
    handle_batch_embed_image(runner, job_id, {"image_type": "catalog"})
    jdb.close()

    assert len(calls) == 1
    assert calls[0][0] == [str(b)]


@patch("jobs.handlers.add_job_log")
@patch("jobs.handlers.load_config")
def test_batch_embed_image_fingerprint_mismatch_clears_checkpoint(
    mock_load_config, mock_add_log, tmp_path, monkeypatch
) -> None:
    from jobs.handlers import handle_batch_embed_image

    a = tmp_path / "a.jpg"
    b = tmp_path / "b.jpg"
    _write_min_jpg(a)
    _write_min_jpg(b)

    db_path = tmp_path / "library.db"
    jobs_path = tmp_path / "jobs.db"
    jdb = init_db(str(jobs_path))
    job_id = create_job(jdb, "batch_embed_image", {"image_type": "catalog"})

    conn = init_database(str(db_path))
    store_image(
        conn,
        {
            "date_taken": "2024-01-10",
            "filename": "a.jpg",
            "filepath": str(a),
            "rating": 1,
        },
    )
    store_image(
        conn,
        {
            "date_taken": "2024-01-11",
            "filename": "b.jpg",
            "filepath": str(b),
            "rating": 1,
        },
    )
    conn.close()

    row = get_job(jdb, job_id)
    meta = dict(row.get("metadata") or {})
    meta["checkpoint"] = {
        "checkpoint_version": CHECKPOINT_VERSION,
        "job_type": "batch_embed_image",
        "fingerprint": "deadbeef" * 8,
        "processed_pairs": ["2024-01-10_a.jpg"],
        "total_at_start": 2,
    }
    update_job_field(jdb, job_id, "metadata", meta)

    calls: list[tuple[list[str], int]] = []

    def _encode(paths, batch_size=8):
        calls.append((list(paths), batch_size))
        return np.ones((len(paths), 512), dtype=np.float32)

    monkeypatch.setattr(job_handlers, "encode_images", _encode)

    monkeypatch.setenv("LIBRARY_DB", str(db_path))
    mock_load_config.return_value = MagicMock(db_path=str(db_path))

    runner = JobRunner(jdb)
    handle_batch_embed_image(runner, job_id, {"image_type": "catalog"})
    jdb.close()

    messages = [c.args[3] for c in mock_add_log.call_args_list if len(c.args) > 3]
    assert any("batch_embed_image fingerprint changed" in str(m) for m in messages)
    assert len(calls) == 1
    assert len(calls[0][0]) == 2


@patch("jobs.handlers.add_job_log")
@patch("jobs.handlers.load_config")
def test_batch_embed_image_resolves_filepath_before_encode(
    mock_load_config, _mock_add_log, tmp_path, monkeypatch
) -> None:
    from jobs.handlers import handle_batch_embed_image

    resolved_jpg = tmp_path / "resolved.jpg"
    _write_min_jpg(resolved_jpg)

    db_path = tmp_path / "library.db"
    conn = init_database(str(db_path))
    store_image(
        conn,
        {
            "date_taken": "2024-02-01",
            "filename": "resolved.jpg",
            "filepath": "//tnas/ccanales/resolved.jpg",
            "rating": 1,
        },
    )
    conn.close()

    calls: list[list[str]] = []

    def _encode(paths, batch_size=8):
        calls.append(list(paths))
        return np.ones((len(paths), 512), dtype=np.float32)

    monkeypatch.setattr(job_handlers, "encode_images", _encode)
    monkeypatch.setattr(job_handlers, "resolve_filepath", lambda _p: str(resolved_jpg))
    monkeypatch.setattr(
        job_handlers,
        "get_or_create_cached_image",
        lambda _db, _k, path: path,
    )

    monkeypatch.setenv("LIBRARY_DB", str(db_path))
    mock_load_config.return_value = MagicMock(db_path=str(db_path))

    runner = _make_runner()
    handle_batch_embed_image(runner, "job-resolve", {"image_type": "catalog"})

    assert len(calls) == 1
    assert calls[0] == [str(resolved_jpg)]


@patch("jobs.handlers.add_job_log")
@patch("jobs.handlers.load_config")
def test_batch_embed_image_uses_cached_path_for_encode(
    mock_load_config, _mock_add_log, tmp_path, monkeypatch
) -> None:
    from jobs.handlers import handle_batch_embed_image

    original_jpg = tmp_path / "original.jpg"
    cached_jpg = tmp_path / "cached.jpg"
    _write_min_jpg(original_jpg)
    _write_min_jpg(cached_jpg)

    db_path = tmp_path / "library.db"
    conn = init_database(str(db_path))
    store_image(
        conn,
        {
            "date_taken": "2024-02-03",
            "filename": "original.jpg",
            "filepath": str(original_jpg),
            "rating": 1,
        },
    )
    conn.close()

    calls: list[list[str]] = []

    def _encode(paths, batch_size=8):
        calls.append(list(paths))
        return np.ones((len(paths), 512), dtype=np.float32)

    monkeypatch.setattr(job_handlers, "encode_images", _encode)
    monkeypatch.setattr(
        job_handlers,
        "get_or_create_cached_image",
        lambda _db, _k, _path: str(cached_jpg),
    )

    monkeypatch.setenv("LIBRARY_DB", str(db_path))
    mock_load_config.return_value = MagicMock(db_path=str(db_path))

    runner = _make_runner()
    handle_batch_embed_image(runner, "job-cached", {"image_type": "catalog"})

    assert len(calls) == 1
    assert calls[0] == [str(cached_jpg)]


@patch("jobs.handlers.add_job_log")
@patch("jobs.handlers.load_config")
def test_batch_embed_image_preflight_fails_fast_when_paths_inaccessible(
    mock_load_config, _mock_add_log, tmp_path, monkeypatch
) -> None:
    from jobs.handlers import handle_batch_embed_image

    db_path = tmp_path / "library.db"
    conn = init_database(str(db_path))
    for i in range(4):
        store_image(
            conn,
            {
                "date_taken": f"2024-03-{i + 1:02d}",
                "filename": f"bad-{i}.jpg",
                "filepath": "" if i % 2 == 0 else f"/definitely/missing-{i}.jpg",
                "rating": 1,
            },
        )
    conn.close()

    mock_enc = MagicMock(return_value=np.ones((1, 512), dtype=np.float32))
    monkeypatch.setattr(job_handlers, "encode_images", mock_enc)
    monkeypatch.setattr(job_handlers, "_EMBED_PREFLIGHT_SAMPLE_SIZE", 4)
    monkeypatch.setattr(job_handlers, "_EMBED_PREFLIGHT_FAIL_RATIO", 0.5)

    monkeypatch.setenv("LIBRARY_DB", str(db_path))
    mock_load_config.return_value = MagicMock(db_path=str(db_path))

    runner = _make_runner()
    handle_batch_embed_image(runner, "job-preflight", {"image_type": "catalog"})

    runner.fail_job.assert_called_once()
    fail_message = str(runner.fail_job.call_args[0][1])
    assert "Embed preflight" in fail_message
    assert "All sampled images are inaccessible" in fail_message
    assert "verify catalog filepath values" in fail_message
    runner.complete_job.assert_not_called()
    mock_enc.assert_not_called()


@patch("jobs.handlers.add_job_log")
@patch("jobs.handlers.load_config")
def test_batch_embed_image_does_not_preflight_fail_on_compression_unavailable(
    mock_load_config, _mock_add_log, tmp_path, monkeypatch
) -> None:
    from jobs.handlers import handle_batch_embed_image

    good_jpg = tmp_path / "ok.jpg"
    _write_min_jpg(good_jpg)

    db_path = tmp_path / "library.db"
    conn = init_database(str(db_path))
    store_image(
        conn,
        {
            "date_taken": "2024-03-10",
            "filename": "ok.jpg",
            "filepath": str(good_jpg),
            "rating": 1,
        },
    )
    conn.close()

    monkeypatch.setattr(job_handlers, "_EMBED_PREFLIGHT_SAMPLE_SIZE", 1)
    monkeypatch.setattr(job_handlers, "_EMBED_PREFLIGHT_FAIL_RATIO", 0.1)
    monkeypatch.setattr(
        job_handlers,
        "get_or_create_cached_image",
        lambda _db, _k, _path: None,
    )
    monkeypatch.setattr(
        job_handlers,
        "encode_images",
        lambda paths, batch_size=8: np.ones((len(paths), 512), dtype=np.float32),
    )

    monkeypatch.setenv("LIBRARY_DB", str(db_path))
    mock_load_config.return_value = MagicMock(db_path=str(db_path))

    runner = _make_runner()
    handle_batch_embed_image(runner, "job-compress-miss", {"image_type": "catalog"})

    runner.fail_job.assert_not_called()
    runner.complete_job.assert_called_once()
    result = runner.complete_job.call_args[0][1]
    assert result["embedded"] == 0
    assert result["skipped"] == 1
    assert result["skip_reason_counts"]["encode_failed"] == 1


@patch("jobs.handlers.add_job_log")
@patch("jobs.handlers.load_config")
def test_batch_embed_image_reports_grouped_skip_reason_counts(
    mock_load_config, _mock_add_log, tmp_path, monkeypatch
) -> None:
    from jobs.handlers import handle_batch_embed_image

    good_jpg = tmp_path / "good.jpg"
    _write_min_jpg(good_jpg)

    db_path = tmp_path / "library.db"
    conn = init_database(str(db_path))
    key_empty = store_image(
        conn,
        {
            "date_taken": "2024-04-01",
            "filename": "empty.jpg",
            "filepath": "",
            "rating": 1,
        },
    )
    key_missing = store_image(
        conn,
        {
            "date_taken": "2024-04-02",
            "filename": "missing.jpg",
            "filepath": "/missing/path.jpg",
            "rating": 1,
        },
    )
    key_good = store_image(
        conn,
        {
            "date_taken": "2024-04-03",
            "filename": "good.jpg",
            "filepath": str(good_jpg),
            "rating": 1,
        },
    )
    conn.close()

    missing_key = "missing-no-row-key"
    monkeypatch.setattr(
        job_handlers,
        "list_catalog_keys_needing_clip_embedding",
        lambda *args, **kwargs: [missing_key, key_empty, key_missing, key_good],
    )
    monkeypatch.setattr(job_handlers, "_EMBED_PREFLIGHT_SAMPLE_SIZE", 0)
    monkeypatch.setattr(
        job_handlers,
        "encode_images",
        lambda paths, batch_size=8: [None for _ in paths],
    )

    monkeypatch.setenv("LIBRARY_DB", str(db_path))
    mock_load_config.return_value = MagicMock(db_path=str(db_path))

    runner = _make_runner()
    handle_batch_embed_image(runner, "job-grouped-reasons", {"image_type": "catalog"})

    runner.complete_job.assert_called_once()
    result = runner.complete_job.call_args[0][1]
    assert result["embedded"] == 0
    assert result["skipped"] == 3
    assert result["failed"] == 1
    assert result["skip_reason_counts"] == {
        "no_row": 1,
        "empty_path": 1,
        "unresolved_or_missing": 1,
        "encode_failed": 1,
    }


@patch("jobs.handlers.add_job_log")
@patch("jobs.handlers.load_config")
def test_batch_embed_image_suppresses_excessive_skip_detail_logs(
    mock_load_config, mock_add_log, tmp_path, monkeypatch
) -> None:
    from jobs.handlers import handle_batch_embed_image

    db_path = tmp_path / "library.db"
    init_database(str(db_path)).close()

    missing_keys = [f"missing-{i}" for i in range(20)]
    monkeypatch.setattr(
        job_handlers,
        "list_catalog_keys_needing_clip_embedding",
        lambda *args, **kwargs: missing_keys,
    )
    monkeypatch.setattr(job_handlers, "_EMBED_PREFLIGHT_SAMPLE_SIZE", 0)
    monkeypatch.setenv("LIBRARY_DB", str(db_path))
    mock_load_config.return_value = MagicMock(db_path=str(db_path))

    runner = _make_runner()
    handle_batch_embed_image(runner, "job-skip-sampling", {"image_type": "catalog"})

    warnings = [
        str(c.args[3])
        for c in mock_add_log.call_args_list
        if len(c.args) > 3 and c.args[2] == "warning" and "skipped image embed" in str(c.args[3])
    ]
    info = [str(c.args[3]) for c in mock_add_log.call_args_list if len(c.args) > 3 and c.args[2] == "info"]

    assert len(warnings) <= job_handlers._EMBED_SKIP_DETAIL_LOG_LIMIT
    assert any("additional no_row skip logs suppressed" in msg for msg in info)


@patch("jobs.handlers.add_job_log")
@patch("jobs.handlers.load_config")
def test_batch_embed_image_uses_vision_cache_when_original_missing(
    mock_load_config, _mock_add_log, tmp_path, monkeypatch
) -> None:
    """Cache-first lookup: a usable cached JPEG is enough — original may be gone.

    Reproduces the motion-photo lrdata case: ``prepare_catalog`` already
    cached a compressed JPEG for the image, then Lightroom cleaned up the
    original. Embed must succeed off the cache without faulting.
    """
    from jobs.handlers import handle_batch_embed_image

    cached_jpg = tmp_path / "cached.jpg"
    _write_min_jpg(cached_jpg)
    missing_original = tmp_path / "missing" / "original.jpg"

    db_path = tmp_path / "library.db"
    conn = init_database(str(db_path))
    catalog_key = store_image(
        conn,
        {
            "date_taken": "2024-05-09",
            "filename": "original.jpg",
            "filepath": str(missing_original),
            "rating": 1,
        },
    )
    with library_write(conn):
        store_vision_cached_image(conn, catalog_key, str(cached_jpg), None, 12345.0)
    conn.close()

    captured_paths: list[list[str]] = []

    def _encode(paths, batch_size=8):
        captured_paths.append(list(paths))
        return np.ones((len(paths), 512), dtype=np.float32)

    monkeypatch.setattr(job_handlers, "encode_images", _encode)
    monkeypatch.setenv("LIBRARY_DB", str(db_path))
    mock_load_config.return_value = MagicMock(db_path=str(db_path))

    runner = _make_runner()
    handle_batch_embed_image(runner, "job-cache-first", {"image_type": "catalog"})

    runner.fail_job.assert_not_called()
    runner.complete_job.assert_called_once()
    result = runner.complete_job.call_args[0][1]
    assert result["embedded"] == 1
    assert result["skipped"] == 0
    assert captured_paths == [[str(cached_jpg)]]


@patch("jobs.handlers.add_job_log")
@patch("jobs.handlers.load_config")
def test_batch_embed_image_preflight_warns_and_continues_on_partial_miss(
    mock_load_config, mock_add_log, tmp_path, monkeypatch
) -> None:
    """Soft preflight: 70-99% missing logs a warning and proceeds.

    The per-file loop counts each missing file under
    ``unresolved_or_missing`` and the job completes cleanly with whatever
    embeddings did succeed.
    """
    from jobs.handlers import handle_batch_embed_image

    good_jpg = tmp_path / "good.jpg"
    _write_min_jpg(good_jpg)

    db_path = tmp_path / "library.db"
    conn = init_database(str(db_path))
    for i in range(7):
        store_image(
            conn,
            {
                "date_taken": f"2024-06-{i + 1:02d}",
                "filename": f"missing-{i}.jpg",
                "filepath": f"/definitely/missing-{i}.jpg",
                "rating": 1,
            },
        )
    store_image(
        conn,
        {
            "date_taken": "2024-06-09",
            "filename": "good.jpg",
            "filepath": str(good_jpg),
            "rating": 1,
        },
    )
    conn.close()

    monkeypatch.setattr(job_handlers, "_EMBED_PREFLIGHT_SAMPLE_SIZE", 8)
    monkeypatch.setattr(job_handlers, "_EMBED_PREFLIGHT_FAIL_RATIO", 0.5)
    monkeypatch.setattr(job_handlers, "_PREFLIGHT_RNG_SEED", 1234)
    monkeypatch.setattr(
        job_handlers,
        "encode_images",
        lambda paths, batch_size=8: np.ones((len(paths), 512), dtype=np.float32),
    )
    monkeypatch.setenv("LIBRARY_DB", str(db_path))
    mock_load_config.return_value = MagicMock(db_path=str(db_path))

    runner = _make_runner()
    handle_batch_embed_image(runner, "job-partial-miss", {"image_type": "catalog"})

    runner.fail_job.assert_not_called()
    runner.complete_job.assert_called_once()
    result = runner.complete_job.call_args[0][1]
    assert result["embedded"] == 1
    assert result["skipped"] == 7
    assert result["skip_reason_counts"]["unresolved_or_missing"] == 7
    warnings = [
        str(c.args[3])
        for c in mock_add_log.call_args_list
        if len(c.args) > 3 and c.args[2] == "warning"
    ]
    assert any(
        "Embed preflight" in msg and "Continuing" in msg for msg in warnings
    ), warnings


@patch("jobs.handlers.add_job_log")
@patch("jobs.handlers.load_config")
def test_batch_embed_image_preflight_does_not_abort_in_chain_mode(
    mock_load_config, mock_add_log, tmp_path, monkeypatch
) -> None:
    """Even at 100% sample-failure, chain_mode never aborts — chain proceeds
    to stack/similarity steps with whatever embeddings already exist."""
    from jobs.handlers import handle_batch_embed_image

    db_path = tmp_path / "library.db"
    conn = init_database(str(db_path))
    for i in range(4):
        store_image(
            conn,
            {
                "date_taken": f"2024-07-{i + 1:02d}",
                "filename": f"missing-{i}.jpg",
                "filepath": f"/definitely/missing-{i}.jpg",
                "rating": 1,
            },
        )
    conn.close()

    monkeypatch.setattr(job_handlers, "_EMBED_PREFLIGHT_SAMPLE_SIZE", 4)
    monkeypatch.setattr(job_handlers, "_EMBED_PREFLIGHT_FAIL_RATIO", 0.5)
    monkeypatch.setattr(
        job_handlers,
        "encode_images",
        lambda paths, batch_size=8: np.ones((len(paths), 512), dtype=np.float32),
    )
    monkeypatch.setenv("LIBRARY_DB", str(db_path))
    mock_load_config.return_value = MagicMock(db_path=str(db_path))

    runner = _make_runner()
    handle_batch_embed_image(
        runner,
        "job-chain-allmiss",
        {"image_type": "catalog", "_catalog_cache_chain": True},
    )

    runner.fail_job.assert_not_called()
    runner.complete_job.assert_called_once()
    result = runner.complete_job.call_args[0][1]
    assert result["embedded"] == 0
    assert result["skipped"] == 4
    warnings = [
        str(c.args[3])
        for c in mock_add_log.call_args_list
        if len(c.args) > 3 and c.args[2] == "warning"
    ]
    assert any("Embed preflight" in msg for msg in warnings), warnings
