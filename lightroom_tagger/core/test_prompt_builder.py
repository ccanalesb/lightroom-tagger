"""Tests for :mod:`lightroom_tagger.core.prompt_builder`."""

from __future__ import annotations

from lightroom_tagger.core.prompt_builder import (
    build_description_user_prompt,
    build_scoring_user_prompt,
)


def test_build_scoring_user_prompt_omits_not_attempted_for_baseline_perspective() -> None:
    row = {
        "slug": "street",
        "display_name": "Street",
        "prompt_markdown": "## Street\nEvaluate geometry.",
    }
    out = build_scoring_user_prompt(row)
    assert "not_attempted" not in out


def test_build_scoring_user_prompt_gates_not_attempted_on_optional_perspective() -> None:
    row = {
        "slug": "framing",
        "display_name": "Framing",
        "prompt_markdown": "## Framing\nEvaluate the framing device.",
        "optional": 1,
    }
    out = build_scoring_user_prompt(row)
    assert '"not_attempted"' in out
    assert "genuinely absent" in out
    assert "score low" in out.lower()


def test_build_description_user_prompt_is_prose_only_without_scoring() -> None:
    out = build_description_user_prompt()
    assert "summary" in out
    assert "composition" in out
    assert "subjects" in out
    assert "mood_tags" in out
    assert "dominant_colors" in out
    assert '"perspectives"' not in out
    assert '"best_perspective"' not in out
    assert '"score"' not in out
    assert "1-10" not in out
    for slug in ("street", "documentary", "publisher", "color_theory"):
        assert slug not in out
