"""Identity API response models — best photos, mirror signature, post-next suggestions."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from api.schemas.catalog import IdentityPerPerspectiveScore

ImageTypeLiteral = Literal['catalog', 'instagram']


class IdentityBestPhotoItem(BaseModel):
    model_config = ConfigDict(extra='forbid')

    image_key: str
    image_type: ImageTypeLiteral | None = None
    peak_percentile: float
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
    ranking_key: str | None = None
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


class MirrorDescriptor(BaseModel):
    model_config = ConfigDict(extra='forbid')

    token: str
    log_odds: float
    count: int


class MirrorExemplarPerPerspective(BaseModel):
    model_config = ConfigDict(extra='forbid')

    perspective_slug: str
    display_name: str
    score: int
    percentile: float


class MirrorExemplar(BaseModel):
    model_config = ConfigDict(extra='forbid')

    image_key: str
    filename: str
    date_taken: str
    rating: int
    instagram_posted: bool
    score: int
    percentile: float
    purity: float
    rationale_preview: str
    per_perspective: list[MirrorExemplarPerPerspective]
    stack_id: int | None = None
    stack_size: int | None = None


class MirrorTechniqueSection(BaseModel):
    model_config = ConfigDict(extra='forbid')

    perspective_slug: str
    display_name: str
    strength_label: str
    leading_not_distinctive: bool
    crowned: bool
    win_rate: float
    chance_rate: float
    z_score: float
    votes: int
    photos_on: int
    coverage: float
    low_coverage: bool
    descriptors: list[MirrorDescriptor]
    exemplars: list[MirrorExemplar]
    exemplar_total: int


class MirrorOtherLens(BaseModel):
    model_config = ConfigDict(extra='forbid')

    perspective_slug: str
    display_name: str
    strength_label: str
    win_rate: float
    chance_rate: float
    z_score: float
    coverage: float
    low_coverage: bool
    votes: int
    photos_on: int
    exemplar_total: int


class MirrorMeta(BaseModel):
    model_config = ConfigDict(extra='forbid')

    active_perspectives: list[str] | None = None
    total_catalog_images: int | None = None
    voting_rule: str | None = None
    crowning_rule: str | None = None
    low_coverage_threshold: float | None = None
    exemplar_initial_limit: int | None = None
    exemplar_page_size: int | None = None
    descriptor_min_count: int | None = None
    scores_are_advisory: str | None = None
    fallback_active: bool | None = None


class MirrorResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    population: int
    sections: list[MirrorTechniqueSection]
    other_lenses: list[MirrorOtherLens]
    meta: MirrorMeta


class MirrorLensExemplarsResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    items: list[MirrorExemplar]
    total: int


class MirrorLensExemplarsQuery(BaseModel):
    limit: int | None = None
    offset: int | None = None


class PostNextCandidate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    image_key: str
    image_type: ImageTypeLiteral | None = None
    filename: str
    date_taken: str
    rating: int
    peak_percentile: float
    peak_perspective_slug: str
    peak_perspective_display_name: str
    is_signature: bool
    perspectives_covered: int
    per_perspective: list[IdentityPerPerspectiveScore]
    reasons: list[str]
    reason_codes: list[str]


class PostNextSuggestionsMeta(BaseModel):
    model_config = ConfigDict(extra='forbid')

    weighting: str | None = None
    ranking_key: str | None = None
    min_perspectives_used: int | None = None
    coverage_rule: str | None = None
    high_score_rule: str | None = None


class PostNextSuggestionsResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    candidates: list[PostNextCandidate]
    total: int
    meta: PostNextSuggestionsMeta
    empty_state: str | None = None


class PostNextSuggestionsQuery(BaseModel):
    limit: int | None = None
    offset: int | None = None
    sort_by_date: str | None = None
