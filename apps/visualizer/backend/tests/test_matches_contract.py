"""Contract tests for Matches pydantic models."""

from __future__ import annotations

import os
import tempfile

import pytest
from api.schemas.matches import (
    Match,
    MatchesListResponse,
    MatchGroup,
    MatchRejectConflictResponse,
    MatchRejectSuccessResponse,
    MatchValidateResponse,
    validate_match,
    validate_match_group,
    validate_matches_list_response,
)
from tests.test_matches_api_pin import _LIST_MATCHES_PIN, _seed_pin_fixture

from lightroom_tagger.core.database import init_database


def test_matches_list_response_round_trip_from_pin():
    validated = MatchesListResponse.model_validate(
        validate_matches_list_response(_LIST_MATCHES_PIN)
    )

    assert validated.total == 1
    assert len(validated.match_groups) == 1
    assert validated.match_groups[0].instagram_key == 'ig/pin'
    assert len(validated.matches) == 1


def test_match_round_trip_from_pin_candidate():
    candidate = _LIST_MATCHES_PIN['match_groups'][0]['candidates'][0]
    validated = Match.model_validate(validate_match(candidate))

    assert validated.catalog_key == 'cat_pin'
    assert validated.score == 0.88
    assert validated.vision_result == 'SAME'


def test_match_group_round_trip_from_pin():
    group = _LIST_MATCHES_PIN['match_groups'][0]
    validated = MatchGroup.model_validate(validate_match_group(group))

    assert validated.candidate_count == 1
    assert validated.has_validated is False
    assert validated.all_rejected is False


def test_match_validate_response_round_trip():
    payload = MatchValidateResponse.model_validate({'validated': True})
    assert payload.validated is True


def test_match_reject_success_response_round_trip():
    payload = MatchRejectSuccessResponse.model_validate({'rejected': True})
    assert payload.rejected is True


def test_match_reject_conflict_response_round_trip():
    payload = MatchRejectConflictResponse.model_validate({
        'error': 'Match has been validated; un-validate it before rejecting.',
        'rejected': False,
    })
    assert payload.rejected is False


def test_match_rejects_wrong_shape():
    with pytest.raises(Exception):
        validate_match({'instagram_key': 'only-key'})


def test_matches_list_response_rejects_wrong_shape():
    with pytest.raises(Exception):
        validate_matches_list_response({'total': 1})


def test_matches_list_response_round_trip_from_live_fixture():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_database(db_path)
        _seed_pin_fixture(db)
        db.close()

        import config
        import utils.db as db_utils

        config.LIBRARY_DB = db_path
        db_utils.LIBRARY_DB = db_path
        from app import create_app

        client = create_app().test_client()
        resp = client.get('/api/images/matches?limit=50&offset=0')
        assert resp.status_code == 200
        validated = MatchesListResponse.model_validate(resp.get_json())
        assert validated.total >= 1
