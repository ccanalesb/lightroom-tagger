import threading

from database import add_job_log, get_job, update_job_field, update_job_status


class JobRunner:
    def __init__(self, db, emit_progress=None):
        self.db = db
        self.emit_progress = emit_progress or (lambda *args: None)
        self.active_jobs: dict[str, threading.Event] = {}

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
        """Update job progress."""
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
        return bool(ev and ev.is_set())

    def clear_cancel_registration(self, job_id: str) -> None:
        self.active_jobs.pop(job_id, None)

    def signal_cancel(self, job_id: str) -> None:
        """Set the cooperative cancel flag for a running job (no DB writes)."""
        if job_id in self.active_jobs:
            self.active_jobs[job_id].set()

    def finalize_cancelled(self, job_id: str) -> None:
        """Clear in-memory cancel state and ensure DB reflects cooperative cancel."""
        self.clear_cancel_registration(job_id)
        row = get_job(self.db, job_id)
        if not row:
            return
        logs = row.get('logs') or []
        stop_msg = 'Job stopped after cancel request'
        has_stop_msg = any(
            isinstance(entry, dict) and entry.get('message') == stop_msg for entry in logs
        )
        status = row.get('status')
        if status == 'running':
            update_job_status(self.db, job_id, 'cancelled')
            if not has_stop_msg:
                add_job_log(self.db, job_id, 'info', stop_msg)
        elif status == 'cancelled' and not has_stop_msg:
            add_job_log(self.db, job_id, 'info', stop_msg)
