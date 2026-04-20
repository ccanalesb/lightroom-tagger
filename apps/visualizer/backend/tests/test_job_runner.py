import os
import sys
import tempfile
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from database import count_job_logs, create_job, get_job, init_db
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


def test_log_from_worker_uses_thread_local_connection():
    """Regression for the 3h stall on job 50710bf6: four worker log
    callbacks shared one sqlite3 connection, serializing on its internal
    mutex. The runner's :meth:`log_from_worker` must hand each thread its
    own connection so their appends don't block each other."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_db(db_path)

        runner = JobRunner(db, db_path=db_path)
        job_id = create_job(db, 'test_job', {})
        runner.start_job(job_id, 'test_job', {})
        baseline_log_count = count_job_logs(db, job_id)  # "Job started" entry

        barrier = threading.Barrier(4)
        errors: list[Exception] = []
        seen_conns: set[int] = set()
        seen_conns_lock = threading.Lock()

        def worker(thread_idx: int):
            try:
                barrier.wait()
                for i in range(25):
                    runner.log_from_worker(job_id, 'debug', f't{thread_idx} line {i}')
                conn = runner.thread_db()
                with seen_conns_lock:
                    seen_conns.add(id(conn))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, errors
        # Each worker saw its own connection object (one per thread).
        assert len(seen_conns) == 4
        # Every log made it through (plus the "started" row baseline)
        assert count_job_logs(db, job_id) == baseline_log_count + 4 * 25


def test_finalize_cancelled_is_idempotent_across_many_logs():
    """``finalize_cancelled`` used to load every log entry into memory just
    to scan for the stop marker — which was O(n) on a 20k-entry log. The
    new implementation must stay O(1) and still be idempotent (calling it
    twice after cancel shouldn't duplicate the stop-marker log)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_db(db_path)

        runner = JobRunner(db, db_path=db_path)
        job_id = create_job(db, 'test_job', {})
        runner.start_job(job_id, 'test_job', {})
        for i in range(500):
            runner.log_from_worker(job_id, 'debug', f'noise {i}')

        runner.signal_cancel(job_id)
        from database import update_job_status
        update_job_status(db, job_id, 'cancelled')

        runner.finalize_cancelled(job_id)
        after_first = count_job_logs(db, job_id)
        runner.finalize_cancelled(job_id)
        after_second = count_job_logs(db, job_id)
        assert after_first == after_second  # stop-marker not duplicated

        job = get_job(db, job_id, include_all_logs=True)
        stop_markers = [
            e for e in job['logs']
            if e['message'] == 'Job stopped after cancel request'
        ]
        assert len(stop_markers) == 1
