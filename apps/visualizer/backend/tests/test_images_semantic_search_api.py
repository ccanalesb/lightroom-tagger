"""Tests for POST /api/images/search/semantic-search (mocked embed + hybrid search)."""

from __future__ import annotations

import pytest
from app import create_app

from lightroom_tagger.core.database import init_database, store_image, store_image_description
from lightroom_tagger.core.semantic_search import SemanticSearchMeta, SemanticSearchRow


@pytest.fixture
def semantic_search_client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "library.db")
    conn = init_database(db_path)
    k_alpha = store_image(
        conn,
        {
            "date_taken": "2024-01-10",
            "filename": "alpha.jpg",
            "rating": 3,
            "id": "100",
        },
    )
    k_beta = store_image(
        conn,
        {
            "date_taken": "2024-02-11",
            "filename": "beta.jpg",
            "rating": 4,
            "id": "200",
        },
    )
    store_image_description(
        conn,
        {
            "image_key": k_alpha,
            "image_type": "catalog",
            "summary": "alpha story scene",
            "subjects": [],
            "best_perspective": "p",
            "perspectives": {},
            "composition": {},
            "technical": {},
            "model_used": "t",
        },
    )
    store_image_description(
        conn,
        {
            "image_key": k_beta,
            "image_type": "catalog",
            "summary": "beta river scene",
            "subjects": [],
            "best_perspective": "p",
            "perspectives": {},
            "composition": {},
            "technical": {},
            "model_used": "t",
        },
    )
    conn.close()

    monkeypatch.setattr("utils.db.LIBRARY_DB", db_path)
    app = create_app()
    return app.test_client(), k_alpha, k_beta


def test_semantic_search_returns_metadata_and_row_extras(
    semantic_search_client, monkeypatch
):
    client, k_alpha, _k_beta = semantic_search_client

    fixed_blob = b"\xef" * (768 * 4)

    def fake_hybrid(
        _db,
        *,
        user_query,
        fts_match,
        query_vec_blob,
        limit,
        offset,
    ):
        _ = (user_query, fts_match, query_vec_blob, limit, offset)
        return (
            [
                SemanticSearchRow(
                    image_key=k_alpha,
                    rrf_score=0.03278688524590164,
                    why_matched="FTS match · embedding: 0.88",
                ),
            ],
            1,
            SemanticSearchMeta(
                missing_embeddings_count=2,
                semantic_index_empty=False,
                rrf_k=60,
                fts_no_match=False,
            ),
        )

    monkeypatch.setattr(
        "lightroom_tagger.core.catalog_search.embed_query_to_vec_blob", lambda _q: fixed_blob
    )
    monkeypatch.setattr(
        "lightroom_tagger.core.catalog_search.run_semantic_hybrid_search", fake_hybrid
    )

    r = client.post(
        "/api/images/search/semantic-search",
        json={"query": "alpha beta", "limit": 10, "offset": 0},
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data["total"] == 1
    assert isinstance(data["metadata"]["missing_embeddings_count"], int)
    assert data["metadata"]["missing_embeddings_count"] == 2
    assert data["metadata"]["rrf_k"] == 60

    assert len(data["images"]) == 1
    img = data["images"][0]
    assert img["key"] == k_alpha
    assert "score" in img
    assert img["score"] == pytest.approx(0.03278688524590164)
    assert img["why_matched"] == "FTS match · embedding: 0.88"
    tu = img["thumbnail_url"]
    assert tu.startswith("/api/images/catalog/")
    assert tu.endswith("/thumbnail")
    assert f"/api/images/catalog/{k_alpha}/thumbnail" == tu


def test_semantic_search_rejects_short_query(semantic_search_client, monkeypatch):
    client, _k_alpha, _k_beta = semantic_search_client
    monkeypatch.setattr(
        "lightroom_tagger.core.catalog_search.embed_query_to_vec_blob",
        lambda _q: b"\x00" * (768 * 4),
    )
    monkeypatch.setattr(
        "lightroom_tagger.core.catalog_search.run_semantic_hybrid_search",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("should not run")),
    )

    r = client.post("/api/images/search/semantic-search", json={"query": "a"})
    assert r.status_code == 400
    assert "error" in r.get_json()
