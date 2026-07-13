"""Scores API response models — single source of truth for image_scores shapes."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class ImageScoreRow(BaseModel):
    model_config = ConfigDict(extra='forbid')

    id: int | None = None
    image_key: str
    image_type: str
    perspective_slug: str
    score: int
    rationale: str | None = None
    model_used: str | None = None
    prompt_version: str
    scored_at: str
    is_current: bool
    repaired_from_malformed: bool
    not_attempted: bool = False


class ScoresCurrentResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    image_key: str
    image_type: Literal['catalog', 'instagram']
    current: list[ImageScoreRow]


class ScoresHistoryResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    image_key: str
    image_type: Literal['catalog', 'instagram']
    perspective_slug: str
    history: list[ImageScoreRow]


def validate_image_score_row(row: dict) -> dict:
    return ImageScoreRow.model_validate(row).model_dump(mode='json')
