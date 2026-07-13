"""Contract tests for Stacks pydantic models."""

from __future__ import annotations

import pytest
from app import create_app

from api.schemas.stacks import (
    StackMembersResponse,
    StackMergeResponse,
    StackRepresentativeResponse,
    StackSplitMemberResponse,
    validate_stack_metadata,
)
from lightroom_tagger.core.database import (
    init_database,
    library_write,
    stack_merge_into,
    stack_set_representative,
    stack_split_member_out,
    store_image,
)


def _insert_stack(conn, rep_key: str, member_keys: list[str]) -> int:
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
def stacks_contract_client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "library.db")
    conn = init_database(db_path)
    keys = [
        store_image(
            conn,
            {
                "date_taken": f"2024-01-0{i + 1}",
                "filename": f"{letter}.jpg",
                "filepath": f"/x/{letter}.jpg",
                "id": str(i + 1),
            },
        )
        for i, letter in enumerate(("a", "b", "c"))
    ]
    rep, m1, m2 = keys
    sid = _insert_stack(conn, rep, [rep, m1, m2])
    conn.close()
    monkeypatch.setattr("utils.db.LIBRARY_DB", db_path)
    return create_app().test_client(), db_path, sid, rep, m1, m2


def test_stack_members_response_round_trip(stacks_contract_client):
    client, _db_path, sid, *_rest = stacks_contract_client
    payload = client.get(f"/api/images/stacks/{sid}/members").get_json()
    validated = StackMembersResponse.model_validate(payload)
    assert len(validated.items) == 3


def test_stack_split_member_response_round_trip_from_handler(stacks_contract_client):
    client, _db_path, sid, _rep, m1, _m2 = stacks_contract_client
    payload = client.post(
        f"/api/images/stacks/{sid}/split-member",
        json={"image_key": m1},
    ).get_json()
    validated = StackSplitMemberResponse.model_validate(payload)
    assert validated.split_out_key == m1
    assert validated.remaining_stack is not None
    validate_stack_metadata(validated.remaining_stack.model_dump(mode="json"))


def test_stack_merge_response_round_trip_from_db_helper(stacks_contract_client):
    _client, db_path, sid, rep, m1, m2 = stacks_contract_client
    conn = init_database(db_path)
    solo_key = store_image(
        conn,
        {
            "date_taken": "2024-02-01",
            "filename": "solo.jpg",
            "filepath": "/x/solo.jpg",
            "id": "9",
        },
    )
    other_sid = _insert_stack(conn, solo_key, [solo_key])
    with library_write(conn):
        result = stack_merge_into(conn, sid, other_sid)
    validated = StackMergeResponse.model_validate(result)
    assert validated.merged_stack_id == other_sid
    assert validated.stack.stack_member_count >= 3
    conn.close()


def test_stack_representative_response_round_trip_from_db_helper(stacks_contract_client):
    _client, db_path, sid, _rep, m1, _m2 = stacks_contract_client
    conn = init_database(db_path)
    with library_write(conn):
        result = stack_set_representative(conn, sid, m1)
    validated = StackRepresentativeResponse.model_validate(result)
    assert validated.stack.representative_key == m1
    conn.close()


def test_stack_metadata_rejects_wrong_shape():
    with pytest.raises(Exception):
        validate_stack_metadata({"stack_id": 1})
