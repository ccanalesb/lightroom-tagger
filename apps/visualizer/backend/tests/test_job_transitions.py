import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from database import (
    add_job_log,
    create_job,
    get_job,
    init_db,
    update_job_field,
    update_job_status,
)
from jobs.transitions import (
    can_cancel,
    can_retry,
    transition_cancel,
    transition_retry,
)


@pytest.fixture
def db():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield init_db(os.path.join(tmpdir, 'test.db'))


def _create(db, status='pending'):
    job_id = create_job(db, 'vision_match', {})
    if status != 'pending':
        update_job_status(db, job_id, status)
    return job_id


@pytest.mark.parametrize(
    'status,expected',
    [
        ('pending', True),
        ('running', True),
        ('completed', False),
        ('failed', False),
        ('cancelled', False),
    ],
)
def test_can_cancel(db, status, expected):
    job_id = _create(db, status)
    assert can_cancel(get_job(db, job_id)) is expected


@pytest.mark.parametrize(
    'status,expected',
    [
        ('pending', False),
        ('running', False),
        ('completed', False),
        ('failed', True),
        ('cancelled', True),
    ],
)
def test_can_retry(db, status, expected):
    job_id = _create(db, status)
    assert can_retry(get_job(db, job_id)) is expected


@pytest.mark.parametrize(
    'status,edge,should_signal,db_status',
    [
        ('pending', 'cancelled', False, 'cancelled'),
        ('running', 'cancelled', True, 'cancelled'),
        ('completed', 'noop', False, 'completed'),
        ('failed', 'noop', False, 'failed'),
        ('cancelled', 'noop', True, 'cancelled'),
    ],
)
def test_transition_cancel(db, status, edge, should_signal, db_status):
    job_id = _create(db, status)
    outcome = transition_cancel(db, job_id)

    assert outcome.edge == edge
    assert outcome.should_signal_cancel is should_signal
    assert outcome.job is not None
    assert outcome.job['id'] == job_id
    assert get_job(db, job_id)['status'] == db_status

    if edge == 'cancelled':
        assert outcome.reason is None
        logs = get_job(db, job_id)['logs']
        assert any(log['message'] == 'Cancel requested via API' for log in logs)
    elif edge == 'noop':
        assert outcome.reason == f'Job is already {status}'
        assert 'cancel_noop' not in outcome.job


def test_transition_cancel_not_found(db):
    outcome = transition_cancel(db, 'missing-id')
    assert outcome.edge == 'invalid'
    assert outcome.job is None
    assert outcome.reason == 'Job not found'
    assert outcome.should_signal_cancel is False


@pytest.mark.parametrize(
    'status,edge,result_status',
    [
        ('pending', 'invalid', 'pending'),
        ('running', 'invalid', 'running'),
        ('completed', 'invalid', 'completed'),
        ('failed', 'retried', 'pending'),
        ('cancelled', 'retried', 'pending'),
    ],
)
def test_transition_retry(db, status, edge, result_status):
    job_id = _create(db, status)
    if status in ('failed', 'cancelled'):
        update_job_field(db, job_id, 'error', 'boom')
        db.execute('UPDATE jobs SET error_severity = ? WHERE id = ?', ('error', job_id))
        db.commit()
        update_job_field(db, job_id, 'result', {'done': True})
        update_job_status(db, job_id, status, progress=50, current_step='step')

    outcome = transition_retry(db, job_id)

    assert outcome.edge == edge
    assert outcome.should_signal_cancel is False
    job = get_job(db, job_id)
    assert job['status'] == result_status

    if edge == 'retried':
        assert job['progress'] == 0
        row = db.execute(
            'SELECT error, error_severity, result FROM jobs WHERE id = ?', (job_id,)
        ).fetchone()
        assert row['error'] == 'null'
        assert row['error_severity'] is None
        assert row['result'] == 'null'
        logs = job['logs']
        assert any(log['message'] == 'Job queued for retry' for log in logs)
    elif edge == 'invalid':
        assert outcome.reason == 'Can only retry failed or cancelled jobs'


def test_transition_retry_not_found(db):
    outcome = transition_retry(db, 'missing-id')
    assert outcome.edge == 'invalid'
    assert outcome.job is None
    assert outcome.reason == 'Job not found'
