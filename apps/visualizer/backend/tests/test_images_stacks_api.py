"""STACK-05: POST stack split, merge, and change-representative (transactional DB helpers + API)."""

from __future__ import annotations

import sqlite3

import pytest
from app import create_app

from lightroom_tagger.core.database import (
    init_database,
    library_write,
    stack_merge_into,
    stack_set_representative,
    stack_split_member_out,
    store_image,
)


def _insert_stack(
    conn: sqlite3.Connection, rep_key: str, member_keys: list[str]
) -> int:
    n = len(member_keys)
    conn.execute(
        "INSERT INTO image_stacks (representative_key, stack_size, user_modified) "
        "VALUES (?, ?, 0)",
        (rep_key, n),
    )
    conn.commit()
    row = conn.execute("SELECT last_insert_rowid() AS x").fetchone()
    assert row is not None
    sid = int(row["x"])
    for k in member_keys:
        conn.execute(
            "INSERT INTO image_stack_members (stack_id, image_key) VALUES (?, ?)",
            (sid, k),
        )
    conn.commit()
    return sid


@pytest.fixture
def stack_mutations_client(tmp_path, monkeypatch):
    """Three catalog images in a 3-key stack (rep + two members)."""
    db_path = str(tmp_path / "library.db")
    conn = init_database(db_path)
    keys: list[str] = []
    for i, letter in enumerate(("a", "b", "c")):
        keys.append(
            store_image(
                conn,
                {
                    "date_taken": f"2024-01-0{i + 1}",
                    "filename": f"{letter}.jpg",
                    "filepath": f"/x/{letter}.jpg",
                    "id": str(i + 1),
                    "rating": 3 - i,
                },
            )
        )
    rep, m1, m2 = keys[0], keys[1], keys[2]
    sid = _insert_stack(conn, rep, [rep, m1, m2])
    conn.close()

    monkeypatch.setattr("utils.db.LIBRARY_DB", db_path)
    app = create_app()
    return app.test_client(), db_path, sid, rep, m1, m2


def test_stack_split_member_happy_path_removes_one_keeps_metadata(
    stack_mutations_client,
) -> None:
    client, db_path, sid, rep, m1, m2 = stack_mutations_client
    rv = client.post(
        f"/api/images/stacks/{sid}/split-member",
        json={"image_key": m1},
    )
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["split_out_key"] == m1
    assert data["dissolved"] is False
    rem = data["remaining_stack"]
    assert rem is not None
    assert rem["stack_member_count"] == 2
    assert set(rem["member_keys"]) == {rep, m2}
    assert rem["representative_key"] == rep

    db = init_database(db_path)
    try:
        n = db.execute(
            "SELECT COUNT(*) AS c FROM image_stack_members WHERE stack_id = ?",
            (sid,),
        ).fetchone()
        assert int(n["c"]) == 2
    finally:
        db.close()


def test_stack_split_dissolves_when_two_members_remain_as_solo(
    tmp_path, monkeypatch
) -> None:
    db_path = str(tmp_path / "library.db")
    conn = init_database(db_path)
    k1 = store_image(
        conn,
        {
            "date_taken": "2024-01-01",
            "filename": "u.jpg",
            "filepath": "/u.jpg",
            "id": "1",
        },
    )
    k2 = store_image(
        conn,
        {
            "date_taken": "2024-01-02",
            "filename": "v.jpg",
            "filepath": "/v.jpg",
            "id": "2",
        },
    )
    sid = _insert_stack(conn, k1, [k1, k2])
    conn.close()

    monkeypatch.setattr("utils.db.LIBRARY_DB", db_path)
    client = create_app().test_client()
    rv = client.post(
        f"/api/images/stacks/{sid}/split-member",
        json={"image_key": k1},
    )
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["dissolved"] is True
    assert data["remaining_stack"] is None

    db = init_database(db_path)
    try:
        assert (
            db.execute(
                "SELECT COUNT(*) AS c FROM image_stacks WHERE stack_id = ?",
                (sid,),
            ).fetchone()["c"]
            == 0
        )
        assert (
            db.execute("SELECT COUNT(*) AS c FROM image_stack_members").fetchone()["c"]
            == 0
        )
    finally:
        db.close()


def test_stack_split_rejects_member_not_in_stack(stack_mutations_client) -> None:
    client, _db_path, sid, _rep, _m1, m2 = stack_mutations_client
    solo_db = init_database(_db_path)
    try:
        outsider = store_image(
            solo_db,
            {
                "date_taken": "2024-02-01",
                "filename": "solo.jpg",
                "filepath": "/solo.jpg",
                "id": "99",
            },
        )
        solo_db.commit()
    finally:
        solo_db.close()

    rv = client.post(
        f"/api/images/stacks/{sid}/split-member",
        json={"image_key": outsider},
    )
    assert rv.status_code == 400
    assert "not a member" in rv.get_json()["error"].lower()


def test_stack_split_unknown_stack_returns_404(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "library.db")
    conn = init_database(db_path)
    conn.close()
    monkeypatch.setattr("utils.db.LIBRARY_DB", db_path)
    client = create_app().test_client()
    rv = client.post(
        "/api/images/stacks/42/split-member",
        json={"image_key": "any"},
    )
    assert rv.status_code == 404


def test_stack_merge_combines_members_and_deletes_source(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "library.db")
    conn = init_database(db_path)
    keys_a: list[str] = []
    for i in range(2):
        keys_a.append(
            store_image(
                conn,
                {
                    "date_taken": f"2024-03-0{i + 1}",
                    "filename": f"ma{i}.jpg",
                    "filepath": f"/ma{i}.jpg",
                    "id": f"a{i}",
                },
            )
        )
    keys_b: list[str] = []
    for i in range(2):
        keys_b.append(
            store_image(
                conn,
                {
                    "date_taken": f"2024-04-0{i + 1}",
                    "filename": f"mb{i}.jpg",
                    "filepath": f"/mb{i}.jpg",
                    "id": f"b{i}",
                },
            )
        )
    ta, tb = keys_a[0], keys_b[0]
    sid_a = _insert_stack(conn, ta, keys_a)
    sid_b = _insert_stack(conn, tb, keys_b)
    conn.close()

    monkeypatch.setattr("utils.db.LIBRARY_DB", db_path)
    client = create_app().test_client()
    rv = client.post(
        f"/api/images/stacks/{sid_a}/merge",
        json={"source_stack_id": sid_b},
    )
    assert rv.status_code == 200
    payload = rv.get_json()
    assert payload["merged_stack_id"] == sid_b
    st = payload["stack"]
    assert st["stack_id"] == sid_a
    assert st["stack_member_count"] == 4
    assert set(st["member_keys"]) == set(keys_a + keys_b)

    db = init_database(db_path)
    try:
        assert (
            db.execute(
                "SELECT COUNT(*) AS c FROM image_stacks WHERE stack_id = ?",
                (sid_b,),
            ).fetchone()["c"]
            == 0
        )
    finally:
        db.close()


def test_stack_merge_self_returns_400(stack_mutations_client) -> None:
    client, _db_path, sid, *_rest = stack_mutations_client
    rv = client.post(
        f"/api/images/stacks/{sid}/merge",
        json={"source_stack_id": sid},
    )
    assert rv.status_code == 400


def test_stack_merge_missing_source_returns_404(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "library.db")
    conn = init_database(db_path)
    k = store_image(
        conn,
        {
            "date_taken": "2024-01-01",
            "filename": "only.jpg",
            "filepath": "/only.jpg",
            "id": "1",
        },
    )
    sid = _insert_stack(conn, k, [k])
    conn.close()
    monkeypatch.setattr("utils.db.LIBRARY_DB", db_path)
    client = create_app().test_client()
    rv = client.post(
        f"/api/images/stacks/{sid}/merge",
        json={"source_stack_id": 9999},
    )
    assert rv.status_code == 404


def test_stack_representative_change_happy_path(stack_mutations_client) -> None:
    client, _db_path, sid, rep, m1, _m2 = stack_mutations_client
    rv = client.post(
        f"/api/images/stacks/{sid}/representative",
        json={"image_key": m1},
    )
    assert rv.status_code == 200
    st = rv.get_json()["stack"]
    assert st["representative_key"] == m1
    assert st["stack_member_count"] == 3
    assert rep in st["member_keys"]


def test_stack_representative_rejects_non_member(stack_mutations_client) -> None:
    client, _db_path, sid, *_ = stack_mutations_client
    rv = client.post(
        f"/api/images/stacks/{sid}/representative",
        json={"image_key": "not-a-real-catalog-key"},
    )
    assert rv.status_code == 400


def test_stack_representative_unknown_stack_returns_404(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "library.db")
    init_database(db_path).close()
    monkeypatch.setattr("utils.db.LIBRARY_DB", db_path)
    client = create_app().test_client()
    rv = client.post(
        "/api/images/stacks/7/representative",
        json={"image_key": "x"},
    )
    assert rv.status_code == 404


def test_stack_split_db_helper_rollbacks_on_failure(tmp_path) -> None:
    """Split is atomic: failed mid-flight should not apply (nested transaction check via rollback)."""
    db_path = str(tmp_path / "library.db")
    conn = init_database(db_path)
    k1 = store_image(
        conn,
        {
            "date_taken": "2024-01-01",
            "filename": "r1.jpg",
            "filepath": "/r1.jpg",
            "id": "1",
        },
    )
    k2 = store_image(
        conn,
        {
            "date_taken": "2024-01-02",
            "filename": "r2.jpg",
            "filepath": "/r2.jpg",
            "id": "2",
        },
    )
    _insert_stack(conn, k1, [k1, k2])
    conn.close()

    db = init_database(db_path)
    try:
        with pytest.raises(Exception):
            with library_write(db):
                stack_split_member_out(db, 999, k1)
                raise RuntimeError("abort")
        cnt = db.execute("SELECT COUNT(*) AS c FROM image_stack_members").fetchone()
        assert int(cnt["c"]) == 2
    finally:
        db.close()


def test_stack_merge_db_invalid_target_rollback(tmp_path) -> None:
    db_path = str(tmp_path / "library.db")
    conn = init_database(db_path)
    keys = []
    for i in range(2):
        keys.append(
            store_image(
                conn,
                {
                    "date_taken": f"2024-05-0{i + 1}",
                    "filename": f"t{i}.jpg",
                    "filepath": f"/t{i}.jpg",
                    "id": str(i),
                },
            )
        )
    s1 = _insert_stack(conn, keys[0], keys)
    k_other = store_image(
        conn,
        {
            "date_taken": "2024-06-01",
            "filename": "o.jpg",
            "filepath": "/o.jpg",
            "id": "o",
        },
    )
    s2 = _insert_stack(conn, k_other, [k_other])
    conn.close()

    db = init_database(db_path)
    try:
        with pytest.raises(Exception):
            with library_write(db):
                stack_merge_into(db, s1, s2)
                raise RuntimeError("abort")
        assert (
            int(
                db.execute(
                    "SELECT COUNT(*) AS c FROM image_stacks",
                ).fetchone()["c"]
            )
            == 2
        )
    finally:
        db.close()


def test_stack_set_representative_db_rollback(tmp_path) -> None:
    db_path = str(tmp_path / "library.db")
    conn = init_database(db_path)
    k1 = store_image(
        conn,
        {
            "date_taken": "2024-01-01",
            "filename": "s1.jpg",
            "filepath": "/s1.jpg",
            "id": "1",
        },
    )
    k2 = store_image(
        conn,
        {
            "date_taken": "2024-01-02",
            "filename": "s2.jpg",
            "filepath": "/s2.jpg",
            "id": "2",
        },
    )
    sid = _insert_stack(conn, k1, [k1, k2])
    conn.close()

    db = init_database(db_path)
    try:
        with pytest.raises(Exception):
            with library_write(db):
                stack_set_representative(db, sid, k2)
                raise RuntimeError("abort")
        rep = db.execute(
            "SELECT representative_key FROM image_stacks WHERE stack_id = ?",
            (sid,),
        ).fetchone()
        assert str(rep["representative_key"]) == k1
    finally:
        db.close()
