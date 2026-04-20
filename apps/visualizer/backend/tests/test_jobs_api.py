import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app import create_app
from database import init_db


@pytest.fixture
def client():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        app = create_app()
        app.db = init_db(db_path)
        client = app.test_client()
        yield client

def test_list_jobs(client):
    response = client.get('/api/jobs/')
    assert response.status_code == 200
    assert response.json['data'] == []
    assert response.json['total'] == 0
    assert response.json['pagination']['current_page'] == 1
    assert response.json['pagination']['limit'] == 50
    assert response.json['pagination']['offset'] == 0
    assert response.json['pagination']['has_more'] is False

def test_create_job(client):
    response = client.post('/api/jobs/',
        json={'type': 'analyze_instagram', 'metadata': {'post_url': 'https://instagram.com/p/ABC'}}
    )
    assert response.status_code == 201
    assert 'id' in response.json
    assert response.json['status'] == 'pending'

def test_create_instagram_import_job(client):
    response = client.post(
        '/api/jobs/',
        json={'type': 'instagram_import', 'metadata': {}},
    )
    assert response.status_code == 201
    assert response.json['type'] == 'instagram_import'

def test_get_job(client):
    create_resp = client.post('/api/jobs/',
        json={'type': 'vision_match', 'metadata': {}}
    )
    job_id = create_resp.json['id']

    response = client.get(f'/api/jobs/{job_id}')
    assert response.status_code == 200
    assert response.json['type'] == 'vision_match'

def test_get_active_jobs(client):
    response = client.get('/api/jobs/active')
    assert response.status_code == 200
    assert len(response.json) == 0

    client.post('/api/jobs/',
        json={'type': 'vision_match', 'metadata': {}}
    )

    response = client.get('/api/jobs/active')
    assert response.status_code == 200
    assert len(response.json) == 1


def _seed_jobs(client, count, job_type='vision_match'):
    ids = []
    for _ in range(count):
        resp = client.post('/api/jobs/', json={'type': job_type, 'metadata': {}})
        ids.append(resp.json['id'])
    return ids


def test_list_jobs_respects_limit_and_offset(client):
    _seed_jobs(client, 4)
    page_one = client.get('/api/jobs/?limit=2&offset=0').json
    page_two = client.get('/api/jobs/?limit=2&offset=2').json
    assert len(page_one['data']) == 2
    assert len(page_two['data']) == 2
    assert page_one['total'] == 4
    assert page_two['total'] == 4
    assert page_one['data'][0]['id'] != page_two['data'][0]['id']
    assert page_one['pagination']['current_page'] == 1
    assert page_two['pagination']['current_page'] == 2


def test_list_jobs_total_count_matches_status_filter(client):
    from database import update_job_status
    ids = _seed_jobs(client, 3)
    extra = _seed_jobs(client, 2)
    for job_id in extra:
        update_job_status(client.application.db, job_id, 'completed')
    pending = client.get('/api/jobs/?status=pending').json
    completed = client.get('/api/jobs/?status=completed').json
    assert pending['total'] == 3
    assert completed['total'] == 2
    assert all(j['status'] == 'pending' for j in pending['data'])
    assert all(j['status'] == 'completed' for j in completed['data'])


def test_list_jobs_default_limit_50(client):
    _seed_jobs(client, 60)
    response = client.get('/api/jobs/').json
    assert len(response['data']) == 50
    assert response['total'] == 60
    assert response['pagination']['has_more'] is True


def test_get_job_truncates_logs_when_logs_limit_set(client):
    from database import add_job_log
    create_resp = client.post('/api/jobs/', json={'type': 'vision_match', 'metadata': {}})
    job_id = create_resp.json['id']
    for i in range(30):
        add_job_log(client.application.db, job_id, 'info', f'log entry {i}')
    response = client.get(f'/api/jobs/{job_id}?logs_limit=10').json
    assert len(response['logs']) == 10
    assert response['logs_total'] == 30
    assert response['logs'][-1]['message'] == 'log entry 29'
    assert response['logs'][0]['message'] == 'log entry 20'


def test_get_job_logs_limit_zero_returns_all(client):
    from database import add_job_log
    create_resp = client.post('/api/jobs/', json={'type': 'vision_match', 'metadata': {}})
    job_id = create_resp.json['id']
    for i in range(5):
        add_job_log(client.application.db, job_id, 'info', f'log {i}')
    response = client.get(f'/api/jobs/{job_id}?logs_limit=0').json
    assert len(response['logs']) == 5
    assert response['logs_total'] == 5


def test_get_job_logs_total_present_when_no_param(client):
    from database import add_job_log
    create_resp = client.post('/api/jobs/', json={'type': 'vision_match', 'metadata': {}})
    job_id = create_resp.json['id']
    for i in range(3):
        add_job_log(client.application.db, job_id, 'info', f'log {i}')
    response = client.get(f'/api/jobs/{job_id}').json
    assert len(response['logs']) == 3
    assert response['logs_total'] == 3


def test_list_jobs_limit_clamped_below(client):
    response = client.get('/api/jobs/?limit=0')
    assert response.status_code == 200
    assert response.json['pagination']['limit'] == 1


def test_list_jobs_limit_clamped_above(client):
    response = client.get('/api/jobs/?limit=10000')
    assert response.status_code == 200
    assert response.json['pagination']['limit'] == 500


def test_list_jobs_offset_clamped_negative(client):
    response = client.get('/api/jobs/?offset=-5')
    assert response.status_code == 200
    assert response.json['pagination']['offset'] == 0


def test_cancel_returns_503_json_when_database_locked(client, monkeypatch):
    import sqlite3
    from api import jobs as jobs_api

    create_resp = client.post('/api/jobs/', json={'type': 'vision_match', 'metadata': {}})
    job_id = create_resp.json['id']

    def _raise_locked(*_args, **_kwargs):
        raise sqlite3.OperationalError('database is locked')

    monkeypatch.setattr(jobs_api, 'update_job_status', _raise_locked)

    response = client.delete(f'/api/jobs/{job_id}')
    assert response.status_code == 503
    assert response.is_json
    assert response.json['code'] == 'db_busy'
    assert 'locked' not in response.json['error'].lower() or 'busy' in response.json['error'].lower()


def test_retry_returns_503_json_when_database_locked(client, monkeypatch):
    import sqlite3
    from database import update_job_status
    from api import jobs as jobs_api

    create_resp = client.post('/api/jobs/', json={'type': 'vision_match', 'metadata': {}})
    job_id = create_resp.json['id']
    update_job_status(client.application.db, job_id, 'failed')

    def _raise_locked(*_args, **_kwargs):
        raise sqlite3.OperationalError('database is locked')

    monkeypatch.setattr(jobs_api, 'update_job_status', _raise_locked)

    response = client.post(f'/api/jobs/{job_id}/retry')
    assert response.status_code == 503
    assert response.is_json
    assert response.json['code'] == 'db_busy'


def test_health_reports_library_db_status(client, tmp_path, monkeypatch):
    db = tmp_path / 'library.db'
    db.touch()
    monkeypatch.setenv('LIBRARY_DB', str(db))
    response = client.get('/api/jobs/health')
    assert response.status_code == 200
    body = response.json
    assert body['catalog_available'] is True
    assert body['library_db']['path'] == str(db)
    assert body['library_db']['exists'] is True
    assert 'batch_describe' in body['jobs_requiring_catalog']
    assert body['jobs_requiring_catalog'] == sorted(body['jobs_requiring_catalog'])


def test_health_flags_catalog_unavailable_when_env_path_missing(client, tmp_path, monkeypatch):
    monkeypatch.setenv('LIBRARY_DB', str(tmp_path / 'nope.db'))
    response = client.get('/api/jobs/health')
    assert response.status_code == 200
    body = response.json
    assert body['catalog_available'] is False
    assert body['library_db']['exists'] is False
    assert body['library_db']['reason']


def test_create_catalog_job_rejected_when_library_db_missing(client, tmp_path, monkeypatch):
    monkeypatch.setenv('LIBRARY_DB', str(tmp_path / 'nope.db'))
    response = client.post('/api/jobs/', json={'type': 'batch_describe', 'metadata': {}})
    assert response.status_code == 422
    body = response.json
    assert body['code'] == 'catalog_unavailable'
    assert 'batch_describe' in body['error']
    assert body['library_db']['exists'] is False


def test_create_non_catalog_job_allowed_when_library_db_missing(client, tmp_path, monkeypatch):
    """Jobs that don't touch the catalog (e.g. ``analyze_instagram``) stay allowed."""
    monkeypatch.setenv('LIBRARY_DB', str(tmp_path / 'nope.db'))
    response = client.post('/api/jobs/', json={'type': 'analyze_instagram', 'metadata': {}})
    assert response.status_code == 201
    assert response.json['status'] == 'pending'


def test_create_catalog_job_allowed_when_library_db_exists(client, tmp_path, monkeypatch):
    db = tmp_path / 'library.db'
    db.touch()
    monkeypatch.setenv('LIBRARY_DB', str(db))
    response = client.post('/api/jobs/', json={'type': 'vision_match', 'metadata': {}})
    assert response.status_code == 201


def test_cancel_is_idempotent_on_already_cancelled_job(client):
    """Rapid double-clicks in the UI shouldn't produce a misleading 400.

    The first DELETE flips ``pending``/``running`` to ``cancelled``; a second
    DELETE against the same id used to return 400 ("Can only cancel running
    or pending jobs"). Now it returns 200 with ``cancel_noop: true`` so the
    UI can silently reconcile.
    """
    from database import update_job_status

    create_resp = client.post('/api/jobs/', json={'type': 'vision_match', 'metadata': {}})
    job_id = create_resp.json['id']
    update_job_status(client.application.db, job_id, 'cancelled')

    response = client.delete(f'/api/jobs/{job_id}')
    assert response.status_code == 200
    body = response.json
    assert body['id'] == job_id
    assert body['status'] == 'cancelled'
    assert body['cancel_noop'] is True
    assert 'cancelled' in body['cancel_noop_reason']


def test_cancel_is_idempotent_on_completed_job(client):
    """Cancel against a completed job is treated as a no-op, not an error."""
    from database import update_job_status

    create_resp = client.post('/api/jobs/', json={'type': 'vision_match', 'metadata': {}})
    job_id = create_resp.json['id']
    update_job_status(client.application.db, job_id, 'completed')

    response = client.delete(f'/api/jobs/{job_id}')
    assert response.status_code == 200
    assert response.json['cancel_noop'] is True
    assert response.json['status'] == 'completed'


def test_cancel_is_idempotent_on_failed_job(client):
    """Cancel against a failed job is treated as a no-op, not an error."""
    from database import update_job_status

    create_resp = client.post('/api/jobs/', json={'type': 'vision_match', 'metadata': {}})
    job_id = create_resp.json['id']
    update_job_status(client.application.db, job_id, 'failed')

    response = client.delete(f'/api/jobs/{job_id}')
    assert response.status_code == 200
    assert response.json['cancel_noop'] is True
    assert response.json['status'] == 'failed'


def test_processor_health_reports_not_running_before_thread_start(client):
    """When the test fixture builds an app without starting the processor
    thread, the endpoint still returns 200 with ``running: false`` and null
    heartbeat fields. This is the signal a human would use during an
    incident: "the processor isn't alive at all".
    """
    response = client.get('/api/jobs/_processor_health')
    assert response.status_code == 200
    body = response.json
    assert body['running'] is False
    assert body['started_at'] is None
    assert body['last_iteration_at'] is None
    assert body['last_iteration_age_seconds'] is None
    assert body['iterations_total'] == 0
    assert body['current_job_id'] is None
    assert body['pending_count'] == 0
    assert body['stale'] is False  # No heartbeat yet — not stale, just absent.


def test_processor_health_marks_stale_after_heartbeat_ages_out(client, monkeypatch):
    """If the processor *has* ticked but stopped ticking, ``stale`` flips
    to True. We fake an ancient heartbeat via the module-level dict.
    """
    import time as _time

    from app import _processor_health, _processor_health_lock

    with _processor_health_lock:
        _processor_health['started_at'] = _time.time() - 300
        # Older than _PROCESSOR_STALE_AFTER_SECONDS (15s).
        _processor_health['last_iteration_at'] = _time.time() - 60
        _processor_health['iterations_total'] = 42

    try:
        response = client.get('/api/jobs/_processor_health')
        assert response.status_code == 200
        body = response.json
        assert body['iterations_total'] == 42
        assert body['last_iteration_age_seconds'] is not None
        assert body['last_iteration_age_seconds'] > body['stale_threshold_seconds']
        assert body['stale'] is True
    finally:
        # Reset module state so we don't poison sibling tests.
        with _processor_health_lock:
            _processor_health['started_at'] = None
            _processor_health['last_iteration_at'] = None
            _processor_health['iterations_total'] = 0


def test_processor_health_reports_pending_count_from_db(client):
    """Pending jobs in the DB show up in ``pending_count`` so operators
    can spot "pending not being picked up" from one endpoint.
    """
    # Enqueue two jobs.
    client.post('/api/jobs/', json={'type': 'vision_match', 'metadata': {}})
    client.post('/api/jobs/', json={'type': 'vision_match', 'metadata': {}})

    response = client.get('/api/jobs/_processor_health')
    assert response.status_code == 200
    assert response.json['pending_count'] == 2


def test_cancel_does_not_swallow_non_lock_operational_errors(client, monkeypatch):
    """Non-lock OperationalErrors must propagate so real bugs aren't hidden as 503s."""
    import sqlite3
    from api import jobs as jobs_api

    create_resp = client.post('/api/jobs/', json={'type': 'vision_match', 'metadata': {}})
    job_id = create_resp.json['id']

    def _raise_other(*_args, **_kwargs):
        raise sqlite3.OperationalError('no such table: jobs')

    monkeypatch.setattr(jobs_api, 'update_job_status', _raise_other)

    with pytest.raises(sqlite3.OperationalError, match='no such table'):
        client.delete(f'/api/jobs/{job_id}')
