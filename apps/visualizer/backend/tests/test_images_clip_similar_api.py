"""GET /api/images/catalog/<key>/similar and GET /api/images/stacks/<id>/members (SIM-02 / STACK-03)."""

from __future__ import annotations

import sqlite3

import pytest
import sqlite_vec
from app import create_app

from lightroom_tagger.core.database import (
    insert_catalog_similarity_group,
    init_database,
    library_write,
    store_image,
    upsert_image_clip_embedding,
)


def _unit_axis(dim: int) -> bytes:
    v = [0.0] * 512
    v[dim] = 1.0
    return sqlite_vec.serialize_float32(v)


def _insert_two_member_stack(conn: sqlite3.Connection, rep_key: str, mem_key: str) -> int:
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


@pytest.fixture
def clip_similar_client(tmp_path, monkeypatch):
    """Two catalog images; CLIP rows with identical embedding so the second is a neighbor of the first."""
    db_path = str(tmp_path / "library.db")
    conn = init_database(db_path)
    k_seed = store_image(
        conn,
        {
            "date_taken": "2024-01-01",
            "filename": "seed.jpg",
            "filepath": "/seed.jpg",
            "id": "1",
        },
    )
    k_nb = store_image(
        conn,
        {
            "date_taken": "2024-01-02",
            "filename": "near.jpg",
            "filepath": "/near.jpg",
            "id": "2",
        },
    )
    blob = _unit_axis(0)
    with library_write(conn):
        upsert_image_clip_embedding(conn, k_seed, blob)
        upsert_image_clip_embedding(conn, k_nb, blob)
    conn.close()

    monkeypatch.setattr("utils.db.LIBRARY_DB", db_path)
    app = create_app()
    return app.test_client(), k_seed, k_nb


def test_clip_similar_missing_embedding_returns_404_with_contract_message(
    tmp_path, monkeypatch
) -> None:
    db_path = str(tmp_path / "library.db")
    conn = init_database(db_path)
    k = store_image(
        conn,
        {
            "date_taken": "2024-01-01",
            "filename": "noemb.jpg",
            "filepath": "/a.jpg",
            "id": "9",
        },
    )
    conn.close()
    monkeypatch.setattr("utils.db.LIBRARY_DB", db_path)
    client = create_app().test_client()
    r = client.get(f"/api/images/catalog/{k}/similar")
    assert r.status_code == 404
    data = r.get_json()
    assert data is not None
    assert "Visual similarity is unavailable" in (data.get("error") or "")


def test_clip_similar_success_includes_meta_and_similarity(clip_similar_client) -> None:
    client, k_seed, k_nb = clip_similar_client
    r = client.get(f"/api/images/catalog/{k_seed}/similar?limit=10&offset=0")
    assert r.status_code == 200
    data = r.get_json()
    assert data is not None
    assert data["meta"]["clip_model_id"] == "clip-ViT-B-32"
    assert data["meta"]["clip_embed_dim"] == 512
    assert data["total"] >= 1
    images = data["images"]
    by_key = {im["key"]: im for im in images}
    assert k_nb in by_key
    im = by_key[k_nb]
    assert 0.0 <= im["similarity"] <= 1.0
    assert "why_matched" in im
    assert "Visual match (" in im["why_matched"]


def test_catalog_similarity_groups_endpoint_returns_persisted_groups(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "library.db")
    conn = init_database(db_path)
    k_seed = store_image(
        conn,
        {
            "date_taken": "2024-01-02",
            "filename": "seed.jpg",
            "filepath": "/seed.jpg",
            "id": "1",
        },
    )
    k_candidate = store_image(
        conn,
        {
            "date_taken": "2024-01-01",
            "filename": "candidate.jpg",
            "filepath": "/candidate.jpg",
            "id": "2",
        },
    )
    insert_catalog_similarity_group(
        conn,
        seed_key=k_seed,
        candidates=[
            {
                "candidate_key": k_candidate,
                "similarity": 0.95,
                "rank": 1,
                "why_matched": "Visual match (95%)",
            }
        ],
        job_id="job-1",
    )
    conn.close()

    monkeypatch.setattr("utils.db.LIBRARY_DB", db_path)
    client = create_app().test_client()
    r = client.get("/api/images/catalog-similarity-groups")

    assert r.status_code == 200
    data = r.get_json()
    assert data is not None
    assert data["total"] == 1
    group = data["items"][0]
    assert group["seed"]["key"] == k_seed
    assert group["candidates"][0]["key"] == k_candidate
    assert group["candidates"][0]["similarity"] == 0.95


@pytest.fixture
def stack_members_client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "library.db")
    conn = init_database(db_path)
    k_rep = store_image(
        conn,
        {
            "date_taken": "2024-01-01",
            "filename": "rep.jpg",
            "filepath": "/rep.jpg",
            "id": "r1",
        },
    )
    k_mem = store_image(
        conn,
        {
            "date_taken": "2024-01-02",
            "filename": "mem.jpg",
            "filepath": "/mem.jpg",
            "id": "m1",
        },
    )
    sid = _insert_two_member_stack(conn, k_rep, k_mem)
    conn.close()
    monkeypatch.setattr("utils.db.LIBRARY_DB", db_path)
    return create_app().test_client(), sid, k_rep, k_mem


def test_stack_members_includes_both_keys_ordered(stack_members_client) -> None:
    client, sid, k_rep, k_mem = stack_members_client
    r = client.get(f"/api/images/stacks/{sid}/members")
    assert r.status_code == 200
    data = r.get_json()
    assert data is not None
    items = data["items"]
    keys = [it["key"] for it in items]
    assert keys == sorted([k_rep, k_mem])
    for it in items:
        assert "stack_member_count" in it
        assert it.get("stack_member_count") == 2
        assert "is_stack_representative" in it
        assert "stack_id" in it


def test_stack_members_unknown_404_includes_stack_word(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "library.db")
    conn = init_database(db_path)
    conn.close()
    monkeypatch.setattr("utils.db.LIBRARY_DB", db_path)
    client = create_app().test_client()
    r = client.get("/api/images/stacks/99999/members")
    assert r.status_code == 404
    assert "stack" in ((r.get_json() or {}).get("error") or "").lower()


@pytest.fixture
def catalog_stack_badge_client(tmp_path, monkeypatch):
    """Single-image stack of size 1 does not use image_stack_members the same way — use 2 members."""
    db_path = str(tmp_path / "library.db")
    conn = init_database(db_path)
    k_rep = store_image(
        conn,
        {
            "date_taken": "2024-01-10",
            "filename": "a.jpg",
            "filepath": "/a.jpg",
            "id": "a",
        },
    )
    k_mem = store_image(
        conn,
        {
            "date_taken": "2024-01-10",
            "filename": "b.jpg",
            "filepath": "/b.jpg",
            "id": "b",
        },
    )
    _insert_two_member_stack(conn, k_rep, k_mem)
    conn.close()
    monkeypatch.setattr("utils.db.LIBRARY_DB", db_path)
    return create_app().test_client(), k_rep


def test_catalog_list_includes_stack_member_count(
    catalog_stack_badge_client,
) -> None:
    client, k_rep = catalog_stack_badge_client
    r = client.get("/api/images/catalog?limit=50&offset=0")
    assert r.status_code == 200
    data = r.get_json()
    assert data is not None
    rep_row = next((im for im in data["images"] if im["key"] == k_rep), None)
    assert rep_row is not None
    assert rep_row.get("stack_member_count") == 2
    assert rep_row.get("is_stack_representative") is True
    assert rep_row.get("stack_id") is not None
