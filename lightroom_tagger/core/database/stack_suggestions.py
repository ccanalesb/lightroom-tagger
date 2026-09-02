"""Catalog similarity pairs reframed as stack suggestions (#226 / #231)."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from datetime import datetime

from lightroom_tagger.core.database.frame_substance_sql import flagged_exists_sql
from lightroom_tagger.core.database.stacks import (
    select_stack_representative_key_for_keys,
    stack_id_for_image_key,
    stack_merge_into,
    stack_metadata_for_api,
)
from lightroom_tagger.core.exceptions import StackMutationError

_PENDING_PAIRS_SQL = f"""
WITH pairs AS (
    SELECT
        g.group_id,
        g.seed_key,
        c.candidate_key,
        c.similarity,
        c.why_matched,
        CASE WHEN g.seed_key < c.candidate_key THEN g.seed_key ELSE c.candidate_key END AS key_a,
        CASE WHEN g.seed_key < c.candidate_key THEN c.candidate_key ELSE g.seed_key END AS key_b
    FROM catalog_similarity_groups g
    INNER JOIN catalog_similarity_candidates c ON c.group_id = g.group_id
)
SELECT
    p.group_id,
    p.seed_key,
    p.candidate_key,
    p.similarity,
    p.why_matched,
    p.key_a,
    p.key_b,
    i1.date_taken AS seed_date_taken,
    i2.date_taken AS candidate_date_taken,
    m1.stack_id AS seed_stack_id,
    m2.stack_id AS candidate_stack_id,
    CASE
        WHEN m1.stack_id IS NULL AND m2.stack_id IS NULL THEN 0
        WHEN m1.stack_id IS NULL OR m2.stack_id IS NULL THEN 1
        ELSE 2
    END AS stack_status_rank,
    ABS(
        COALESCE(strftime('%s', i1.date_taken), 0)
        - COALESCE(strftime('%s', i2.date_taken), 0)
    ) AS time_gap_seconds
FROM pairs p
INNER JOIN images i1 ON i1.key = p.seed_key
INNER JOIN images i2 ON i2.key = p.candidate_key
LEFT JOIN image_stack_members m1 ON m1.image_key = p.seed_key
LEFT JOIN image_stack_members m2 ON m2.image_key = p.candidate_key
LEFT JOIN catalog_similarity_rejections r
    ON r.key_a = p.key_a AND r.key_b = p.key_b
WHERE r.key_a IS NULL
  AND NOT (
      m1.stack_id IS NOT NULL
      AND m2.stack_id IS NOT NULL
      AND m1.stack_id = m2.stack_id
  )
  AND NOT {flagged_exists_sql("p.seed_key", "p.candidate_key")}
"""


def normalize_image_pair(key_a: str, key_b: str) -> tuple[str, str]:
    """Return lexicographically ordered pair so (a,b) and (b,a) collide."""
    a, b = str(key_a), str(key_b)
    if a == b:
        raise ValueError("image keys must differ")
    return (a, b) if a < b else (b, a)


def is_catalog_similarity_pair_rejected(
    db: sqlite3.Connection, key_a: str, key_b: str
) -> bool:
    a, b = normalize_image_pair(key_a, key_b)
    row = db.execute(
        """
        SELECT 1 AS o FROM catalog_similarity_rejections
        WHERE key_a = ? AND key_b = ?
        LIMIT 1
        """,
        (a, b),
    ).fetchone()
    return row is not None


def reject_catalog_similarity_pair(
    db: sqlite3.Connection, key_a: str, key_b: str
) -> None:
    """Persist a user rejection for a normalized image-key pair."""
    a, b = normalize_image_pair(key_a, key_b)
    db.execute(
        """
        INSERT OR IGNORE INTO catalog_similarity_rejections (key_a, key_b, rejected_at)
        VALUES (?, ?, ?)
        """,
        (a, b, datetime.now().isoformat()),
    )
    db.commit()


def stack_create_from_keys(db: sqlite3.Connection, member_keys: Sequence[str]) -> dict:
    """Create a new stack from *member_keys* (>= 2). Call inside :func:`library_write`."""
    keys = [str(k) for k in member_keys if k]
    unique_keys = sorted(set(keys))
    if len(unique_keys) < 2:
        raise StackMutationError("at least two distinct image keys required", status_code=400)
    rep = select_stack_representative_key_for_keys(db, unique_keys)
    if not rep or rep not in unique_keys:
        raise StackMutationError("stack representative selection failed", status_code=500)
    n = len(unique_keys)
    cur = db.execute(
        """
        INSERT INTO image_stacks (representative_key, stack_size, user_modified)
        VALUES (?, ?, 1)
        """,
        (rep, n),
    )
    stack_id = int(cur.lastrowid)
    for mkey in unique_keys:
        db.execute(
            "INSERT INTO image_stack_members (stack_id, image_key) VALUES (?, ?)",
            (stack_id, mkey),
        )
    meta = stack_metadata_for_api(db, stack_id)
    assert meta is not None
    return {"stack": meta}


def stack_add_member(db: sqlite3.Connection, stack_id: int, image_key: str) -> dict:
    """Add *image_key* to an existing stack. Call inside :func:`library_write`."""
    stack_row = db.execute(
        "SELECT stack_id FROM image_stacks WHERE stack_id = ?",
        (stack_id,),
    ).fetchone()
    if not stack_row:
        raise StackMutationError("stack not found", status_code=404)

    existing = db.execute(
        "SELECT stack_id FROM image_stack_members WHERE image_key = ? LIMIT 1",
        (image_key,),
    ).fetchone()
    if existing:
        sid = int(existing["stack_id"])
        if sid == stack_id:
            meta = stack_metadata_for_api(db, stack_id)
            assert meta is not None
            return {"stack": meta}
        raise StackMutationError("image_key already belongs to another stack", status_code=400)

    db.execute(
        "INSERT INTO image_stack_members (stack_id, image_key) VALUES (?, ?)",
        (stack_id, image_key),
    )
    member_rows = db.execute(
        "SELECT image_key FROM image_stack_members WHERE stack_id = ?",
        (stack_id,),
    ).fetchall()
    keys = [str(r["image_key"]) for r in member_rows]
    n = len(keys)
    db.execute(
        """
        UPDATE image_stacks
        SET stack_size = ?, user_modified = 1
        WHERE stack_id = ?
        """,
        (n, stack_id),
    )
    meta = stack_metadata_for_api(db, stack_id)
    assert meta is not None
    return {"stack": meta}


def stack_accept_suggestion_pair(
    db: sqlite3.Connection, key_a: str, key_b: str
) -> dict:
    """Create, extend, or merge stacks so *key_a* and *key_b* share one stack.

    Call inside :func:`library_write`.
    """
    a, b = str(key_a), str(key_b)
    if a == b:
        raise StackMutationError("image keys must differ", status_code=400)

    sid_a = stack_id_for_image_key(db, a)
    sid_b = stack_id_for_image_key(db, b)

    if sid_a is not None and sid_b is not None:
        if sid_a == sid_b:
            meta = stack_metadata_for_api(db, sid_a)
            assert meta is not None
            return {"stack": meta}
        return stack_merge_into(db, sid_a, sid_b)
    if sid_a is not None:
        return stack_add_member(db, sid_a, b)
    if sid_b is not None:
        return stack_add_member(db, sid_b, a)
    return stack_create_from_keys(db, [a, b])


def count_pending_stack_suggestions(db: sqlite3.Connection) -> int:
    """Pending stack-to-confirm pairs after rejection, flagged-frame, and stack filters."""
    row = db.execute(
        f"SELECT COUNT(*) AS c FROM ({_PENDING_PAIRS_SQL}) pending",
    ).fetchone()
    return int(row["c"]) if row else 0


def list_pending_stack_suggestions(
    db: sqlite3.Connection, *, limit: int, offset: int
) -> tuple[list[dict], int]:
    """Page of pending pairs ranked by stack status then time proximity."""
    total = count_pending_stack_suggestions(db)
    rows = db.execute(
        f"""
        SELECT *
        FROM ({_PENDING_PAIRS_SQL}) pending
        ORDER BY stack_status_rank ASC, time_gap_seconds ASC, group_id DESC
        LIMIT ? OFFSET ?
        """,
        (int(limit), int(offset)),
    ).fetchall()
    return [dict(r) for r in rows], total
