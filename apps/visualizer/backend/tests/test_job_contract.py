"""Contract tests for Jobs pydantic models and socket payload validation."""

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from api.schemas.jobs import (
    Job,
    build_job_emit_payload,
    validate_job_payload,
    validate_jobs_recovered_payload,
)
from database import add_job_log, create_job, get_job, init_db, list_jobs


@pytest.fixture
def db():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield init_db(os.path.join(tmpdir, 'test.db'))


def test_job_model_round_trip_includes_log_summary_fields(db):
    job_id = create_job(db, 'vision_match', {})
    add_job_log(db, job_id, 'warning', 'careful')
    add_job_log(db, job_id, 'error', 'boom')

    row = next(job for job in list_jobs(db) if job['id'] == job_id)
    validated = Job.model_validate(validate_job_payload(row))

    assert validated.warning_count == 1
    assert validated.error_count == 1
    assert validated.logs_total == 2
    assert validated.last_log_at is not None


def test_build_job_emit_payload_enriches_get_job_row(db):
    job_id = create_job(db, 'vision_match', {})
    add_job_log(db, job_id, 'info', 'hello')

    raw = get_job(db, job_id)
    assert 'warning_count' not in raw

    payload = build_job_emit_payload(db, raw)
    assert payload['warning_count'] == 0
    assert payload['error_count'] == 0
    assert payload['logs_total'] == 1
    assert payload['last_log_at'] is not None


def test_validate_job_payload_rejects_wrong_shape():
    with pytest.raises(Exception):
        validate_job_payload({'id': 'only-id'})


def test_validate_jobs_recovered_payload_accepts_job_ids():
    payload = validate_jobs_recovered_payload({'job_ids': ['a', 'b']})
    assert payload == {'job_ids': ['a', 'b']}


def test_validate_jobs_recovered_payload_rejects_wrong_shape():
    with pytest.raises(Exception):
        validate_jobs_recovered_payload({'job_ids': 'not-a-list'})
