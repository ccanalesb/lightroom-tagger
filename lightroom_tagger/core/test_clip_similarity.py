"""SIM-02: CLIP-only KNN similarity (``clip_similarity``)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
import sqlite_vec

from lightroom_tagger.core.clip_similarity import (
    NoClipEmbeddingError,
    get_clip_embedding_blob_for_key,
    run_clip_similar_for_seed,
    shortlist_catalog_candidates_by_clip,
)
from lightroom_tagger.core.database import (
    init_database,
    library_write,
    store_image,
    upsert_image_clip_embedding,
)


def _unit_axis(dim: int) -> bytes:
    """512-d one-hot (L2=1) on axis *dim* for deterministic cosine KNN order."""
    v = [0.0] * 512
    v[dim] = 1.0
    return sqlite_vec.serialize_float32(v)


def test_get_clip_embedding_blob_for_key_none_when_missing(tmp_path) -> None:
    conn = init_database(str(tmp_path / "lib.db"))
    k = store_image(
        conn,
        {"date_taken": "2024-01-01", "filename": "a.jpg", "filepath": "/a.jpg"},
    )
    assert get_clip_embedding_blob_for_key(conn, k) is None


def test_run_clip_similar_for_seed_raises_no_clip_embedding_error(tmp_path) -> None:
    conn = init_database(str(tmp_path / "lib.db"))
    k = store_image(
        conn,
        {"date_taken": "2024-01-01", "filename": "a.jpg", "filepath": "/a.jpg"},
    )
    with pytest.raises(NoClipEmbeddingError) as ei:
        run_clip_similar_for_seed(conn, k, limit=10, offset=0)
    assert ei.value.seed_key == k


def test_seed_key_never_appears_in_results(tmp_path) -> None:
    conn = init_database(str(tmp_path / "lib.db"))
    keys = []
    for i in range(4):
        k = store_image(
            conn,
            {
                "date_taken": f"2024-01-0{i+1}",
                "filename": f"p{i}.jpg",
                "filepath": f"/p{i}.jpg",
            },
        )
        keys.append(k)
    seed = keys[0]
    b0 = _unit_axis(0)
    with library_write(conn):
        for k in keys:
            upsert_image_clip_embedding(conn, k, b0)

    rows, meta = run_clip_similar_for_seed(conn, seed, limit=20, offset=0)
    out_keys = [k for k, _ in rows]
    assert seed not in out_keys
    assert set(out_keys) <= set(keys) - {seed}
    assert meta.get("clip_model_id") == "clip-ViT-B-32"
    assert meta.get("clip_embed_dim") == 512


def test_knn_sql_targets_image_clip_embeddings_only() -> None:
    """KNN must query ``image_clip_embeddings`` (D-05); never ``image_text_embeddings``."""
    from pathlib import Path

    text = (Path(__file__).resolve().parent / "clip_similarity.py").read_text()
    assert "FROM image_clip_embeddings" in text
    assert "image_text_embeddings" not in text


def _insert_two_member_stack(
    conn,
    rep_key: str,
    mem_key: str,
) -> int:
    conn.execute(
        "INSERT INTO image_stacks (representative_key, stack_size) VALUES (?, ?)",
        (rep_key, 2),
    )
    conn.commit()
    row = conn.execute("SELECT last_insert_rowid() AS x").fetchone()
    assert row is not None
    sid = int(row["x"])
    conn.execute(
        "INSERT INTO image_stack_members (stack_id, image_key) VALUES (?, ?)",
        (sid, rep_key),
    )
    conn.execute(
        "INSERT INTO image_stack_members (stack_id, image_key) VALUES (?, ?)",
        (sid, mem_key),
    )
    conn.commit()
    return sid


@patch('lightroom_tagger.core.clip_similarity.knn_clip_catalog_keys')
def test_shortlist_catalog_candidates_by_clip_length_subset_and_order(mock_knn, tmp_path) -> None:
    """Output size, subset, and KNN-first-seen order among allowed keys."""
    conn = init_database(str(tmp_path / 'lib.db'))
    seed = store_image(
        conn,
        {'date_taken': '2024-01-01', 'filename': 'seed.jpg', 'filepath': '/seed.jpg'},
    )
    with library_write(conn):
        upsert_image_clip_embedding(conn, seed, _unit_axis(0))

    mock_knn.return_value = [
        ('noise', 0.01),
        ('k3', 0.02),
        ('k1', 0.03),
        ('k2', 0.04),
    ]
    cand = ['k1', 'k2', 'k4']
    out = shortlist_catalog_candidates_by_clip(conn, seed, cand, top_k=2)
    assert len(out) <= 2
    assert set(out) <= set(cand)
    assert out == ['k1', 'k2']
    mock_knn.assert_called_once()


def test_shortlist_catalog_candidates_by_clip_empty_candidates(tmp_path) -> None:
    conn = init_database(str(tmp_path / 'lib.db'))
    k = store_image(
        conn,
        {'date_taken': '2024-01-01', 'filename': 'a.jpg', 'filepath': '/a.jpg'},
    )
    with library_write(conn):
        upsert_image_clip_embedding(conn, k, _unit_axis(0))
    assert shortlist_catalog_candidates_by_clip(conn, k, [], top_k=5) == []


def test_shortlist_catalog_candidates_by_clip_missing_seed_embedding_returns_empty(tmp_path) -> None:
    conn = init_database(str(tmp_path / 'lib.db'))
    k = store_image(
        conn,
        {'date_taken': '2024-01-01', 'filename': 'a.jpg', 'filepath': '/a.jpg'},
    )
    assert shortlist_catalog_candidates_by_clip(conn, k, ['x'], top_k=3) == []


def test_non_representative_stack_member_excluded_from_similar(tmp_path) -> None:
    """KNN may rank a stack member first, but it must not appear (primary grid rule)."""
    conn = init_database(str(tmp_path / "lib.db"))
    rep_key = store_image(
        conn,
        {
            "date_taken": "2024-01-01",
            "filename": "rep.jpg",
            "filepath": "/rep.jpg",
            "id": "1",
        },
    )
    mem_key = store_image(
        conn,
        {
            "date_taken": "2024-01-02",
            "filename": "mem.jpg",
            "filepath": "/mem.jpg",
            "id": "2",
        },
    )
    seed_key = store_image(
        conn,
        {
            "date_taken": "2024-01-10",
            "filename": "seed.jpg",
            "filepath": "/seed.jpg",
            "id": "3",
        },
    )
    _insert_two_member_stack(conn, rep_key, mem_key)

    # Query (seed) on axis 0; mem shares axis 0 (closest after seed); rep on axis 1.
    b_seed = _unit_axis(0)
    b_mem = _unit_axis(0)
    b_rep = _unit_axis(1)

    with library_write(conn):
        upsert_image_clip_embedding(conn, seed_key, b_seed)
        upsert_image_clip_embedding(conn, mem_key, b_mem)
        upsert_image_clip_embedding(conn, rep_key, b_rep)

    rows, _ = run_clip_similar_for_seed(conn, seed_key, limit=20, offset=0)
    out = [k for k, _ in rows]
    assert mem_key not in out
    assert rep_key in out
