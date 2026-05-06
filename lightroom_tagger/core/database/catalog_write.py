"""Single-writer serialization for `library.db` updates."""

from __future__ import annotations

import contextlib
import sqlite3
import threading
import time


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
