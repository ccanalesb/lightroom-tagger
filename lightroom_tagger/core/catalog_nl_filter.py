"""Allowlisted Pydantic model for NL-derived catalog filter payloads.

The LLM (or a JSON test fixture) may only supply the fields on :class:`CatalogNlFilter`.
There is **no** raw SQL in this type — the HTTP layer maps validated values to
:func:`lightroom_tagger.core.database.query_catalog_images` keyword arguments.
"""

from __future__ import annotations

import json
import re
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from lightroom_tagger.core.structured_output import StructuredOutputError, repair_json_text

_CATALOG_SCORE_PERSPECTIVE_SLUG_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

# Keys accepted by :func:`query_catalog_images` that this NL model is allowed
# to set (excludes e.g. ``limit`` / ``offset`` pagination, ``analyzed`` / ``color_label``).
_CATALOG_NL_FILTER_QUERY_KEYS: frozenset[str] = frozenset(
    {
        "posted",
        "month",
        "keyword",
        "min_rating",
        "date_from",
        "date_to",
        "score_perspective",
        "min_score",
        "sort_by_score",
        "sort_by_date",
        "description_search",
        "dominant_colors",
        "mood_tags",
    }
)


class CatalogNlFilter(BaseModel):
    """Strict allowlist of filter fields for natural-language search."""

    model_config = ConfigDict(extra="forbid")

    posted: bool | None = None
    month: str | None = None
    keyword: str | None = None
    min_rating: int | None = None
    date_from: str | None = None
    date_to: str | None = None
    score_perspective: str | None = None
    min_score: int | None = Field(default=None, ge=1, le=10)
    sort_by_score: Literal["asc", "desc"] | None = None
    sort_by_date: Literal["newest", "oldest"] | None = None
    description_search: str | None = None
    dominant_colors: list[str] | None = None
    mood_tags: list[str] | None = None

    @model_validator(mode="after")
    def _validate_score_perspective(self) -> Self:
        if self.min_score is not None or self.sort_by_score is not None:
            if self.score_perspective is None:
                raise ValueError(
                    "score_perspective is required when min_score or sort_by_score is set"
                )
        if self.score_perspective is not None:
            sp = self.score_perspective.strip()
            if not sp:
                raise ValueError("score_perspective must be a non-empty catalog slug (score_perspective)")
            if not _CATALOG_SCORE_PERSPECTIVE_SLUG_RE.match(sp):
                raise ValueError("score_perspective does not match the allowed slug (score_perspective)")
        return self


def parse_catalog_nl_filter_from_llm(raw: str) -> CatalogNlFilter:
    """Repair common LLM JSON issues, then validate as :class:`CatalogNlFilter`.

    Re-raises :class:`json.JSONDecodeError`, :class:`~pydantic.ValidationError`, or
    :class:`StructuredOutputError` for callers to map to HTTP 400.
    """
    try:
        repaired = repair_json_text(raw)
    except StructuredOutputError:
        raise
    try:
        return CatalogNlFilter.model_validate_json(repaired)
    except (json.JSONDecodeError, ValidationError):
        raise


def catalog_nl_filter_to_query_kwargs(f: CatalogNlFilter) -> dict[str, Any]:
    """Map a validated filter to ``query_catalog_images`` keyword arguments (no pagination)."""
    dumped = f.model_dump(exclude_none=True)
    return {k: v for k, v in dumped.items() if k in _CATALOG_NL_FILTER_QUERY_KEYS}
