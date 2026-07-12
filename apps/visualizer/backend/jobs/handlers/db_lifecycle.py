"""Patchable library-DB lifecycle helper for job handlers."""

from __future__ import annotations

import contextlib
import sqlite3
from collections.abc import Callable, Iterator


def make_managed_library_db(
    opener: Callable[[str], sqlite3.Connection],
) -> Callable[[str], contextlib.AbstractContextManager[sqlite3.Connection]]:
    """Return a ``managed_library_db`` CM built on ``opener``.

    Handlers pass a thunk such as ``lambda p: init_database(p)`` so the
    module-level ``init_database`` name is resolved at call time, keeping
    unit tests that patch ``jobs.handlers.<module>.init_database`` working.
    """

    @contextlib.contextmanager
    def managed_library_db(path: str) -> Iterator[sqlite3.Connection]:
        conn = opener(path)
        try:
            yield conn
        finally:
            conn.close()

    return managed_library_db
