"""Tests for :mod:`lightroom_tagger.core.scoring_service`."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from lightroom_tagger.core.database import (
    get_current_scores_for_image,
    init_database,
    insert_perspective,
)
from lightroom_tagger.core.scoring_service import (
    compute_prompt_version,
    score_image_for_perspective,
)


def test_compute_prompt_version_changes_when_prompt_markdown_changes() -> None:
    a = compute_prompt_version(
        {"slug": "street", "display_name": "Street", "prompt_markdown": "v1"},
    )
    b = compute_prompt_version(
        {"slug": "street", "display_name": "Street", "prompt_markdown": "v2"},
    )
    assert a != b


def test_compute_prompt_version_stable_for_identical_markdown() -> None:
    row = {"slug": "doc", "display_name": "Doc", "prompt_markdown": "same body"}
    assert compute_prompt_version(row) == compute_prompt_version(dict(row))


def test_score_image_persists_row_and_passes_llm_fixer(tmp_path) -> None:
    db_path = tmp_path / "library.db"
    conn = init_database(str(db_path))
    insert_perspective(
        conn,
        slug="score_test_persp",
        display_name="Score test",
        prompt_markdown="Score harshly.",
        description="",
    )
    conn.commit()

    img_path = tmp_path / "2020-01-01_test.jpg"
    img_path.write_bytes(b"x")
    conn.execute(
        """
        INSERT INTO images (key, filepath, date_taken, filename)
        VALUES (?, ?, ?, ?)
        """,
        ("2020-01-01_test.jpg", str(img_path), "2020-01-01", "test.jpg"),
    )
    conn.commit()

    raw_json = (
        '{"perspective_slug": "score_test_persp", "score": 8, "rationale": "Strong geometry."}'
    )

    def assert_fixer_not_none(raw: str, **kwargs: object):
        assert kwargs.get("llm_fixer") is not None
        from lightroom_tagger.core.structured_output import parse_score_response_with_retry

        return parse_score_response_with_retry(raw, **kwargs)

    mock_registry = MagicMock()
    mock_client = MagicMock()
    mock_registry.list_models.return_value = [{"id": "vision-model", "vision": True}]
    mock_registry.get_client.return_value = mock_client

    mock_dispatcher = MagicMock()
    mock_dispatcher.call_with_fallback.return_value = (raw_json, "ollama", "vision-model")

    with (
        patch(
            "lightroom_tagger.core.scoring_service.parse_score_response_with_retry",
            side_effect=assert_fixer_not_none,
        ),
        patch(
            "lightroom_tagger.core.scoring_service.ProviderRegistry",
            return_value=mock_registry,
        ),
        patch(
            "lightroom_tagger.core.scoring_service.FallbackDispatcher",
            return_value=mock_dispatcher,
        ),
        patch(
            "lightroom_tagger.core.scoring_service.get_viewable_path",
            side_effect=lambda p: p,
        ),
        patch(
            "lightroom_tagger.core.scoring_service.compress_image",
            side_effect=lambda p: p,
        ),
    ):
        status, ok, err = score_image_for_perspective(
            conn,
            image_key="2020-01-01_test.jpg",
            image_type="catalog",
            perspective_slug="score_test_persp",
            force=True,
            provider_id="ollama",
            model="vision-model",
            log_callback=None,
        )

    assert err is None
    assert status == "scored"
    assert ok is True

    rows = get_current_scores_for_image(conn, "2020-01-01_test.jpg", "catalog")
    assert len(rows) == 1
    assert rows[0]["score"] == 8
    assert rows[0]["is_current"] == 1
    assert rows[0]["prompt_version"] == compute_prompt_version(
        {
            "slug": "score_test_persp",
            "display_name": "Score test",
            "prompt_markdown": "Score harshly.",
        },
    )


def test_score_image_skips_video_without_calling_provider(tmp_path) -> None:
    """Video files must short-circuit before the vision dispatcher — otherwise
    compress_image silently returns the raw bytes and the provider spends
    minutes retrying, wedging the scoring worker pool."""
    db_path = tmp_path / "library.db"
    conn = init_database(str(db_path))
    insert_perspective(
        conn,
        slug="video_skip_test",
        display_name="Video skip test",
        prompt_markdown="unused",
        description="",
    )
    conn.commit()

    video_path = tmp_path / "2024-06-01_clip.mov"
    video_path.write_bytes(b"not an image")
    conn.execute(
        "INSERT INTO images (key, filepath, date_taken, filename) VALUES (?, ?, ?, ?)",
        ("2024-06-01_clip", str(video_path), "2024-06-01", "clip.mov"),
    )
    conn.commit()

    with (
        patch("lightroom_tagger.core.scoring_service.FallbackDispatcher") as mock_disp,
        patch("lightroom_tagger.core.scoring_service.compress_image") as mock_compress,
    ):
        status, ok, err = score_image_for_perspective(
            conn,
            image_key="2024-06-01_clip",
            image_type="catalog",
            perspective_slug="video_skip_test",
            force=True,
            provider_id="ollama",
            model="vision-model",
            log_callback=None,
        )

    assert status == "skipped"
    assert ok is False
    assert err is not None and "Video file not scorable" in err
    mock_disp.assert_not_called()
    mock_compress.assert_not_called()
    # And nothing was written to image_scores
    rows = get_current_scores_for_image(conn, "2024-06-01_clip", "catalog")
    assert rows == []
