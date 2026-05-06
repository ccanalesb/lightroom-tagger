import contextlib
import hashlib
import json
import os
import re
import shutil
import sqlite3
import threading
import time
from collections.abc import Collection, Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path


class StackMutationError(ValueError):
    """Invalid stack edit; ``status_code`` is intended for HTTP error mapping."""

    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


from .catalog import library_write
from .db_init import _deserialize_row, _serialize_json


def build_description_search_document(summary: str, subjects_json_or_obj: object) -> str:
    """Build normalized full-text for summary + subjects (D-06)."""
    part = re.sub(r"\s+", " ", (summary or "").strip())
    if isinstance(subjects_json_or_obj, str):
        try:
            subj = json.loads(subjects_json_or_obj)
        except (json.JSONDecodeError, TypeError):
            subj = []
    elif isinstance(subjects_json_or_obj, list):
        subj = subjects_json_or_obj
    else:
        subj = []
    joined = " ".join(s for s in subj if isinstance(s, str))
    if not joined:
        return part
    if not part:
        return joined
    return f"{part} {joined}"


def build_description_fts_query(raw: str | None) -> tuple[str | None, str | None]:
    """Build an FTS5 ``MATCH`` string (AND-joined tokens) for ``description_search`` (NLS-02, D-11–D-13).

    Returns ``(match_str, err)`` where *match_str* is suitable as the sole bound parameter to
    ``... MATCH ?``, or ``None`` when no FTS filter should be applied. *err* is ``None`` unless
    the caller should return HTTP 400 with body ``err`` (short-query rule, D-12).

    Tokenization: maximal ASCII alphanumeric runs (``[A-Za-z0-9]+`` on the stripped input) so
    punctuation and SQL/FTS metacharacters never appear in the match string. Tokens shorter
    than 2 characters are dropped. If no tokens remain, no FTS filter applies (D-13).
    """
    if raw is None:
        return (None, None)
    s = raw.strip()
    if not s:
        return (None, None)
    if len(s) < 2:
        return (None, "description_search must be at least 2 characters")
    tokens = re.findall(r"[A-Za-z0-9]+", s)
    words = [t for t in tokens if len(t) >= 2]
    if not words:
        return (None, None)
    # Double-quote each term so FTS5 reserved tokens (e.g. OR, AND, NOT) are literals.
    quoted = ('"' + t.replace('"', '""') + '"' for t in words)
    return (" AND ".join(quoted), None)


def _coerce_has_repetition(value) -> int | None:
    if value is None:
        return None
    if value in (True, 1, "1", "true", "yes"):
        return 1
    if value in (False, 0, "0", "false", "no"):
        return 0
    return 0


def _visual_attr_json(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return _serialize_json(value)
    return None


def update_instagram_status(db: sqlite3.Connection, key: str, posted: bool = True,
                            post_date: str = None, url: str = None, index: int = 0) -> bool:
    """Update Instagram status for an image."""
    cursor = db.execute("""
        UPDATE images SET instagram_posted = ?, instagram_post_date = ?,
            instagram_url = ?, instagram_index = ?
        WHERE key = ?
    """, (int(posted), post_date, url, index, key))
    db.commit()
    return cursor.rowcount > 0


def search_by_instagram_posted(db: sqlite3.Connection, posted: bool = True) -> list[dict]:
    """Search images by Instagram posted status."""
    rows = db.execute(
        "SELECT * FROM images WHERE instagram_posted = ?", (int(posted),)
    ).fetchall()
    return [_deserialize_row(r) for r in rows]



def list_clip_embedded_catalog_keys_newest_first(db: sqlite3.Connection) -> list[str]:
    """Catalog keys with CLIP embeddings, ordered newest-to-oldest for batch jobs."""
    rows = db.execute(
        """
        SELECT e.image_key AS key, i.date_taken AS date_taken
        FROM image_clip_embeddings e
        INNER JOIN images i ON i.key = e.image_key
        ORDER BY i.date_taken DESC, i.key DESC
        """
    ).fetchall()
    return [str(r["key"]) for r in rows if r["key"]]


def clear_catalog_similarity_results(db: sqlite3.Connection) -> None:
    """Clear derived catalog similarity job output."""
    db.execute("DELETE FROM catalog_similarity_candidates")
    db.execute("DELETE FROM catalog_similarity_groups")
    db.commit()


def insert_catalog_similarity_group(
    db: sqlite3.Connection,
    *,
    seed_key: str,
    candidates: Sequence[dict],
    job_id: str | None = None,
) -> int:
    """Persist one catalog similarity group and its ranked candidate rows."""
    if not candidates:
        raise ValueError("candidates must not be empty")
    best_similarity = max(float(c.get("similarity") or 0.0) for c in candidates)
    cur = db.execute(
        """
        INSERT INTO catalog_similarity_groups
            (seed_key, candidate_count, best_similarity, job_id, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            seed_key,
            len(candidates),
            best_similarity,
            job_id,
            datetime.now().isoformat(),
        ),
    )
    group_id = int(cur.lastrowid)
    db.executemany(
        """
        INSERT INTO catalog_similarity_candidates
            (group_id, candidate_key, similarity, rank, why_matched)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (
                group_id,
                str(c["candidate_key"]),
                float(c["similarity"]),
                int(c.get("rank") or idx + 1),
                str(c.get("why_matched") or ""),
            )
            for idx, c in enumerate(candidates)
        ],
    )
    db.commit()
    return group_id


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


def catalog_has_instagram_match_conflict(
    db: sqlite3.Connection, catalog_key: str, insta_key: str
) -> bool:
    """True when *catalog_key* already has a library match to a different Instagram key."""
    row = db.execute(
        """
        SELECT 1 FROM matches
        WHERE catalog_key = ? AND insta_key IS NOT NULL AND insta_key != ?
        LIMIT 1
        """,
        (catalog_key, insta_key),
    ).fetchone()
    return row is not None


def apply_instagram_match_to_stack_members(
    db: sqlite3.Connection,
    *,
    insta_key: str,
    representative_key: str,
    template: dict,
    commit: bool = True,
) -> dict:
    """Persist matches for non-representative stack members from a rep-level template.

    The representative's match row(s) are stored by the caller. This function adds
    rows for other members, skipping members that already match a different
    ``insta_key`` (non-destructive).

    Returns:
        ``applied_count``, ``skipped_conflicts_count``, ``skipped_other_count``,
        and ``lightroom_catalog_keys`` (representative plus applied members; used
        for Lightroom keyword writes).
    """
    members = list_catalog_stack_member_keys(db, representative_key)
    applied = 0
    skipped_conflicts = 0
    skipped_other = 0
    lightroom_catalog_keys: list[str] = [representative_key]

    for member_key in members:
        if member_key == representative_key:
            continue
        if catalog_has_instagram_match_conflict(db, member_key, insta_key):
            skipped_conflicts += 1
            continue
        exists_row = db.execute(
            "SELECT 1 FROM images WHERE key = ? LIMIT 1",
            (member_key,),
        ).fetchone()
        if not exists_row:
            skipped_other += 1
            continue

        rec = {
            "catalog_key": member_key,
            "insta_key": insta_key,
            "phash_distance": template.get("phash_distance"),
            "phash_score": template.get("phash_score"),
            "desc_similarity": template.get("desc_similarity"),
            "vision_result": template.get("vision_result"),
            "vision_score": template.get("vision_score"),
            "total_score": template.get("total_score"),
            "model_used": template.get("model_used"),
            "rank": template.get("rank", 1),
            "vision_reasoning": template.get("vision_reasoning"),
        }
        store_match(db, rec, commit=False)
        applied += 1
        lightroom_catalog_keys.append(member_key)

    if commit:
        db.commit()

    return {
        "applied_count": applied,
        "skipped_conflicts_count": skipped_conflicts,
        "skipped_other_count": skipped_other,
        "lightroom_catalog_keys": lightroom_catalog_keys,
    }


def get_images_without_hash(db: sqlite3.Connection) -> list[dict]:
    """Get all images that don't have a computed hash yet."""
    rows = db.execute(
        "SELECT * FROM images WHERE image_hash IS NULL"
    ).fetchall()
    return [_deserialize_row(r) for r in rows]


def update_image_hash(db: sqlite3.Connection, key: str, image_hash: str) -> bool:
    """Update the image hash for an image."""
    cursor = db.execute(
        "UPDATE images SET image_hash = ? WHERE key = ?", (image_hash, key)
    )
    db.commit()
    return cursor.rowcount > 0


def batch_update_hashes(db: sqlite3.Connection, updates: list[dict]) -> int:
    """Batch update image hashes."""
    count = 0
    for update in updates:
        key = update.get('key')
        image_hash = update.get('image_hash')
        if key and image_hash and update_image_hash(db, key, image_hash):
            count += 1
    return count



# ---------------------------------------------------------------------------
# Instagram dump media
# ---------------------------------------------------------------------------

def init_instagram_dump_table(db: sqlite3.Connection):
    """No-op: table is created in init_database."""
    pass


def store_instagram_dump_media(db: sqlite3.Connection, record: dict) -> str:
    """Store Instagram dump media record. Idempotent by media_key."""
    media_key = record.get('media_key')
    if not media_key:
        raise ValueError("media_key is required")

    record.setdefault('processed', False)
    record.setdefault('matched_catalog_key', None)
    record.setdefault('vision_result', None)
    record.setdefault('vision_score', None)
    record.setdefault('processed_at', None)
    record.setdefault('added_at', datetime.now().isoformat())
    record.setdefault('exif_data', None)
    record.setdefault('post_url', None)
    record.setdefault('image_hash', None)

    exif_data = _serialize_json(record.get('exif_data'))

    db.execute("""
        INSERT INTO instagram_dump_media
            (media_key, file_path, filename, date_folder, caption, created_at,
             exif_data, post_url, image_hash, processed, matched_catalog_key,
             vision_result, vision_score, processed_at, added_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(media_key) DO UPDATE SET
            file_path=COALESCE(excluded.file_path, instagram_dump_media.file_path),
            filename=COALESCE(excluded.filename, instagram_dump_media.filename),
            date_folder=COALESCE(excluded.date_folder, instagram_dump_media.date_folder),
            caption=COALESCE(excluded.caption, instagram_dump_media.caption),
            exif_data=COALESCE(excluded.exif_data, instagram_dump_media.exif_data),
            post_url=COALESCE(excluded.post_url, instagram_dump_media.post_url),
            image_hash=COALESCE(excluded.image_hash, instagram_dump_media.image_hash)
    """, (
        media_key, record.get('file_path'), record.get('filename'),
        record.get('date_folder'), record.get('caption'),
        record.get('created_at'), exif_data, record.get('post_url'),
        record.get('image_hash'), int(bool(record.get('processed', False))),
        record.get('matched_catalog_key'), record.get('vision_result'),
        record.get('vision_score'), record.get('processed_at'),
        record.get('added_at'),
    ))
    db.commit()
    return media_key


def get_instagram_dump_media(db: sqlite3.Connection, media_key: str) -> dict | None:
    """Get Instagram dump media by key."""
    row = db.execute(
        "SELECT * FROM instagram_dump_media WHERE media_key = ?", (media_key,)
    ).fetchone()
    return _deserialize_row(row) if row else None


def get_dump_media_by_hash(db: sqlite3.Connection, image_hash: str) -> list:
    """Get Instagram dump media by image hash."""
    rows = db.execute(
        "SELECT * FROM instagram_dump_media WHERE image_hash = ?", (image_hash,)
    ).fetchall()
    return [_deserialize_row(r) for r in rows]


_VIDEO_EXTENSIONS_CLAUSE = (
    "LOWER(file_path) NOT LIKE '%.mp4' AND "
    "LOWER(file_path) NOT LIKE '%.mov' AND "
    "LOWER(file_path) NOT LIKE '%.avi' AND "
    "LOWER(file_path) NOT LIKE '%.mkv'"
)

# Same exclusions as :data:`_VIDEO_EXTENSIONS_CLAUSE` for ``instagram_dump_media``
# queries that alias the table as ``m``.
_INSTAGRAM_DUMP_CLIP_VIDEO_GUARD = _VIDEO_EXTENSIONS_CLAUSE.replace(
    "file_path", "m.file_path"
)


def get_unprocessed_dump_media(db: sqlite3.Connection, limit: int = None,
                                run_start: str = None,
                                include_processed: bool = False) -> list:
    """Get Instagram dump media for matching.

    Args:
        run_start: ISO timestamp; skip images already attempted in this run
                   (last_attempted_at >= run_start).
        include_processed: If True, also return already-processed rows.
    """
    clauses: list[str] = [_VIDEO_EXTENSIONS_CLAUSE]
    params: list = []
    if not include_processed:
        clauses.append("processed = 0")
        clauses.append(
            "media_key NOT IN "
            "(SELECT insta_key FROM matches WHERE validated_at IS NOT NULL)"
        )
    if run_start:
        clauses.append("(last_attempted_at IS NULL OR last_attempted_at < ?)")
        params.append(run_start)
    where = " AND ".join(clauses) if clauses else "1=1"
    sql = f"SELECT * FROM instagram_dump_media WHERE {where} ORDER BY date_folder DESC, media_key DESC"
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    rows = db.execute(sql, params).fetchall()
    return [_deserialize_row(r) for r in rows]


def get_instagram_by_date_filter(db: sqlite3.Connection, month: str = None,
                                  year: str = None, last_months: int = None,
                                  run_start: str = None,
                                  include_processed: bool = False) -> list:
    """Get Instagram dump media filtered by date.

    Args:
        run_start: ISO timestamp; skip images already attempted in this run.
        include_processed: If True, also return already-processed rows.
    """
    clauses: list[str] = [_VIDEO_EXTENSIONS_CLAUSE]
    params: list = []
    if not include_processed:
        clauses.append("processed = 0")
        clauses.append(
            "media_key NOT IN "
            "(SELECT insta_key FROM matches WHERE validated_at IS NOT NULL)"
        )
    if run_start:
        clauses.append("(last_attempted_at IS NULL OR last_attempted_at < ?)")
        params.append(run_start)

    if month:
        clauses.append("date_folder = ?")
        params.append(month)
    elif year:
        clauses.append("date_folder LIKE ?")
        params.append(f'{year}%')
    elif last_months:
        from_date = (datetime.now() - timedelta(days=last_months * 30)).strftime('%Y%m')
        clauses.append("date_folder >= ?")
        params.append(from_date)

    where = " AND ".join(clauses) if clauses else "1=1"
    rows = db.execute(f"SELECT * FROM instagram_dump_media WHERE {where} ORDER BY date_folder DESC, media_key DESC", params).fetchall()
    return [_deserialize_row(r) for r in rows]


def mark_dump_media_processed(db: sqlite3.Connection, media_key: str,
                               matched_catalog_key: str = None,
                               vision_result: str = None,
                               vision_score: float = None) -> bool:
    """Mark Instagram dump media as processed with match results."""
    cursor = db.execute("""
        UPDATE instagram_dump_media SET
            processed = 1, matched_catalog_key = ?, vision_result = ?,
            vision_score = ?, processed_at = ?
        WHERE media_key = ?
    """, (matched_catalog_key, vision_result, vision_score,
          datetime.now().isoformat(), media_key))
    db.commit()
    return cursor.rowcount > 0


def mark_dump_media_attempted(db: sqlite3.Connection, media_key: str,
                               vision_result: str = None,
                               vision_score: float = None) -> bool:
    """Record an attempt without marking as permanently processed.

    Stores the best vision result for debugging and sets last_attempted_at
    so the current run can skip it. Does NOT set processed=1.
    """
    cursor = db.execute("""
        UPDATE instagram_dump_media SET
            last_attempted_at = ?,
            vision_result = COALESCE(?, vision_result),
            vision_score = COALESCE(?, vision_score)
        WHERE media_key = ?
    """, (datetime.now().isoformat(), vision_result, vision_score, media_key))
    db.commit()
    return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# Instagram images (legacy crawled)
# ---------------------------------------------------------------------------

def init_instagram_table(db: sqlite3.Connection):
    """No-op: table is created in init_database."""
    pass


def _instagram_row_key(local_path: str | None, post_url: str, filename: str) -> str:
    """Stable primary key for instagram_images (new rows)."""
    basis = (local_path or "").strip() or f"{post_url}|{filename}"
    return "insta_" + hashlib.sha256(basis.encode("utf-8", errors="replace")).hexdigest()


def store_instagram_image(db: sqlite3.Connection, record: dict) -> str:
    """Store Instagram image with analysis. Idempotent by local_path."""
    local_path = record.get('local_path')
    post_url = record.get('post_url', '')
    filename = record.get('filename', '')
    key = None
    if local_path:
        row = db.execute(
            "SELECT key FROM instagram_images WHERE local_path = ? LIMIT 1",
            (local_path,),
        ).fetchone()
        if row:
            key = row["key"]
    if key is None:
        key = _instagram_row_key(local_path, post_url, filename)
    record['key'] = key
    record['crawled_at'] = datetime.now().isoformat()

    exif = _serialize_json(record.get('exif'))

    db.execute("""
        INSERT INTO instagram_images (key, local_path, post_url, filename, description,
            image_hash, instagram_folder, crawled_at, phash, exif)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            local_path=excluded.local_path, post_url=excluded.post_url,
            filename=excluded.filename, description=excluded.description,
            image_hash=excluded.image_hash, instagram_folder=excluded.instagram_folder,
            crawled_at=excluded.crawled_at,
            phash=COALESCE(excluded.phash, instagram_images.phash),
            exif=COALESCE(excluded.exif, instagram_images.exif)
    """, (
        key, local_path, post_url, filename, record.get('description'),
        record.get('image_hash'), record.get('instagram_folder'),
        record['crawled_at'], record.get('phash'), exif,
    ))
    db.commit()
    return key


def get_instagram_images_needing_analysis(db: sqlite3.Connection) -> list:
    """Get Instagram images without phash."""
    rows = db.execute(
        "SELECT * FROM instagram_images WHERE phash IS NULL"
    ).fetchall()
    return [_deserialize_row(r) for r in rows]


# ---------------------------------------------------------------------------
# Matches
# ---------------------------------------------------------------------------

def init_matches_table(db: sqlite3.Connection):
    """No-op: table is created in init_database."""
    pass


def delete_matches_for_insta_key(db: sqlite3.Connection, insta_key: str,
                                  commit: bool = True) -> None:
    """Remove all match rows for an Instagram key (e.g. before replacing candidate set)."""
    db.execute("DELETE FROM matches WHERE insta_key = ?", (insta_key,))
    if commit:
        db.commit()


def store_match(db: sqlite3.Connection, record: dict, commit: bool = True) -> str:
    """Store match between catalog and Instagram image."""
    catalog_key = record.get('catalog_key')
    insta_key = record.get('insta_key')
    record['matched_at'] = datetime.now().isoformat()

    db.execute("""
        INSERT INTO matches (catalog_key, insta_key, phash_distance, phash_score,
            desc_similarity, vision_result, vision_score, total_score, matched_at,
            model_used, rank, vision_reasoning)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(catalog_key, insta_key) DO UPDATE SET
            phash_distance=excluded.phash_distance, phash_score=excluded.phash_score,
            desc_similarity=excluded.desc_similarity, vision_result=excluded.vision_result,
            vision_score=excluded.vision_score, total_score=excluded.total_score,
            matched_at=excluded.matched_at, model_used=excluded.model_used,
            rank=excluded.rank, vision_reasoning=excluded.vision_reasoning
    """, (
        catalog_key, insta_key, record.get('phash_distance'),
        record.get('phash_score'), record.get('desc_similarity'),
        record.get('vision_result'), record.get('vision_score'),
        record.get('total_score'), record['matched_at'],
        record.get('model_used'), record.get('rank', 1),
        record.get('vision_reasoning'),
    ))
    if commit:
        db.commit()
    return f"{catalog_key} <-> {insta_key}"


def _backfill_instagram_created_at_from_catalog(
    db: sqlite3.Connection, catalog_key: str, insta_key: str
) -> None:
    """If catalog has date_taken and Instagram side has no created_at, copy it (D-12)."""
    cat = db.execute(
        "SELECT date_taken FROM images WHERE key = ?", (catalog_key,)
    ).fetchone()
    if not cat:
        return
    raw_dt = cat.get("date_taken")
    if raw_dt is None or (isinstance(raw_dt, str) and not raw_dt.strip()):
        return
    date_val = raw_dt.strip() if isinstance(raw_dt, str) else str(raw_dt)

    insta_img = db.execute(
        "SELECT key, created_at FROM instagram_images WHERE key = ? LIMIT 1",
        (insta_key,),
    ).fetchone()
    if insta_img is not None:
        ca = insta_img.get("created_at")
        if ca is None or (isinstance(ca, str) and not str(ca).strip()):
            db.execute(
                "UPDATE instagram_images SET created_at = ? WHERE key = ?",
                (date_val, insta_key),
            )
        return

    dump = db.execute(
        "SELECT media_key, created_at FROM instagram_dump_media WHERE media_key = ? LIMIT 1",
        (insta_key,),
    ).fetchone()
    if dump is None:
        return
    ca = dump.get("created_at")
    if ca is None or (isinstance(ca, str) and not str(ca).strip()):
        db.execute(
            "UPDATE instagram_dump_media SET created_at = ? WHERE media_key = ?",
            (date_val, insta_key),
        )


def validate_match(db: sqlite3.Connection, catalog_key: str, insta_key: str) -> bool:
    """Stamp a match as human-validated.

    Also mirrors the pairing onto ``instagram_dump_media.matched_catalog_key``
    so both matching pipelines (bulk script + on-demand) share one
    "matched" signal for the Instagram tab badge, and marks the catalog
    image as posted to Instagram.
    """
    with db:
        cursor = db.execute(
            "UPDATE matches SET validated_at = ? WHERE catalog_key = ? AND insta_key = ?",
            (datetime.now().isoformat(), catalog_key, insta_key),
        )
        if cursor.rowcount == 0:
            return False
        db.execute(
            "UPDATE instagram_dump_media SET matched_catalog_key = ? "
            "WHERE media_key = ?",
            (catalog_key, insta_key),
        )
        db.execute(
            "UPDATE images SET instagram_posted = 1 WHERE key = ?",
            (catalog_key,),
        )
        _backfill_instagram_created_at_from_catalog(db, catalog_key, insta_key)
    return True


def unvalidate_match(db: sqlite3.Connection, catalog_key: str, insta_key: str) -> bool:
    """Remove human validation (undo validate, not reject).

    Clears ``instagram_dump_media.matched_catalog_key`` when no other
    validated match remains for the same insta_key, so the IG tab
    "matched" badge reflects the current validation state.
    """
    with db:
        cursor = db.execute(
            "UPDATE matches SET validated_at = NULL WHERE catalog_key = ? AND insta_key = ?",
            (catalog_key, insta_key),
        )
        if cursor.rowcount == 0:
            return False
        # Match the most-recent validated pairing so unvalidate → next
        # validation → unvalidate is deterministic. Mirrors the selection
        # used by `_backfill_matched_catalog_key_from_validated_matches`.
        remaining = db.execute(
            "SELECT catalog_key FROM matches "
            "WHERE insta_key = ? AND validated_at IS NOT NULL "
            "ORDER BY validated_at DESC LIMIT 1",
            (insta_key,),
        ).fetchone()
        if remaining:
            db.execute(
                "UPDATE instagram_dump_media SET matched_catalog_key = ? "
                "WHERE media_key = ?",
                (remaining['catalog_key'], insta_key),
            )
        else:
            db.execute(
                "UPDATE instagram_dump_media SET matched_catalog_key = NULL "
                "WHERE media_key = ?",
                (insta_key,),
            )
        # Clear instagram_posted if no validated match still references this catalog image
        still_validated = db.execute(
            "SELECT 1 FROM matches WHERE catalog_key = ? AND validated_at IS NOT NULL LIMIT 1",
            (catalog_key,),
        ).fetchone()
        if not still_validated:
            db.execute(
                "UPDATE images SET instagram_posted = 0 WHERE key = ?",
                (catalog_key,),
            )
    return True


def reject_match(db: sqlite3.Connection, catalog_key: str, insta_key: str) -> bool:
    """Delete match row and add pair to rejected blocklist.

    Also resets the instagram image's processed flag so it can match other
    catalog candidates in future runs.
    """
    db.execute(
        "DELETE FROM matches WHERE catalog_key = ? AND insta_key = ?",
        (catalog_key, insta_key),
    )
    db.execute(
        "INSERT OR REPLACE INTO rejected_matches (catalog_key, insta_key, rejected_at) "
        "VALUES (?, ?, ?)",
        (catalog_key, insta_key, datetime.now().isoformat()),
    )
    db.execute(
        "UPDATE instagram_dump_media SET processed = 0, matched_catalog_key = NULL "
        "WHERE media_key = ?",
        (insta_key,),
    )
    # Reset instagram_posted only if no validated match still references this catalog image
    still_validated = db.execute(
        "SELECT 1 FROM matches WHERE catalog_key = ? AND validated_at IS NOT NULL LIMIT 1",
        (catalog_key,),
    ).fetchone()
    if not still_validated:
        db.execute(
            "UPDATE images SET instagram_posted = 0 WHERE key = ?",
            (catalog_key,),
        )
    db.commit()
    return True


def get_rejected_pairs(db: sqlite3.Connection) -> set[tuple[str, str]]:
    """Return set of (catalog_key, insta_key) pairs in the blocklist."""
    rows = db.execute("SELECT catalog_key, insta_key FROM rejected_matches").fetchall()
    return {(r['catalog_key'], r['insta_key']) for r in rows}


# ---------------------------------------------------------------------------
# Vision cache
# ---------------------------------------------------------------------------

VISION_CACHE_OVERSIZED_SENTINEL = "__oversized__"


def init_vision_cache_table(db: sqlite3.Connection):
    """No-op: table is created in init_database."""
    pass


def init_vision_comparisons_table(db: sqlite3.Connection):
    """No-op: table is created in init_database."""
    pass


def get_vision_cached_image(db: sqlite3.Connection, catalog_key: str) -> dict | None:
    """Get cached compressed image by catalog key."""
    row = db.execute(
        "SELECT * FROM vision_cache WHERE key = ?", (catalog_key,)
    ).fetchone()
    return dict(row) if row else None


def store_vision_cached_image(db: sqlite3.Connection, catalog_key: str,
                               compressed_path: str, phash: str | None,
                               original_mtime: float) -> bool:
    """Store compressed image info in vision cache.

    Routed through :func:`library_write` because this runs on the describe
    worker hot path and previously raced with other workers' commits.
    """
    with library_write(db):
        db.execute("""
            INSERT INTO vision_cache (key, compressed_path, phash, compressed_at, original_mtime)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                compressed_path=excluded.compressed_path, phash=excluded.phash,
                compressed_at=excluded.compressed_at, original_mtime=excluded.original_mtime
        """, (catalog_key, compressed_path, phash, datetime.now().isoformat(), original_mtime))
    return True


def is_vision_cache_valid(db: sqlite3.Connection, catalog_key: str,
                           original_path: str) -> bool:
    """Check if cached image is still valid (mtime unchanged)."""
    cached = get_vision_cached_image(db, catalog_key)
    if not cached:
        return False
    comp = cached.get('compressed_path') or ''

    from lightroom_tagger.core.analyzer import RAW_EXTENSIONS, VIDEO_EXTENSIONS

    ext = os.path.splitext(original_path)[1].lower()
    if ext in VIDEO_EXTENSIONS:
        return False

    if ext in RAW_EXTENSIONS:
        if comp == original_path:
            return False
        if comp == VISION_CACHE_OVERSIZED_SENTINEL:
            return False

    if comp == VISION_CACHE_OVERSIZED_SENTINEL:
        try:
            current_mtime = os.path.getmtime(original_path)
            return cached.get('original_mtime') == current_mtime
        except OSError:
            return False

    if not comp or not os.path.exists(comp):
        return False
    try:
        current_mtime = os.path.getmtime(original_path)
        return cached.get('original_mtime') == current_mtime
    except OSError:
        return False


def get_cache_stats(db: sqlite3.Connection) -> dict:
    """Get vision cache statistics."""
    total = db.execute("SELECT COUNT(*) as cnt FROM images").fetchone()['cnt']
    cached = db.execute("SELECT COUNT(*) as cnt FROM vision_cache").fetchone()['cnt']

    cache_size_bytes = 0
    rows = db.execute("SELECT compressed_path FROM vision_cache").fetchall()
    for row in rows:
        path = row.get('compressed_path', '')
        if path and os.path.exists(path):
            cache_size_bytes += os.path.getsize(path)

    return {
        'total': total,
        'cached': cached,
        'missing': total - cached,
        'cache_size_mb': cache_size_bytes / (1024 * 1024),
    }


# ---------------------------------------------------------------------------
# Vision comparisons
# ---------------------------------------------------------------------------

def get_vision_comparison(db: sqlite3.Connection, catalog_key: str,
                           insta_key: str) -> dict | None:
    """Get cached vision comparison result."""
    row = db.execute(
        "SELECT * FROM vision_comparisons WHERE catalog_key = ? AND insta_key = ?",
        (catalog_key, insta_key)
    ).fetchone()
    return dict(row) if row else None


def store_vision_comparison(db: sqlite3.Connection, catalog_key: str, insta_key: str,
                            result: str, vision_score: float, model_used: str) -> bool:
    """Store vision comparison result in cache. Never expires."""
    db.execute("""
        INSERT INTO vision_comparisons (catalog_key, insta_key, result, vision_score,
            compared_at, model_used)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(catalog_key, insta_key) DO UPDATE SET
            result=excluded.result, vision_score=excluded.vision_score,
            compared_at=excluded.compared_at, model_used=excluded.model_used
    """, (catalog_key, insta_key, result, vision_score,
          datetime.now().isoformat(), model_used))
    db.commit()
    return True


# ---------------------------------------------------------------------------
# Image descriptions
# ---------------------------------------------------------------------------

def init_image_descriptions_table(db: sqlite3.Connection):
    """No-op: table is created in init_database."""
    pass


def store_image_description(db: sqlite3.Connection, record: dict) -> str:
    """Store image description. Idempotent by image_key.

    Routed through :func:`library_write` because this runs on the describe
    worker hot path.
    """
    image_key = record.get('image_key')
    if not image_key:
        raise ValueError("image_key is required")

    record['described_at'] = datetime.now().isoformat()
    image_type = record.get("image_type", "")
    dominant_colors = _visual_attr_json(record.get("dominant_colors"))
    mood_tags = _visual_attr_json(record.get("mood_tags"))
    has_repetition = _coerce_has_repetition(record.get("has_repetition"))
    if image_type == "catalog":
        description_search_document = build_description_search_document(
            record.get("summary", ""),
            record.get("subjects", []),
        )
    else:
        description_search_document = None

    with library_write(db):
        db.execute("""
            INSERT INTO image_descriptions
                (image_key, image_type, summary, composition, perspectives,
                 technical, subjects, best_perspective, model_used, described_at,
                 dominant_colors, mood_tags, has_repetition, description_search_document)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(image_key) DO UPDATE SET
                image_type=excluded.image_type, summary=excluded.summary,
                composition=excluded.composition, perspectives=excluded.perspectives,
                technical=excluded.technical, subjects=excluded.subjects,
                best_perspective=excluded.best_perspective, model_used=excluded.model_used,
                described_at=excluded.described_at,
                dominant_colors=excluded.dominant_colors, mood_tags=excluded.mood_tags,
                has_repetition=excluded.has_repetition,
                description_search_document=excluded.description_search_document
        """, (
            image_key, image_type,
            record.get('summary', ''),
            _serialize_json(record.get('composition', {})),
            _serialize_json(record.get('perspectives', {})),
            _serialize_json(record.get('technical', {})),
            _serialize_json(record.get('subjects', [])),
            record.get('best_perspective', ''),
            record.get('model_used', ''),
            record['described_at'],
            dominant_colors, mood_tags, has_repetition, description_search_document,
        ))
        row = db.execute(
            "SELECT rowid FROM image_descriptions WHERE image_key = ?",
            (image_key,),
        ).fetchone()
        if row is not None:
            rowid = row["rowid"]
            db.execute("DELETE FROM image_descriptions_fts WHERE rowid = ?", (rowid,))
            doc = description_search_document
            if image_type == "catalog" and doc and str(doc).strip():
                db.execute(
                    "INSERT INTO image_descriptions_fts(rowid, description_search_document) "
                    "VALUES(?, ?)",
                    (rowid, doc),
                )
    return image_key


def get_image_description(db: sqlite3.Connection, image_key: str) -> dict | None:
    """Get description by image key."""
    row = db.execute(
        "SELECT * FROM image_descriptions WHERE image_key = ?", (image_key,)
    ).fetchone()
    if not row:
        return None
    row = dict(row)
    for col in (
        'composition',
        'perspectives',
        'technical',
        'subjects',
        'dominant_colors',
        'mood_tags',
    ):
        val = row.get(col)
        if isinstance(val, str):
            try:
                row[col] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                pass
    return row


def get_undescribed_catalog_images(
    db: sqlite3.Connection, months: int | None = None, min_rating: int | None = None
) -> list[dict]:
    """Get catalog images that don't have descriptions yet."""
    sql = """
        SELECT i.* FROM images i
        LEFT JOIN image_descriptions d
            ON i.key = d.image_key AND d.image_type = 'catalog'
        WHERE d.image_key IS NULL
        AND LOWER(i.filepath) NOT LIKE '%.mov'
        AND LOWER(i.filepath) NOT LIKE '%.mp4'
        AND LOWER(i.filepath) NOT LIKE '%.avi'
        AND LOWER(i.filepath) NOT LIKE '%.mkv'
        AND LOWER(i.filepath) NOT LIKE '%.wmv'
        AND LOWER(i.filepath) NOT LIKE '%.m4v'
        AND LOWER(i.filepath) NOT LIKE '%.3gp'
        AND LOWER(i.filepath) NOT LIKE '%.webm'
        AND LOWER(i.filepath) NOT LIKE '%.mts'
        AND LOWER(i.filepath) NOT LIKE '%.m2ts'
    """
    params: list = []
    if months:
        sql += " AND i.date_taken >= date('now', ?)"
        params.append(f'-{months} months')
    if min_rating is not None:
        sql += " AND i.rating >= ?"
        params.append(min_rating)
    rows = db.execute(sql, params).fetchall()
    return [_deserialize_row(r) for r in rows]


def get_undescribed_instagram_images(db: sqlite3.Connection, months: int = None) -> list[dict]:
    """Get Instagram dump media that don't have descriptions yet."""
    sql = """
        SELECT m.* FROM instagram_dump_media m
        LEFT JOIN image_descriptions d
            ON m.media_key = d.image_key AND d.image_type = 'instagram'
        WHERE d.image_key IS NULL
        AND LOWER(m.file_path) NOT LIKE '%.mov'
        AND LOWER(m.file_path) NOT LIKE '%.mp4'
        AND LOWER(m.file_path) NOT LIKE '%.avi'
        AND LOWER(m.file_path) NOT LIKE '%.mkv'
        AND LOWER(m.file_path) NOT LIKE '%.wmv'
        AND LOWER(m.file_path) NOT LIKE '%.m4v'
        AND LOWER(m.file_path) NOT LIKE '%.3gp'
        AND LOWER(m.file_path) NOT LIKE '%.webm'
        AND LOWER(m.file_path) NOT LIKE '%.mts'
        AND LOWER(m.file_path) NOT LIKE '%.m2ts'
    """
    params: list = []
    if months:
        sql += " AND m.created_at >= date('now', ?)"
        params.append(f'-{months} months')
    rows = db.execute(sql, params).fetchall()
    return [_deserialize_row(r) for r in rows]


def _embeddable_catalog_description_sql(alias: str = "d") -> str:
    """SQL fragment: catalog row has FTS-aligned text (persisted doc or non-empty summary)."""
    a = alias
    return (
        f"(({a}.description_search_document IS NOT NULL "
        f"AND TRIM({a}.description_search_document) != '') "
        f"OR (TRIM(COALESCE({a}.summary, '')) != ''))"
    )


def count_catalog_images_missing_text_embedding(conn: sqlite3.Connection) -> int:
    """Count catalog images with embeddable description text but no vec0 row yet."""
    frag = _embeddable_catalog_description_sql("d")
    row = conn.execute(
        f"""
        SELECT COUNT(*) AS cnt
        FROM images i
        INNER JOIN image_descriptions d ON d.image_key = i.key AND d.image_type = 'catalog'
        WHERE {frag}
          AND NOT EXISTS (
              SELECT 1 FROM image_text_embeddings e WHERE e.image_key = d.image_key
          )
        """
    ).fetchone()
    return int(row["cnt"] if row else 0)


def _sort_catalog_key_rows_newest_first(rows: list[sqlite3.Row]) -> list[str]:
    """Return keys sorted by ``date_taken`` desc, then key desc."""
    keyed: list[tuple[str, str]] = []
    for row in rows:
        key = str(row["key"])
        date_taken = str(row["date_taken"] or "")
        keyed.append((key, date_taken))
    keyed.sort(key=lambda item: (item[1], item[0]), reverse=True)
    return [key for key, _ in keyed]


def _list_catalog_keys_text_embed_sql_params(
    *,
    months: int | None,
    year: str | None,
    min_rating: int | None,
) -> tuple[str, tuple]:
    frag = _embeddable_catalog_description_sql("d")
    parts: list[str] = [frag]
    params: list = []
    if months is not None:
        parts.append("i.date_taken >= date('now', ?)")
        params.append(f"-{months} months")
    if year is not None:
        parts.append("strftime('%Y', i.date_taken) = ?")
        params.append(year)
    if min_rating is not None:
        parts.append("i.rating >= ?")
        params.append(min_rating)
    where = " AND ".join(parts)
    sql = f"""
        SELECT i.key AS key, i.date_taken AS date_taken
        FROM images i
        INNER JOIN image_descriptions d ON d.image_key = i.key AND d.image_type = 'catalog'
        WHERE {where}
        ORDER BY i.key ASC
    """
    return sql, tuple(params)


def list_catalog_keys_needing_text_embedding(
    conn: sqlite3.Connection,
    *,
    months: int | None,
    year: str | None,
    min_rating: int | None,
) -> list[tuple[str, str]]:
    """Catalog keys with embeddable text in the date/rating window, excluding vec0 rows."""
    sql, params = _list_catalog_keys_text_embed_sql_params(
        months=months,
        year=year,
        min_rating=min_rating,
    )
    rows = conn.execute(sql, params).fetchall()
    embedded_keys = {
        str(r["image_key"])
        for r in conn.execute("SELECT image_key FROM image_text_embeddings").fetchall()
    }
    filtered_rows = [r for r in rows if str(r["key"]) not in embedded_keys]
    ordered_keys = _sort_catalog_key_rows_newest_first(filtered_rows)
    return [(key, "catalog") for key in ordered_keys]


def list_catalog_keys_for_text_embed_force(
    conn: sqlite3.Connection,
    *,
    months: int | None,
    year: str | None,
    min_rating: int | None,
) -> list[tuple[str, str]]:
    """All embeddable catalog keys in the window, including keys already in ``image_text_embeddings``."""
    sql, params = _list_catalog_keys_text_embed_sql_params(
        months=months,
        year=year,
        min_rating=min_rating,
    )
    rows = conn.execute(sql, params).fetchall()
    ordered_keys = _sort_catalog_key_rows_newest_first(rows)
    return [(key, "catalog") for key in ordered_keys]


def upsert_image_text_embedding(
    conn: sqlite3.Connection, image_key: str, vec_blob: bytes
) -> None:
    """Replace vec0 row for ``image_key``. Call inside :func:`library_write` only."""
    conn.execute("DELETE FROM image_text_embeddings WHERE image_key = ?", (image_key,))
    conn.execute(
        "INSERT INTO image_text_embeddings(embedding, image_key) VALUES (?, ?)",
        (vec_blob, image_key),
    )


def upsert_image_clip_embedding(
    conn: sqlite3.Connection, image_key: str, embedding_blob: bytes
) -> None:
    """Replace vec0 row for ``image_key``. Call inside :func:`library_write` only."""
    conn.execute("DELETE FROM image_clip_embeddings WHERE image_key = ?", (image_key,))
    conn.execute(
        "INSERT INTO image_clip_embeddings(embedding, image_key) VALUES (?, ?)",
        (embedding_blob, image_key),
    )


def _list_catalog_keys_clip_embed_sql_params(
    *,
    months: int | None,
    year: str | None,
    min_rating: int | None,
) -> tuple[str, tuple]:
    parts: list[str] = [
        "i.filepath IS NOT NULL AND TRIM(COALESCE(i.filepath, '')) != ''",
    ]
    params: list = []
    if months is not None:
        parts.append("i.date_taken >= date('now', ?)")
        params.append(f"-{months} months")
    if year is not None:
        parts.append("strftime('%Y', i.date_taken) = ?")
        params.append(year)
    if min_rating is not None:
        parts.append("i.rating >= ?")
        params.append(min_rating)
    where = " AND ".join(parts)
    sql = f"""
        SELECT i.key AS key, i.date_taken AS date_taken
        FROM images i
        WHERE {where}
        ORDER BY i.key ASC
    """
    return sql, tuple(params)


def list_catalog_keys_needing_clip_embedding(
    conn: sqlite3.Connection,
    *,
    months: int | None,
    year: str | None,
    min_rating: int | None,
) -> list[str]:
    """Catalog keys with a usable file path in the date/rating window, missing CLIP vec0 rows."""
    sql, params = _list_catalog_keys_clip_embed_sql_params(
        months=months,
        year=year,
        min_rating=min_rating,
    )
    rows = conn.execute(sql, params).fetchall()
    embedded_keys = {
        str(r["image_key"])
        for r in conn.execute("SELECT image_key FROM image_clip_embeddings").fetchall()
    }
    filtered_rows = [r for r in rows if str(r["key"]) not in embedded_keys]
    return _sort_catalog_key_rows_newest_first(filtered_rows)


def list_catalog_keys_for_clip_embed_force(
    conn: sqlite3.Connection,
    *,
    months: int | None,
    year: str | None,
    min_rating: int | None,
) -> list[str]:
    """All catalog keys with a usable file path in the window, including keys in ``image_clip_embeddings``."""
    sql, params = _list_catalog_keys_clip_embed_sql_params(
        months=months,
        year=year,
        min_rating=min_rating,
    )
    rows = conn.execute(sql, params).fetchall()
    return _sort_catalog_key_rows_newest_first(rows)


def _instagram_dump_clip_embed_filters(
    *,
    months: int | None,
    year: str | None,
) -> tuple[list[str], list]:
    """Base ``WHERE`` fragments (alias ``m``) for Instagram dump CLIP-eligible rows.

    Mirrors the date window semantics of :func:`_list_catalog_keys_clip_embed_sql_params`
    (``months`` rolling window + optional calendar ``year``). Dump rows have no
    rating column — ``min_rating`` does not apply here.

    ``date_folder`` values follow the compact ``YYYYMM`` ordering used by
    :func:`get_instagram_by_date_filter` (lexicographic ``>=`` cutoff).
    """
    parts: list[str] = [
        "m.file_path IS NOT NULL AND TRIM(COALESCE(m.file_path, '')) != ''",
        _INSTAGRAM_DUMP_CLIP_VIDEO_GUARD,
    ]
    params: list = []
    if months is not None:
        from_date = (datetime.now() - timedelta(days=months * 30)).strftime("%Y%m")
        parts.append("m.date_folder >= ?")
        params.append(from_date)
    if year is not None:
        parts.append("m.date_folder LIKE ?")
        params.append(f"{year}%")
    return parts, params


def _list_instagram_dump_clip_embed_sql_params(
    *,
    months: int | None,
    year: str | None,
) -> tuple[str, tuple]:
    """WHERE clause fragments for Instagram dump rows eligible for CLIP embedding."""
    parts, params_list = _instagram_dump_clip_embed_filters(months=months, year=year)
    where_sql = " AND ".join(parts)
    sql = f"""
        SELECT m.media_key AS media_key, m.date_folder AS date_folder
        FROM instagram_dump_media m
        WHERE {where_sql}
        ORDER BY m.date_folder DESC, m.media_key DESC
    """
    return sql, tuple(params_list)


def list_instagram_dump_keys_needing_clip_embedding(
    conn: sqlite3.Connection,
    *,
    months: int | None,
    year: str | None,
    min_rating: int | None,
) -> list[str]:
    """Instagram dump ``media_key`` values with usable paths, missing CLIP vec0 rows.

    Uses the active embedding dimension implicitly via presence in
    ``image_clip_embeddings`` (same invalidation story as catalog listings).

    ``min_rating`` is accepted for parity with catalog helpers but ignored —
    dump media has no catalog rating column.
    """
    _ = min_rating
    parts, params_list = _instagram_dump_clip_embed_filters(months=months, year=year)
    parts_with_null = [*parts, "ce.image_key IS NULL"]
    where_sql = " AND ".join(parts_with_null)
    sql = f"""
        SELECT m.media_key AS media_key
        FROM instagram_dump_media m
        LEFT JOIN image_clip_embeddings ce ON ce.image_key = m.media_key
        WHERE {where_sql}
        ORDER BY m.date_folder DESC, m.media_key DESC
    """
    rows = conn.execute(sql, tuple(params_list)).fetchall()
    return [str(row["media_key"]) for row in rows]


def list_instagram_dump_keys_for_clip_embed_force(
    conn: sqlite3.Connection,
    *,
    months: int | None,
    year: str | None,
    min_rating: int | None,
) -> list[str]:
    """All Instagram dump keys in the date window with usable paths (including embedded).

    ``min_rating`` is ignored — see :func:`list_instagram_dump_keys_needing_clip_embedding`.
    """
    _ = min_rating
    sql, params = _list_instagram_dump_clip_embed_sql_params(months=months, year=year)
    rows = conn.execute(sql, params).fetchall()
    return [str(row["media_key"]) for row in rows]


def get_all_images_with_descriptions(db: sqlite3.Connection,
                                     image_type: str = None,
                                     described_only: bool = False,
                                     limit: int = 50,
                                     offset: int = 0) -> tuple[list[dict], int]:
    """Get images joined with their descriptions for the descriptions page.

    Returns (items, total_count).
    """
    parts = []
    params: list = []

    if image_type != 'instagram':
        parts.append("""
            SELECT i.key AS image_key, 'catalog' AS image_type,
                   i.filename, i.date_taken AS date_ref,
                   d.summary, d.best_perspective, d.model_used AS desc_model,
                   d.described_at,
                   CASE WHEN d.image_key IS NOT NULL THEN 1 ELSE 0 END AS has_description
            FROM images i
            LEFT JOIN image_descriptions d
                ON i.key = d.image_key AND d.image_type = 'catalog'
        """)

    if image_type != 'catalog':
        parts.append("""
            SELECT m.media_key AS image_key, 'instagram' AS image_type,
                   m.filename, m.created_at AS date_ref,
                   d.summary, d.best_perspective, d.model_used AS desc_model,
                   d.described_at,
                   CASE WHEN d.image_key IS NOT NULL THEN 1 ELSE 0 END AS has_description
            FROM instagram_dump_media m
            LEFT JOIN image_descriptions d
                ON m.media_key = d.image_key AND d.image_type = 'instagram'
        """)

    union_sql = " UNION ALL ".join(parts)

    if described_only:
        wrapper = f"SELECT * FROM ({union_sql}) t WHERE t.has_description = 1"
    else:
        wrapper = f"SELECT * FROM ({union_sql}) t"

    count_sql = f"SELECT COUNT(*) AS cnt FROM ({wrapper})"
    total = db.execute(count_sql, params * len(parts)).fetchone()['cnt']

    page_sql = (
        f"{wrapper} ORDER BY CASE WHEN t.described_at IS NULL THEN 1 ELSE 0 END, "
        f"t.described_at DESC, t.date_ref DESC LIMIT ? OFFSET ?"
    )
    all_params = params * len(parts) + [limit, offset]
    rows = db.execute(page_sql, all_params).fetchall()

    return [_deserialize_row(r) for r in rows], total


# ---------------------------------------------------------------------------
# Perspectives & image scores (structured scoring)
# ---------------------------------------------------------------------------
#
# ## Queryable score fields (image_scores)
#
# - **id**: Surrogate primary key for this score row.
# - **image_key**: Library image identity (e.g. ``YYYY-MM-DD_filename.jpg``).
# - **image_type**: ``catalog`` vs ``instagram`` (dump media keys).
# - **perspective_slug**: Stable key matching ``perspectives.slug``.
# - **score**: Integer rubric score 1–10.
# - **rationale**: Short text justification from the model.
# - **model_used**: Provider/model identifier for the scoring call.
# - **prompt_version**: Rubric/prompt revision label; unique per image+type+slug.
# - **scored_at**: ISO-8601 timestamp when the score was recorded.
# - **is_current**: 1 if this row is the active score for this image+type+slug.
# - **repaired_from_malformed**: 1 if the row was persisted after output repair.
#
# Join ``image_scores`` with ``LEFT JOIN`` from catalog/dump rows: **no matching
# row means that image has not been scored yet** for that perspective (and type).


def list_perspectives(
    conn: sqlite3.Connection, *, active_only: bool = False
) -> list[dict]:
    """Return perspective rows as dicts ordered by ``slug``."""
    sql = "SELECT * FROM perspectives"
    if active_only:
        sql += " WHERE active = 1"
    sql += " ORDER BY slug ASC"
    rows = conn.execute(sql).fetchall()
    return [dict(r) for r in rows]


def get_perspective_by_slug(conn: sqlite3.Connection, slug: str) -> dict | None:
    """Return one perspective row by ``slug``, or ``None``."""
    row = conn.execute(
        "SELECT * FROM perspectives WHERE slug = ? LIMIT 1", (slug,)
    ).fetchone()
    return dict(row) if row else None


def insert_perspective(
    conn: sqlite3.Connection,
    *,
    slug: str,
    display_name: str,
    prompt_markdown: str,
    description: str = "",
    active: bool = True,
    source_filename: str | None = None,
) -> None:
    """Insert a ``perspectives`` row. Caller commits."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO perspectives (
            slug, display_name, description, prompt_markdown,
            active, source_filename, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            slug,
            display_name,
            description,
            prompt_markdown,
            1 if active else 0,
            source_filename,
            now,
            now,
        ),
    )


def update_perspective(
    conn: sqlite3.Connection,
    slug: str,
    *,
    display_name: str | None = None,
    description: str | None = None,
    prompt_markdown: str | None = None,
    active: bool | None = None,
) -> bool:
    """Partially update a perspective by ``slug``. Returns whether a row was updated."""
    fields: list[str] = []
    values: list = []
    if display_name is not None:
        fields.append("display_name = ?")
        values.append(display_name)
    if description is not None:
        fields.append("description = ?")
        values.append(description)
    if prompt_markdown is not None:
        fields.append("prompt_markdown = ?")
        values.append(prompt_markdown)
    if active is not None:
        fields.append("active = ?")
        values.append(1 if active else 0)
    if not fields:
        return False
    now = datetime.now(timezone.utc).isoformat()
    fields.append("updated_at = ?")
    values.append(now)
    values.append(slug)
    cur = conn.execute(
        f"UPDATE perspectives SET {', '.join(fields)} WHERE slug = ?",
        tuple(values),
    )
    if cur.rowcount > 0:
        return True
    return get_perspective_by_slug(conn, slug) is not None


def delete_perspective(conn: sqlite3.Connection, slug: str) -> bool:
    """Delete a perspective by ``slug``. Returns whether a row was removed."""
    cur = conn.execute("DELETE FROM perspectives WHERE slug = ?", (slug,))
    return cur.rowcount > 0


def insert_image_score(conn: sqlite3.Connection, row: dict) -> int:
    """Insert one ``image_scores`` row; return ``lastrowid``.

    Caller manages transactions and coordinating ``is_current`` / supersede calls.
    """
    cursor = conn.execute(
        """
        INSERT INTO image_scores (
            image_key, image_type, perspective_slug, score, rationale,
            model_used, prompt_version, scored_at, is_current,
            repaired_from_malformed
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row["image_key"],
            row.get("image_type", "catalog"),
            row["perspective_slug"],
            row["score"],
            row.get("rationale", ""),
            row.get("model_used", ""),
            row.get("prompt_version", ""),
            row["scored_at"],
            int(row.get("is_current", 1)),
            int(row.get("repaired_from_malformed", 0)),
        ),
    )
    last = cursor.lastrowid
    assert last is not None
    return int(last)


def supersede_previous_current_scores(
    conn: sqlite3.Connection,
    image_key: str,
    image_type: str,
    perspective_slug: str,
    new_prompt_version: str,
) -> None:
    """Set ``is_current = 0`` for rows matching key, type, and slug whose
    ``prompt_version`` is not ``new_prompt_version``.

    Call before inserting a new current row for the same image+type+slug so only
    the new version remains ``is_current = 1``.
    """
    conn.execute(
        """
        UPDATE image_scores
        SET is_current = 0
        WHERE image_key = ?
          AND image_type = ?
          AND perspective_slug = ?
          AND prompt_version != ?
        """,
        (image_key, image_type, perspective_slug, new_prompt_version),
    )


def get_current_scores_for_image(
    conn: sqlite3.Connection, image_key: str, image_type: str = "catalog"
) -> list[dict]:
    """Return all ``image_scores`` rows for this image with ``is_current = 1``."""
    rows = conn.execute(
        """
        SELECT * FROM image_scores
        WHERE image_key = ? AND image_type = ? AND is_current = 1
        ORDER BY perspective_slug ASC
        """,
        (image_key, image_type),
    ).fetchall()
    return [dict(r) for r in rows]


def list_score_history_for_perspective(
    conn: sqlite3.Connection, image_key: str, image_type: str, perspective_slug: str
) -> list[dict]:
    """Return all ``image_scores`` rows for one image and perspective, newest first.

    Rows include ``id``, ``is_current``, ``prompt_version``, ``model_used``,
    ``repaired_from_malformed``, and the rest of the table columns. After
    :func:`supersede_previous_current_scores`, older rubric versions remain with
    ``is_current = 0`` on purpose; API consumers use ``is_current`` to mark the
    active rubric version.
    """
    rows = conn.execute(
        """
        SELECT * FROM image_scores
        WHERE image_key = ? AND image_type = ? AND perspective_slug = ?
        ORDER BY scored_at DESC, id DESC
        """,
        (image_key, image_type, perspective_slug),
    ).fetchall()
    return [dict(r) for r in rows]


def list_all_scores_for_image(
    conn: sqlite3.Connection, image_key: str, image_type: str
) -> list[dict]:
    """Return every ``image_scores`` row for an image, grouped by slug then recency.

    Perspectives are ordered alphabetically; within each slug, rows are newest first.
    """
    rows = conn.execute(
        """
        SELECT * FROM image_scores
        WHERE image_key = ? AND image_type = ?
        ORDER BY perspective_slug ASC, scored_at DESC, id DESC
        """,
        (image_key, image_type),
    ).fetchall()
    return [dict(r) for r in rows]
