from database import add_job_log, update_job_status
from tinydb import Query


class JobRunner:
    def __init__(self, db, emit_progress=None):
        self.db = db
        self.emit_progress = emit_progress or (lambda *args: None)
        self.active_jobs = {}

    def start_job(self, job_id: str, job_type: str, metadata: dict):
        """Mark job as running."""
        update_job_status(self.db, job_id, 'running', progress=0, current_step='Starting...')
        add_job_log(self.db, job_id, 'info', f'Job {job_type} started')

    def update_progress(self, job_id: str, progress: int, current_step: str):
        """Update job progress."""
        update_job_status(self.db, job_id, 'running', progress=progress, current_step=current_step)
        add_job_log(self.db, job_id, 'info', current_step)
        self.emit_progress(job_id, progress, current_step)

    def complete_job(self, job_id: str, result: dict):
        """Mark job as completed."""
        update_job_status(self.db, job_id, 'completed', progress=100)
        add_job_log(self.db, job_id, 'info', 'Job completed successfully')

        self.db.table('jobs').update({'result': result}, Query().id == job_id)

    def fail_job(self, job_id: str, error: str):
        """Mark job as failed."""
        update_job_status(self.db, job_id, 'failed')
        add_job_log(self.db, job_id, 'error', error)

        self.db.table('jobs').update({'error': error}, Query().id == job_id)

    def cancel_job(self, job_id: str):
        """Cancel a running job."""
        if job_id in self.active_jobs:
            self.active_jobs[job_id].cancel()
        update_job_status(self.db, job_id, 'cancelled')
        add_job_log(self.db, job_id, 'info', 'Job cancelled')
