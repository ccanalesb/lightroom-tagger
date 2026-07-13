"""Matches API response models — single source of truth for match-review shapes."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

VisionResult = Literal['SAME', 'DIFFERENT', 'UNCERTAIN']


class Match(BaseModel):
    """Enriched match row from ``GET /api/images/matches``."""

    model_config = ConfigDict(extra='forbid')

    instagram_key: str
    catalog_key: str
    score: float
    insta_key: str | None = None
    phash_distance: int | None = None
    phash_score: float | None = None
    desc_similarity: float | None = None
    vision_result: VisionResult | str | None = None
    vision_reasoning: str | None = None
    vision_score: float | None = None
    total_score: float | None = None
    model_used: str | None = None
    validated_at: str | None = None
    rank: int | None = None
    matched_at: str | None = None
    instagram_image: dict[str, Any] | None = None
    catalog_image: dict[str, Any] | None = None
    catalog_description: dict[str, Any] | None = None
    insta_description: dict[str, Any] | None = None


class MatchGroup(BaseModel):
    """Grouped candidates for one Instagram key."""

    model_config = ConfigDict(extra='forbid')

    instagram_key: str
    candidates: list[Match]
    best_score: float
    candidate_count: int
    has_validated: bool
    all_rejected: bool = False
    instagram_image: dict[str, Any] | None = None


class MatchesListResponse(BaseModel):
    """``GET /api/images/matches`` response body."""

    model_config = ConfigDict(extra='forbid')

    total: int
    total_groups: int
    total_matches: int
    match_groups: list[MatchGroup]
    matches: list[Match]


class MatchValidateResponse(BaseModel):
    """``PATCH .../validate`` success body."""

    model_config = ConfigDict(extra='forbid')

    validated: bool


class MatchRejectSuccessResponse(BaseModel):
    """``PATCH .../reject`` success body."""

    model_config = ConfigDict(extra='forbid')

    rejected: Literal[True]


class MatchRejectConflictResponse(BaseModel):
    """``PATCH .../reject`` 409 when the match is already validated."""

    model_config = ConfigDict(extra='forbid')

    error: str
    rejected: Literal[False]


def validate_match(payload: dict) -> dict:
    """Validate an enriched match dict; raises on shape drift."""
    return Match.model_validate(payload).model_dump(mode='json')


def validate_match_group(payload: dict) -> dict:
    """Validate a match group dict; raises on shape drift."""
    return MatchGroup.model_validate(payload).model_dump(mode='json')


def validate_matches_list_response(payload: dict) -> dict:
    """Validate the list-matches response body; raises on shape drift."""
    return MatchesListResponse.model_validate(payload).model_dump(mode='json')
