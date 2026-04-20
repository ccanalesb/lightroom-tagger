import threading

from database import (
    add_job_log,
    get_job,
    job_log_has_message,
    make_connection_for_path,
    update_job_field,
    update_job_status,
)

from .checkpoint import merge_checkpoint_into_metadata


class JobRunner:
    """Coordinate job lifecycle across the processor thread and workers.

    Each thread that mutates the jobs DB through the runner should use its
    *own* sqlite3 connection. The runner carries a ``db_path`` for that
    purpose; call :meth:`thread_db` (or pass one of the logging helpers the
    runner exposes) and you'll get a thread-local connection. ``self.db``
    remains the connection belonging to whichever thread constructed the
    runner (typically the processor thread) so existing single-threaded
    call sites are unaffected.
    """

    def __init__(self, db, emit_progress=None, *, db_path: str | None = None):
        self.db = db
        # Path is optional for legacy tests that build a JobRunner directly
        # from a connection. Production paths pass ``db_path`` so the runner
        # can hand out thread-local connections to worker threads.
        self.db_path = db_path
        self.emit_progress = emit_progress or (lambda *args: None)
        self.active_jobs: dict[str, threading.Event] = {}

    # ------------------------------------------------------------------
    # Thread-local DB handle
    # ------------------------------------------------------------------
    def thread_db(self):
        """Return a sqlite3 connection owned by the calling thread.

        Worker threads must never share ``self.db`` — that was the root
        cause of the 3h main-thread stall observed on job 50710bf6, where
        four worker log callbacks and the coordinator loop all serialized
        on a single connection's internal mutex.
        """
        if self.db_path is None:
            # Legacy callers that built the runner without a path fall back
            # to the shared connection. Only safe from the owning thread,
            # and that is exactly how the old tests use it.
            return self.db
        return make_connection_for_path(self.db_path)

    def log_from_worker(self, job_id: str, level: str, message: str) -> None:
        """Append a log entry using the *calling thread's* connection.

        Workers pump hundreds of debug messages per minute; routing them
        through ``self.db`` would re-serialize everything on one mutex.
        """
        add_job_log(self.thread_db(), job_id, level, message)

    def start_job(self, job_id: str, job_type: str, metadata: dict) -> bool:
        """Mark job as running. Returns False if the job row is gone or already cancelled."""
        row = get_job(self.db, job_id)
        if not row or row.get('status') == 'cancelled':
            return False
        cancel_event = threading.Event()
        self.active_jobs[job_id] = cancel_event
        update_job_status(self.db, job_id, 'running', progress=0, current_step='Starting...')
        add_job_log(self.db, job_id, 'info', f'Job {job_type} started')
        return True

    def update_progress(self, job_id: str, progress: int, current_step: str):
        """Update job progress. No-op if the job has been cancelled or already completed."""
        if self.is_cancelled(job_id):
            return
        row = get_job(self.db, job_id)
        if row and row.get('status') in ('completed', 'cancelled'):
            return
        update_job_status(self.db, job_id, 'running', progress=progress, current_step=current_step)
        add_job_log(self.db, job_id, 'info', current_step)
        self.emit_progress(job_id, progress, current_step)

    def complete_job(self, job_id: str, result: dict):
        """Mark job as completed."""
        row = get_job(self.db, job_id)
        if row and row.get('status') == 'cancelled':
            self.clear_cancel_registration(job_id)
            return
        update_job_status(self.db, job_id, 'completed', progress=100)
        add_job_log(self.db, job_id, 'info', 'Job completed successfully')

        update_job_field(self.db, job_id, 'result', result)
        self.db.execute(
            "UPDATE jobs SET error_severity = NULL WHERE id = ?",
            (job_id,),
        )
        self.db.commit()
        self.clear_cancel_registration(job_id)

    def fail_job(self, job_id: str, error: str, *, severity: str = 'error') -> None:
        """Mark job as failed."""
        if severity not in ('warning', 'error', 'critical'):
            severity = 'error'
        row = get_job(self.db, job_id)
        if row and row.get('status') == 'cancelled':
            self.clear_cancel_registration(job_id)
            return
        update_job_status(self.db, job_id, 'failed')
        add_job_log(self.db, job_id, 'error', error)

        self.db.execute(
            "UPDATE jobs SET error = ?, error_severity = ? WHERE id = ?",
            (error, severity, job_id),
        )
        self.db.commit()
        self.clear_cancel_registration(job_id)

    def is_cancelled(self, job_id: str) -> bool:
        ev = self.active_jobs.get(job_id)
        if ev and ev.is_set():
            return True
        row = get_job(self.db, job_id)
        if row and row.get('status') == 'cancelled':
            if ev:
                ev.set()
            return True
        return False

    def clear_cancel_registration(self, job_id: str) -> None:
        self.active_jobs.pop(job_id, None)

    def persist_checkpoint(self, job_id: str, checkpoint_body: dict) -> None:
        """Merge versioned checkpoint data into ``jobs.metadata`` (jobs DB)."""
        row = get_job(self.db, job_id)
        if not row:
            return
        meta = row.get("metadata") or {}
        if not isinstance(meta, dict):
            meta = {}
        new_meta = merge_checkpoint_into_metadata(meta, checkpoint_body)
        update_job_field(self.db, job_id, "metadata", new_meta)

    def clear_checkpoint(self, job_id: str) -> None:
        """Remove resume checkpoint from job metadata (e.g. after successful completion)."""
        row = get_job(self.db, job_id)
        if not row:
            return
        meta = row.get("metadata") or {}
        if not isinstance(meta, dict):
            meta = {}
        new_meta = {**meta, "checkpoint": None}
        update_job_field(self.db, job_id, "metadata", new_meta)

    def signal_cancel(self, job_id: str) -> None:
        """Set the cooperative cancel flag for a running job (no DB writes)."""
        if job_id in self.active_jobs:
            self.active_jobs[job_id].set()

    def finalize_cancelled(self, job_id: str) -> None:
        """Clear in-memory cancel state and ensure DB reflects cooperative cancel."""
        self.clear_cancel_registration(job_id)
        # Avoid pulling the full logs — ``job_log_has_message`` is an
        # index-backed ``LIMIT 1`` lookup so this is fast even when a job
        # has accumulated 20k+ log rows.
        row = get_job(self.db, job_id, logs_limit=0)
        if not row:
            return
        stop_msg = 'Job stopped after cancel request'
        has_stop_msg = job_log_has_message(self.db, job_id, stop_msg)
        status = row.get('status')
        if status == 'running':
            update_job_status(self.db, job_id, 'cancelled')
            if not has_stop_msg:
                add_job_log(self.db, job_id, 'info', stop_msg)
        elif status == 'cancelled' and not has_stop_msg:
            add_job_log(self.db, job_id, 'info', stop_msg)
