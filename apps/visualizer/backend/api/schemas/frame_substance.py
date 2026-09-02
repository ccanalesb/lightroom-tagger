"""Frame substance per-image API models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from lightroom_tagger.lightroom.writer import KeywordAddResult, KeywordRemoveResult


class FrameSubstanceInstrument(BaseModel):
    model_config = ConfigDict(extra='forbid')

    kind: Literal['pixel_detector', 'excusal_channel']
    verdict: Literal['void', 'illegible'] | None = None
    tier: Literal['A', 'B'] | None = None
    advisory: bool = False


class FrameSubstanceResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    image_key: str
    has_detection_run: bool
    verdict: Literal['void', 'illegible', 'ok', 'unknown'] | None = None
    unknown_reason: str | None = None
    detector_version: str | None = None
    judged_at: str | None = None
    is_stale: bool = False
    has_override: bool = False
    flagged: bool = False
    has_cull_keyword: bool | None = None
    instrument: FrameSubstanceInstrument | None = None
    restore_tier: Literal['A', 'B'] | None = None
    catalog_write_available: bool
    catalog_write_unavailable_reason: str | None = None


class FrameSubstanceOverrideResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    image_key: str
    has_override: bool


class CullKeywordMutationResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    image_key: str
    result: KeywordAddResult | KeywordRemoveResult = Field(
        description='Three-way writer outcome; never collapsed into a boolean.'
    )
