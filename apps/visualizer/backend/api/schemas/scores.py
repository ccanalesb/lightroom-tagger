"""Scores API response models — single source of truth for image_scores shapes."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ImageScoreRow(BaseModel):
    model_config = ConfigDict(extra='forbid')

    id: int | None = None
    image_key: str
    image_type: str
    perspective_slug: str
    score: int
    rationale: str = ''
    model_used: str = ''
    prompt_version: str = ''
    scored_at: str
    is_current: bool
    repaired_from_malformed: bool = False
    not_attempted: bool = False


class ScoresCurrentResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    image_key: str
    image_type: str
    current: list[ImageScoreRow]


class ScoresHistoryResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    image_key: str
    image_type: str
    perspective_slug: str
    history: list[ImageScoreRow]


def validate_image_score_row(row: dict) -> dict:
    """Validate a normalized score row; raises on shape drift."""
    return ImageScoreRow.model_validate(row).model_dump(mode='json')
