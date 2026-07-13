"""Identity API response models — best photos, style fingerprint, post-next suggestions."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from api.schemas.catalog import IdentityPerPerspectiveScore

ImageTypeLiteral = Literal['catalog', 'instagram']


class IdentityBestPhotoItem(BaseModel):
    model_config = ConfigDict(extra='forbid')

    image_key: str
    image_type: ImageTypeLiteral | None = None
    aggregate_score: float
    perspectives_covered: int
    eligible: bool | None = None
    per_perspective: list[IdentityPerPerspectiveScore]
    filename: str
    date_taken: str
    rating: int
    instagram_posted: bool
    stack_id: int | None = None
    stack_member_count: int | None = None
    is_stack_representative: bool | None = None


class IdentityBestPhotosMeta(BaseModel):
    model_config = ConfigDict(extra='forbid')

    active_perspectives: list[str] | None = None
    weighting: str | None = None
    min_perspectives_used: int | None = None
    coverage_rule: str | None = None
    total_catalog_images: int | None = None
    eligible_count: int | None = None
    scored_any_count: int | None = None
    coverage_note: str | None = None


class IdentityBestPhotosResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    items: list[IdentityBestPhotoItem]
    total: int
    meta: IdentityBestPhotosMeta


class IdentityBestPhotosQuery(BaseModel):
    limit: int | None = None
    offset: int | None = None
    min_perspectives: int | None = None
    sort_by_date: str | None = None
    posted: str | None = None


class StyleFingerprintPerPerspective(BaseModel):
    model_config = ConfigDict(extra='forbid')

    perspective_slug: str
    mean_score: float | None = None
    median_score: float | None = None
    count_scores: int


class StyleFingerprintMeta(BaseModel):
    model_config = ConfigDict(extra='forbid')

    tokenization_note: str | None = None
    perspectives_included: list[str] | None = None
    weighting: str | None = None
    scores_are_advisory: str | None = None


class TopRationaleToken(BaseModel):
    model_config = ConfigDict(extra='forbid')

    token: str
    count: int


class StyleFingerprintResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    per_perspective: list[StyleFingerprintPerPerspective]
    aggregate_distribution: dict[str, int]
    aggregate_distribution_note: str | None = None
    top_rationale_tokens: list[TopRationaleToken]
    evidence: dict[str, list[str]]
    evidence_note: str | None = None
    meta: StyleFingerprintMeta


class PostNextCandidate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    image_key: str
    image_type: ImageTypeLiteral | None = None
    filename: str
    date_taken: str
    rating: int
    aggregate_score: float
    perspectives_covered: int
    per_perspective: list[IdentityPerPerspectiveScore]
    reasons: list[str]
    reason_codes: list[str]


class PostNextSuggestionsMeta(BaseModel):
    model_config = ConfigDict(extra='forbid')

    weighting: str | None = None
    min_perspectives_used: int | None = None
    coverage_rule: str | None = None
    timezone_assumption: str | None = None
    high_score_rule: str | None = None
    posted_semantics: str | None = None
    cadence_gap: bool | None = None
    cadence_note: str | None = None


class PostNextSuggestionsResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    candidates: list[PostNextCandidate]
    total: int
    meta: PostNextSuggestionsMeta
    empty_state: str | None = None


class PostNextSuggestionsQuery(BaseModel):
    limit: int | None = None
    offset: int | None = None
    lookback_days_recent: int | None = None
    lookback_days_baseline: int | None = None
    sort_by_date: str | None = None
