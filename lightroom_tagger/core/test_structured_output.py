from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from lightroom_tagger.core.structured_output import (
    STRUCTURED_OUTPUT_RAW_PREVIEW_MAX_CHARS,
    ScoreResponse,
    StructuredOutputError,
    parse_score_response,
    parse_score_response_with_retry,
)
from lightroom_tagger.core.vision_client import make_score_json_llm_fixer

RAW_TRAILING_COMMA = '{"perspective_slug":"street","score":6,"rationale":"ok",}'

RAW_FENCE = """```json
{"perspective_slug":"doc","score":8,"rationale":"inside fence"}
```"""

RAW_INVALID_TYPE = "totally not json {{{"

RAW_FIXER_SAVES = "{this is not valid json at all"

RAW_LLM_FIXER_SAVES = "%%%garbage%%%"

RAW_PREVIEW_TRUNCATION = ("Z" * 400) + "{{not_valid"


def test_raw_trailing_comma_parses() -> None:
    m = parse_score_response(RAW_TRAILING_COMMA)
    assert m.score == 6
    assert m.perspective_slug == "street"
    assert m.rationale == "ok"


def test_raw_fence_parses() -> None:
    m = parse_score_response(RAW_FENCE)
    assert m.perspective_slug == "doc"
    assert m.score == 8


def test_raw_invalid_type_raises_structured_output_error() -> None:
    with pytest.raises(StructuredOutputError) as excinfo:
        parse_score_response_with_retry(RAW_INVALID_TYPE)
    assert "Score response validation failed" in str(excinfo.value)


def test_raw_fixer_saves() -> None:
    def fixer(_raw: str, _err: str) -> str:
        return '{"perspective_slug":"publisher","score":5,"rationale":"fixed"}'

    m, repaired = parse_score_response_with_retry(RAW_FIXER_SAVES, fixer=fixer)
    assert repaired is True
    assert m.score == 5
    assert m.perspective_slug == "publisher"


def test_raw_llm_fixer_saves() -> None:
    def llm_fixer(_raw: str, _err: str) -> str:
        return '{"perspective_slug":"street","score":7,"rationale":"llm"}'

    m, repaired = parse_score_response_with_retry(
        RAW_LLM_FIXER_SAVES,
        fixer=None,
        llm_fixer=llm_fixer,
    )
    assert repaired is True
    assert m.score == 7
    assert m.perspective_slug == "street"


def test_raw_preview_truncation() -> None:
    with pytest.raises(StructuredOutputError) as excinfo:
        parse_score_response_with_retry(RAW_PREVIEW_TRUNCATION)
    preview = excinfo.value.raw_preview
    assert preview is not None
    assert len(preview) <= STRUCTURED_OUTPUT_RAW_PREVIEW_MAX_CHARS


def test_score_above_ten_rejected() -> None:
    with pytest.raises(ValidationError):
        ScoreResponse.model_validate_json('{"perspective_slug":"a","score":11,"rationale":"b"}')


def test_repair_log_uses_static_prefix_on_fixer_path() -> None:
    log = MagicMock()

    def fixer(_raw: str, _err: str) -> str:
        return '{"perspective_slug":"publisher","score":5,"rationale":"fixed"}'

    parse_score_response_with_retry(
        RAW_FIXER_SAVES,
        fixer=fixer,
        log_repair=log,
    )
    log.assert_called_once()
    assert log.call_args[0][0].startswith("[structured_output] repaired:")


def test_make_score_json_llm_fixer_invokes_complete_text_fn() -> None:
    complete = MagicMock(return_value='{"perspective_slug":"street","score":9,"rationale":"api"}')
    fixer = make_score_json_llm_fixer(complete, client=object(), model="m")
    out = fixer("broken {{{", "some validation error")
    assert "perspective_slug" in out
    complete.assert_called_once()
    call_kw = complete.call_args.kwargs
    assert "system" in call_kw and "user" in call_kw
    assert "perspective_slug" in call_kw["system"]
