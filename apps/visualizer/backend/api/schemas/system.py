"""System and cache health API response models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SystemStatusResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    status: str


class Stats(BaseModel):
    model_config = ConfigDict(extra='forbid')

    catalog_images: int
    instagram_images: int
    posted_to_instagram: int
    matches_found: int
    db_path: str


class VisionModelEntry(BaseModel):
    model_config = ConfigDict(extra='forbid')

    name: str
    provider_id: str | None = None
    default: bool


class VisionModelsResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    models: list[VisionModelEntry]
    fallback: bool


class CatalogCacheReadyResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    cached: bool


class CacheStatus(BaseModel):
    model_config = ConfigDict(extra='forbid')

    total_images: int
    cached_images: int
    missing: int
    cache_size_mb: float
    cache_dir: str


class CachePipelineRun(BaseModel):
    model_config = ConfigDict(extra='forbid')

    job_id: str
    type: str
    status: str
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None


class CachePipelineStatus(BaseModel):
    model_config = ConfigDict(extra='forbid')

    catalog_sync: CachePipelineRun | None = None
    embed_catalog: CachePipelineRun | None = None
    embed_catalog_and_instagram: CachePipelineRun | None = None
    stack_detect: CachePipelineRun | None = None
    catalog_similarity: CachePipelineRun | None = None
    catalog_cache_build: CachePipelineRun | None = None
    prepare_catalog: CachePipelineRun | None = None
