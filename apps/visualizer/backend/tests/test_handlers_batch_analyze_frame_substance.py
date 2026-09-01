"""Tests for frame-substance chaining inside batch_analyze."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from lightroom_tagger.core.vision_op import VisionOpOutcome

_WRITTEN = VisionOpOutcome(status="written")


def _make_runner() -> MagicMock:
    runner = MagicMock()
    runner.db = MagicMock()
    runner.is_cancelled.return_value = False
    return runner


@patch("jobs.handlers.analyze.add_job_log")
@patch("lightroom_tagger.core.frame_substance_batch.run_frame_substance_detection")
@patch("jobs.handlers.analyze._score_single_image")
@patch("lightroom_tagger.core.description_service.describe_matched_image")
@patch("lightroom_tagger.core.database.get_undescribed_catalog_images")
@patch("jobs.handlers.analyze.init_database")
@patch("jobs.handlers.analyze.load_config")
@patch("jobs.handlers.analyze.os.getenv", return_value="/tmp/library.db")
@patch("jobs.handlers.common.require_library_db", return_value="/tmp/library.db")
def test_batch_analyze_runs_frame_substance_between_describe_and_score(
    _mock_exists,
    _mock_getenv,
    mock_config,
    mock_init_db,
    mock_get_undescribed,
    mock_describe,
    mock_score,
    mock_frame_substance,
    _mock_add_log,
) -> None:
    from jobs.handlers import handle_batch_analyze

    mock_config.return_value = MagicMock(db_path="/tmp/library.db")
    mock_db = MagicMock()
    mock_db.execute.return_value.fetchall.return_value = []
    mock_init_db.return_value = mock_db

    mock_get_undescribed.return_value = [{"key": "img_001"}]
    mock_describe.return_value = _WRITTEN
    mock_score.return_value = _WRITTEN
    mock_frame_substance.return_value = {
        "total": 1,
        "count_void": 0,
        "count_illegible": 0,
        "count_ok": 1,
        "count_unknown": 0,
    }

    order: list[str] = []

    def mark_describe(*_args, **_kwargs):
        order.append("describe")
        return _WRITTEN

    def mark_frame(*_args, **_kwargs):
        order.append("frame_substance")
        return {
            "total": 1,
            "count_void": 0,
            "count_illegible": 0,
            "count_ok": 1,
            "count_unknown": 0,
        }

    def mark_score(*_args, **_kwargs):
        order.append("score")
        return _WRITTEN

    mock_describe.side_effect = mark_describe
    mock_frame_substance.side_effect = mark_frame
    mock_score.side_effect = mark_score

    runner = _make_runner()
    handle_batch_analyze(
        runner,
        "job-chain-fs",
        {"image_type": "catalog", "max_workers": 1, "perspective_slugs": ["p1"]},
    )

    assert order == ["describe", "frame_substance", "score"]
    mock_frame_substance.assert_called_once()
    call_kwargs = mock_frame_substance.call_args.kwargs
    assert call_kwargs.get("stale_only") is True
    assert call_kwargs.get("image_keys") == {"img_001"}
    runner.complete_job.assert_called_once()


@patch("jobs.handlers.analyze.add_job_log")
@patch("lightroom_tagger.core.frame_substance_batch.run_frame_substance_detection")
@patch("jobs.handlers.analyze._score_single_image")
@patch("lightroom_tagger.core.description_service.describe_matched_image")
@patch("lightroom_tagger.core.database.get_undescribed_catalog_images")
@patch("jobs.handlers.analyze.init_database")
@patch("jobs.handlers.analyze.load_config")
@patch("jobs.handlers.analyze.os.getenv", return_value="/tmp/library.db")
@patch("jobs.handlers.common.require_library_db", return_value="/tmp/library.db")
def test_batch_analyze_frame_substance_failure_still_scores(
    _mock_exists,
    _mock_getenv,
    mock_config,
    mock_init_db,
    mock_get_undescribed,
    mock_describe,
    mock_score,
    mock_frame_substance,
    _mock_add_log,
) -> None:
    from jobs.handlers import handle_batch_analyze

    mock_config.return_value = MagicMock(db_path="/tmp/library.db")
    mock_db = MagicMock()
    mock_db.execute.return_value.fetchall.return_value = []
    mock_init_db.return_value = mock_db

    mock_get_undescribed.return_value = [{"key": "img_a"}, {"key": "img_b"}]
    mock_describe.return_value = _WRITTEN
    mock_score.return_value = _WRITTEN
    mock_frame_substance.side_effect = RuntimeError("detector blew up")

    runner = _make_runner()
    handle_batch_analyze(
        runner,
        "job-fs-fail",
        {"image_type": "catalog", "max_workers": 1, "perspective_slugs": ["p1"]},
    )

    runner.fail_job.assert_not_called()
    runner.complete_job.assert_called_once()
    assert mock_score.call_count == 2
