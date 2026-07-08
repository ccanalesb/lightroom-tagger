"""Structured catalog filtering and listing queries."""

from __future__ import annotations

import sqlite3
from collections.abc import Collection, Sequence

from lightroom_tagger.core.database.catalog_query_filters import (
    _append_query_catalog_image_filters,
    _non_empty_str_list_for_json_array_filter,
)
from lightroom_tagger.core.database.db_init import _deserialize_row


def filter_order_keys_in_catalog(
    db: sqlite3.Connection,
    keys: list[str],
    *,
    posted: bool | None = None,
    month: str | None = None,
    keyword: str | None = None,
    min_rating: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    color_label: str | None = None,
    analyzed: bool | None = None,
    score_perspective: str | None = None,
    min_score: int | None = None,
    description_search: str | None = None,
    dominant_colors: list[str] | None = None,
    mood_tags: list[str] | None = None,
    has_repetition: bool | None = None,
) -> list[str]:
    """Return members of *keys* that satisfy the same filters as :func:`query_catalog_images`.

    Preserves **input order**. ``sort_by_*`` are not applicable to membership and are
    omitted. Empty *keys* → ``[]``.

    **min_score** requires **score_perspective** (same rule as :func:`query_catalog_images`).
    """
    if not keys:
        return []
    sp = (score_perspective or "").strip()
    use_score_join = bool(sp)
    if min_score is not None and not use_score_join:
        raise ValueError("min_score requires score_perspective")
    if min_score is not None and not (1 <= min_score <= 10):
        raise ValueError("min_score must be between 1 and 10")

    ph = ",".join("?" * len(keys))
    clauses: list[str] = [f"i.key IN ({ph})"]
    bindings: list = list(keys)
    _append_query_catalog_image_filters(
        clauses,
        bindings,
        posted=posted,
        month=month,
        keyword=keyword,
        min_rating=min_rating,
        date_from=date_from,
        date_to=date_to,
        color_label=color_label,
        analyzed=analyzed,
        min_score=min_score,
        description_search=description_search,
        dominant_colors=dominant_colors,
        mood_tags=mood_tags,
        has_repetition=has_repetition,
    )
    where_sql = "WHERE " + " AND ".join(clauses)
    join_sql = (
        "FROM images i "
        "LEFT JOIN image_descriptions d ON i.key = d.image_key AND d.image_type = 'catalog' "
    )
    join_bindings: list = []
    if use_score_join:
        join_sql += (
            "LEFT JOIN image_scores s ON s.image_key = i.key "
            "AND s.image_type = 'catalog' AND s.perspective_slug = ? AND s.is_current = 1 "
        )
        join_bindings.append(sp)
    join_sql += (
        "LEFT JOIN image_stack_members AS m_st ON m_st.image_key = i.key "
        "LEFT JOIN image_stacks AS st ON st.stack_id = m_st.stack_id "
    )
    params = join_bindings + bindings
    rows = db.execute(
        f"SELECT i.key AS image_key {join_sql} {where_sql}",
        params,
    ).fetchall()
    matched = {str(r["image_key"]) for r in rows}
    return [k for k in keys if k in matched]


def query_catalog_images(
    db: sqlite3.Connection,
    *,
    posted: bool | None = None,
    month: str | None = None,
    keyword: str | None = None,
    min_rating: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    color_label: str | None = None,
    analyzed: bool | None = None,
    score_perspective: str | None = None,
    min_score: int | None = None,
    sort_by_score: str | None = None,
    sort_by_date: str | None = None,
    description_search: str | None = None,
    dominant_colors: list[str] | None = None,
    mood_tags: list[str] | None = None,
    has_repetition: bool | None = None,
    restrict_to_keys: Collection[str] | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """List catalog images with AND-combined filters, SQL pagination, and total count.

    **description_search** — optional FTS5 match over ``image_descriptions`` for
    ``image_type='catalog'`` only. Invalid short queries raise ``ValueError`` with message
    ``description_search must be at least 2 characters`` (map to HTTP 400 in the API).

    Optional **score_perspective** enables a ``LEFT JOIN`` on ``image_scores`` for the
    current row (``is_current=1``, ``image_type='catalog'``) for that slug.

    **min_score** (1–10) requires **score_perspective** and keeps only rows with a
    non-null score ``>= min_score``.

    **sort_by_score** ``asc`` / ``desc`` requires **score_perspective**. Unscored rows
    for that perspective sort after scored rows in both directions (``s.score IS NULL``
    last via SQLite boolean ordering).

    **sort_by_date** ``newest`` / ``oldest`` orders by ``i.date_taken``. When both
    ``sort_by_score`` and ``sort_by_date`` are set, score wins as the primary key and
    date is the tiebreaker.

    **dominant_colors** / **mood_tags** — optional lists of strings; if non-empty
    (after dropping blank elements), a row must have at least one token from the
    list present as a JSON array element in ``image_descriptions.dominant_colors`` /
    ``mood_tags`` (catalog join row ``d``). Filters use SQLite ``json_each`` with
    bound parameters; invalid or non-array JSON in the column is excluded.
    """
    if sort_by_score is not None and sort_by_score not in ("asc", "desc"):
        raise ValueError("sort_by_score must be 'asc' or 'desc'")
    if sort_by_date is not None and sort_by_date not in ("newest", "oldest"):
        raise ValueError("sort_by_date must be 'newest' or 'oldest'")

    sp = (score_perspective or "").strip()
    use_score_join = bool(sp)

    if sort_by_score is not None and not use_score_join:
        raise ValueError("sort_by_score requires score_perspective")

    if min_score is not None and not use_score_join:
        raise ValueError("min_score requires score_perspective")

    if min_score is not None and not (1 <= min_score <= 10):
        raise ValueError("min_score must be between 1 and 10")

    clauses: list[str] = ["1=1"]
    bindings: list = []
    _append_query_catalog_image_filters(
        clauses,
        bindings,
        posted=posted,
        month=month,
        keyword=keyword,
        min_rating=min_rating,
        date_from=date_from,
        date_to=date_to,
        color_label=color_label,
        analyzed=analyzed,
        min_score=min_score,
        description_search=description_search,
        dominant_colors=dominant_colors,
        mood_tags=mood_tags,
        has_repetition=has_repetition,
    )

    # get_catalog_schema may expose global catalog counts; when a pin is active, catalog listing/search here is still restricted to restrict_to_keys at execution time.
    if restrict_to_keys is not None:
        rk = [str(k) for k in restrict_to_keys if k]
        if not rk:
            clauses.append("1=0")
        else:
            ph = ",".join("?" * len(rk))
            clauses.append(f"i.key IN ({ph})")
            bindings.extend(rk)

    where_sql = "WHERE " + " AND ".join(clauses)
    join_sql = (
        "FROM images i "
        "LEFT JOIN image_descriptions d ON i.key = d.image_key AND d.image_type = 'catalog' "
    )
    join_bindings: list = []
    if use_score_join:
        join_sql += (
            "LEFT JOIN image_scores s ON s.image_key = i.key "
            "AND s.image_type = 'catalog' AND s.perspective_slug = ? AND s.is_current = 1 "
        )
        join_bindings.append(sp)
    join_sql += (
        "LEFT JOIN image_stack_members AS m_st ON m_st.image_key = i.key "
        "LEFT JOIN image_stacks AS st ON st.stack_id = m_st.stack_id "
    )

    # Date becomes a tiebreaker for score sorts only when the caller asked
    # for it explicitly; otherwise keep the original `i.key ASC` tiebreaker
    # so unrelated callers aren't silently re-ordered by date.
    if sort_by_date is None:
        date_tiebreaker = "i.key ASC"
    else:
        date_order = "ASC" if sort_by_date == "oldest" else "DESC"
        date_tiebreaker = f"i.date_taken {date_order}, i.key ASC"

    if sort_by_score == "desc":
        order_sql = (
            f"ORDER BY (s.score IS NULL) ASC, s.score DESC, {date_tiebreaker}"
        )
    elif sort_by_score == "asc":
        order_sql = (
            f"ORDER BY (s.score IS NULL) ASC, s.score ASC, {date_tiebreaker}"
        )
    elif sort_by_date == "oldest":
        order_sql = "ORDER BY i.date_taken ASC, i.key ASC"
    else:
        order_sql = "ORDER BY i.date_taken DESC, i.key ASC"

    select_cols = (
        "i.*, d.summary AS description_summary, "
        "d.best_perspective AS description_best_perspective, "
        "d.perspectives AS description_perspectives_json"
    )
    if use_score_join:
        select_cols += ", s.score AS catalog_perspective_score"
    select_cols += (
        ", st.stack_id AS stack_id, st.stack_size AS stack_member_count, "
        "CASE WHEN st.stack_id IS NOT NULL AND i.key = st.representative_key "
        "THEN 1 ELSE 0 END AS is_stack_representative"
    )

    count_params = join_bindings + bindings
    count_row = db.execute(
        f"SELECT COUNT(*) AS cnt {join_sql} {where_sql}",
        count_params,
    ).fetchone()
    total_count = int(count_row["cnt"])

    select_params = join_bindings + bindings + [limit, offset]
    rows = db.execute(
        f"SELECT {select_cols} {join_sql} {where_sql} {order_sql} LIMIT ? OFFSET ?",
        select_params,
    ).fetchall()
    return [_deserialize_row(r) for r in rows], total_count


def query_catalog_images_by_keys(
    db: sqlite3.Connection,
    keys: Sequence[str],
    *,
    score_perspective: str | None = None,
    primary_grid_only: bool = True,
) -> list[dict]:
    """Load catalog rows for ``keys`` with the same columns/joins as :func:`query_catalog_images`.

    Preserves **input order** via ``ORDER BY CASE i.key WHEN …``. Empty ``keys`` → ``[]``.

    When ``primary_grid_only`` is True (default), non-representative stack members are
    excluded (same collapse as :func:`query_catalog_images`). Pass False to load every
    key in *keys*, e.g. burst stack member lists.
    """
    if not keys:
        return []
    key_list = [str(k) for k in keys]
    sp = (score_perspective or "").strip()
    use_score_join = bool(sp)

    ph = ",".join("?" * len(key_list))
    case_when = " ".join(
        f"WHEN ? THEN {i}" for i in range(len(key_list))
    )
    order_sql = f"ORDER BY CASE i.key {case_when} END"

    select_cols = (
        "i.*, d.summary AS description_summary, "
        "d.best_perspective AS description_best_perspective, "
        "d.perspectives AS description_perspectives_json"
    )
    if use_score_join:
        select_cols += ", s.score AS catalog_perspective_score"
    select_cols += (
        ", st.stack_id AS stack_id, st.stack_size AS stack_member_count, "
        "CASE WHEN st.stack_id IS NOT NULL AND i.key = st.representative_key "
        "THEN 1 ELSE 0 END AS is_stack_representative"
    )

    join_sql = (
        "FROM images i "
        "LEFT JOIN image_descriptions d ON i.key = d.image_key AND d.image_type = 'catalog' "
    )
    join_bindings: list = []
    if use_score_join:
        join_sql += (
            "LEFT JOIN image_scores s ON s.image_key = i.key "
            "AND s.image_type = 'catalog' AND s.perspective_slug = ? AND s.is_current = 1 "
        )
        join_bindings.append(sp)
    join_sql += (
        "LEFT JOIN image_stack_members AS m_st ON m_st.image_key = i.key "
        "LEFT JOIN image_stacks AS st ON st.stack_id = m_st.stack_id "
    )

    if primary_grid_only:
        where_sql = (
            f"WHERE i.key IN ({ph}) AND (m_st.image_key IS NULL OR i.key = st.representative_key)"
        )
    else:
        where_sql = f"WHERE i.key IN ({ph})"
    params = join_bindings + key_list + key_list

    rows = db.execute(
        f"SELECT {select_cols} {join_sql} {where_sql} {order_sql}",
        params,
    ).fetchall()
    return [_deserialize_row(r) for r in rows]


def catalog_key_is_primary_grid_row(db: sqlite3.Connection, image_key: str) -> bool:
    """True for catalog keys that are stack representatives or not in a multi-key stack.

    False when the key is a **non-representative** member of a stack (hidden from
    the default primary grid, same as :func:`query_catalog_images` collapse).
    """
    row = db.execute(
        """
        SELECT NOT EXISTS(
            SELECT 1 FROM image_stack_members m
            INNER JOIN image_stacks s ON s.stack_id = m.stack_id
            WHERE m.image_key = ? AND m.image_key <> s.representative_key
        ) AS ok
        """,
        (image_key,),
    ).fetchone()
    return bool(row and int(row["ok"]))


__all__ = (
    "_append_query_catalog_image_filters",
    "_non_empty_str_list_for_json_array_filter",
    "catalog_key_is_primary_grid_row",
    "filter_order_keys_in_catalog",
    "query_catalog_images",
    "query_catalog_images_by_keys",
)
