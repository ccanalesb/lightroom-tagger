"""Tests for POST /api/images/chat-search (NL + semantic; LLM mocked)."""

from __future__ import annotations

import pytest
from app import create_app

from lightroom_tagger.core.clip_similarity import NoClipEmbeddingError
from lightroom_tagger.core.database import init_database, store_image
from lightroom_tagger.core.semantic_search import SemanticSearchMeta, SemanticSearchRow


@pytest.fixture
def chat_search_client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "library.db")
    conn = init_database(db_path)
    k = store_image(
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

    import api.images as api_images

    _orig_list = api_images.ProviderRegistry.list_providers

    def _list_providers_nl_only(self):
        return [{**p, "tool_calling": False} for p in _orig_list(self)]

    monkeypatch.setattr(api_images.ProviderRegistry, "list_providers", _list_providers_nl_only)

    app = create_app()
    return app.test_client(), k


def test_chat_search_nl_filter_path(
    chat_search_client, monkeypatch
) -> None:
    client, _k = chat_search_client
    monkeypatch.setattr(
        "api.images.nl_catalog_search.run_nl_catalog_filter_llm_multi_turn",
        lambda *a, **k: '{"keyword": "mountain"}',
    )
    r = client.post(
        "/api/images/chat-search", json={"message": "show mountains"}
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data["search_mode"] == "nl_filter"
    assert data["filters"] is not None
    assert data["filters"].get("keyword") == "mountain"
    assert "total" in data
    assert "images" in data
    assert isinstance(data["images"], list)
    assert data.get("metadata") is None


def test_chat_search_semantic_fallback(
    chat_search_client, monkeypatch
) -> None:
    client, k = chat_search_client

    monkeypatch.setattr(
        "api.images.nl_catalog_search.run_nl_catalog_filter_llm_multi_turn",
        lambda *a, **k: "{}",
    )

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
        _ = (fts_match, query_vec_blob, limit, offset, restrict_to_keys)
        return (
            [
                SemanticSearchRow(
                    image_key=k,
                    rrf_score=0.1,
                    why_matched="test",
                ),
            ],
            1,
            SemanticSearchMeta(
                missing_embeddings_count=0,
                semantic_index_empty=False,
                rrf_k=60,
                fts_no_match=False,
            ),
        )

    monkeypatch.setattr("api.images.embed_query_to_vec_blob", lambda _q: fixed_blob)
    monkeypatch.setattr("api.images.run_semantic_hybrid_search", fake_hybrid)

    r = client.post(
        "/api/images/chat-search", json={"message": "hills in spring"}
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data["search_mode"] == "semantic"
    meta = data.get("metadata")
    assert meta is not None
    assert meta["missing_embeddings_count"] == 0
    assert meta["semantic_index_empty"] is False
    assert meta["rrf_k"] == 60
    assert meta["fts_no_match"] is False
    assert data.get("filters") is None
    assert data["total"] == 1


def test_chat_search_empty_message_400(chat_search_client) -> None:
    client, _k = chat_search_client
    r = client.post("/api/images/chat-search", json={"message": "  "})
    assert r.status_code == 400
    err = r.get_json().get("error", "")
    assert "message" in err.lower() or "non-empty" in err.lower()


def test_chat_search_multiturn_forwards_current_message_last(
    chat_search_client, monkeypatch
) -> None:
    client, _k = chat_search_client
    captured: list = []

    def multi_turn(turns, **kw):
        captured.append(turns)
        return '{"keyword": "lake"}'

    monkeypatch.setattr(
        "api.images.nl_catalog_search.run_nl_catalog_filter_llm_multi_turn",
        multi_turn,
    )
    r = client.post(
        "/api/images/chat-search",
        json={
            "message": "second",
            "messages": [
                {"role": "user", "content": "first"},
                {"role": "assistant", "content": "ok"},
            ],
        },
    )
    assert r.status_code == 200
    assert len(captured) == 1
    turns = captured[0]
    assert turns[-1] == {"role": "user", "content": "second"}
    assert turns[0] == {"role": "user", "content": "first"}
    assert turns[1] == {"role": "assistant", "content": "ok"}


def test_chat_search_pin_active_semantic_passes_restrict_to_keys(
    chat_search_client, monkeypatch
) -> None:
    client, k = chat_search_client
    captured: dict = {}

    def capture_hybrid(_db, **kw):
        captured["restrict_to_keys"] = kw.get("restrict_to_keys")
        return (
            [
                SemanticSearchRow(
                    image_key=k,
                    rrf_score=0.1,
                    why_matched="test",
                ),
            ],
            1,
            SemanticSearchMeta(
                missing_embeddings_count=0,
                semantic_index_empty=False,
                rrf_k=60,
                fts_no_match=False,
            ),
        )

    monkeypatch.setattr(
        "api.images.nl_catalog_search.run_nl_catalog_filter_llm_multi_turn",
        lambda *a, **k: "{}",
    )
    monkeypatch.setattr("api.images.embed_query_to_vec_blob", lambda _q: b"\xef" * (768 * 4))
    monkeypatch.setattr("api.images.run_semantic_hybrid_search", capture_hybrid)
    monkeypatch.setattr(
        "api.images.list_pin_similarity_candidate_keys",
        lambda _db, seed: [seed, "neighbor-key"],
    )
    r = client.post(
        "/api/images/chat-search",
        json={"message": "hills in spring", "pinned_image_key": k},
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data["search_mode"] == "semantic"
    assert data["metadata"]["pin_state"] == "active"
    assert captured["restrict_to_keys"] == frozenset({k, "neighbor-key"})


def test_chat_search_pin_inactive_no_clip_embedding_falls_back_semantic(
    chat_search_client, monkeypatch
) -> None:
    client, k = chat_search_client
    captured: dict = {}

    def capture_hybrid(_db, **kw):
        captured["restrict_to_keys"] = kw.get("restrict_to_keys")
        return (
            [
                SemanticSearchRow(
                    image_key=k,
                    rrf_score=0.1,
                    why_matched="test",
                ),
            ],
            1,
            SemanticSearchMeta(
                missing_embeddings_count=0,
                semantic_index_empty=False,
                rrf_k=60,
                fts_no_match=False,
            ),
        )

    def boom(_db, seed):
        raise NoClipEmbeddingError(seed)

    monkeypatch.setattr(
        "api.images.nl_catalog_search.run_nl_catalog_filter_llm_multi_turn",
        lambda *a, **k: "{}",
    )
    monkeypatch.setattr("api.images.embed_query_to_vec_blob", lambda _q: b"\xef" * (768 * 4))
    monkeypatch.setattr("api.images.run_semantic_hybrid_search", capture_hybrid)
    monkeypatch.setattr("api.images.list_pin_similarity_candidate_keys", boom)
    r = client.post(
        "/api/images/chat-search",
        json={"message": "hills in spring", "pinned_image_key": k},
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data["metadata"]["pin_state"] == "inactive"
    assert data["metadata"]["fallback_reason"] == "no_clip_embedding"
    assert captured["restrict_to_keys"] is None


def test_chat_search_pin_inactive_invalid_key_metadata(
    chat_search_client, monkeypatch
) -> None:
    client, _k = chat_search_client
    captured: dict = {}

    def capture_hybrid(_db, **kw):
        captured["restrict_to_keys"] = kw.get("restrict_to_keys")
        return (
            [],
            0,
            SemanticSearchMeta(
                missing_embeddings_count=0,
                semantic_index_empty=False,
                rrf_k=60,
                fts_no_match=True,
            ),
        )

    monkeypatch.setattr(
        "api.images.nl_catalog_search.run_nl_catalog_filter_llm_multi_turn",
        lambda *a, **k: "{}",
    )
    monkeypatch.setattr("api.images.embed_query_to_vec_blob", lambda _q: b"\xef" * (768 * 4))
    monkeypatch.setattr("api.images.run_semantic_hybrid_search", capture_hybrid)
    r = client.post(
        "/api/images/chat-search",
        json={"message": "hills in spring", "pinned_image_key": "not-a-real-catalog-key"},
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data["metadata"]["pin_state"] == "inactive"
    assert data["metadata"]["fallback_reason"] == "invalid_pin_key"
    assert captured["restrict_to_keys"] is None


def test_chat_search_invalid_llm_json_400(
    chat_search_client, monkeypatch
) -> None:
    client, _k = chat_search_client
    monkeypatch.setattr(
        "api.images.nl_catalog_search.run_nl_catalog_filter_llm_multi_turn",
        lambda *a, **k: "not-json",
    )
    r = client.post(
        "/api/images/chat-search", json={"message": "anything here"}
    )
    assert r.status_code == 400
    err = r.get_json()["error"]
    assert "NL filter" in err
