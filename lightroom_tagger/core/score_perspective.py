"""Validate ``score_perspective`` values by catalog row existence."""

from __future__ import annotations

import sqlite3

from lightroom_tagger.core.database import get_perspective_by_slug


def validate_score_perspective_exists(
    db: sqlite3.Connection,
    slug: str | None,
) -> tuple[str | None, str | None]:
    """Return ``(normalized_slug, error_message)``.

    Empty/absent slug → ``(None, None)``. Unknown slug → ``(None, "unknown perspective '…'")``.
    Existence is satisfied by any row in ``perspectives``, regardless of ``active``.
    """
    sp = (slug or "").strip() or None
    if sp is None:
        return None, None
    if get_perspective_by_slug(db, sp) is None:
        return None, f"unknown perspective '{sp}'"
    return sp, None
