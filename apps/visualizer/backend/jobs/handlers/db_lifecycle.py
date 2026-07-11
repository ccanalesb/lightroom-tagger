"""Patchable library-DB lifecycle helper for job handlers."""

from __future__ import annotations

import contextlib
import sqlite3
from collections.abc import Iterator


def make_managed_library_db(module_globals: dict) -> contextlib.AbstractContextManager[sqlite3.Connection]:
    """Return a ``managed_library_db`` CM that resolves ``init_database`` at call time.

    Handler modules pass ``globals()`` so unit tests can keep patching
    ``jobs.handlers.<module>.init_database`` unchanged.
    """

    @contextlib.contextmanager
    def managed_library_db(path: str) -> Iterator[sqlite3.Connection]:
        conn = module_globals['init_database'](path)
        try:
            yield conn
        finally:
            conn.close()

    return managed_library_db
