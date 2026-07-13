"""Contract tests for Perspectives pydantic models."""

from __future__ import annotations

import pytest

from api.perspectives import _row_detail, _row_list_item
from api.schemas.perspectives import (
    PerspectiveDetail,
    PerspectiveListResponse,
    PerspectiveScore,
    PerspectiveSummary,
    validate_perspective_detail,
    validate_perspective_summary,
)
from lightroom_tagger.core.database import get_perspective_by_slug, init_database


@pytest.fixture
def library_db(tmp_path, monkeypatch):
    db_path = tmp_path / "library.db"
    monkeypatch.setattr("utils.db.LIBRARY_DB", str(db_path))
    conn = init_database(str(db_path))
    yield conn
    conn.close()


def test_perspective_summary_round_trip_from_list_row(library_db):
    row = get_perspective_by_slug(library_db, "street")
    assert row is not None

    payload = _row_list_item(row)
    validated = PerspectiveSummary.model_validate(validate_perspective_summary(payload))

    assert validated.slug == "street"
    assert validated.active is True
    assert isinstance(validated.optional, bool)


def test_perspective_detail_round_trip_from_detail_row(library_db):
    row = get_perspective_by_slug(library_db, "street")
    assert row is not None

    payload = _row_detail(row)
    validated = PerspectiveDetail.model_validate(validate_perspective_detail(payload))

    assert validated.slug == "street"
    assert validated.prompt_markdown
    assert "prompt_markdown" in payload


def test_perspective_list_response_round_trip(library_db):
    from lightroom_tagger.core.database import list_perspectives

    rows = list_perspectives(library_db)
    payload = [_row_list_item(row) for row in rows]
    validated = PerspectiveListResponse.model_validate(payload)

    assert len(validated.root) >= 1
    assert any(item.slug == "street" for item in validated.root)


def test_perspective_score_round_trip_from_description_sample():
    sample = {"analysis": "Strong geometry", "score": 7}
    validated = PerspectiveScore.model_validate(sample)
    assert validated.analysis == "Strong geometry"
    assert validated.score == 7


def test_perspective_summary_rejects_wrong_shape():
    with pytest.raises(Exception):
        validate_perspective_summary({"id": 1})
