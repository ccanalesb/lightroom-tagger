"""Contract and behaviour tests for stack suggestion endpoints."""

from __future__ import annotations

from lightroom_tagger.core.database import (
    init_database,
    insert_catalog_similarity_group,
    insert_image_score,
    library_write,
    reject_catalog_similarity_pair,
    store_image,
)

from api.schemas.stacks import (
    StackSuggestionAcceptResponse,
    StackSuggestionRejectResponse,
    StackSuggestionsResponse,
)


def _score(conn, image_key: str, score: int) -> None:
    insert_image_score(
        conn,
        {
            "image_key": image_key,
            "image_type": "catalog",
            "perspective_slug": "alpha",
            "score": score,
            "rationale": "r",
            "model_used": "m",
            "prompt_version": "v1",
            "scored_at": "2026-01-01T00:00:00+00:00",
            "is_current": 1,
        },
    )
    conn.commit()


def _client_with_pair(tmp_path, monkeypatch):
    from app import create_app

    db_path = str(tmp_path / "library.db")
    conn = init_database(db_path)
    k_a = store_image(
        conn,
        {"date_taken": "2026-03-20T13:55:40", "filename": "a.jpg", "filepath": "/a.jpg"},
    )
    k_b = store_image(
        conn,
        {"date_taken": "2026-03-20T13:55:41", "filename": "b.jpg", "filepath": "/b.jpg"},
    )
    _score(conn, k_a, 8)
    _score(conn, k_b, 8)
    insert_catalog_similarity_group(
        conn,
        seed_key=k_a,
        candidates=[
            {
                "candidate_key": k_b,
                "similarity": 0.95,
                "rank": 1,
                "why_matched": "Visual match (95%)",
            }
        ],
    )
    conn.close()
    monkeypatch.setattr("utils.db.LIBRARY_DB", db_path)
    return create_app().test_client(), k_a, k_b


def test_stack_suggestions_list_round_trip(tmp_path, monkeypatch) -> None:
    client, k_a, k_b = _client_with_pair(tmp_path, monkeypatch)
    payload = client.get("/api/images/stacks/suggestions").get_json()
    validated = StackSuggestionsResponse.model_validate(payload)
    assert validated.total == 1
    assert len(validated.items) == 1
    assert {validated.items[0].image_a.key, validated.items[0].image_b.key} == {k_a, k_b}


def test_stack_suggestion_reject_then_rerun_stays_hidden(tmp_path, monkeypatch) -> None:
    from jobs.handlers import handle_batch_catalog_similarity
    from database import create_job, init_db
    from jobs.runner import JobRunner
    import sqlite_vec

    client, k_a, k_b = _client_with_pair(tmp_path, monkeypatch)
    reject_payload = client.post(
        "/api/images/stacks/suggestions/reject",
        json={"image_key_a": k_a, "image_key_b": k_b},
    ).get_json()
    StackSuggestionRejectResponse.model_validate(reject_payload)

    assert client.get("/api/images/stacks/suggestions").get_json()["total"] == 0

    lib_path = tmp_path / "library.db"
    conn = init_database(str(lib_path))
    k_c = store_image(
        conn,
        {"date_taken": "2026-03-20T13:55:42", "filename": "c.jpg", "filepath": "/c.jpg"},
    )

    def _axis(dim: int) -> bytes:
        v = [0.0] * 512
        v[dim] = 1.0
        return sqlite_vec.serialize_float32(v)

    with library_write(conn):
        from lightroom_tagger.core.database import upsert_image_clip_embedding

        upsert_image_clip_embedding(conn, k_a, _axis(0))
        upsert_image_clip_embedding(conn, k_b, _axis(0))
        upsert_image_clip_embedding(conn, k_c, _axis(1))
    conn.close()

    jobs_db = init_db(str(tmp_path / "jobs.db"))
    job_id = create_job(jobs_db, "batch_catalog_similarity", {})
    monkeypatch.setenv("LIBRARY_DB", str(lib_path))
    runner = JobRunner(jobs_db)
    handle_batch_catalog_similarity(
        runner,
        job_id,
        {"min_similarity": 0.9, "limit_per_seed": 5},
    )

    payload = client.get("/api/images/stacks/suggestions").get_json()
    assert payload["total"] == 0


def test_stack_suggestion_accept_round_trip(tmp_path, monkeypatch) -> None:
    client, k_a, k_b = _client_with_pair(tmp_path, monkeypatch)
    payload = client.post(
        "/api/images/stacks/suggestions/accept",
        json={"image_key_a": k_a, "image_key_b": k_b},
    ).get_json()
    validated = StackSuggestionAcceptResponse.model_validate(payload)
    assert validated.stack.stack_member_count == 2
    assert client.get("/api/images/stacks/suggestions").get_json()["total"] == 0


def test_stack_suggestion_accept_merges_two_stacks(tmp_path, monkeypatch) -> None:
    """Accepting a pair whose images live in different stacks merges them (contract stays stack-only)."""
    from lightroom_tagger.core.database import stack_create_from_keys

    from app import create_app

    db_path = str(tmp_path / "library.db")
    conn = init_database(db_path)
    keys = [
        store_image(
            conn,
            {
                "date_taken": f"2026-03-20T13:55:4{i}",
                "filename": f"{i}.jpg",
                "filepath": f"/{i}.jpg",
            },
        )
        for i in range(4)
    ]
    for k in keys:
        _score(conn, k, 8)
    with library_write(conn):
        stack_create_from_keys(conn, [keys[0], keys[1]])
        stack_create_from_keys(conn, [keys[2], keys[3]])
    conn.close()
    monkeypatch.setattr("utils.db.LIBRARY_DB", db_path)
    client = create_app().test_client()

    resp = client.post(
        "/api/images/stacks/suggestions/accept",
        json={"image_key_a": keys[0], "image_key_b": keys[2]},
    )
    assert resp.status_code == 200
    validated = StackSuggestionAcceptResponse.model_validate(resp.get_json())
    assert validated.stack.stack_member_count == 4
