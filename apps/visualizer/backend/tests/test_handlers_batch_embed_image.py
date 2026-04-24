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
    store_image,
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
    mock_load_config, _mock_add_log, tmp_path, monkeypatch
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
