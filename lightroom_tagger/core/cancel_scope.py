"""Thread-local cooperative cancellation scope.

A batch job worker registers a ``cancel_check`` callback for its current
thread; any deeper code (retry sleeps, fallback dispatcher) that wants to be
interruptible can read it without the signature plumbing that would otherwise
be required across five layers (runner → handler → description_service →
analyzer → dispatcher → retry).

Contract
--------
- ``install(check)`` sets the current thread's check and returns a handle that
  restores the previous value when closed. Use it as a context manager so
  exceptions always clean up:

      with install(lambda: runner.is_cancelled(job_id)):
          describe_matched_image(...)

- ``is_cancelled()`` returns ``False`` when no scope is active, so callers
  that are unaware of cancellation keep their old behavior.

The scope is *per-thread*. When a parallel batch dispatches each item to a
``ThreadPoolExecutor`` worker, each worker should install its own scope
(workers don't inherit thread-local state from the submitting thread).
"""

from __future__ import annotations

import contextlib
import threading
from collections.abc import Callable, Iterator

_checks: dict[int, Callable[[], bool]] = {}
_lock = threading.Lock()


def has_active_scope() -> bool:
    """Return True if the current thread has a cancel scope installed.

    Callers use this to decide whether to opt into cooperative cancel —
    e.g. ``retry_with_backoff`` stays in its legacy ``time.sleep(wait)``
    code path when nothing has subscribed.
    """
    tid = threading.get_ident()
    with _lock:
        return tid in _checks


def is_cancelled() -> bool:
    """Return True if a cancel has been requested for the current thread."""
    tid = threading.get_ident()
    # Snapshot the callback under the lock, then invoke it outside the lock —
    # the callback itself may do I/O (DB lookups) and we don't want to block
    # other threads while it runs.
    with _lock:
        check = _checks.get(tid)
    if check is None:
        return False
    try:
        return bool(check())
    except Exception:
        # A broken check must never wedge the worker: treat as "not cancelled"
        # so the caller keeps processing. This matches the historical
        # behavior before cancel_scope existed.
        return False


@contextlib.contextmanager
def install(check: Callable[[], bool]) -> Iterator[None]:
    """Install ``check`` as the cancel callback for the current thread.

    The previous callback (if any) is restored on exit so nested scopes
    compose — though in practice the batch handlers only install one scope
    at a time.
    """
    tid = threading.get_ident()
    with _lock:
        previous = _checks.get(tid)
        _checks[tid] = check
    try:
        yield
    finally:
        with _lock:
            if previous is None:
                _checks.pop(tid, None)
            else:
                _checks[tid] = previous


def clear() -> None:
    """Forcibly clear the current thread's scope (used by tests)."""
    tid = threading.get_ident()
    with _lock:
        _checks.pop(tid, None)
