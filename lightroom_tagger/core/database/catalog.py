"""Catalog images: library-write discipline, CRUD, and structured queries."""

from __future__ import annotations

import contextlib
import json
import os
import re
import sqlite3
import threading
import time
from collections.abc import Collection, Sequence
from datetime import datetime

from .db_init import _deserialize_row, _serialize_json


# ---------------------------------------------------------------------------
# Single-writer discipline for ``library.db``
# ---------------------------------------------------------------------------
#
# SQLite (including WAL mode) allows exactly one writer at a time. Under
# parallel describe/score workers (4 threads, each with its own connection,
# each doing UPDATE/INSERT around a slow vision-model call) we were hitting
# ``OperationalError: database is locked`` at 10–30% of writes.
#
# Two distinct failure modes caused this:
#
#   1. Python's default isolation level auto-BEGINs a *deferred* transaction
#      on the first SELECT. When DML later runs on the same connection,
#      SQLite must upgrade the read lock to a write lock — that upgrade
#      fails *immediately* with SQLITE_BUSY if another writer is active,
#      ignoring ``busy_timeout`` (because the upgrade cannot safely wait
#      without deadlocking).
#
#   2. Multiple helper functions (``store_image_description``,
#      ``store_vision_cached_image``, ``insert_image_score``,
#      ``supersede_previous_current_scores``, ``delete_scores_for_version``)
#      each open their own implicit transaction and commit immediately,
#      so workers race on the writer seat across many small hot-path calls.
#
# The fix is a single process-wide writer lock plus ``BEGIN IMMEDIATE`` on
# every library.db write. ``BEGIN IMMEDIATE`` takes the writer lock up
# front and *does* honor ``busy_timeout``, so concurrent Python threads
# queue on the lock instead of racing SQLite and losing. Reads remain
# fully parallel: each worker keeps its own connection, only writes go
# through the serializer.
#
# Call sites should use :func:`library_write` rather than bare
# ``conn.commit()`` whenever they modify ``library.db`` from a context
# that may run in parallel with other workers.

# ``RLock`` (not ``Lock``) so that nested ``library_write`` calls on the
# same thread don't self-deadlock. In practice we don't currently nest,
# but the score/describe call graph changes often and a non-reentrant
# lock would turn a future refactor into a production hang. The inner
# BEGIN IMMEDIATE is still guarded by SQLite itself — re-entering
# ``library_write`` on the same thread means the outer ``BEGIN IMMEDIATE``
# is already in effect, so the inner block just piggy-backs on it (see
# the ``in_transaction`` check below).
_LIBRARY_WRITE_LOCK = threading.RLock()


@contextlib.contextmanager
def library_write(
    conn: sqlite3.Connection,
    *,
    retries: int = 5,
    log=None,
):
    """Acquire the library-DB writer seat for a single transaction.

    Usage::

        with library_write(conn):
            conn.execute("INSERT ...")
            conn.execute("UPDATE ...")

    Semantics:

    * Holds ``_LIBRARY_WRITE_LOCK`` for the duration, so at most one Python
      thread in this process owns a library-DB write transaction at a time.
    * Calls ``conn.rollback()`` first to discard any implicit deferred read
      transaction (see failure mode #1 above), then ``BEGIN IMMEDIATE``
      which grabs the SQLite writer seat and honors ``busy_timeout``.
    * On success, commits. On any exception inside the ``with`` block,
      rolls back and re-raises.
    * Retries ``SQLITE_BUSY`` from ``BEGIN IMMEDIATE`` with exponential
      backoff — this handles the rare case that an external process (not
      this Python process) holds the writer seat longer than
      ``busy_timeout``.

    The ``log`` hook receives ``("level", "message")`` tuples and is
    intended for job-log forwarding so retries are visible in the UI.
    """
    acquired = False
    owns_transaction = False
    try:
        _LIBRARY_WRITE_LOCK.acquire()
        acquired = True

        # Nested ``library_write`` on the same thread: the outer call
        # already has an open ``BEGIN IMMEDIATE`` transaction and will
        # handle commit/rollback. Just yield so the inner block runs
        # inside the outer transaction.
        if conn.in_transaction:
            yield conn
            return

        last_exc: Exception | None = None
        for attempt in range(retries):
            try:
                conn.rollback()
                conn.execute("BEGIN IMMEDIATE")
                owns_transaction = True
                break
            except sqlite3.OperationalError as exc:
                last_exc = exc
                if "database is locked" in str(exc) and attempt < retries - 1:
                    if log is not None:
                        log(
                            "warning",
                            f"[library-write] lock busy, retry "
                            f"{attempt + 1}/{retries}",
                        )
                    time.sleep(0.1 * (2 ** attempt) + (time.time() % 0.05))
                    continue
                raise
        if not owns_transaction:  # pragma: no cover
            raise last_exc if last_exc else sqlite3.OperationalError(
                "library_write: failed to acquire writer seat"
            )

        try:
            yield conn
        except Exception:
            with contextlib.suppress(sqlite3.Error):
                conn.rollback()
            owns_transaction = False
            raise
        else:
            conn.commit()
            owns_transaction = False
    finally:
        if acquired:
            _LIBRARY_WRITE_LOCK.release()

def resolve_filepath(path: str) -> str:
    """Resolve UNC/network paths to local mount points.

    Set NAS_PATH_PREFIX and NAS_MOUNT_POINT env vars to configure.
    Falls back to auto-detecting SMB mounts under /Volumes/.
    Handles case-insensitive server names (NAS vs tnas vs TNAS).
    
    Example: //tnas/ccanales/Foo/bar.jpg -> /Volumes/ccanales/Foo/bar.jpg
    """
    if not path or not path.startswith('//'):
        return path

    prefix = os.getenv('NAS_PATH_PREFIX', '')
    mount = os.getenv('NAS_MOUNT_POINT', '')

    # Parse path: //server/share/rest/of/path
    path_parts = path.lstrip('/').split('/', 2)  # ['server', 'share', 'rest/of/path']
    if len(path_parts) < 2:
        return path
    
    server_name = path_parts[0]  # e.g., "tnas", "NAS", "TNAS"
    share_name = path_parts[1]   # e.g., "ccanales"
    rest_of_path = path_parts[2] if len(path_parts) > 2 else ""
    
    # If we have a configured prefix and mount, check if share names match
    if prefix and mount:
        prefix_parts = prefix.lstrip('/').split('/')
        if len(prefix_parts) >= 2 and prefix_parts[1] == share_name:
            configured = os.path.join(mount, rest_of_path) if rest_of_path else mount
            if os.path.exists(configured):
                return configured

    # Auto-detect: scan /Volumes/ for matching mounts (handles -1 suffix etc.)
    try:
        for name in sorted(os.listdir('/Volumes/'), reverse=True):
            if name.startswith(share_name):
                candidate = os.path.join('/Volumes', name)
                if os.path.ismount(candidate):
                    resolved = os.path.join(candidate, rest_of_path) if rest_of_path else candidate
                    if os.path.exists(resolved):
                        return resolved
    except OSError:
        pass

    # Last resort: return configured path even if it doesn't exist
    if prefix and mount:
        prefix_parts = prefix.lstrip('/').split('/')
        if len(prefix_parts) >= 2 and prefix_parts[1] == share_name:
            return os.path.join(mount, rest_of_path) if rest_of_path else mount

    return path

# ---------------------------------------------------------------------------
# Images (catalog)
# ---------------------------------------------------------------------------

def generate_key(record: dict) -> str:
    """Generate unique key from record: {date_taken}_{filename}

    Date portion matches ``lightroom.reader.generate_record_key`` (YYYY-MM-DD only).
    """
    date_taken = record.get('date_taken', 'unknown')
    date_part = date_taken[:10] if date_taken else 'unknown'
    filename = record.get('filename', 'unknown')
    return f"{date_part}_{filename}"

def store_image(db: sqlite3.Connection, record: dict) -> str:
    """Store image record, return key. Upsert if exists."""
    key = generate_key(record)
    record['key'] = key

    params = {
        'key': key,
        'id': record.get('id'),
        'filename': record.get('filename', ''),
        'filepath': record.get('filepath', ''),
        'date_taken': record.get('date_taken', ''),
        'rating': record.get('rating', 0),
        'pick': record.get('pick', 0),
        'color_label': record.get('color_label', ''),
        'keywords': _serialize_json(record.get('keywords', [])),
        'title': record.get('title', ''),
        'caption': record.get('caption', ''),
        'description': record.get('description', ''),
        'copyright': record.get('copyright', ''),
        'camera_make': record.get('camera_make', ''),
        'camera_model': record.get('camera_model', ''),
        'lens': record.get('lens', ''),
        'focal_length': record.get('focal_length', ''),
        'aperture': record.get('aperture', ''),
        'shutter_speed': record.get('shutter_speed', ''),
        'iso': record.get('iso', ''),
        'gps_latitude': record.get('gps_latitude'),
        'gps_longitude': record.get('gps_longitude'),
        'width': record.get('width'),
        'height': record.get('height'),
        'file_size': record.get('file_size'),
        'instagram_posted': int(bool(record.get('instagram_posted', False))),
        'instagram_post_date': record.get('instagram_post_date'),
        'instagram_url': record.get('instagram_url'),
        'instagram_index': record.get('instagram_index', 0),
        'image_hash': record.get('image_hash'),
        'analyzed_at': record.get('analyzed_at'),
        'phash': record.get('phash'),
        'exif': _serialize_json(record.get('exif')),
        'catalog_path': record.get('catalog_path', ''),
    }

    db.execute("""
        INSERT INTO images (key, id, filename, filepath, date_taken, rating, pick,
            color_label, keywords, title, caption, description, copyright,
            camera_make, camera_model, lens, focal_length, aperture,
            shutter_speed, iso, gps_latitude, gps_longitude, width, height,
            file_size, instagram_posted, instagram_post_date, instagram_url,
            instagram_index, image_hash, analyzed_at, phash, exif, catalog_path)
        VALUES (:key, :id, :filename, :filepath, :date_taken, :rating, :pick,
            :color_label, :keywords, :title, :caption, :description, :copyright,
            :camera_make, :camera_model, :lens, :focal_length, :aperture,
            :shutter_speed, :iso, :gps_latitude, :gps_longitude, :width, :height,
            :file_size, :instagram_posted, :instagram_post_date, :instagram_url,
            :instagram_index, :image_hash, :analyzed_at, :phash, :exif, :catalog_path)
        ON CONFLICT(key) DO UPDATE SET
            id=excluded.id,
            filename=excluded.filename, filepath=excluded.filepath,
            date_taken=excluded.date_taken, rating=excluded.rating,
            pick=excluded.pick, color_label=excluded.color_label,
            keywords=excluded.keywords, title=excluded.title,
            caption=excluded.caption, description=excluded.description,
            copyright=excluded.copyright, camera_make=excluded.camera_make,
            camera_model=excluded.camera_model, lens=excluded.lens,
            focal_length=excluded.focal_length, aperture=excluded.aperture,
            shutter_speed=excluded.shutter_speed, iso=excluded.iso,
            gps_latitude=excluded.gps_latitude, gps_longitude=excluded.gps_longitude,
            width=excluded.width, height=excluded.height,
            file_size=excluded.file_size, image_hash=excluded.image_hash,
            analyzed_at=excluded.analyzed_at, phash=excluded.phash,
            exif=excluded.exif, catalog_path=excluded.catalog_path
    """, params)
    db.commit()
    return key

def store_images_batch(db: sqlite3.Connection, records: list[dict]) -> int:
    """Store multiple records, return count."""
    count = 0
    for record in records:
        store_image(db, record)
        count += 1
    return count

def get_image(db: sqlite3.Connection, key: str) -> dict | None:
    """Get image by key."""
    row = db.execute("SELECT * FROM images WHERE key = ?", (key,)).fetchone()
    return _deserialize_row(row) if row else None

def search_by_keyword(db: sqlite3.Connection, keyword: str) -> list[dict]:
    """Search images by keyword in keywords, filename, title, description."""
    pattern = f'%{keyword}%'
    rows = db.execute("""
        SELECT * FROM images
        WHERE keywords LIKE ? COLLATE NOCASE
           OR filename LIKE ? COLLATE NOCASE
           OR title LIKE ? COLLATE NOCASE
           OR description LIKE ? COLLATE NOCASE
    """, (pattern, pattern, pattern, pattern)).fetchall()
    return [_deserialize_row(r) for r in rows]

def search_by_rating(db: sqlite3.Connection, min_rating: int = 0) -> list[dict]:
    """Search images by minimum rating."""
    rows = db.execute("SELECT * FROM images WHERE rating >= ?", (min_rating,)).fetchall()
    return [_deserialize_row(r) for r in rows]

def search_by_date(db: sqlite3.Connection, start_date: str, end_date: str = None) -> list[dict]:
    """Search images by date range (ISO format)."""
    if end_date:
        rows = db.execute(
            "SELECT * FROM images WHERE date_taken >= ? AND date_taken <= ?",
            (start_date, end_date)
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM images WHERE date_taken >= ?", (start_date,)
        ).fetchall()
    return [_deserialize_row(r) for r in rows]

def search_by_color_label(db: sqlite3.Connection, label: str) -> list[dict]:
    """Search images by color label (case-insensitive)."""
    rows = db.execute(
        "SELECT * FROM images WHERE LOWER(color_label) = LOWER(?)", (label,)
    ).fetchall()
    return [_deserialize_row(r) for r in rows]

def get_all_images(db: sqlite3.Connection) -> list[dict]:
    """Get all images."""
    rows = db.execute("SELECT * FROM images").fetchall()
    return [_deserialize_row(r) for r in rows]

def get_image_count(db: sqlite3.Connection) -> int:
    """Get total image count."""
    return db.execute("SELECT COUNT(*) as cnt FROM images").fetchone()['cnt']

def delete_image(db: sqlite3.Connection, key: str) -> bool:
    """Delete image by key."""
    cursor = db.execute("DELETE FROM images WHERE key = ?", (key,))
    db.commit()
    return cursor.rowcount > 0

def clear_all(db: sqlite3.Connection) -> int:
    """Clear all images. Returns count."""
    count = get_image_count(db)
    db.execute("DELETE FROM images")
    db.commit()
    return count
def _non_empty_str_list_for_json_array_filter(values: list[str] | None) -> list[str] | None:
    """Strip elements, drop blank entries; return None if no filter should apply.

    A list of only whitespace is treated as no filter, matching "empty list" semantics.
    """
    if values is None or len(values) == 0:
        return None
    out = [str(v).strip() for v in values if v is not None and str(v).strip()]
    return out or None

def _append_query_catalog_image_filters(
    clauses: list[str],
    bindings: list,
    *,
    posted: bool | None = None,
    month: str | None = None,
    keyword: str | None = None,
    min_rating: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    color_label: str | None = None,
    analyzed: bool | None = None,
    min_score: int | None = None,
    description_search: str | None = None,
    dominant_colors: list[str] | None = None,
    mood_tags: list[str] | None = None,
    has_repetition: bool | None = None,
) -> None:
    """Append shared catalog list AND-clauses (incl. stack collapse) to *clauses* / *bindings*.

    Used by :func:`query_catalog_images` and :func:`filter_order_keys_in_catalog`. The
    caller must initialize *clauses* (e.g. ``[\"1=1\"]`` or ``i.key IN (...)``) and *bindings*.
    """
    from ._legacy import build_description_fts_query

    if posted is True:
        clauses.append("i.instagram_posted = 1")
    elif posted is False:
        clauses.append("i.instagram_posted = 0")

    if month and len(month) == 6 and month.isdigit():
        clauses.append("strftime('%Y%m', i.date_taken) = ?")
        bindings.append(month)

    kw = (keyword or "").strip()
    if kw:
        pattern = f"%{kw}%"
        clauses.append(
            "("
            "i.keywords LIKE ? COLLATE NOCASE OR "
            "i.filename LIKE ? COLLATE NOCASE OR "
            "i.title LIKE ? COLLATE NOCASE OR "
            "i.description LIKE ? COLLATE NOCASE"
            ")"
        )
        bindings.extend([pattern, pattern, pattern, pattern])

    if min_rating is not None:
        clauses.append("i.rating >= ?")
        bindings.append(min_rating)

    if date_from:
        clauses.append("i.date_taken >= ?")
        bindings.append(date_from)

    if date_to:
        clauses.append("i.date_taken <= ?")
        bindings.append(date_to)

    cl = (color_label or "").strip()
    if cl:
        clauses.append("LOWER(i.color_label) = LOWER(?)")
        bindings.append(cl)

    if analyzed is True:
        clauses.append("d.image_key IS NOT NULL")
    elif analyzed is False:
        clauses.append("d.image_key IS NULL")

    if min_score is not None:
        clauses.append("s.score IS NOT NULL AND s.score >= ?")
        bindings.append(min_score)

    if (description_search or "").strip():
        match_str, fts_err = build_description_fts_query(description_search)
        if fts_err:
            raise ValueError(fts_err)
        if match_str is not None:
            clauses.append(
                "i.key IN ("
                "SELECT d2.image_key FROM image_descriptions d2 "
                "INNER JOIN image_descriptions_fts ON image_descriptions_fts.rowid = d2.rowid "
                "WHERE d2.image_type = 'catalog' AND image_descriptions_fts MATCH ?"
                ")"
            )
            bindings.append(match_str)

    dc_tokens = _non_empty_str_list_for_json_array_filter(dominant_colors)
    if dc_tokens:
        dc_ph = ",".join("?" * len(dc_tokens))
        clauses.append(
            "("
            "d.dominant_colors IS NOT NULL AND json_type(d.dominant_colors) = 'array' "
            "AND EXISTS ("
            "SELECT 1 FROM json_each(d.dominant_colors) AS jde "
            f"WHERE jde.value IN ({dc_ph})"
            ")"
            ")"
        )
        bindings.extend(dc_tokens)

    if has_repetition is True:
        clauses.append("d.has_repetition = 1")
    elif has_repetition is False:
        clauses.append("(d.has_repetition IS NULL OR d.has_repetition = 0)")

    mt_tokens = _non_empty_str_list_for_json_array_filter(mood_tags)
    if mt_tokens:
        mt_ph = ",".join("?" * len(mt_tokens))
        clauses.append(
            "("
            "d.mood_tags IS NOT NULL AND json_type(d.mood_tags) = 'array' "
            "AND EXISTS ("
            "SELECT 1 FROM json_each(d.mood_tags) AS jme "
            f"WHERE jme.value IN ({mt_ph})"
            ")"
            ")"
        )
        bindings.extend(mt_tokens)

    clauses.append("(m_st.image_key IS NULL OR i.key = st.representative_key)")

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
) -> list[dict]:
    """Load catalog rows for ``keys`` with the same columns/joins as :func:`query_catalog_images`.

    Preserves **input order** via ``ORDER BY CASE i.key WHEN …``. Empty ``keys`` → ``[]``.
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

    where_sql = (
        f"WHERE i.key IN ({ph}) AND (m_st.image_key IS NULL OR i.key = st.representative_key)"
    )
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
# ---------------------------------------------------------------------------
# Catalog table helpers (aliases for images table)
# ---------------------------------------------------------------------------

def init_catalog_table(db: sqlite3.Connection):
    """No-op: images table is created in init_database."""
    pass

def store_catalog_image(db: sqlite3.Connection, record: dict) -> str:
    """Store catalog image with analysis. Idempotent."""
    key = record.get('key')
    record['analyzed_at'] = datetime.now().isoformat()
    keywords = _serialize_json(record.get('keywords', []))
    exif = _serialize_json(record.get('exif'))

    db.execute("""
        INSERT INTO images (key, filepath, analyzed_at, phash, exif, catalog_path,
            date_taken, filename, rating, keywords, color_label, title, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            analyzed_at=excluded.analyzed_at,
            phash=COALESCE(excluded.phash, images.phash),
            exif=COALESCE(excluded.exif, images.exif),
            catalog_path=COALESCE(excluded.catalog_path, images.catalog_path),
            description=COALESCE(excluded.description, images.description)
    """, (
        key, record.get('filepath'), record['analyzed_at'],
        record.get('phash'), exif, record.get('catalog_path', ''),
        record.get('date_taken', ''), record.get('filename', ''),
        record.get('rating', 0), keywords,
        record.get('color_label', ''), record.get('title', ''),
        record.get('description', ''),
    ))
    db.commit()
    return key

def get_catalog_images_needing_analysis(db: sqlite3.Connection) -> list:
    """Get catalog images without phash."""
    rows = db.execute("SELECT * FROM images WHERE phash IS NULL").fetchall()
    return [_deserialize_row(r) for r in rows]

def get_catalog_images_missing_cache(db: sqlite3.Connection) -> list:
    """Get catalog images without vision cache entries.
    
    Returns images that either:
    - Don't have a cache entry at all
    - Have a cache entry but the compressed file doesn't exist
    """
    rows = db.execute("""
        SELECT i.* FROM images i
        LEFT JOIN vision_cache vc ON i.key = vc.key
        WHERE vc.key IS NULL OR vc.compressed_path IS NULL
    """).fetchall()
    
    images = [_deserialize_row(r) for r in rows]
    
    # Also check if cached files actually exist on disk
    cached_rows = db.execute("""
        SELECT i.*, vc.compressed_path FROM images i
        INNER JOIN vision_cache vc ON i.key = vc.key
        WHERE vc.compressed_path IS NOT NULL
    """).fetchall()
    
    for row in cached_rows:
        compressed_path = row.get('compressed_path', '')
        if compressed_path and not os.path.exists(compressed_path):
            images.append(_deserialize_row(row))
    
    return images

def get_all_catalog_images(db: sqlite3.Connection) -> list:
    """Get all catalog images with resolved file paths."""
    rows = db.execute(
        "SELECT * FROM images ORDER BY date_taken DESC, key DESC"
    ).fetchall()
    images = [_deserialize_row(r) for r in rows]
    for img in images:
        if img.get('filepath'):
            img['filepath'] = resolve_filepath(img['filepath'])
    return images
