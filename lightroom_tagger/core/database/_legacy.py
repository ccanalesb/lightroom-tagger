import contextlib
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


from .catalog import library_write
from .db_init import _deserialize_row, _serialize_json
from .instagram import _INSTAGRAM_DUMP_CLIP_VIDEO_GUARD


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
