import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from database import create_job, get_job, init_db
from jobs.runner import JobRunner


def test_job_runner_starts_job():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_db(db_path)

        runner = JobRunner(db)
        job_id = create_job(db, 'analyze_instagram', {'test': True})

        runner.start_job(job_id, 'analyze_instagram', {})

        job = get_job(db, job_id)
        assert job['status'] == 'running'
        assert job['started_at'] is not None

def test_job_runner_emits_progress_updates():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_db(db_path)

        progress_updates = []

        def mock_emit_progress(job_id, progress, step):
            progress_updates.append((progress, step))

        runner = JobRunner(db, emit_progress=mock_emit_progress)
        job_id = create_job(db, 'test_job', {})

        runner.update_progress(job_id, 50, 'Halfway done')

        assert len(progress_updates) == 1
        assert progress_updates[0] == (50, 'Halfway done')

        job = get_job(db, job_id)
        assert job['progress'] == 50
        assert job['current_step'] == 'Halfway done'

def test_job_runner_completes_job():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_db(db_path)

        runner = JobRunner(db)
        job_id = create_job(db, 'test_job', {})

        runner.complete_job(job_id, {'result': 'success'})

        job = get_job(db, job_id)
        assert job['status'] == 'completed'
        assert job['completed_at'] is not None
        assert job['result'] == {'result': 'success'}
