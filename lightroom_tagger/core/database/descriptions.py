"""Image description and FTS DB helpers."""

import json
import re
import sqlite3
from datetime import datetime

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


def _description_row_to_dict(row: dict) -> dict:
    """Detach and JSON-decode description columns."""
    out = dict(row)
    for col in (
        "composition",
        "perspectives",
        "technical",
        "subjects",
        "dominant_colors",
        "mood_tags",
    ):
        val = out.get(col)
        if isinstance(val, str):
            try:
                out[col] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                pass
    return out


def get_all_image_descriptions(db: sqlite3.Connection) -> list[dict]:
    """All rows from ``image_descriptions``."""
    rows = db.execute("SELECT * FROM image_descriptions").fetchall()
    return [_description_row_to_dict(r) for r in rows]


def get_image_descriptions_by_type(
    db: sqlite3.Connection, image_type: str
) -> list[dict]:
    """Description rows filtered by ``image_type`` (``catalog`` or ``instagram``)."""
    rows = db.execute(
        "SELECT * FROM image_descriptions WHERE image_type = ?",
        (image_type,),
    ).fetchall()
    return [_description_row_to_dict(r) for r in rows]
