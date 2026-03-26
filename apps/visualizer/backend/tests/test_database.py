import os
import tempfile

import pytest

from database import (
    add_job_log,
    create_job,
    get_job,
    init_db,
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
