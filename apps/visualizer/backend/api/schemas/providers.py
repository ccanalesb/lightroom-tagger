"""Providers API response models — single source of truth for provider shapes."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, RootModel

ProviderModelSource = Literal['config', 'discovered', 'user']


class Provider(BaseModel):
    model_config = ConfigDict(extra='forbid')

    id: str
    name: str
    available: bool
    tool_calling: bool


class ProviderModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

    id: str
    name: str
    source: ProviderModelSource
    vision: bool | None = None


class ProviderDefaultsEntry(BaseModel):
    model_config = ConfigDict(extra='forbid')

    provider: str
    model: str | None = None


class ProviderDefaults(BaseModel):
    model_config = ConfigDict(extra='forbid')

    vision_comparison: ProviderDefaultsEntry
    description: ProviderDefaultsEntry


class DescriptionModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

    provider_id: str
    provider_name: str
    model_id: str
    model_name: str
    tool_calling: bool


class DescriptionModelsResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    models: list[DescriptionModel]
    default_provider: str | None = None
    default_model: str | None = None


class FallbackOrderResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    order: list[str]


class ProviderHealthResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    reachable: bool
    error: str | None = None


class ProviderDeletedResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    deleted: bool


class ProviderReorderSuccessResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    success: bool


class ProviderModelsListResponse(RootModel[list[ProviderModel]]):
    """``GET /api/providers/<id>/models`` response body."""


class ProviderListResponse(RootModel[list[Provider]]):
    """``GET /api/providers/`` response body."""
