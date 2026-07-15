"""Contract tests for Search pydantic models."""

from __future__ import annotations

import pytest
from app import create_app

from api.schemas.search import (
    ChatSearchResponse,
    NlSearchResponse,
    SemanticSearchResponse,
    validate_chat_search_response,
)
from lightroom_tagger.core.database import init_database, store_image
from lightroom_tagger.core.semantic_search import SemanticSearchMeta, SemanticSearchRow


@pytest.fixture
def search_contract_client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "library.db")
    conn = init_database(db_path)
    store_image(
        conn,
        {
            "date_taken": "2024-05-20",
            "filename": "hill.jpg",
            "rating": 3,
            "id": "50",
        },
    )
    conn.close()
    monkeypatch.setattr("utils.db.LIBRARY_DB", db_path)

    from lightroom_tagger.core.provider_registry import ProviderRegistry

    _orig_list = ProviderRegistry.list_providers

    def _list_providers_nl_only(self):
        return [{**p, "tool_calling": False} for p in _orig_list(self)]

    monkeypatch.setattr(
        "lightroom_tagger.core.catalog_search.ProviderRegistry.list_providers",
        _list_providers_nl_only,
    )
    return create_app().test_client()


def test_nl_search_response_round_trip(search_contract_client, monkeypatch):
    client = search_contract_client
    monkeypatch.setattr(
        "lightroom_tagger.core.nl_catalog_search.run_nl_catalog_filter_llm",
        lambda *a, **k: '{"posted": false}',
    )
    payload = client.post(
        "/api/images/search/nl-search", json={"query": "unposted only"}
    ).get_json()
    validated = NlSearchResponse.model_validate(payload)
    assert validated.filters["posted"] is False
    assert isinstance(validated.images, list)


def test_semantic_search_response_round_trip(search_contract_client, monkeypatch):
    client = search_contract_client
    fixed_blob = b"\xef" * (768 * 4)

    def fake_hybrid(
        _db,
        *,
        user_query,
        fts_match,
        query_vec_blob,
        limit,
        offset,
        restrict_to_keys=None,
    ):
        row = SemanticSearchRow(
            image_key="unused",
            rrf_score=0.42,
            why_matched="fts+embed",
        )
        meta = SemanticSearchMeta(
            missing_embeddings_count=0,
            semantic_index_empty=False,
            rrf_k=60,
            fts_no_match=False,
        )
        return [row], 1, meta

    monkeypatch.setattr(
        "lightroom_tagger.core.catalog_search.embed_query_to_vec_blob",
        lambda _q: fixed_blob,
    )
    monkeypatch.setattr(
        "lightroom_tagger.core.catalog_search.run_semantic_hybrid_search",
        fake_hybrid,
    )
    payload = client.post(
        "/api/images/search/semantic-search",
        json={"query": "mountain scene"},
    ).get_json()
    validated = SemanticSearchResponse.model_validate(payload)
    assert validated.total == 1
    assert validated.metadata.rrf_k == 60


def test_chat_search_response_round_trip(search_contract_client, monkeypatch):
    client = search_contract_client
    monkeypatch.setattr(
        "lightroom_tagger.core.nl_catalog_search.run_nl_catalog_filter_llm_multi_turn",
        lambda *a, **k: '{"keyword": "mountain"}',
    )
    payload = client.post(
        "/api/images/search/chat-search", json={"message": "show mountains"}
    ).get_json()
    validated = ChatSearchResponse.model_validate(validate_chat_search_response(payload))
    assert validated.search_mode == "nl_filter"
    assert validated.filters is not None


def test_chat_search_response_rejects_wrong_shape():
    with pytest.raises(Exception):
        validate_chat_search_response({"search_mode": "semantic"})
