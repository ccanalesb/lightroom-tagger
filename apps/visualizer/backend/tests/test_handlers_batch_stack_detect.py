"""Tests for batch_stack_detect job handler (real library SQLite, mocked job runner)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from lightroom_tagger.core.database import init_database, store_image


def _make_runner() -> MagicMock:
    runner = MagicMock()
    runner.db = MagicMock()
    runner.is_cancelled.return_value = False
    return runner


@patch("jobs.handlers.add_job_log")
@patch("jobs.handlers.load_config")
def test_handle_batch_stack_detect_zero_work(
    mock_load_config, _mock_add_log, tmp_path, monkeypatch
) -> None:
    from jobs.handlers import handle_batch_stack_detect

    db_path = tmp_path / "library.db"
    init_database(str(db_path)).close()
    monkeypatch.setenv("LIBRARY_DB", str(db_path))
    mock_load_config.return_value = MagicMock(
        db_path=str(db_path), stack_burst_delta_ms=2000
    )

    runner = _make_runner()
    handle_batch_stack_detect(runner, "job-zero", {})

    runner.complete_job.assert_called_once()
    result = runner.complete_job.call_args[0][1]
    assert result["stacks_created"] == 0
    assert result["stacks_updated"] == 0
    assert result["images_stacked"] == 0
    assert result["images_skipped_no_date"] == 0
    assert result["images_skipped_already_stacked"] == 0
    for k in (
        "stacks_created",
        "stacks_updated",
        "images_stacked",
        "images_skipped_no_date",
        "images_skipped_already_stacked",
    ):
        assert isinstance(result[k], int)


@patch("jobs.handlers.add_job_log")
@patch("jobs.handlers.load_config")
def test_handle_batch_stack_detect_burst_creates_one_stack(
    mock_load_config, _mock_add_log, tmp_path, monkeypatch
) -> None:
    from jobs.handlers import handle_batch_stack_detect

    db_path = tmp_path / "library.db"
    conn = init_database(str(db_path))
    store_image(
        conn,
        {
            "date_taken": "2024-01-15T10:00:00+00:00",
            "filename": "a.jpg",
            "rating": 1,
        },
    )
    k_high = store_image(
        conn,
        {
            "date_taken": "2024-01-15T10:00:00.500000+00:00",
            "filename": "b.jpg",
            "rating": 5,
        },
    )
    store_image(
        conn,
        {
            "date_taken": "2024-01-15T10:00:01+00:00",
            "filename": "c.jpg",
            "rating": 2,
        },
    )
    conn.close()

    monkeypatch.setenv("LIBRARY_DB", str(db_path))
    mock_load_config.return_value = MagicMock(
        db_path=str(db_path), stack_burst_delta_ms=2000
    )

    runner = _make_runner()
    handle_batch_stack_detect(runner, "job-burst", {"delta_ms": 2000})

    runner.complete_job.assert_called_once()
    result = runner.complete_job.call_args[0][1]
    assert result["stacks_created"] == 1
    assert result["images_stacked"] == 3

    lib = init_database(str(db_path))
    try:
        st = lib.execute(
            "SELECT representative_key, stack_size FROM image_stacks"
        ).fetchone()
        assert st is not None
        assert int(st["stack_size"]) == 3
        assert st["representative_key"] == k_high
        n_members = lib.execute("SELECT COUNT(*) AS c FROM image_stack_members").fetchone()
        assert int(n_members["c"]) == 3
    finally:
        lib.close()


@patch("jobs.handlers.add_job_log")
@patch("jobs.handlers.load_config")
def test_handle_batch_stack_detect_skips_no_date_and_logs(
    mock_load_config, mock_add_log, tmp_path, monkeypatch
) -> None:
    from jobs.handlers import handle_batch_stack_detect

    db_path = tmp_path / "library.db"
    conn = init_database(str(db_path))
    store_image(
        conn,
        {
            "date_taken": None,
            "filename": "nodate.jpg",
            "rating": 0,
        },
    )
    conn.close()

    monkeypatch.setenv("LIBRARY_DB", str(db_path))
    mock_load_config.return_value = MagicMock(
        db_path=str(db_path), stack_burst_delta_ms=2000
    )

    runner = _make_runner()
    handle_batch_stack_detect(runner, "job-skip", {})

    runner.complete_job.assert_called_once()
    result = runner.complete_job.call_args[0][1]
    assert result["images_skipped_no_date"] >= 1
    assert result["images_stacked"] == 0
    # Not assigned to a stack
    lib = init_database(str(db_path))
    try:
        m = lib.execute("SELECT COUNT(*) AS c FROM image_stack_members").fetchone()
        assert int(m["c"]) == 0
    finally:
        lib.close()

    messages = [c.args[3] for c in mock_add_log.call_args_list if len(c.args) > 3]
    assert any("skipped" in str(m).lower() for m in messages)


@patch("jobs.handlers.add_job_log")
@patch("jobs.handlers.load_config")
def test_handle_batch_stack_detect_incremental_skips_stacked(
    mock_load_config, _mock_add_log, tmp_path, monkeypatch
) -> None:
    from jobs.handlers import handle_batch_stack_detect

    db_path = tmp_path / "library.db"
    conn = init_database(str(db_path))
    store_image(
        conn,
        {
            "date_taken": "2024-01-15T10:00:00+00:00",
            "filename": "a.jpg",
            "rating": 1,
        },
    )
    store_image(
        conn,
        {
            "date_taken": "2024-01-15T10:00:00.500000+00:00",
            "filename": "b.jpg",
            "rating": 5,
        },
    )
    store_image(
        conn,
        {
            "date_taken": "2024-01-15T10:00:01+00:00",
            "filename": "c.jpg",
            "rating": 2,
        },
    )
    conn.close()
    monkeypatch.setenv("LIBRARY_DB", str(db_path))
    mock_load_config.return_value = MagicMock(
        db_path=str(db_path), stack_burst_delta_ms=2000
    )

    r1 = _make_runner()
    handle_batch_stack_detect(r1, "job-inc-1", {"delta_ms": 2000})
    r1.complete_job.assert_called_once()

    r2 = _make_runner()
    handle_batch_stack_detect(r2, "job-inc-2", {})
    r2.complete_job.assert_called_once()
    res2 = r2.complete_job.call_args[0][1]
    assert res2["images_skipped_already_stacked"] >= 3
    assert res2["stacks_created"] == 0


@patch("jobs.handlers.add_job_log")
@patch("jobs.handlers.load_config")
def test_handle_batch_stack_detect_force_rebuild_recreates(
    mock_load_config, _mock_add_log, tmp_path, monkeypatch
) -> None:
    from jobs.handlers import handle_batch_stack_detect

    db_path = tmp_path / "library.db"
    conn = init_database(str(db_path))
    store_image(
        conn,
        {
            "date_taken": "2024-01-15T10:00:00+00:00",
            "filename": "a.jpg",
            "rating": 1,
        },
    )
    store_image(
        conn,
        {
            "date_taken": "2024-01-15T10:00:00.500000+00:00",
            "filename": "b.jpg",
            "rating": 5,
        },
    )
    store_image(
        conn,
        {
            "date_taken": "2024-01-15T10:00:01+00:00",
            "filename": "c.jpg",
            "rating": 2,
        },
    )
    conn.close()
    monkeypatch.setenv("LIBRARY_DB", str(db_path))
    mock_load_config.return_value = MagicMock(
        db_path=str(db_path), stack_burst_delta_ms=2000
    )

    r1 = _make_runner()
    handle_batch_stack_detect(r1, "job-f1", {"delta_ms": 2000})
    r1.complete_job.assert_called_once()

    r2 = _make_runner()
    handle_batch_stack_detect(r2, "job-f2", {"force": True, "delta_ms": 2000})
    r2.complete_job.assert_called_once()
    res2 = r2.complete_job.call_args[0][1]
    assert res2["stacks_created"] == 1
    assert res2["images_stacked"] == 3

    lib = init_database(str(db_path))
    try:
        n_st = lib.execute("SELECT COUNT(*) AS c FROM image_stacks").fetchone()
        n_m = lib.execute("SELECT COUNT(*) AS c FROM image_stack_members").fetchone()
        assert int(n_st["c"]) == 1
        assert int(n_m["c"]) == 3
    finally:
        lib.close()
