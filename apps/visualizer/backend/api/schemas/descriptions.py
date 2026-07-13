"""Descriptions API response models — single source of truth for description shapes."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from api.schemas.jobs import PaginationMeta
from api.schemas.perspectives import PerspectiveScore

ImageType = Literal['catalog', 'instagram']


class DescriptionComposition(BaseModel):
    model_config = ConfigDict(extra='allow')

    layers: list[str] | None = None
    techniques: list[str] | None = None
    problems: list[str] | None = None
    depth: str | None = None
    balance: str | None = None


class DescriptionTechnical(BaseModel):
    model_config = ConfigDict(extra='allow')

    dominant_colors: list[str] | None = None
    mood: str | None = None
    lighting: str | None = None
    time_of_day: str | None = None


class DescriptionPerspectives(BaseModel):
    model_config = ConfigDict(extra='allow')

    street: PerspectiveScore | None = None
    documentary: PerspectiveScore | None = None
    publisher: PerspectiveScore | None = None


class ImageDescription(BaseModel):
    """Full description row returned by ``GET /api/descriptions/<image_key>``."""

    model_config = ConfigDict(extra='allow')

    image_key: str
    image_type: str
    summary: str = ''
    composition: DescriptionComposition | None = None
    perspectives: DescriptionPerspectives | None = None
    technical: DescriptionTechnical | None = None
    subjects: list[str] = Field(default_factory=list)
    best_perspective: str = ''
    model_used: str = ''
    described_at: str | None = None


class DescriptionItem(BaseModel):
    model_config = ConfigDict(extra='forbid')

    image_key: str
    image_type: ImageType
    filename: str | None = None
    date_ref: str | None = None
    summary: str | None = None
    best_perspective: str | None = None
    desc_model: str | None = None
    described_at: str | None = None
    has_description: int


class DescriptionsListResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    total: int
    items: list[DescriptionItem]
    pagination: PaginationMeta


class DescriptionGetResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    description: ImageDescription | None


class DescriptionGenerateRequest(BaseModel):
    image_type: str = 'catalog'
    force: bool = False
    model: str | None = None
    provider_id: str | None = None
    provider_model: str | None = None


class DescriptionGenerateResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    generated: bool
    description: ImageDescription | None


def validate_description_item(row: dict) -> dict:
    """Validate a list-row dict; raises on shape drift."""
    return DescriptionItem.model_validate(row).model_dump(mode='json')


def validate_image_description(row: dict) -> dict:
    """Validate a description dict; raises on shape drift."""
    return ImageDescription.model_validate(row).model_dump(mode='json')
