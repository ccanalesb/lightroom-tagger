"""Analytics API response and query models — posting frequency, heatmap, captions, unposted catalog."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from api.schemas.jobs import PaginationMeta

AnalyticsGranularity = Literal['day', 'week', 'month']


class PostingFrequencyBucket(BaseModel):
    model_config = ConfigDict(extra='forbid')

    bucket_start: str
    count: int


class PostingFrequencyMeta(BaseModel):
    model_config = ConfigDict(extra='forbid')

    timestamp_source: str | None = None
    granularity: AnalyticsGranularity | None = None
    timezone_assumption: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    bucket_expression: str | None = None


class PostingFrequencyResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    buckets: list[PostingFrequencyBucket]
    meta: PostingFrequencyMeta


class PostingFrequencyQuery(BaseModel):
    date_from: str | None = None
    date_to: str | None = None
    granularity: str = 'day'


class HeatmapCell(BaseModel):
    model_config = ConfigDict(extra='forbid')

    dow: int
    hour: int
    count: int


class PostingHeatmapMeta(BaseModel):
    model_config = ConfigDict(extra='forbid')

    dow_labels: list[str] | None = None
    timezone_assumption: str | None = None
    timezone_note: str | None = None
    date_from: str | None = None
    date_to: str | None = None


class PostingHeatmapResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    cells: list[HeatmapCell]
    meta: PostingHeatmapMeta


class PostingHeatmapQuery(BaseModel):
    date_from: str | None = None
    date_to: str | None = None


class CaptionHashtagMeta(BaseModel):
    model_config = ConfigDict(extra='forbid')

    timezone_assumption: str | None = None
    hashtag_pattern: str | None = None
    timestamp_scope: str | None = None


class TopHashtagRow(BaseModel):
    model_config = ConfigDict(extra='forbid')

    tag: str
    count: int


class TopWordRow(BaseModel):
    model_config = ConfigDict(extra='forbid')

    word: str
    count: int


class CaptionStatsResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    post_count: int
    with_caption_count: int
    avg_caption_len: float
    median_caption_len: float | None = None
    top_hashtags: list[TopHashtagRow]
    posts_with_hashtags: int
    avg_hashtags_per_post: float
    top_words: list[TopWordRow]
    meta: CaptionHashtagMeta


class CaptionStatsQuery(BaseModel):
    date_from: str | None = None
    date_to: str | None = None


class UnpostedCatalogItem(BaseModel):
    model_config = ConfigDict(extra='forbid')

    key: str
    filename: str
    date_taken: str
    rating: int


class UnpostedCatalogResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    total: int
    images: list[UnpostedCatalogItem]
    pagination: PaginationMeta


class UnpostedCatalogQuery(BaseModel):
    month: str | None = None
    min_rating: int | None = None
    date_from: str | None = None
    date_to: str | None = None
    limit: int | None = None
    offset: int | None = None


def validate_unposted_catalog_item(row: dict) -> dict:
    return UnpostedCatalogItem.model_validate(row).model_dump(mode='json')
