"""Catalog browse, similarity, and image-detail API models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

class IdentityPerPerspectiveScore(BaseModel):
    model_config = ConfigDict(extra='forbid')

    perspective_slug: str
    display_name: str
    score: int
    prompt_version: str
    model_used: str
    scored_at: str
    rationale_preview: str


class CatalogImage(BaseModel):
    """Catalog list / search row shape (``query_catalog_images`` + API transforms)."""

    model_config = ConfigDict(extra='forbid')

    key: str
    id: int | None = None
    filename: str | None = None
    filepath: str | None = None
    date_taken: str | None = None
    rating: int | None = None
    pick: bool | None = None
    color_label: str | None = None
    keywords: list[str] = Field(default_factory=list)
    title: str | None = None
    caption: str | None = None
    description: str | None = None
    copyright: str | None = None
    width: int | None = None
    height: int | None = None
    instagram_posted: bool | None = None
    instagram_url: str | None = None
    image_hash: str | None = None
    image_type: Literal['catalog', 'instagram'] | None = None
    ai_analyzed: bool | None = None
    description_summary: str | None = None
    description_best_perspective: str | None = None
    description_perspectives: dict[str, Any] | None = None
    catalog_perspective_score: int | None = None
    catalog_score_perspective: str | None = None
    stack_id: int | None = None
    stack_member_count: int | None = None
    is_stack_representative: bool | None = None
    analyzed_at: str | None = None
    aperture: str | None = None
    camera_make: str | None = None
    camera_model: str | None = None
    catalog_path: str | None = None
    exif: str | None = None
    file_size: int | None = None
    focal_length: str | None = None
    gps_latitude: float | None = None
    gps_longitude: float | None = None
    instagram_index: int | None = None
    instagram_post_date: str | None = None
    iso: str | None = None
    lens: str | None = None
    phash: str | None = None
    shutter_speed: str | None = None
    similarity: float | None = None
    why_matched: str | None = None
    thumbnail_url: str | None = None
    score: float | None = None


class CatalogListResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    total: int
    images: list[CatalogImage]


class CatalogMonthsResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    months: list[str]


class ClipSimilarMeta(BaseModel):
    model_config = ConfigDict(extra='forbid')

    clip_model_id: str
    clip_embed_dim: int
    knn_fetched: int
    knn_k_used: int | None = None


class CatalogSimilarResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    images: list[CatalogImage]
    total: int
    meta: ClipSimilarMeta


class CatalogSimilarityGroup(BaseModel):
    model_config = ConfigDict(extra='forbid')

    group_id: int
    seed: CatalogImage
    candidates: list[CatalogImage]
    candidate_count: int
    best_similarity: float
    job_id: str | None = None
    created_at: str | None = None


class CatalogSimilarityGroupsResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    items: list[CatalogSimilarityGroup]
    total: int


class ImageView(BaseModel):
    """``GET /api/images/<image_type>/<image_key>`` consolidated detail shape."""

    model_config = ConfigDict(extra='forbid')

    image_type: Literal['catalog', 'instagram']
    key: str
    id: int | None = None
    filename: str | None = None
    filepath: str | None = None
    local_path: str | None = None
    date_taken: str | None = None
    created_at: str | None = None
    rating: int | None = None
    pick: bool | None = None
    color_label: str | None = None
    keywords: list[str] | None = None
    title: str | None = None
    caption: str | None = None
    copyright: str | None = None
    width: int | None = None
    height: int | None = None
    instagram_posted: bool | None = None
    instagram_url: str | None = None
    post_url: str | None = None
    image_hash: str | None = None
    stack_id: int | None = None
    stack_member_count: int | None = None
    is_stack_representative: bool | None = None
    instagram_folder: str | None = None
    date_folder: str | None = None
    source_folder: str | None = None
    matched_catalog_key: str | None = None
    processed: bool | None = None
    ai_analyzed: bool | None = None
    description_summary: str | None = None
    description_best_perspective: str | None = None
    catalog_perspective_score: int | None = None
    catalog_score_perspective: str | None = None
    available_score_perspectives: list[str] | None = None
    identity_aggregate_score: float | None = None
    identity_perspectives_covered: int | None = None
    identity_eligible: bool | None = None
    identity_per_perspective: list[IdentityPerPerspectiveScore] = Field(default_factory=list)
    analyzed_at: str | None = None
    aperture: str | None = None
    camera_make: str | None = None
    camera_model: str | None = None
    catalog_path: str | None = None
    description: str | None = None
    exif: str | None = None
    exif_data: Any | None = None
    file_size: int | None = None
    focal_length: str | None = None
    gps_latitude: float | None = None
    gps_longitude: float | None = None
    instagram_index: int | None = None
    instagram_post_date: str | None = None
    iso: str | None = None
    lens: str | None = None
    phash: str | None = None
    shutter_speed: str | None = None
    added_at: str | None = None
    file_path: str | None = None
    last_attempted_at: str | None = None
    media_key: str | None = None
    processed_at: str | None = None
    vision_result: str | None = None
    vision_score: float | None = None


ImageDetailResponse = ImageView


def validate_catalog_image(row: dict) -> dict:
    return CatalogImage.model_validate(row).model_dump(mode='json')


def validate_image_view(row: dict) -> dict:
    return ImageView.model_validate(row).model_dump(mode='json')
