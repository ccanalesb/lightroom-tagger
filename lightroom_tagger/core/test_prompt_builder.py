"""Tests for :mod:`lightroom_tagger.core.prompt_builder`."""

from __future__ import annotations

from lightroom_tagger.core.prompt_builder import build_description_user_prompt


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
