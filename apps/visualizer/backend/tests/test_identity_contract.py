"""Contract tests for Identity pydantic models."""

from __future__ import annotations

import pytest
from app import create_app

from api.schemas.identity import (
    IdentityBestPhotosResponse,
    MirrorLensExemplarsResponse,
    MirrorResponse,
    PostNextSuggestionsResponse,
)
from lightroom_tagger.core.database import init_database, insert_image_score, store_image


@pytest.fixture
def identity_contract_client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "library.db")
    conn = init_database(db_path)
    key = store_image(
        conn,
        {
            "date_taken": "2024-09-01",
            "filename": "contract.jpg",
            "instagram_posted": False,
        },
    )
    slug_row = conn.execute(
        "SELECT slug FROM perspectives WHERE active = 1 ORDER BY slug LIMIT 1"
    ).fetchone()
    assert slug_row is not None
    insert_image_score(
        conn,
        {
            "image_key": key,
            "image_type": "catalog",
            "perspective_slug": str(slug_row["slug"]),
            "score": 8,
            "rationale": "Strong composition and light.",
            "model_used": "test-model",
            "prompt_version": "v-test",
            "scored_at": "2024-09-01T12:00:00+00:00",
            "is_current": 1,
        },
    )
    conn.close()
    monkeypatch.setattr("utils.db.LIBRARY_DB", db_path)
    return create_app().test_client()


def test_best_photos_round_trip_from_handler(identity_contract_client):
    payload = identity_contract_client.get("/api/identity/best-photos").get_json()
    assert payload is not None

    validated = IdentityBestPhotosResponse.model_validate(payload)
    assert isinstance(validated.total, int)
    assert validated.meta.weighting == "peak_within_perspective_percentile"
    assert validated.meta.ranking_key == "peak_percentile"


def test_mirror_round_trip_from_handler(identity_contract_client):
    payload = identity_contract_client.get("/api/identity/mirror").get_json()
    assert payload is not None

    validated = MirrorResponse.model_validate(payload)
    assert isinstance(validated.population, int)
    assert isinstance(validated.sections, list)
    assert isinstance(validated.other_lenses, list)


def test_mirror_lens_exemplars_round_trip_from_handler(identity_contract_client):
    slug_row = identity_contract_client.get("/api/identity/mirror").get_json()
    assert slug_row is not None
    section = (slug_row.get("sections") or [None])[0]
    if section is None:
        pytest.skip("no mirror sections in fixture catalog")
    slug = section["perspective_slug"]
    payload = identity_contract_client.get(
        f"/api/identity/mirror/lens/{slug}/exemplars?limit=5&offset=0"
    ).get_json()
    assert payload is not None

    validated = MirrorLensExemplarsResponse.model_validate(payload)
    assert isinstance(validated.total, int)
    assert isinstance(validated.items, list)


def test_suggestions_round_trip_from_handler(identity_contract_client):
    payload = identity_contract_client.get("/api/identity/suggestions").get_json()
    assert payload is not None

    validated = PostNextSuggestionsResponse.model_validate(payload)
    assert isinstance(validated.total, int)
    assert validated.meta.timezone_assumption == "UTC"
    assert validated.meta.ranking_key == "peak_percentile"


def test_best_photos_rejects_wrong_shape():
    with pytest.raises(Exception):
        IdentityBestPhotosResponse.model_validate({"items": "not-a-list", "total": 0, "meta": {}})
