"""Lightroom config path API models (``/api/config/*``)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ConfigCatalogGetResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    catalog_path: str
    resolved_path: str
    exists: bool


class ConfigCatalogPutRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    catalog_path: str


class ConfigCatalogPutResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    catalog_path: str
    ok: bool


class ConfigInstagramDumpGetResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    instagram_dump_path: str
    resolved_path: str
    exists: bool


class ConfigInstagramDumpPutRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    instagram_dump_path: str


class ConfigInstagramDumpPutResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    instagram_dump_path: str
    ok: bool


class ConfigStackDetectionGetResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    stack_burst_delta_ms: int


class ConfigStackDetectionPutRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    stack_burst_delta_ms: int


class ConfigStackDetectionPutResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    stack_burst_delta_ms: int
    ok: bool
