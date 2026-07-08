"""Perspective and image score DB helpers."""

import re
import sqlite3
from datetime import datetime, timezone

# The yt-to-photo-prompt-lab exporter marks an optional (excusable) dimension with
# an HTML comment in the perspective markdown. This marker is the sole source of
# truth for ``perspectives.optional``: it is re-derived on every write of
# ``prompt_markdown`` (seed, create, edit, reset-to-default) so a changed marker
# always wins and cannot drift. See ADR-0005.
_OPTIONAL_MARKER_RE = re.compile(r"<!--\s*optional\s*:\s*true\s*-->", re.IGNORECASE)


def markdown_marks_optional(markdown: str) -> bool:
    """Whether perspective markdown opts into the excusable (not-attempted) contract."""
    return bool(_OPTIONAL_MARKER_RE.search(markdown or ""))

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
    """Insert a ``perspectives`` row. Caller commits.

    ``optional`` (excusable) is derived from the ``prompt_markdown`` marker, never
    passed in: an optional perspective may be scored ``not_attempted`` and such
    excused rows are excluded from identity aggregation. See ADR-0005.
    """
    now = datetime.now(timezone.utc).isoformat()
    optional = markdown_marks_optional(prompt_markdown)
    conn.execute(
        """
        INSERT INTO perspectives (
            slug, display_name, description, prompt_markdown,
            active, optional, source_filename, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            slug,
            display_name,
            description,
            prompt_markdown,
            1 if active else 0,
            1 if optional else 0,
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
    """Partially update a perspective by ``slug``. Returns whether a row was updated.

    ``optional`` is not a parameter: whenever ``prompt_markdown`` is written, it is
    re-derived from the markdown marker so the marker stays authoritative (a removed
    marker un-sets optional). Updates that don't touch the markdown leave it. See ADR-0005.
    """
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
        fields.append("optional = ?")
        values.append(1 if markdown_marks_optional(prompt_markdown) else 0)
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
            repaired_from_malformed, not_attempted
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            int(row.get("not_attempted", 0)),
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


def get_all_current_perspective_slugs(conn: sqlite3.Connection) -> list[str]:
    """Distinct perspective slugs with at least one current score row."""
    rows = conn.execute(
        "SELECT DISTINCT perspective_slug FROM image_scores "
        "WHERE is_current = 1 ORDER BY perspective_slug"
    ).fetchall()
    return [str(r["perspective_slug"]) for r in rows]


def get_available_score_perspectives_for_image(
    conn: sqlite3.Connection, image_key: str, image_type: str = "catalog"
) -> list[str]:
    """Current-score perspective slugs available for one image."""
    rows = conn.execute(
        "SELECT DISTINCT perspective_slug FROM image_scores "
        "WHERE image_key = ? AND image_type = ? AND is_current = 1 "
        "ORDER BY perspective_slug",
        (image_key, image_type),
    ).fetchall()
    return [str(r["perspective_slug"]) for r in rows]
