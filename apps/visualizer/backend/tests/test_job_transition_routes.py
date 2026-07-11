"""Route-boundary tests for cancel/retry — HTTP, socketio, signal_cancel."""

import os
import sys
import tempfile
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app import create_app
from database import init_db, update_job_field, update_job_status


@pytest.fixture
def client():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        app = create_app()
        app.db = init_db(db_path)
        client = app.test_client()
        yield client


@pytest.fixture
def mock_socketio(monkeypatch):
    mock = MagicMock()
    import app as app_mod

    monkeypatch.setattr(app_mod, 'socketio', mock)
    return mock


@pytest.fixture
def mock_runner(monkeypatch):
    runner = MagicMock()
    monkeypatch.setattr('app.get_job_runner', lambda: runner)
    return runner


def _create(client, status='pending'):
    resp = client.post('/api/jobs/', json={'type': 'vision_match', 'metadata': {}})
    job_id = resp.json['id']
    if status != 'pending':
        update_job_status(client.application.db, job_id, status)
    return job_id


@pytest.mark.parametrize('status', ['pending', 'running'])
def test_cancel_active_job_emits_socketio(client, mock_socketio, mock_runner, status):
    job_id = _create(client, status)

    response = client.delete(f'/api/jobs/{job_id}')

    assert response.status_code == 200
    assert response.json['status'] == 'cancelled'
    assert 'cancel_noop' not in response.json
    mock_socketio.emit.assert_called_once()
    assert mock_socketio.emit.call_args[0][0] == 'job_updated'
    assert mock_socketio.emit.call_args[0][1]['id'] == job_id
    if status == 'running':
        mock_runner.signal_cancel.assert_called_once_with(job_id)
    else:
        mock_runner.signal_cancel.assert_not_called()


@pytest.mark.parametrize('status', ['cancelled', 'completed', 'failed'])
def test_cancel_terminal_job_is_noop(client, mock_socketio, mock_runner, status):
    job_id = _create(client, status)

    response = client.delete(f'/api/jobs/{job_id}')

    assert response.status_code == 200
    assert response.json['status'] == status
    assert response.json['cancel_noop'] is True
    assert status in response.json['cancel_noop_reason']
    mock_socketio.emit.assert_not_called()
    if status == 'cancelled':
        mock_runner.signal_cancel.assert_called_once_with(job_id)
    else:
        mock_runner.signal_cancel.assert_not_called()


def test_cancel_not_found(client, mock_socketio, mock_runner):
    response = client.delete('/api/jobs/does-not-exist')
    assert response.status_code == 404
    assert response.json['error'] == 'Job not found'
    mock_socketio.emit.assert_not_called()
    mock_runner.signal_cancel.assert_not_called()


@pytest.mark.parametrize('status', ['failed', 'cancelled'])
def test_retry_requeues_job(client, status):
    job_id = _create(client, status)
    update_job_field(client.application.db, job_id, 'error', 'boom')
    client.application.db.execute(
        'UPDATE jobs SET error_severity = ? WHERE id = ?', ('error', job_id)
    )
    client.application.db.commit()

    response = client.post(f'/api/jobs/{job_id}/retry')

    assert response.status_code == 200
    assert response.json['status'] == 'pending'
    assert response.json['progress'] == 0


@pytest.mark.parametrize('status', ['pending', 'running', 'completed'])
def test_retry_rejects_non_retryable(client, status):
    job_id = _create(client, status)

    response = client.post(f'/api/jobs/{job_id}/retry')

    assert response.status_code == 400
    assert response.json['error'] == 'Can only retry failed or cancelled jobs'


def test_retry_not_found(client):
    response = client.post('/api/jobs/does-not-exist/retry')
    assert response.status_code == 404
    assert response.json['error'] == 'Job not found'
