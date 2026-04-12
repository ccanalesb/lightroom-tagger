"""Pydantic validation and deterministic JSON repair for score-shaped LLM payloads.

Score responses for ``image_scores`` (Phase 6+) must pass through this module so
malformed JSON never silently becomes empty rows. Multi-perspective describe
blobs still use :func:`lightroom_tagger.core.analyzer.parse_description_response`
until a later refactor (Phase 5 scope).

Deterministic repair uses a single-pass trailing-comma cleanup regex. **Limitation:**
commas immediately before ``}`` or ``]`` inside JSON string values may be altered;
nested edge cases are acceptable for this mitigation tier.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

STRUCTURED_OUTPUT_MAX_CHARS = 512_000
STRUCTURED_OUTPUT_RAW_PREVIEW_MAX_CHARS = 200

_FENCE_PATTERN = re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", re.DOTALL)
_TRAILING_COMMA_PATTERN = re.compile(r",(\s*[}\]])")


class PerspectiveScorePayload(BaseModel):
    """One perspective block inside a legacy multi-perspective describe payload."""

    model_config = ConfigDict(extra="forbid")

    analysis: str
    score: int = Field(ge=1, le=10)


class ScoreResponse(BaseModel):
    """Single perspective line item validated before ``image_scores`` insert."""

    model_config = ConfigDict(extra="forbid")

    perspective_slug: str
    score: int = Field(ge=1, le=10)
    rationale: str


def _truncate_preview(text: str, max_len: int = STRUCTURED_OUTPUT_RAW_PREVIEW_MAX_CHARS) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


class StructuredOutputError(Exception):
    """Raised when a score payload cannot be validated after repair and optional fixers."""

    def __init__(
        self,
        message: str,
        *,
        raw_preview: str | None = None,
        validation_errors: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.raw_preview = _truncate_preview(raw_preview) if raw_preview is not None else None
        self.validation_errors: list[str] = list(validation_errors or [])

    def __str__(self) -> str:
        base = super().__str__()
        parts: list[str] = [base]
        if self.validation_errors:
            parts.append("Errors: " + "; ".join(self.validation_errors))
        if self.raw_preview is not None:
            prev = _truncate_preview(self.raw_preview)
            parts.append(f"Raw preview: {prev}")
        return " ".join(parts)


def _reject_if_too_large(raw: str) -> None:
    if len(raw) > STRUCTURED_OUTPUT_MAX_CHARS:
        preview = _truncate_preview(raw)
        raise StructuredOutputError(
            "Score response validation failed: input too large",
            raw_preview=preview,
            validation_errors=[],
        )


def _validation_error_messages(exc: ValidationError) -> list[str]:
    return [f"{_format_loc(e.get('loc'))}: {e.get('msg', '')}" for e in exc.errors()]


def _format_loc(loc: Any) -> str:
    if not isinstance(loc, tuple):
        return str(loc)
    return ".".join(str(x) for x in loc if x != "body")


def repair_json_text(raw: str) -> str:
    """Deterministically normalize common LLM JSON issues (fences, trailing commas).

    Does not call the LLM. Raises :class:`StructuredOutputError` containing the
    exact substring ``input too large`` when ``len(raw)`` exceeds
    :data:`STRUCTURED_OUTPUT_MAX_CHARS`.
    """
    _reject_if_too_large(raw)
    text = raw.strip()
    fence_match = _FENCE_PATTERN.search(text)
    if fence_match:
        text = fence_match.group(1).strip()
    prev: str | None = None
    while prev != text:
        prev = text
        text = _TRAILING_COMMA_PATTERN.sub(r"\1", text)
    return text


def parse_score_response(raw: str) -> ScoreResponse:
    """Repair *raw* deterministically, then validate as :class:`ScoreResponse`."""
    text = repair_json_text(raw)
    return ScoreResponse.model_validate_json(text)


def parse_score_response_with_retry(
    raw: str,
    fixer: Callable[[str, str], str] | None = None,
    llm_fixer: Callable[[str, str], str] | None = None,
    *,
    log_repair: Callable[[str], None] | None = None,
) -> tuple[ScoreResponse, bool]:
    """Validate *raw* with optional injected fixers and a single LLM repair attempt.

    Returns ``(model, repaired_flag)``. On the first successful
    :func:`parse_score_response`, ``repaired_flag`` is ``False``.

    If that raises :class:`ValidationError`, an optional *fixer* and then
    *llm_fixer* may each run **once**. Successful recovery sets
    ``repaired_flag`` to ``True`` and may invoke *log_repair* with a message
    whose prefix is exactly ``[structured_output] repaired:``.

    Raises :class:`StructuredOutputError` with substring
    ``Score response validation failed`` when validation still fails.
    """
    _reject_if_too_large(raw)
    try:
        return parse_score_response(raw), False
    except StructuredOutputError:
        raise
    except ValidationError as first_exc:
        err_summary = str(first_exc)
        val_errs = _validation_error_messages(first_exc)

        if fixer is not None:
            candidate = fixer(raw, err_summary)
            try:
                model = parse_score_response(candidate)
                if log_repair is not None:
                    log_repair(
                        "[structured_output] repaired: Injected fixer returned valid score JSON."
                    )
                return model, True
            except (ValidationError, StructuredOutputError):
                pass

        if llm_fixer is not None:
            candidate = llm_fixer(raw, err_summary)
            try:
                model = parse_score_response(candidate)
                if log_repair is not None:
                    log_repair(
                        "[structured_output] repaired: LLM JSON repair returned valid score JSON."
                    )
                return model, True
            except (ValidationError, StructuredOutputError):
                pass

        preview_source = repair_json_text(raw) if len(raw) <= STRUCTURED_OUTPUT_MAX_CHARS else raw
        raise StructuredOutputError(
            "Score response validation failed",
            raw_preview=preview_source,
            validation_errors=val_errs,
        ) from first_exc


__all__ = [
    "STRUCTURED_OUTPUT_MAX_CHARS",
    "STRUCTURED_OUTPUT_RAW_PREVIEW_MAX_CHARS",
    "PerspectiveScorePayload",
    "ScoreResponse",
    "StructuredOutputError",
    "parse_score_response",
    "parse_score_response_with_retry",
    "repair_json_text",
]
