"""Natural language, semantic, and chat search API models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from api.schemas.catalog import CatalogImage


class NlSearchRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    query: str
    limit: int | None = None
    offset: int | None = None
    provider_id: str | None = None
    model: str | None = None


class NlSearchResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    filters: dict[str, Any]
    total: int
    images: list[CatalogImage]


class SemanticSearchRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    query: str
    limit: int | None = None
    offset: int | None = None
    score_perspective: str | None = None


class SemanticSearchMetadata(BaseModel):
    model_config = ConfigDict(extra='forbid')

    missing_embeddings_count: int
    semantic_index_empty: bool
    rrf_k: int
    fts_no_match: bool


class SemanticSearchResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    total: int
    images: list[CatalogImage]
    metadata: SemanticSearchMetadata


class ChatSearchMessage(BaseModel):
    model_config = ConfigDict(extra='forbid')

    role: str
    content: str | None = None
    tool_calls: list[Any] | None = None
    tool_call_id: str | None = None


class ChatSearchRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    message: str
    messages: list[ChatSearchMessage] | None = None
    limit: int | None = None
    offset: int | None = None
    provider_id: str | None = None
    model: str | None = None
    score_perspective: str | None = None
    pinned_image_key: str | None = None


class ChatSearchResultImage(CatalogImage):
    score: float | None = None
    why_matched: str | None = None
    thumbnail_url: str | None = None


SearchMode = Literal['nl_filter', 'semantic', 'tool_calling']


class ChatSearchResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    search_mode: SearchMode
    total: int
    images: list[ChatSearchResultImage]
    filters: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    messages: list[ChatSearchMessage] | None = None
    assistant_message: str | None = None


def validate_chat_search_response(row: dict) -> dict:
    return ChatSearchResponse.model_validate(row).model_dump(mode='json')
