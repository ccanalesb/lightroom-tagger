"""Burst stack API models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from api.schemas.catalog import CatalogImage


class StackMetadata(BaseModel):
    model_config = ConfigDict(extra='forbid')

    stack_id: int
    representative_key: str
    stack_member_count: int
    member_keys: list[str]


class StackMembersResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    items: list[CatalogImage]


class StackSplitMemberRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    image_key: str


class StackSplitMemberResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    split_out_key: str
    remaining_stack: StackMetadata | None = None
    dissolved: bool


class StackMergeRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    source_stack_id: int


class StackMergeResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    stack: StackMetadata
    merged_stack_id: int


class StackRepresentativeRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    image_key: str


class StackRepresentativeResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    stack: StackMetadata


def validate_stack_metadata(row: dict) -> dict:
    return StackMetadata.model_validate(row).model_dump(mode='json')
