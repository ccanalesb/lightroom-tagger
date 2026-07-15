"""Tests for catalog_search front door (slice 1: semantic mode)."""

from __future__ import annotations

import pytest

from lightroom_tagger.core.catalog_search import (
    CatalogSearchInputError,
    search_catalog,
)
from lightroom_tagger.core.database import (
    init_database,
    store_image,
    store_image_description,
)
from lightroom_tagger.core.semantic_search import SemanticSearchMeta, SemanticSearchRow


@pytest.fixture
def catalog_db(tmp_path):
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
    yield conn, k_alpha, k_beta
    conn.close()


def test_search_catalog_semantic_annotates_rows_and_metadata(catalog_db, monkeypatch):
    conn, k_alpha, k_beta = catalog_db
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
        _ = (user_query, fts_match, query_vec_blob, limit, offset, restrict_to_keys)
        return (
            [
                SemanticSearchRow(
                    image_key=k_beta,
                    rrf_score=0.05,
                    why_matched="Embedding match (0.91)",
                ),
                SemanticSearchRow(
                    image_key=k_alpha,
                    rrf_score=0.03,
                    why_matched="FTS match · embedding: 0.88",
                ),
            ],
            2,
            SemanticSearchMeta(
                missing_embeddings_count=1,
                semantic_index_empty=False,
                rrf_k=60,
                fts_no_match=False,
            ),
        )

    monkeypatch.setattr(
        "lightroom_tagger.core.catalog_search.embed_query_to_vec_blob",
        lambda _q: fixed_blob,
    )
    monkeypatch.setattr(
        "lightroom_tagger.core.catalog_search.run_semantic_hybrid_search",
        fake_hybrid,
    )

    result = search_catalog(
        conn,
        "alpha beta",
        mode="semantic",
        limit=10,
        offset=0,
    )

    assert result.mode == "semantic"
    assert result.total == 2
    assert result.filters is None
    assert result.assistant_message is None
    assert result.messages is None
    assert result.metadata == {
        "missing_embeddings_count": 1,
        "semantic_index_empty": False,
        "rrf_k": 60,
        "fts_no_match": False,
    }

    assert len(result.images) == 2
    assert [img["key"] for img in result.images] == [k_beta, k_alpha]
    assert result.images[0]["score"] == pytest.approx(0.05)
    assert result.images[0]["why_matched"] == "Embedding match (0.91)"
    assert result.images[1]["score"] == pytest.approx(0.03)
    assert "filename" in result.images[0]
    assert "thumbnail_url" not in result.images[0]


def test_search_catalog_rejects_empty_query(catalog_db):
    conn, _k_alpha, _k_beta = catalog_db
    with pytest.raises(CatalogSearchInputError, match="non-empty"):
        search_catalog(conn, "", mode="semantic", limit=10, offset=0)
    with pytest.raises(CatalogSearchInputError, match="non-empty"):
        search_catalog(conn, None, mode="semantic", limit=10, offset=0)


def test_search_catalog_rejects_short_query(catalog_db, monkeypatch):
    conn, _k_alpha, _k_beta = catalog_db
    monkeypatch.setattr(
        "lightroom_tagger.core.catalog_search.embed_query_to_vec_blob",
        lambda _q: (_ for _ in ()).throw(AssertionError("should not run")),
    )
    with pytest.raises(CatalogSearchInputError, match="at least 2 characters"):
        search_catalog(conn, "a", mode="semantic", limit=10, offset=0)


def test_search_catalog_rejects_no_searchable_term(catalog_db, monkeypatch):
    conn, _k_alpha, _k_beta = catalog_db
    monkeypatch.setattr(
        "lightroom_tagger.core.catalog_search.embed_query_to_vec_blob",
        lambda _q: (_ for _ in ()).throw(AssertionError("should not run")),
    )
    with pytest.raises(CatalogSearchInputError, match="searchable term"):
        search_catalog(conn, "++", mode="semantic", limit=10, offset=0)


def test_search_catalog_non_semantic_mode_raises(catalog_db):
    conn, _k_alpha, _k_beta = catalog_db
    with pytest.raises(NotImplementedError):
        search_catalog(conn, "hello world", mode="auto", limit=10, offset=0)
