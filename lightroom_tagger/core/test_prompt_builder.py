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


def test_build_description_user_prompt_includes_slugs_and_perspective_count() -> None:
    rows = [
        {
            "slug": "street",
            "display_name": "Street",
            "prompt_markdown": "## Street\nEvaluate geometry.",
        },
        {
            "slug": "color_theory",
            "display_name": "Color Theory",
            "prompt_markdown": "## Color\nEvaluate palette.",
        },
    ]
    out = build_description_user_prompt(rows)
    assert "color_theory" in out
    assert "Analyze this photograph from 2 expert perspectives" in out
