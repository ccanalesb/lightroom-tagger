"""Perspectives API response models — single source of truth for perspective shapes."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, RootModel


class PerspectiveSummary(BaseModel):
    model_config = ConfigDict(extra='forbid')

    id: int
    slug: str
    display_name: str
    description: str
    active: bool
    optional: bool
    source_filename: str | None = None
    updated_at: str | None = None


class PerspectiveDetail(PerspectiveSummary):
    prompt_markdown: str
    created_at: str | None = None


class PerspectiveScore(BaseModel):
    """Nested perspective line item in image descriptions."""

    model_config = ConfigDict(extra='forbid')

    analysis: str
    score: int


class PerspectiveListResponse(RootModel[list[PerspectiveSummary]]):
    """``GET /api/perspectives/`` response body."""


def validate_perspective_summary(row: dict) -> dict:
    """Validate a list-row dict; raises on shape drift."""
    return PerspectiveSummary.model_validate(row).model_dump(mode='json')


def validate_perspective_detail(row: dict) -> dict:
    """Validate a detail-row dict; raises on shape drift."""
    return PerspectiveDetail.model_validate(row).model_dump(mode='json')
