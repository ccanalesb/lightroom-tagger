"""Contract tests for Scores pydantic models."""

from __future__ import annotations

import pytest

from api.scores import _normalize_score_row
from api.schemas.scores import (
    ImageScoreRow,
    ScoresCurrentResponse,
    ScoresHistoryResponse,
    validate_image_score_row,
)
from lightroom_tagger.core.database import init_database, insert_image_score


@pytest.fixture
def library_db(tmp_path):
    conn = init_database(str(tmp_path / 'library.db'))
    yield conn
    conn.close()


def test_image_score_row_round_trip_from_normalized_row(library_db):
    ts = '2024-01-01T00:00:00+00:00'
    insert_image_score(
        library_db,
        {
            'image_key': 'img.jpg',
            'image_type': 'catalog',
            'perspective_slug': 'street',
            'score': 9,
            'rationale': 'Strong geometry',
            'model_used': 'test-model',
            'prompt_version': 'street:v1',
            'scored_at': ts,
            'is_current': 1,
            'repaired_from_malformed': 0,
            'not_attempted': 0,
        },
    )
    library_db.commit()

    row = dict(
        library_db.execute(
            "SELECT * FROM image_scores WHERE image_key = ?",
            ('img.jpg',),
        ).fetchone()
    )
    payload = _normalize_score_row(row)
    validated = ImageScoreRow.model_validate(validate_image_score_row(payload))
    assert validated.score == 9
    assert validated.is_current is True
    assert validated.not_attempted is False


def test_scores_current_response_round_trip(library_db):
    ts = '2024-01-01T00:00:00+00:00'
    insert_image_score(
        library_db,
        {
            'image_key': 'img.jpg',
            'image_type': 'catalog',
            'perspective_slug': 'street',
            'score': 7,
            'prompt_version': 'street:v1',
            'scored_at': ts,
            'is_current': 1,
        },
    )
    library_db.commit()

    row = dict(
        library_db.execute(
            "SELECT * FROM image_scores WHERE image_key = ? AND is_current = 1",
            ('img.jpg',),
        ).fetchone()
    )
    payload = {
        'image_key': 'img.jpg',
        'image_type': 'catalog',
        'current': [_normalize_score_row(row)],
    }
    validated = ScoresCurrentResponse.model_validate(payload)
    assert len(validated.current) == 1
    assert validated.current[0].perspective_slug == 'street'


def test_scores_history_response_round_trip(library_db):
    ts = '2024-01-01T00:00:00+00:00'
    insert_image_score(
        library_db,
        {
            'image_key': 'img.jpg',
            'image_type': 'catalog',
            'perspective_slug': 'street',
            'score': 5,
            'prompt_version': 'street:v1',
            'scored_at': ts,
            'is_current': 1,
        },
    )
    library_db.commit()

    row = dict(
        library_db.execute(
            "SELECT * FROM image_scores WHERE image_key = ?",
            ('img.jpg',),
        ).fetchone()
    )
    payload = {
        'image_key': 'img.jpg',
        'image_type': 'catalog',
        'perspective_slug': 'street',
        'history': [_normalize_score_row(row)],
    }
    validated = ScoresHistoryResponse.model_validate(payload)
    assert validated.perspective_slug == 'street'
    assert len(validated.history) == 1


def test_image_score_row_rejects_wrong_shape():
    with pytest.raises(Exception):
        validate_image_score_row({'image_key': 'only-key'})
