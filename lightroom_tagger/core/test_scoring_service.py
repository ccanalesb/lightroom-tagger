"""Tests for :mod:`lightroom_tagger.core.scoring_service`."""

from __future__ import annotations

from contextlib import ExitStack
from unittest.mock import MagicMock, patch

from lightroom_tagger.core.database import (
    get_current_scores_for_image,
    init_database,
    insert_perspective,
)
from lightroom_tagger.core.provider_registry import ProviderRegistry
from lightroom_tagger.core.provider_resolution import ResolvedModel, resolve_model
from lightroom_tagger.core.scoring_service import (
    compute_prompt_version,
    score_image_for_perspective,
)


def _fake_registry(
    *,
    defaults: dict | None = None,
    fallback_order: list[str] | None = None,
) -> MagicMock:
    registry = MagicMock(spec=ProviderRegistry)
    registry.defaults = defaults or {}
    registry.fallback_order = fallback_order or []
    return registry


def _scoring_patches(
    *,
    mock_registry: MagicMock,
    mock_dispatcher: MagicMock,
    provider_id: str = "ollama",
    model: str = "vision-model",
):
    """Patch resolve_model + vision path helpers for scoring integration tests."""
    return (
        patch(
            "lightroom_tagger.core.vision_op.resolve_model",
            return_value=ResolvedModel(provider_id, model, mock_registry),
        ),
        patch(
            "lightroom_tagger.core.vision_op.FallbackDispatcher",
            return_value=mock_dispatcher,
        ),
        patch(
            "lightroom_tagger.core.analyzer.scoring.get_viewable_path_managed",
            side_effect=lambda p: (p, False),
        ),
        patch(
            "lightroom_tagger.core.analyzer.scoring.compress_image",
            side_effect=lambda p: p,
        ),
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

    mock_registry = _fake_registry()
    mock_client = MagicMock()
    mock_registry.get_client.return_value = mock_client

    mock_dispatcher = MagicMock()
    mock_dispatcher.call_with_fallback.return_value = (raw_json, "ollama", "vision-model")

    with ExitStack() as stack:
        stack.enter_context(
            patch(
                "lightroom_tagger.core.analyzer.scoring.parse_score_response_with_retry",
                side_effect=assert_fixer_not_none,
            ),
        )
        for p in _scoring_patches(mock_registry=mock_registry, mock_dispatcher=mock_dispatcher):
            stack.enter_context(p)
        outcome = score_image_for_perspective(
            conn,
            image_key="2020-01-01_test.jpg",
            image_type="catalog",
            perspective_slug="score_test_persp",
            force=True,
            provider_id="ollama",
            model="vision-model",
            log_callback=None,
        )

    assert outcome.reason is None
    assert outcome.wrote is True

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


def test_score_image_persists_not_attempted_for_optional_perspective(tmp_path) -> None:
    conn = init_database(str(tmp_path / "library.db"))
    insert_perspective(
        conn,
        slug="opt_persp",
        display_name="Optional persp",
        prompt_markdown="<!-- optional: true -->\nEvaluate the optional technique.",
        description="",
    )
    conn.commit()

    img_path = tmp_path / "2020-01-01_opt.jpg"
    img_path.write_bytes(b"x")
    conn.execute(
        "INSERT INTO images (key, filepath, date_taken, filename) VALUES (?, ?, ?, ?)",
        ("2020-01-01_opt.jpg", str(img_path), "2020-01-01", "opt.jpg"),
    )
    conn.commit()

    raw_json = (
        '{"perspective_slug": "opt_persp", "score": 5, '
        '"rationale": "Technique absent.", "not_attempted": true}'
    )

    captured: dict[str, str] = {}

    def capture_prompt(prow: dict) -> str:
        from lightroom_tagger.core.prompt_builder import build_scoring_user_prompt as real

        out = real(prow)
        captured["prompt"] = out
        return out

    mock_registry = _fake_registry()
    mock_registry.get_client.return_value = MagicMock()
    mock_dispatcher = MagicMock()
    mock_dispatcher.call_with_fallback.return_value = (raw_json, "ollama", "vision-model")

    with ExitStack() as stack:
        stack.enter_context(
            patch(
                "lightroom_tagger.core.scoring_service.build_scoring_user_prompt",
                side_effect=capture_prompt,
            ),
        )
        for p in _scoring_patches(mock_registry=mock_registry, mock_dispatcher=mock_dispatcher):
            stack.enter_context(p)
        outcome = score_image_for_perspective(
            conn,
            image_key="2020-01-01_opt.jpg",
            image_type="catalog",
            perspective_slug="opt_persp",
            force=True,
            provider_id="ollama",
            model="vision-model",
            log_callback=None,
        )

    assert outcome.reason is None
    assert outcome.wrote is True
    assert '"not_attempted"' in captured["prompt"]
    rows = get_current_scores_for_image(conn, "2020-01-01_opt.jpg", "catalog")
    assert rows[0]["not_attempted"] == 1
    assert rows[0]["score"] == 5


def test_score_image_honors_description_vision_model_env(tmp_path, monkeypatch) -> None:
    """Scoring must use resolve_model so DESCRIPTION_VISION_MODEL env is honoured."""
    monkeypatch.setenv("DESCRIPTION_VISION_MODEL", "env-desc-model")

    conn = init_database(str(tmp_path / "library.db"))
    insert_perspective(
        conn,
        slug="env_persp",
        display_name="Env test",
        prompt_markdown="Score it.",
        description="",
    )
    conn.commit()

    img_path = tmp_path / "2020-01-01_env.jpg"
    img_path.write_bytes(b"x")
    conn.execute(
        "INSERT INTO images (key, filepath, date_taken, filename) VALUES (?, ?, ?, ?)",
        ("2020-01-01_env.jpg", str(img_path), "2020-01-01", "env.jpg"),
    )
    conn.commit()

    raw_json = '{"perspective_slug": "env_persp", "score": 7, "rationale": "OK."}'
    registry = _fake_registry(
        defaults={"description": {"provider": "ollama", "model": "json-default"}},
        fallback_order=["ollama"],
    )
    registry.get_client.return_value = MagicMock()

    mock_dispatcher = MagicMock()
    mock_dispatcher.call_with_fallback.return_value = (raw_json, "ollama", "env-desc-model")

    with (
        patch(
            "lightroom_tagger.core.provider_resolution.ProviderRegistry",
            return_value=registry,
        ),
        patch(
            "lightroom_tagger.core.vision_op.resolve_model",
            wraps=resolve_model,
        ),
        patch(
            "lightroom_tagger.core.vision_op.FallbackDispatcher",
            return_value=mock_dispatcher,
        ),
        patch(
            "lightroom_tagger.core.analyzer.scoring.get_viewable_path_managed",
            side_effect=lambda p: (p, False),
        ),
        patch(
            "lightroom_tagger.core.analyzer.scoring.compress_image",
            side_effect=lambda p: p,
        ),
    ):
        outcome = score_image_for_perspective(
            conn,
            image_key="2020-01-01_env.jpg",
            image_type="catalog",
            perspective_slug="env_persp",
            force=True,
            provider_id="ollama",
            model=None,
            log_callback=None,
        )

    assert outcome.reason is None
    assert outcome.wrote is True
    assert mock_dispatcher.call_with_fallback.call_args.kwargs["model"] == "env-desc-model"


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
        patch("lightroom_tagger.core.vision_op.resolve_model") as mock_resolve,
        patch("lightroom_tagger.core.vision_op.FallbackDispatcher") as mock_disp,
        patch("lightroom_tagger.core.analyzer.scoring.compress_image") as mock_compress,
    ):
        outcome = score_image_for_perspective(
            conn,
            image_key="2024-06-01_clip",
            image_type="catalog",
            perspective_slug="video_skip_test",
            force=True,
            provider_id="ollama",
            model="vision-model",
            log_callback=None,
        )

    assert outcome.status == "skipped"
    assert outcome.wrote is False
    assert outcome.reason is not None and "Video file not scorable" in outcome.reason
    mock_resolve.assert_not_called()
    mock_disp.assert_not_called()
    mock_compress.assert_not_called()
    rows = get_current_scores_for_image(conn, "2024-06-01_clip", "catalog")
    assert rows == []
