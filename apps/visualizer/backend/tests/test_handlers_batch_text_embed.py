"""Tests for batch_text_embed job handler (mocked embed_texts, real library SQLite)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from lightroom_tagger.core.database import init_database, store_image, store_image_description


def _make_runner():
    runner = MagicMock()
    runner.db = MagicMock()
    runner.is_cancelled.return_value = False
    return runner


@patch("jobs.handlers.add_job_log")
@patch("jobs.handlers.load_config")
def test_batch_text_embed_zero_work_completes(mock_load_config, _mock_add_log, tmp_path, monkeypatch):
    from jobs.handlers import handle_batch_text_embed

    db_path = tmp_path / "library.db"
    init_database(str(db_path)).close()
    monkeypatch.setenv("LIBRARY_DB", str(db_path))
    mock_load_config.return_value = MagicMock(db_path=str(db_path))

    runner = _make_runner()
    handle_batch_text_embed(runner, "job-zero", {"image_type": "catalog"})

    runner.complete_job.assert_called_once()
    result = runner.complete_job.call_args[0][1]
    assert result["embedded"] == 0
    assert result["total"] == 0


@patch("jobs.handlers.add_job_log")
@patch("jobs.handlers.load_config")
def test_batch_text_embed_writes_vec_row(mock_load_config, _mock_add_log, tmp_path, monkeypatch):
    from jobs import handlers
    from jobs.handlers import handle_batch_text_embed

    db_path = tmp_path / "library.db"
    conn = init_database(str(db_path))
    image_key = store_image(
        conn,
        {
            "date_taken": "2024-05-01",
            "filename": "embedme.jpg",
            "rating": 2,
        },
    )
    store_image_description(
        conn,
        {
            "image_key": image_key,
            "image_type": "catalog",
            "summary": "non-empty summary for embed",
            "subjects": [],
            "best_perspective": "p",
            "perspectives": {},
            "composition": {},
            "technical": {},
            "model_used": "t",
        },
    )
    conn.close()

    monkeypatch.setenv("LIBRARY_DB", str(db_path))
    mock_load_config.return_value = MagicMock(db_path=str(db_path))
    monkeypatch.setattr(
        handlers,
        "embed_texts",
        lambda texts, batch_size=16: np.ones((len(texts), 768), dtype=np.float32),
    )

    runner = _make_runner()
    handle_batch_text_embed(runner, "job-embed", {"image_type": "catalog"})

    runner.complete_job.assert_called_once()
    result = runner.complete_job.call_args[0][1]
    assert result["embedded"] == 1

    verify = init_database(str(db_path))
    try:
        row = verify.execute(
            "SELECT COUNT(*) AS c FROM image_text_embeddings"
        ).fetchone()
        assert int(row["c"]) == 1
    finally:
        verify.close()
