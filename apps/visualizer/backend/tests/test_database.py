import json
import os
import sqlite3
import tempfile
import threading

import pytest

from database import (
    DEFAULT_LOG_TAIL,
    add_job_log,
    count_job_logs,
    create_job,
    delete_job_logs,
    get_job,
    init_db,
    job_log_has_message,
    list_jobs,
    make_connection_for_path,
    update_job_field,
    update_job_status,
)


def test_create_job():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_db(db_path)

        job_id = create_job(db, 'analyze_instagram', {'post_url': 'https://instagram.com/p/ABC'})

        assert job_id is not None
        job = get_job(db, job_id)
        assert job['type'] == 'analyze_instagram'
        assert job['status'] == 'pending'
        assert job['progress'] == 0

def test_update_job_status():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_db(db_path)

        job_id = create_job(db, 'vision_match', {})
        update_job_status(db, job_id, 'running', progress=25, current_step='Processing image 1/100')

        job = get_job(db, job_id)
        assert job['status'] == 'running'
        assert job['progress'] == 25
        assert job['current_step'] == 'Processing image 1/100'

def test_add_job_log():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_db(db_path)

        job_id = create_job(db, 'vision_match', {})
        add_job_log(db, job_id, 'info', 'Starting vision matching')

        job = get_job(db, job_id)
        assert len(job['logs']) == 1
        assert job['logs'][0]['level'] == 'info'
        assert job['logs'][0]['message'] == 'Starting vision matching'


def test_update_job_field_persists_json():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_db(db_path)

        job_id = create_job(db, 'vision_match', {'phase': 'init'})
        update_job_field(db, job_id, 'metadata', {'phase': 'running', 'count': 3})
        update_job_field(db, job_id, 'result', {'matches': [{'a': 1}]})

        job = get_job(db, job_id)
        assert job['metadata'] == {'phase': 'running', 'count': 3}
        assert job['result'] == {'matches': [{'a': 1}]}


def test_update_job_field_rejects_unknown_column():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_db(db_path)
        job_id = create_job(db, 'vision_match', {})

        with pytest.raises(ValueError, match='Unsupported job field'):
            update_job_field(db, job_id, 'id', 'evil')


def test_update_job_field_rejects_logs_column():
    """``logs`` was removed from the allowed update fields when we moved the
    log history to a dedicated table. Writing via ``update_job_field`` would
    corrupt the new read path, so the helper must reject it outright."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_db(db_path)
        job_id = create_job(db, 'vision_match', {})

        with pytest.raises(ValueError, match='Unsupported job field'):
            update_job_field(db, job_id, 'logs', [{'timestamp': 'x'}])


def test_add_job_log_appends_without_rewriting_full_history():
    """Previously ``add_job_log`` did SELECT/json.loads/append/json.dumps/UPDATE.
    The new implementation issues a single INSERT, so log writes stay O(1)
    even when the job has accumulated tens of thousands of entries."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_db(db_path)
        job_id = create_job(db, 'batch_score', {})
        for i in range(2500):
            add_job_log(db, job_id, 'debug', f'line {i}')

        # Default tail returned by get_job is DEFAULT_LOG_TAIL in chronological order
        job = get_job(db, job_id)
        assert len(job['logs']) == DEFAULT_LOG_TAIL
        # chronological, so the tail ends with the most recent line
        assert job['logs'][-1]['message'] == 'line 2499'
        assert job['logs'][0]['message'] == f'line {2500 - DEFAULT_LOG_TAIL}'
        # count_job_logs returns the *full* count regardless of tail
        assert count_job_logs(db, job_id) == 2500


def test_get_job_include_all_logs_returns_full_history():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_db(db_path)
        job_id = create_job(db, 'batch_score', {})
        for i in range(50):
            add_job_log(db, job_id, 'info', f'entry {i}')

        job = get_job(db, job_id, include_all_logs=True)
        assert len(job['logs']) == 50
        assert job['logs'][0]['message'] == 'entry 0'
        assert job['logs'][49]['message'] == 'entry 49'


def test_get_job_logs_limit_zero_returns_empty_list():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_db(db_path)
        job_id = create_job(db, 'batch_score', {})
        add_job_log(db, job_id, 'info', 'first')
        job = get_job(db, job_id, logs_limit=0)
        # logs_limit=0 at the database layer means "attach no entries" (the API
        # endpoint reinterprets 0 as 'include_all' for backward compatibility).
        assert job['logs'] == []


def test_job_log_has_message_uses_index_backed_lookup():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_db(db_path)
        job_id = create_job(db, 'batch_score', {})
        add_job_log(db, job_id, 'info', 'something happened')
        add_job_log(db, job_id, 'info', 'Job stopped after cancel request')

        assert job_log_has_message(db, job_id, 'Job stopped after cancel request')
        assert not job_log_has_message(db, job_id, 'never logged')


def test_list_jobs_omits_logs_by_default():
    """Listings would otherwise pull megabytes of log history for every
    running job; ``include_logs`` is opt-in for callers that actually need
    the tail."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_db(db_path)
        job_id = create_job(db, 'batch_score', {})
        for i in range(10):
            add_job_log(db, job_id, 'info', f'line {i}')

        default_listing = list_jobs(db)
        assert len(default_listing) == 1
        assert default_listing[0]['logs'] == []

        with_logs = list_jobs(db, include_logs=True)
        assert len(with_logs[0]['logs']) == 10


def test_add_job_log_silently_ignores_unknown_job_id():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_db(db_path)
        # No exception, no row inserted
        add_job_log(db, 'nonexistent-job-id', 'info', 'whatever')


def test_make_connection_for_path_gives_each_thread_its_own_handle():
    """The whole point of the redesign: workers must not share a connection.
    Verify that different threads asking for the same DB path get different
    connection objects, and that a single thread asking twice gets the same
    cached one.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'shared.db')
        init_db(db_path)

        first = make_connection_for_path(db_path)
        second = make_connection_for_path(db_path)
        assert first is second, "same thread should reuse its connection"

        other_conn = [None]
        errors = [None]

        def grab():
            try:
                other_conn[0] = make_connection_for_path(db_path)
            except Exception as exc:
                errors[0] = exc

        t = threading.Thread(target=grab)
        t.start()
        t.join()
        assert errors[0] is None, errors[0]
        assert other_conn[0] is not None
        assert other_conn[0] is not first, "each thread must get its own connection"


def test_legacy_logs_column_migrated_on_init():
    """Old databases still carry log history in the ``jobs.logs`` JSON blob.
    ``init_db`` must fold that history into the new ``job_logs`` table the
    first time it runs so the UI keeps showing historical entries after
    deploying the new code."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'legacy.db')
        # Bootstrap just enough schema to insert a legacy row. ``init_db``
        # creates the modern table set; we overwrite the row's ``logs``
        # column afterward to simulate an old database.
        db = init_db(db_path)
        job_id = create_job(db, 'batch_score', {})
        legacy_logs = json.dumps([
            {'timestamp': '2026-04-19T13:00:00', 'level': 'info', 'message': 'legacy 1'},
            {'timestamp': '2026-04-19T13:00:01', 'level': 'warning', 'message': 'legacy 2'},
        ])
        db.execute("UPDATE jobs SET logs = ? WHERE id = ?", (legacy_logs, job_id))
        db.commit()
        db.close()
        # Clear the connection cache so init_db reopens fresh
        from database import _TLS
        if hasattr(_TLS, 'conns'):
            _TLS.conns.pop(db_path, None)

        # Reopen: migration should fire.
        db2 = init_db(db_path)
        job = get_job(db2, job_id, include_all_logs=True)
        messages = [e['message'] for e in job['logs']]
        assert messages == ['legacy 1', 'legacy 2']
        # Legacy column emptied so it never double-counts on a future restart
        raw = db2.execute("SELECT logs FROM jobs WHERE id = ?", (job_id,)).fetchone()
        assert (raw['logs'] if isinstance(raw, dict) else raw[0]) == '[]'
