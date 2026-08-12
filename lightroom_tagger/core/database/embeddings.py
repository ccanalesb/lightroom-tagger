"""CLIP embedding DB helpers."""

import sqlite3


def _sort_catalog_key_rows_newest_first(rows: list[sqlite3.Row]) -> list[str]:
    """Return keys sorted by ``date_taken`` desc, then key desc."""
    keyed: list[tuple[str, str]] = []
    for row in rows:
        key = str(row["key"])
        date_taken = str(row["date_taken"] or "")
        keyed.append((key, date_taken))
    keyed.sort(key=lambda item: (item[1], item[0]), reverse=True)
    return [key for key, _ in keyed]


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
