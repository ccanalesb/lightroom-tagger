import os
import uuid
from datetime import datetime

from tinydb import Query, TinyDB


def init_db(db_path: str) -> TinyDB:
    """Initialize database with jobs table."""
    parent_dir = os.path.dirname(db_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)
    db = TinyDB(db_path)
    return db

def create_job(db: TinyDB, job_type: str, metadata: dict) -> str:
    """Create a new job and return job ID."""
    job_id = str(uuid.uuid4())

    job = {
        'id': job_id,
        'type': job_type,
        'status': 'pending',
        'progress': 0,
        'current_step': None,
        'logs': [],
        'result': None,
        'error': None,
        'created_at': datetime.now().isoformat(),
        'started_at': None,
        'completed_at': None,
        'metadata': metadata
    }

    db.table('jobs').insert(job)
    return job_id

def get_job(db: TinyDB, job_id: str) -> dict:
    """Get job by ID."""
    Job = Query()
    results = db.table('jobs').search(Job.id == job_id)
    return results[0] if results else None

def update_job_status(db: TinyDB, job_id: str, status: str,
                      progress: int = None, current_step: str = None):
    """Update job status, progress, and step."""
    Job = Query()
    updates = {'status': status}

    if progress is not None:
        updates['progress'] = progress
    if current_step is not None:
        updates['current_step'] = current_step

    if status == 'running':
        updates['started_at'] = datetime.now().isoformat()
    elif status in ['completed', 'failed', 'cancelled']:
        updates['completed_at'] = datetime.now().isoformat()

    db.table('jobs').update(updates, Job.id == job_id)

def add_job_log(db: TinyDB, job_id: str, level: str, message: str):
    """Add log entry to job."""
    job = get_job(db, job_id)
    if not job:
        return

    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'level': level,
        'message': message
    }

    logs = job.get('logs', [])
    logs.append(log_entry)

    Job = Query()
    db.table('jobs').update({'logs': logs}, Job.id == job_id)

def list_jobs(db: TinyDB, status: str = None, limit: int = 50) -> list:
    """List jobs, optionally filtered by status."""
    Job = Query()

    results = db.table('jobs').search(Job.status == status) if status else db.table('jobs').all()

    return sorted(results, key=lambda j: j['created_at'], reverse=True)[:limit]

def get_active_jobs(db: TinyDB) -> list:
    """Get all active jobs (pending or running)."""
    Job = Query()
    return db.table('jobs').search(
        (Job.status == 'running') | (Job.status == 'pending')
    )


def get_pending_jobs(db: TinyDB) -> list:
    """Get all pending jobs."""
    Job = Query()
    return db.table('jobs').search(Job.status == 'pending')
