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
