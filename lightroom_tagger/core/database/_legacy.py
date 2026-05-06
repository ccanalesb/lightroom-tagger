import os
import sqlite3
from collections.abc import Sequence
from datetime import datetime, timedelta

from .catalog import library_write
from .instagram import _INSTAGRAM_DUMP_CLIP_VIDEO_GUARD


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
