"""STACK-03: catalog / best-photos primary list collapses non-representative stack members."""

from __future__ import annotations

from lightroom_tagger.core.database import (
    catalog_key_is_primary_grid_row,
    init_database,
    query_catalog_images,
    store_image,
)


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
