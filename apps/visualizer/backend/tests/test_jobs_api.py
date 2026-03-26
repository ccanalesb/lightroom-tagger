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
    assert response.json == []

def test_create_job(client):
    response = client.post('/api/jobs/',
        json={'type': 'analyze_instagram', 'metadata': {'post_url': 'https://instagram.com/p/ABC'}}
    )
    assert response.status_code == 201
    assert 'id' in response.json
    assert response.json['status'] == 'pending'

def test_get_job(client):
    create_resp = client.post('/api/jobs/',
        json={'type': 'vision_match', 'metadata': {}}
    )
    job_id = create_resp.json['id']

    response = client.get(f'/api/jobs/{job_id}')
    assert response.status_code == 200
    assert response.json['type'] == 'vision_match'

def test_get_active_jobs(client):
    client.post('/api/jobs/',
        json={'type': 'vision_match', 'metadata': {}}
    )

    response = client.get('/api/jobs/active')
    assert response.status_code == 200
    assert len(response.json) == 0  # No running jobs yet
