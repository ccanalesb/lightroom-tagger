"""Contract tests for Scores pydantic models."""

from __future__ import annotations

import pytest

from api.schemas.scores import (
    ImageScoreRow,
    ScoresCurrentResponse,
    ScoresHistoryResponse,
    validate_image_score_row,
)
from api.scores import _normalize_score_row
from lightroom_tagger.core.database import init_database, insert_image_score


@pytest.fixture
def library_db_path(tmp_path, monkeypatch):
    db_path = tmp_path / "library.db"
    monkeypatch.setattr("utils.db.LIBRARY_DB", str(db_path))
    conn = init_database(str(db_path))
    conn.close()
    return db_path


@pytest.fixture
def client(library_db_path, monkeypatch):
    monkeypatch.setattr("utils.db.LIBRARY_DB", str(library_db_path))
    from app import create_app

    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_scores_current_round_trip_from_handler(client, library_db_path):
    image_key = "nested/path/img.jpg"
    conn = init_database(str(library_db_path))
    ts = "2024-01-01T00:00:00+00:00"
    insert_image_score(
        conn,
        {
            "image_key": image_key,
            "image_type": "catalog",
            "perspective_slug": "street",
            "score": 9,
            "prompt_version": "street:v2",
            "scored_at": ts,
            "is_current": 1,
        },
    )
    conn.commit()
    conn.close()

    enc = "nested%2Fpath%2Fimg.jpg"
    payload = client.get(f"/api/scores/{enc}").get_json()
    validated = ScoresCurrentResponse.model_validate(payload)
    assert validated.image_key == image_key
    assert len(validated.current) == 1
    assert validated.current[0].score == 9


def test_scores_history_round_trip_from_handler(client, library_db_path):
    image_key = "h.jpg"
    slug = "street"
    conn = init_database(str(library_db_path))
    insert_image_score(
        conn,
        {
            "image_key": image_key,
            "image_type": "catalog",
            "perspective_slug": slug,
            "score": 7,
            "prompt_version": "b",
            "scored_at": "2025-01-01T00:00:00+00:00",
            "is_current": 1,
        },
    )
    conn.commit()
    conn.close()

    payload = client.get(f"/api/scores/{image_key}/history?perspective_slug={slug}").get_json()
    validated = ScoresHistoryResponse.model_validate(payload)
    assert validated.perspective_slug == slug
    assert len(validated.history) == 1


def test_image_score_row_round_trip_from_normalize():
    row = {
        "id": 1,
        "image_key": "a.jpg",
        "image_type": "catalog",
        "perspective_slug": "street",
        "score": 8,
        "rationale": "Strong",
        "model_used": "gpt",
        "prompt_version": "street:v1",
        "scored_at": "2024-01-01T00:00:00+00:00",
        "is_current": 1,
        "repaired_from_malformed": 0,
        "not_attempted": 1,
    }
    payload = _normalize_score_row(row)
    validated = ImageScoreRow.model_validate(validate_image_score_row(payload))
    assert validated.is_current is True
    assert validated.not_attempted is True


def test_scores_current_empty_round_trip(client):
    payload = client.get("/api/scores/some%2Fkey.jpg").get_json()
    validated = ScoresCurrentResponse.model_validate(payload)
    assert validated.current == []


def test_image_score_row_rejects_wrong_shape():
    with pytest.raises(Exception):
        validate_image_score_row({"image_key": "only-key"})
