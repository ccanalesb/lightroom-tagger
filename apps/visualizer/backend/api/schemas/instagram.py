"""Instagram dump list and detail API models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from api.schemas.jobs import PaginationMeta


class InstagramExifData(BaseModel):
    model_config = ConfigDict(extra='allow')

    latitude: float | None = None
    longitude: float | None = None
    date_time_original: str | None = None
    device_id: str | None = None
    lens_model: str | None = None
    iso: int | None = None
    aperture: str | None = None
    shutter_speed: str | None = None


class InstagramImage(BaseModel):
    model_config = ConfigDict(extra='forbid')

    key: str
    local_path: str
    filename: str
    instagram_folder: str
    source_folder: str
    date_folder: str
    crawled_at: str
    image_index: int
    total_in_post: int
    post_url: str | None = None
    created_at: str | None = None
    image_hash: str | None = None
    phash: str | None = None
    description: str | None = None
    caption: str | None = None
    processed: bool | None = None
    matched_catalog_key: str | None = None
    matched_model: str | None = None
    match_score: float | None = None
    exif_data: dict[str, Any] | InstagramExifData | None = None


class InstagramListResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    total: int
    images: list[InstagramImage]
    pagination: PaginationMeta


class InstagramMonthsResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    months: list[str]


def validate_instagram_image(row: dict) -> dict:
    return InstagramImage.model_validate(row).model_dump(mode='json')
