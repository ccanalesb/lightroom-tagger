import json
import os
import sqlite3
import uuid
from datetime import datetime


def _dict_factory(cursor, row):
    fields = [column[0] for column in cursor.description]
    return dict(zip(fields, row))


def _deserialize_job(row: dict) -> dict | None:
    if not row:
        return None
    for col in ('logs', 'metadata', 'result'):
        val = row.get(col)
        if isinstance(val, str):
            try:
                row[col] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                pass
    return row


def init_db(db_path: str) -> sqlite3.Connection:
    """Initialize visualizer database with jobs table."""
    parent_dir = os.path.dirname(db_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = _dict_factory
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
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
        CREATE TABLE IF NOT EXISTS provider_models (
            provider_id TEXT NOT NULL,
            model_id TEXT NOT NULL,
            model_name TEXT NOT NULL,
            vision INTEGER DEFAULT 1,
            PRIMARY KEY (provider_id, model_id)
        )
    """)
    conn.commit()
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


def get_job(db: sqlite3.Connection, job_id: str) -> dict | None:
    """Get job by ID."""
    row = db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
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
    """Add log entry to job."""
    job = get_job(db, job_id)
    if not job:
        return
    logs = job.get('logs', [])
    logs.append({
        'timestamp': datetime.now().isoformat(),
        'level': level,
        'message': message,
    })
    db.execute("UPDATE jobs SET logs = ? WHERE id = ?", (json.dumps(logs), job_id))
    db.commit()


_ALLOWED_JOB_UPDATE_FIELDS = frozenset({
    "metadata", "result", "error", "logs",
})


def update_job_field(db: sqlite3.Connection, job_id: str, field: str, value) -> None:
    """Update a single JSON-serializable field on a job."""
    if field not in _ALLOWED_JOB_UPDATE_FIELDS:
        raise ValueError(f"Unsupported job field: {field!r}")
    column = field  # safe: whitelisted only
    serialized = json.dumps(value) if not isinstance(value, str) else value
    db.execute(f"UPDATE jobs SET {column} = ? WHERE id = ?", (serialized, job_id))
    db.commit()


def list_jobs(db: sqlite3.Connection, status: str = None, limit: int = 50, offset: int = 0) -> list:
    """List jobs, optionally filtered by status, paginated via limit/offset."""
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
    return [_deserialize_job(r) for r in rows]


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
    """Get all active jobs (pending or running)."""
    rows = db.execute(
        "SELECT * FROM jobs WHERE status IN ('running', 'pending')"
    ).fetchall()
    return [_deserialize_job(r) for r in rows]


def get_pending_jobs(db: sqlite3.Connection) -> list:
    """Get all pending jobs."""
    rows = db.execute("SELECT * FROM jobs WHERE status = 'pending'").fetchall()
    return [_deserialize_job(r) for r in rows]


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


