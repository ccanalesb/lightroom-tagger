"""Unit and integration tests for RRF helpers and run_semantic_hybrid_search (Phase 3 plan 03-06)."""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pytest
import sqlite_vec

from lightroom_tagger.core.database import (
    init_database,
    library_write,
    store_image,
    store_image_description,
    upsert_image_text_embedding,
)
from lightroom_tagger.core.semantic_search import (
    RRF_K,
    fts_ranked_catalog_keys,
    rrf_scores_from_ranks,
    run_semantic_hybrid_search,
    sort_keys_by_rrf_scores,
)


def _vec_blob_axis(axis: int) -> bytes:
    v = np.zeros(768, dtype=np.float32)
    v[axis] = 1.0
    n = float(np.linalg.norm(v))
    if n > 0:
        v = v / n
    return sqlite_vec.serialize_float32(v.tolist())


def test_rrf_asymmetric_lists_b_wins():
    scores = rrf_scores_from_ranks({"fts": ["a", "b"], "vec": ["b"]})
    ordered = sort_keys_by_rrf_scores(scores)
    assert ordered == ["b", "a"]
    assert scores["b"] > scores["a"]
    assert scores["a"] == pytest.approx(1.0 / (RRF_K + 1))
    assert scores["b"] == pytest.approx(1.0 / (RRF_K + 2) + 1.0 / (RRF_K + 1))


def test_rrf_single_list():
    scores = rrf_scores_from_ranks({"fts": ["x", "y"]})
    assert set(scores.keys()) == {"x", "y"}
    assert scores["x"] == pytest.approx(1.0 / (RRF_K + 1))
    assert scores["y"] == pytest.approx(1.0 / (RRF_K + 2))


def test_hybrid_matrix_a_fts_empty_returns_no_rows_fts_no_match(tmp_path):
    """(a) Vec index non-empty, FTS leg empty → D-08 early return; no embedding-only path."""
    db_path = tmp_path / "t.db"
    conn = init_database(str(db_path))
    try:
        k = store_image(
            conn,
            {
                "date_taken": "2024-01-01",
                "filename": "a.jpg",
                "rating": 1,
            },
        )
        store_image_description(
            conn,
            {
                "image_key": k,
                "image_type": "catalog",
                "summary": "apple orchard daylight",
                "subjects": [],
                "best_perspective": "p",
                "perspectives": {},
                "composition": {},
                "technical": {},
                "model_used": "t",
            },
        )
        blob = _vec_blob_axis(0)
        with library_write(conn):
            upsert_image_text_embedding(conn, k, blob)

        fts_match = '"qqqquniquezzzz"'
        assert fts_ranked_catalog_keys(conn, fts_match, limit=200) == []

        rows, total, meta = run_semantic_hybrid_search(
            conn,
            user_query="qqqquniquezzzz",
            fts_match=fts_match,
            query_vec_blob=blob,
            limit=10,
            offset=0,
        )
        assert rows == []
        assert total == 0
        assert meta.fts_no_match is True
        assert meta.semantic_index_empty is False
        assert isinstance(meta.missing_embeddings_count, int)
        assert meta.missing_embeddings_count >= 0
        assert meta.rrf_k == RRF_K
    finally:
        conn.close()


@patch("lightroom_tagger.core.semantic_search.knn_embedded_catalog_keys", return_value=[])
def test_hybrid_matrix_b_fts_only_when_knn_empty(_mock_knn, tmp_path):
    """(b) Embeddings exist but KNN returns no pairs → FTS-only RRF; why_matched is FTS match."""
    db_path = tmp_path / "t.db"
    conn = init_database(str(db_path))
    try:
        for i, term in enumerate(("alpha_first", "beta_second")):
            k = store_image(
                conn,
                {
                    "date_taken": f"2024-0{i + 1}-15",
                    "filename": f"{i}.jpg",
                    "rating": 1,
                },
            )
            store_image_description(
                conn,
                {
                    "image_key": k,
                    "image_type": "catalog",
                    "summary": f"{term} commontoken",
                    "subjects": [],
                    "best_perspective": "p",
                    "perspectives": {},
                    "composition": {},
                    "technical": {},
                    "model_used": "t",
                },
            )
            with library_write(conn):
                upsert_image_text_embedding(conn, k, _vec_blob_axis(i))

        fts_match = '"alpha_first" AND "commontoken"'
        rows, total, meta = run_semantic_hybrid_search(
            conn,
            user_query="alpha_first commontoken",
            fts_match=fts_match,
            query_vec_blob=b"\x00" * (768 * 4),
            limit=10,
            offset=0,
        )
        assert meta.semantic_index_empty is False
        assert meta.fts_no_match is False
        assert total >= 1
        assert all("FTS match" == r.why_matched for r in rows)
        assert all("embedding:" not in r.why_matched for r in rows)
    finally:
        conn.close()


def test_hybrid_matrix_c_fts_and_vec_both_contribute(tmp_path):
    """(c) Both legs non-empty and overlap → fused order can differ from FTS-only; dual-signal why_matched."""
    db_path = tmp_path / "t.db"
    conn = init_database(str(db_path))
    try:
        summaries = (
            "alpha rareword beta gamma tail0",
            "beta rareword alpha extra tail1",
            "alpha beta rareword zzthird tail2",
        )
        keys: list[str] = []
        for i, summary in enumerate(summaries):
            k = store_image(
                conn,
                {
                    "date_taken": f"2024-0{i + 1}-20",
                    "filename": f"c{i}.jpg",
                    "rating": 1,
                },
            )
            keys.append(k)
            store_image_description(
                conn,
                {
                    "image_key": k,
                    "image_type": "catalog",
                    "summary": summary,
                    "subjects": [],
                    "best_perspective": "p",
                    "perspectives": {},
                    "composition": {},
                    "technical": {},
                    "model_used": "t",
                },
            )
        blobs = [_vec_blob_axis(i) for i in range(3)]
        with library_write(conn):
            for k, b in zip(keys, blobs, strict=True):
                upsert_image_text_embedding(conn, k, b)

        fts_match = '"alpha" AND "beta" AND "rareword"'
        fts_order = fts_ranked_catalog_keys(conn, fts_match, limit=200)
        assert set(fts_order) == set(keys)

        query_blob = blobs[2]
        rows, total, meta = run_semantic_hybrid_search(
            conn,
            user_query="alpha beta rareword",
            fts_match=fts_match,
            query_vec_blob=query_blob,
            limit=10,
            offset=0,
        )
        assert meta.fts_no_match is False
        assert meta.semantic_index_empty is False
        assert total == 3
        result_keys = [r.image_key for r in rows]
        assert result_keys != fts_order

        dual = [r for r in rows if "FTS match · embedding:" in r.why_matched]
        assert len(dual) >= 1
        assert all(
            r.why_matched.startswith("FTS match · embedding:")
            and len(r.why_matched.split(":")[-1].strip()) >= 4
            for r in dual
        )
    finally:
        conn.close()


def test_hybrid_matrix_d_semantic_index_empty_degrades_fts_only(tmp_path):
    """(d) No vec rows → semantic_index_empty; pure FTS BM25 ordering via single-list RRF."""
    db_path = tmp_path / "t.db"
    conn = init_database(str(db_path))
    try:
        for i, summary in enumerate(("alpha zzgamma", "beta zzgamma")):
            k = store_image(
                conn,
                {
                    "date_taken": f"2024-0{i + 1}-10",
                    "filename": f"d{i}.jpg",
                    "rating": 1,
                },
            )
            store_image_description(
                conn,
                {
                    "image_key": k,
                    "image_type": "catalog",
                    "summary": summary,
                    "subjects": [],
                    "best_perspective": "p",
                    "perspectives": {},
                    "composition": {},
                    "technical": {},
                    "model_used": "t",
                },
            )

        n_vec = conn.execute(
            "SELECT COUNT(*) AS c FROM image_text_embeddings"
        ).fetchone()
        assert int(n_vec["c"]) == 0

        fts_match = '"zzgamma"'
        fts_order = fts_ranked_catalog_keys(conn, fts_match, limit=200)
        rows, total, meta = run_semantic_hybrid_search(
            conn,
            user_query="zzgamma",
            fts_match=fts_match,
            query_vec_blob=b"\x00" * (768 * 4),
            limit=10,
            offset=0,
        )
        assert meta.semantic_index_empty is True
        assert meta.fts_no_match is False
        assert total == 2
        assert [r.image_key for r in rows] == fts_order
        assert all(r.why_matched == "FTS match" for r in rows)
    finally:
        conn.close()
