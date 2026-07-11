"""Lifecycle context managers for library DB and Lightroom catalog connections."""

from __future__ import annotations

import contextlib
import sqlite3
from collections.abc import Iterator

from lightroom_tagger.core.database.db_init import init_database
from lightroom_tagger.lightroom.reader import connect_catalog


@contextlib.contextmanager
def managed_library_db(path: str) -> Iterator[sqlite3.Connection]:
    """Open ``path`` via :func:`init_database` and close on exit."""
    conn = init_database(path)
    try:
        yield conn
    finally:
        conn.close()


@contextlib.contextmanager
def managed_catalog(path: str) -> Iterator[sqlite3.Connection]:
    """Open ``path`` via :func:`connect_catalog` and close on exit."""
    conn = connect_catalog(path)
    try:
        yield conn
    finally:
        conn.close()
