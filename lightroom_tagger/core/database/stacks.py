"""Image stack membership and mutations."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence

from lightroom_tagger.core.exceptions import StackMutationError


def list_catalog_stack_member_keys(db: sqlite3.Connection, catalog_key: str) -> list[str]:
    """Return all ``image_key`` values in the stack containing *catalog_key*.

    If the key is not in ``image_stack_members``, returns ``[catalog_key]`` (solo image).
    """
    row = db.execute(
        "SELECT stack_id FROM image_stack_members WHERE image_key = ? LIMIT 1",
        (catalog_key,),
    ).fetchone()
    if not row:
        return [catalog_key]
    stack_id = int(row["stack_id"])
    rows = db.execute(
        "SELECT image_key FROM image_stack_members WHERE stack_id = ? ORDER BY image_key",
        (stack_id,),
    ).fetchall()
    return [str(r["image_key"]) for r in rows]


def select_stack_representative_key_for_keys(
    db: sqlite3.Connection, keys: Sequence[str]
) -> str | None:
    """Pick representative using the same ranking as ``batch_stack_detect`` (handlers)."""
    burst_keys = tuple(str(k) for k in keys if k)
    if not burst_keys:
        return None
    ph = ",".join("?" * len(burst_keys))
    sql = (
        "SELECT i.key AS k FROM images i "
        "LEFT JOIN ( "
        "  SELECT s.image_key AS image_key, AVG(s.score) AS ai_score "
        "  FROM image_scores s "
        "  INNER JOIN perspectives p ON p.slug = s.perspective_slug AND p.active = 1 "
        "  WHERE s.is_current = 1 AND s.image_type = 'catalog' "
        "  GROUP BY s.image_key "
        ") agg ON agg.image_key = i.key "
        f"WHERE i.key IN ({ph}) "
        "ORDER BY (i.rating > 0) DESC, i.rating DESC, COALESCE(agg.ai_score, 0) DESC, "
        "i.date_taken DESC, i.key DESC LIMIT 1"
    )
    row = db.execute(sql, burst_keys).fetchone()
    if not row:
        return None
    r = row.get("k") if isinstance(row, dict) else row[0]
    return str(r) if r is not None else None


def stack_metadata_for_api(db: sqlite3.Connection, stack_id: int) -> dict | None:
    """Stack row plus member keys; ``stack_member_count`` matches live membership."""
    row = db.execute(
        """
        SELECT stack_id, representative_key, stack_size
        FROM image_stacks
        WHERE stack_id = ?
        """,
        (stack_id,),
    ).fetchone()
    if not row:
        return None
    mem_rows = db.execute(
        """
        SELECT image_key FROM image_stack_members
        WHERE stack_id = ?
        ORDER BY image_key ASC
        """,
        (stack_id,),
    ).fetchall()
    member_keys = [str(r["image_key"]) for r in mem_rows]
    return {
        "stack_id": int(row["stack_id"]),
        "representative_key": str(row["representative_key"]),
        "stack_member_count": len(member_keys),
        "member_keys": member_keys,
    }


def catalog_image_stack_row_fields(db: sqlite3.Connection, image_key: str) -> dict:
    """Stack columns aligned with catalog list / by-keys rows for detail API parity.

    Non-members and solo images return ``stack_id`` / ``stack_member_count`` as
    ``None`` and ``is_stack_representative`` false.
    """
    row = db.execute(
        """
        SELECT st.stack_id AS stack_id, st.stack_size AS stack_member_count,
        CASE WHEN st.stack_id IS NOT NULL AND i.key = st.representative_key
             THEN 1 ELSE 0 END AS is_stack_representative
        FROM images i
        LEFT JOIN image_stack_members AS m_st ON m_st.image_key = i.key
        LEFT JOIN image_stacks AS st ON st.stack_id = m_st.stack_id
        WHERE i.key = ?
        """,
        (image_key,),
    ).fetchone()
    if not row or row["stack_id"] is None:
        return {
            "stack_id": None,
            "stack_member_count": None,
            "is_stack_representative": False,
        }
    smc = row["stack_member_count"]
    return {
        "stack_id": int(row["stack_id"]),
        "stack_member_count": int(smc) if smc is not None else None,
        "is_stack_representative": bool(row["is_stack_representative"]),
    }


def stack_split_member_out(
    db: sqlite3.Connection, stack_id: int, image_key: str
) -> dict:
    """Remove *image_key* from *stack_id*; dissolve singleton remnants to solo images.

    Call inside :func:`library_write` so the operation is one atomic transaction.

    Returns:
        ``split_out_key``, ``remaining_stack`` (metadata dict or ``None`` if dissolved),
        ``dissolved`` (True when no ``image_stacks`` row remains for former members).
    """
    stack_row = db.execute(
        "SELECT stack_id, representative_key FROM image_stacks WHERE stack_id = ?",
        (stack_id,),
    ).fetchone()
    if not stack_row:
        raise StackMutationError("stack not found", status_code=404)

    mem = db.execute(
        """
        SELECT 1 AS o FROM image_stack_members
        WHERE stack_id = ? AND image_key = ?
        """,
        (stack_id, image_key),
    ).fetchone()
    if not mem:
        raise StackMutationError(
            "image_key is not a member of this stack", status_code=400
        )

    db.execute(
        "DELETE FROM image_stack_members WHERE stack_id = ? AND image_key = ?",
        (stack_id, image_key),
    )

    remaining_rows = db.execute(
        """
        SELECT image_key FROM image_stack_members
        WHERE stack_id = ?
        ORDER BY image_key ASC
        """,
        (stack_id,),
    ).fetchall()
    remaining_keys = [str(r["image_key"]) for r in remaining_rows]

    if not remaining_keys:
        db.execute("DELETE FROM image_stacks WHERE stack_id = ?", (stack_id,))
        return {
            "split_out_key": image_key,
            "remaining_stack": None,
            "dissolved": True,
        }

    if len(remaining_keys) == 1:
        lone = remaining_keys[0]
        db.execute(
            "DELETE FROM image_stack_members WHERE stack_id = ? AND image_key = ?",
            (stack_id, lone),
        )
        db.execute("DELETE FROM image_stacks WHERE stack_id = ?", (stack_id,))
        return {
            "split_out_key": image_key,
            "remaining_stack": None,
            "dissolved": True,
        }

    old_rep = str(stack_row["representative_key"])
    new_rep = (
        old_rep
        if old_rep in remaining_keys
        else select_stack_representative_key_for_keys(db, remaining_keys)
    )
    if not new_rep or new_rep not in remaining_keys:
        new_rep = sorted(remaining_keys)[-1]

    n = len(remaining_keys)
    # stack_metadata_for_api is authoritative for API stack_member_count (live membership).
    db.execute(
        """
        UPDATE image_stacks
        SET representative_key = ?, stack_size = ?, user_modified = 1
        WHERE stack_id = ?
        """,
        (new_rep, n, stack_id),
    )
    meta = stack_metadata_for_api(db, stack_id)
    assert meta is not None
    return {
        "split_out_key": image_key,
        "remaining_stack": meta,
        "dissolved": False,
    }


def stack_merge_into(
    db: sqlite3.Connection, target_stack_id: int, source_stack_id: int
) -> dict:
    """Move all members from *source_stack_id* into *target_stack_id*; delete source stack.

    Call inside :func:`library_write`.

    Returns:
        ``stack`` (target metadata), ``merged_stack_id`` (source id).
    """
    if target_stack_id == source_stack_id:
        raise StackMutationError("cannot merge a stack into itself", status_code=400)

    t_row = db.execute(
        "SELECT stack_id, representative_key FROM image_stacks WHERE stack_id = ?",
        (target_stack_id,),
    ).fetchone()
    s_row = db.execute(
        "SELECT stack_id FROM image_stacks WHERE stack_id = ?",
        (source_stack_id,),
    ).fetchone()
    if not t_row or not s_row:
        raise StackMutationError("stack not found", status_code=404)

    db.execute(
        """
        UPDATE image_stack_members
        SET stack_id = ?
        WHERE stack_id = ?
        """,
        (target_stack_id, source_stack_id),
    )
    db.execute("DELETE FROM image_stacks WHERE stack_id = ?", (source_stack_id,))

    member_rows = db.execute(
        """
        SELECT image_key FROM image_stack_members
        WHERE stack_id = ?
        ORDER BY image_key ASC
        """,
        (target_stack_id,),
    ).fetchall()
    keys = [str(r["image_key"]) for r in member_rows]
    n = len(keys)
    if n == 0:
        db.execute("DELETE FROM image_stacks WHERE stack_id = ?", (target_stack_id,))
        raise StackMutationError("merge produced an empty stack", status_code=500)

    old_rep = str(t_row["representative_key"])
    new_rep = (
        old_rep
        if old_rep in keys
        else select_stack_representative_key_for_keys(db, keys)
    )
    if not new_rep or new_rep not in keys:
        new_rep = sorted(keys)[-1]

    # stack_metadata_for_api is authoritative for API stack_member_count (live membership).
    db.execute(
        """
        UPDATE image_stacks
        SET representative_key = ?, stack_size = ?, user_modified = 1
        WHERE stack_id = ?
        """,
        (new_rep, n, target_stack_id),
    )
    meta = stack_metadata_for_api(db, target_stack_id)
    assert meta is not None
    return {"stack": meta, "merged_stack_id": source_stack_id}


def stack_set_representative(
    db: sqlite3.Connection, stack_id: int, new_representative_key: str
) -> dict:
    """Set stack representative to *new_representative_key* (must be a member).

    Call inside :func:`library_write`.
    """
    stack_row = db.execute(
        "SELECT stack_id FROM image_stacks WHERE stack_id = ?",
        (stack_id,),
    ).fetchone()
    if not stack_row:
        raise StackMutationError("stack not found", status_code=404)

    mem = db.execute(
        """
        SELECT 1 AS o FROM image_stack_members
        WHERE stack_id = ? AND image_key = ?
        """,
        (stack_id, new_representative_key),
    ).fetchone()
    if not mem:
        raise StackMutationError(
            "image_key is not a member of this stack", status_code=400
        )

    db.execute(
        """
        UPDATE image_stacks
        SET representative_key = ?, user_modified = 1
        WHERE stack_id = ?
        """,
        (new_representative_key, stack_id),
    )
    # Keep stack_size aligned with membership
    cnt_row = db.execute(
        "SELECT COUNT(*) AS c FROM image_stack_members WHERE stack_id = ?",
        (stack_id,),
    ).fetchone()
    n = int(cnt_row["c"]) if cnt_row else 0
    # stack_metadata_for_api is authoritative for API stack_member_count (live membership).
    db.execute(
        "UPDATE image_stacks SET stack_size = ? WHERE stack_id = ?",
        (n, stack_id),
    )
    meta = stack_metadata_for_api(db, stack_id)
    assert meta is not None
    return {"stack": meta}
