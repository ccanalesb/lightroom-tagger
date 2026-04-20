import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime

# Default tail length returned by ``get_job`` when callers don't ask for the
# full history. Chosen to be large enough to cover the active window of a
# long-running job (progress updates, recent warnings) while keeping the
# row-read cost constant as total log volume grows. Callers that need the
# full history pass ``include_all_logs=True`` explicitly.
DEFAULT_LOG_TAIL = 1000

# Internal marker used on dict rows to tell ``_deserialize_job`` the caller
# has already loaded ``logs`` and it should not overwrite them.
_LOGS_PRELOADED = object()


def _dict_factory(cursor, row):
    fields = [column[0] for column in cursor.description]
    return dict(zip(fields, row))


def _deserialize_job(row: dict) -> dict | None:
    """Normalize a raw ``jobs`` row.

    ``logs`` is intentionally not derived from the legacy JSON blob here; the
    caller is expected to attach a list loaded from the ``job_logs`` table (or
    leave it as-is if it was pre-populated by :func:`get_job`). If the row
    predates the migration and still has a JSON-array string for ``logs``, we
    decode it best-effort so tests that insert rows directly keep working.
    """
    if not row:
        return None
    for col in ('metadata', 'result'):
        val = row.get(col)
        if isinstance(val, str):
            try:
                row[col] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                pass
    if 'logs' in row:
        val = row.get('logs')
        if val is _LOGS_PRELOADED:
            pass  # caller already attached a list
        elif isinstance(val, str):
            # Legacy row that still carries the JSON-blob logs column. Decode
            # so the surface stays compatible for callers that haven't been
            # migrated yet.
            try:
                row['logs'] = json.loads(val) if val else []
            except (json.JSONDecodeError, TypeError):
                row['logs'] = []
        elif val is None:
            row['logs'] = []
    return row


# ----------------------------------------------------------------------------
# Schema — see module docstring for the redesign rationale.
#
# Old layout (removed): ``jobs.logs`` was a growing JSON array on the row.
# Every ``add_job_log`` call did ``SELECT logs → json.loads → append →
# json.dumps → UPDATE``. For a scoring job with 15k+ log entries the
# rewrite cost approached O(n²) and the single shared sqlite3 connection —
# used by the main thread, four worker log callbacks, and HTTP handlers —
# serialized on those writes, starving the executor-coordinator main thread
# and wedging long-running jobs (~3h stall observed in production).
#
# New layout: append-only ``job_logs`` table with ``(job_id, id)`` index.
# ``add_job_log`` is a single INSERT. Tail reads are a bounded ``ORDER BY
# id DESC LIMIT N``. Works the same way across threads.
# ----------------------------------------------------------------------------


def _apply_connection_pragmas(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    # Matches the library DB — see ``lightroom_tagger.core.database.init_database``
    # for rationale. The jobs DB is smaller and less contended than the
    # library DB, but workers, the processor coordinator, and HTTP polling
    # all contend for the writer seat when a batch is running.
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA synchronous=NORMAL")


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            progress INTEGER DEFAULT 0,
            current_step TEXT,
            logs TEXT DEFAULT '[]',
            result TEXT,
            error TEXT,
            error_severity TEXT,
            created_at TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT,
            metadata TEXT DEFAULT '{}'
        )
    """)
    pragma_info = conn.execute("PRAGMA table_info(jobs)").fetchall()
    if not any(row["name"] == "error_severity" for row in pragma_info):
        conn.execute("ALTER TABLE jobs ADD COLUMN error_severity TEXT")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_type ON jobs(type)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS job_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            ts TEXT NOT NULL,
            level TEXT NOT NULL,
            message TEXT NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_job_logs_job_id_id ON job_logs(job_id, id)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS provider_models (
            provider_id TEXT NOT NULL,
            model_id TEXT NOT NULL,
            model_name TEXT NOT NULL,
            vision INTEGER DEFAULT 1,
            PRIMARY KEY (provider_id, model_id)
        )
    """)
    conn.commit()


def _migrate_legacy_logs(conn: sqlite3.Connection) -> int:
    """One-time backfill: fold any legacy ``jobs.logs`` JSON arrays into
    the new ``job_logs`` table and null the old column.

    Idempotent: rows whose ``logs`` column is already NULL or empty are
    skipped. Returns the number of rows migrated (useful for tests).
    """
    legacy_rows = conn.execute(
        "SELECT id, logs FROM jobs WHERE logs IS NOT NULL AND logs != '' AND logs != '[]'"
    ).fetchall()
    migrated = 0
    for row in legacy_rows:
        raw = row["logs"] if isinstance(row, dict) else row[1]
        job_id = row["id"] if isinstance(row, dict) else row[0]
        try:
            entries = json.loads(raw) if raw else []
        except (json.JSONDecodeError, TypeError):
            entries = []
        if not isinstance(entries, list):
            entries = []
        if entries:
            conn.executemany(
                "INSERT INTO job_logs (job_id, ts, level, message) VALUES (?, ?, ?, ?)",
                [
                    (
                        job_id,
                        e.get('timestamp') or datetime.now().isoformat(),
                        e.get('level') or 'info',
                        e.get('message') or '',
                    )
                    for e in entries
                    if isinstance(e, dict)
                ],
            )
            migrated += 1
        conn.execute("UPDATE jobs SET logs = '[]' WHERE id = ?", (job_id,))
    if legacy_rows:
        conn.commit()
    return migrated


# Thread-local storage for per-thread connections created by
# :func:`make_connection_for_path`. We cache by path so the same thread can
# open separate connections to different DBs (jobs DB vs tests' tmp DB).
_TLS = threading.local()


def make_connection_for_path(db_path: str) -> sqlite3.Connection:
    """Return a connection owned by the calling thread for ``db_path``.

    The old design shared a single ``sqlite3.Connection`` across the Flask
    request handlers, the job-processor main thread, and every worker
    thread. Under load this serialized all ops on Python's connection mutex
    and was the proximate cause of the 3-hour wedge observed on job
    ``50710bf6``. Giving each thread its own connection lets SQLite itself
    (WAL + ``busy_timeout``) be the only coordination point.

    Safe to call multiple times per thread — subsequent calls for the same
    path return the cached connection.
    """
    cache = getattr(_TLS, 'conns', None)
    if cache is None:
        cache = {}
        _TLS.conns = cache
    conn = cache.get(db_path)
    if conn is not None:
        return conn
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = _dict_factory
    _apply_connection_pragmas(conn)
    cache[db_path] = conn
    return conn


def init_db(db_path: str) -> sqlite3.Connection:
    """Initialize visualizer database with jobs + job_logs tables.

    Returns a connection owned by the calling thread. Other threads should
    call :func:`make_connection_for_path` to get their own.
    """
    parent_dir = os.path.dirname(db_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)
    conn = make_connection_for_path(db_path)
    _ensure_schema(conn)
    _migrate_legacy_logs(conn)
    return conn


def clear_job_failure_details(db: sqlite3.Connection, job_id: str) -> None:
    """Clear persisted failure message and severity for a job."""
    db.execute(
        "UPDATE jobs SET error = NULL, error_severity = NULL WHERE id = ?",
        (job_id,),
    )
    db.commit()


def create_job(db: sqlite3.Connection, job_type: str, metadata: dict) -> str:
    """Create a new job and return job ID."""
    job_id = str(uuid.uuid4())
    db.execute("""
        INSERT INTO jobs (id, type, status, progress, current_step, logs, result,
            error, created_at, started_at, completed_at, metadata)
        VALUES (?, ?, 'pending', 0, NULL, '[]', NULL, NULL, ?, NULL, NULL, ?)
    """, (job_id, job_type, datetime.now().isoformat(), json.dumps(metadata)))
    db.commit()
    return job_id


def _load_logs_tail(
    db: sqlite3.Connection,
    job_id: str,
    *,
    limit: int | None,
) -> list[dict]:
    """Return the most recent log entries for ``job_id`` in chronological order.

    ``limit=None`` returns every entry (used by callers that truly need the
    whole history, typically tests or recovery diagnostics). Otherwise we
    select the tail with a single index-backed query.
    """
    if limit is None:
        rows = db.execute(
            "SELECT ts, level, message FROM job_logs WHERE job_id = ? ORDER BY id ASC",
            (job_id,),
        ).fetchall()
    else:
        if limit <= 0:
            return []
        rows = db.execute(
            "SELECT ts, level, message FROM job_logs "
            "WHERE job_id = ? ORDER BY id DESC LIMIT ?",
            (job_id, limit),
        ).fetchall()
        rows = list(reversed(rows))
    return [
        {
            'timestamp': r['ts'] if isinstance(r, dict) else r[0],
            'level': r['level'] if isinstance(r, dict) else r[1],
            'message': r['message'] if isinstance(r, dict) else r[2],
        }
        for r in rows
    ]


def count_job_logs(db: sqlite3.Connection, job_id: str) -> int:
    row = db.execute(
        "SELECT COUNT(*) AS c FROM job_logs WHERE job_id = ?", (job_id,)
    ).fetchone()
    return int(row["c"]) if row else 0


def get_job(
    db: sqlite3.Connection,
    job_id: str,
    *,
    logs_limit: int | None = DEFAULT_LOG_TAIL,
    include_all_logs: bool = False,
) -> dict | None:
    """Get job by ID with logs attached as a list.

    Parameters
    ----------
    logs_limit:
        Maximum number of recent log entries to attach (chronological). The
        default (``DEFAULT_LOG_TAIL``) is enough for the UI's modal view and
        keeps every row-read O(tail) rather than O(total-history).
    include_all_logs:
        Load the full history, overriding ``logs_limit``. Used by the jobs
        API when the client explicitly asks for all logs (``logs_limit=0``),
        and by recovery paths that scan for specific historical messages.
    """
    row = db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        return None
    effective_limit = None if include_all_logs else logs_limit
    logs = _load_logs_tail(db, job_id, limit=effective_limit)
    # Overwrite the legacy JSON-blob column before deserialize runs so
    # ``_deserialize_job`` doesn't attempt to parse it.
    row = dict(row)
    row['logs'] = logs
    return _deserialize_job(row)


def update_job_status(db: sqlite3.Connection, job_id: str, status: str,
                      progress: int = None, current_step: str = None):
    """Update job status, progress, and step."""
    sets = ["status = ?"]
    params = [status]

    if progress is not None:
        sets.append("progress = ?")
        params.append(progress)
    if current_step is not None:
        sets.append("current_step = ?")
        params.append(current_step)
    if status == 'running':
        sets.append("started_at = ?")
        params.append(datetime.now().isoformat())
    elif status in ('completed', 'failed', 'cancelled'):
        sets.append("completed_at = ?")
        params.append(datetime.now().isoformat())

    params.append(job_id)
    where = "id = ?"
    if status == 'running':
        where += " AND status != 'cancelled'"
    db.execute(f"UPDATE jobs SET {', '.join(sets)} WHERE {where}", params)
    db.commit()


def add_job_log(db: sqlite3.Connection, job_id: str, level: str, message: str):
    """Append a single log entry to ``job_logs`` for ``job_id``.

    O(1) insert regardless of prior log volume. Silently no-ops if the job
    row no longer exists so worker threads that race a cancellation don't
    crash.
    """
    exists = db.execute(
        "SELECT 1 FROM jobs WHERE id = ? LIMIT 1", (job_id,)
    ).fetchone()
    if not exists:
        return
    db.execute(
        "INSERT INTO job_logs (job_id, ts, level, message) VALUES (?, ?, ?, ?)",
        (job_id, datetime.now().isoformat(), level, message),
    )
    db.commit()


def job_log_has_message(
    db: sqlite3.Connection, job_id: str, message: str
) -> bool:
    """Cheap exact-match lookup used by cancel/recovery paths that would
    otherwise load the full log history just to check a single marker.
    """
    row = db.execute(
        "SELECT 1 FROM job_logs WHERE job_id = ? AND message = ? LIMIT 1",
        (job_id, message),
    ).fetchone()
    return row is not None


def delete_job_logs(db: sqlite3.Connection, job_id: str) -> int:
    """Remove all log entries for ``job_id``. Returns rows deleted."""
    cur = db.execute("DELETE FROM job_logs WHERE job_id = ?", (job_id,))
    db.commit()
    return cur.rowcount or 0


_ALLOWED_JOB_UPDATE_FIELDS = frozenset({
    # ``logs`` deliberately removed — log entries live in ``job_logs`` now.
    # Writing to the legacy ``logs`` column is still supported by the
    # migration path on startup, but not via this generic update helper.
    "metadata", "result", "error", "current_step",
})


def update_job_field(db: sqlite3.Connection, job_id: str, field: str, value) -> None:
    """Update a single JSON-serializable field on a job."""
    if field not in _ALLOWED_JOB_UPDATE_FIELDS:
        raise ValueError(f"Unsupported job field: {field!r}")
    column = field  # safe: whitelisted only
    serialized = json.dumps(value) if not isinstance(value, str) else value
    db.execute(f"UPDATE jobs SET {column} = ? WHERE id = ?", (serialized, job_id))
    db.commit()


def list_jobs(
    db: sqlite3.Connection,
    status: str = None,
    limit: int = 50,
    offset: int = 0,
    *,
    include_logs: bool = False,
) -> list:
    """List jobs, optionally filtered by status, paginated via limit/offset.

    Logs are **not** loaded by default: a listing of 50 running jobs used to
    pull tens of megabytes of log history off the row. When ``include_logs``
    is true we attach a per-job tail using :func:`_load_logs_tail` (capped at
    ``DEFAULT_LOG_TAIL``).
    """
    if status:
        rows = db.execute(
            "SELECT * FROM jobs WHERE status = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (status, limit, offset)
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        ).fetchall()
    results = []
    for r in rows:
        r = dict(r)
        if include_logs:
            r['logs'] = _load_logs_tail(db, r['id'], limit=DEFAULT_LOG_TAIL)
        else:
            r['logs'] = []
        results.append(_deserialize_job(r))
    return results


def count_jobs(db: sqlite3.Connection, status: str = None) -> int:
    """Count jobs, optionally filtered by status."""
    if status:
        row = db.execute(
            "SELECT COUNT(*) AS c FROM jobs WHERE status = ?", (status,)
        ).fetchone()
    else:
        row = db.execute("SELECT COUNT(*) AS c FROM jobs").fetchone()
    return int(row["c"]) if row else 0


def get_active_jobs(db: sqlite3.Connection) -> list:
    """Get all active jobs (pending or running). Logs are **not** attached —
    this is used by orphan-recovery and processor loops, neither of which
    needs the log history.
    """
    rows = db.execute(
        "SELECT * FROM jobs WHERE status IN ('running', 'pending')"
    ).fetchall()
    results = []
    for r in rows:
        r = dict(r)
        r['logs'] = []
        results.append(_deserialize_job(r))
    return results


def get_pending_jobs(db: sqlite3.Connection) -> list:
    """Get all pending jobs. Logs omitted for the same reason as
    :func:`get_active_jobs`."""
    rows = db.execute("SELECT * FROM jobs WHERE status = 'pending'").fetchall()
    results = []
    for r in rows:
        r = dict(r)
        r['logs'] = []
        results.append(_deserialize_job(r))
    return results


def get_user_models(
    db: sqlite3.Connection, provider_id: str | None = None
) -> list[dict]:
    """List user-added provider models, optionally filtered by provider."""
    if provider_id is not None:
        rows = db.execute(
            """
            SELECT provider_id, model_id, model_name, vision
            FROM provider_models
            WHERE provider_id = ?
            ORDER BY model_id
            """,
            (provider_id,),
        ).fetchall()
    else:
        rows = db.execute(
            """
            SELECT provider_id, model_id, model_name, vision
            FROM provider_models
            ORDER BY provider_id, model_id
            """
        ).fetchall()
    return [
        user_model_row
        if isinstance(user_model_row, dict)
        else {key: user_model_row[key] for key in user_model_row.keys()}
        for user_model_row in rows
    ]


def add_user_model(
    db: sqlite3.Connection,
    provider_id: str,
    model_id: str,
    model_name: str,
    vision: bool = True,
) -> None:
    """Insert a user-defined model row. Raises sqlite3.IntegrityError on duplicate."""
    db.execute(
        """
        INSERT INTO provider_models (provider_id, model_id, model_name, vision)
        VALUES (?, ?, ?, ?)
        """,
        (provider_id, model_id, model_name, 1 if vision else 0),
    )
    db.commit()


def delete_user_model(
    db: sqlite3.Connection, provider_id: str, model_id: str
) -> bool:
    """Delete a user-defined model. Returns True if a row was removed."""
    cur = db.execute(
        "DELETE FROM provider_models WHERE provider_id = ? AND model_id = ?",
        (provider_id, model_id),
    )
    db.commit()
    return cur.rowcount > 0


