"""STACK-03: catalog / best-photos primary list collapses non-representative stack members."""

from __future__ import annotations

from datetime import datetime, timezone

from lightroom_tagger.core.database import (
    catalog_key_is_primary_grid_row,
    init_database,
    insert_image_score,
    query_catalog_images,
    store_image,
)
from lightroom_tagger.core.identity_service import rank_best_photos


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


def test_query_catalog_images_only_includes_representative_for_stack(tmp_path) -> None:
    """Two members sharing a stack: only the representative row appears in the default list."""
    conn = init_database(str(tmp_path / "lib.db"))

    rep_key = store_image(
        conn,
        {
            "date_taken": "2024-01-01",
            "filename": "rep.jpg",
            "filepath": "/x/rep.jpg",
            "id": "1",
        },
    )
    mem_key = store_image(
        conn,
        {
            "date_taken": "2024-01-02",
            "filename": "mem.jpg",
            "filepath": "/x/mem.jpg",
            "id": "2",
        },
    )
    _insert_two_member_stack(conn, rep_key, mem_key)

    rows, total = query_catalog_images(conn, limit=50, offset=0)
    keys = {r["key"] for r in rows}
    assert rep_key in keys
    assert mem_key not in keys
    assert total == 1
    assert len(rows) == 1
    rep_row = next(r for r in rows if r["key"] == rep_key)
    assert rep_row.get("is_stack_representative") is True
    assert rep_row.get("stack_member_count") == 2
    assert rep_row.get("stack_id") is not None
    assert catalog_key_is_primary_grid_row(conn, rep_key) is True
    assert catalog_key_is_primary_grid_row(conn, mem_key) is False


def test_query_catalog_count_matches_returned_rows_with_solo_and_stack(tmp_path) -> None:
    """Total count and page length match: representative + one solo image, member hidden."""
    conn = init_database(str(tmp_path / "lib.db"))

    rep_key = store_image(
        conn,
        {
            "date_taken": "2024-01-01",
            "filename": "a.jpg",
            "filepath": "/a.jpg",
            "id": "1",
        },
    )
    mem_key = store_image(
        conn,
        {
            "date_taken": "2024-01-02",
            "filename": "b.jpg",
            "filepath": "/b.jpg",
            "id": "2",
        },
    )
    solo_key = store_image(
        conn,
        {
            "date_taken": "2024-03-01",
            "filename": "solo.jpg",
            "filepath": "/solo.jpg",
            "id": "3",
        },
    )
    _insert_two_member_stack(conn, rep_key, mem_key)

    rows, total = query_catalog_images(conn, limit=50, offset=0)
    assert total == 2
    assert len(rows) == 2
    assert mem_key not in {r["key"] for r in rows}
    assert {rep_key, solo_key} == {r["key"] for r in rows}
    solo = next(r for r in rows if r["key"] == solo_key)
    assert solo.get("stack_id") is None
    assert solo.get("stack_member_count") is None
    assert solo.get("is_stack_representative") is False
    assert catalog_key_is_primary_grid_row(conn, solo_key) is True


def test_rank_best_photos_drops_non_representative_with_higher_score(tmp_path) -> None:
    """Stack member with higher aggregate than the rep must not appear in the ranked page."""
    conn = init_database(str(tmp_path / "lib.db"))
    slug_row = conn.execute(
        "SELECT slug FROM perspectives WHERE active = 1 ORDER BY slug LIMIT 1"
    ).fetchone()
    assert slug_row is not None
    slug = str(slug_row["slug"])
    ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    rep_key = store_image(
        conn,
        {
            "date_taken": "2024-01-01",
            "filename": "r.jpg",
            "filepath": "/r.jpg",
            "id": "1",
        },
    )
    mem_key = store_image(
        conn,
        {
            "date_taken": "2024-01-01",
            "filename": "m.jpg",
            "filepath": "/m.jpg",
            "id": "2",
        },
    )
    _insert_two_member_stack(conn, rep_key, mem_key)

    insert_image_score(
        conn,
        {
            "image_key": rep_key,
            "image_type": "catalog",
            "perspective_slug": slug,
            "score": 1,
            "scored_at": ts,
        },
    )
    insert_image_score(
        conn,
        {
            "image_key": mem_key,
            "image_type": "catalog",
            "perspective_slug": slug,
            "score": 10,
            "scored_at": ts,
        },
    )
    conn.commit()

    page, total, _meta = rank_best_photos(conn, limit=20, offset=0)
    keys = [r["image_key"] for r in page]
    assert mem_key not in keys
    assert rep_key in keys
    assert total == 1
    rep = next(r for r in page if r["image_key"] == rep_key)
    assert rep.get("is_stack_representative") is True
    assert rep.get("stack_member_count") == 2
    assert rep.get("stack_id") is not None


def test_stack_exists(tmp_path) -> None:
    from lightroom_tagger.core.database import stack_exists

    conn = init_database(str(tmp_path / "lib.db"))
    assert stack_exists(conn, 1) is False

    rep_key = store_image(
        conn,
        {"date_taken": "2024-01-01", "filename": "rep.jpg", "filepath": "/rep.jpg"},
    )
    mem_key = store_image(
        conn,
        {"date_taken": "2024-01-02", "filename": "mem.jpg", "filepath": "/mem.jpg"},
    )
    sid = _insert_two_member_stack(conn, rep_key, mem_key)
    assert stack_exists(conn, sid) is True
    assert stack_exists(conn, 9999) is False
    conn.close()


def test_list_stack_member_keys(tmp_path) -> None:
    from lightroom_tagger.core.database import list_stack_member_keys

    conn = init_database(str(tmp_path / "lib.db"))
    assert list_stack_member_keys(conn, 1) == []

    rep_key = store_image(
        conn,
        {"date_taken": "2024-01-01", "filename": "b.jpg", "filepath": "/b.jpg"},
    )
    mem_key = store_image(
        conn,
        {"date_taken": "2024-01-02", "filename": "a.jpg", "filepath": "/a.jpg"},
    )
    sid = _insert_two_member_stack(conn, rep_key, mem_key)
    assert list_stack_member_keys(conn, sid) == sorted([rep_key, mem_key])
    assert list_stack_member_keys(conn, 9999) == []
    conn.close()
