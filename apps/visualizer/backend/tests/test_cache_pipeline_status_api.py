"""Tests for ``GET /api/cache/pipeline-status``.

The endpoint surfaces the most recent run for each Catalog Cache pipeline
trigger so the UI can display "Last run X ago" next to each button. The seven
buckets share a small set of edge cases:

* No matching job → ``null``
* ``batch_embed_image`` is split by ``metadata.image_type`` into two buckets
  (catalog-only vs catalog+Instagram). Legacy rows without ``image_type`` map
  to the catalog-only bucket.
* Whichever job has the most recent ``created_at`` wins, regardless of status.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app import create_app
from database import init_db, update_job_status


@pytest.fixture
def client(tmp_path, monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        lib_path = tmp_path / 'library.db'
        lib_path.write_bytes(b'')
        monkeypatch.setenv('LIBRARY_DB', str(lib_path))
        app = create_app()
        app.db = init_db(db_path)
        c = app.test_client()
        yield c


def _create(client, job_type, metadata=None):
    """Create a job + return its id. Yields a small sleep to keep ``created_at`` ordering deterministic."""
    resp = client.post('/api/jobs/', json={'type': job_type, 'metadata': metadata or {}})
    assert resp.status_code == 201, resp.json
    time.sleep(0.005)
    return resp.json['id']


def test_pipeline_status_returns_null_for_every_bucket_when_empty(client):
    resp = client.get('/api/cache/pipeline-status')
    assert resp.status_code == 200
    body = resp.json
    expected_keys = {
        'catalog_sync',
        'embed_catalog',
        'embed_catalog_and_instagram',
        'stack_detect',
        'catalog_similarity',
        'catalog_cache_build',
        'prepare_catalog',
    }
    assert set(body.keys()) == expected_keys
    for v in body.values():
        assert v is None


def test_pipeline_status_buckets_each_simple_job_type(client):
    sync = _create(client, 'catalog_sync')
    sd = _create(client, 'batch_stack_detect')
    sim = _create(client, 'batch_catalog_similarity')
    pc = _create(client, 'prepare_catalog')
    chain = _create(client, 'catalog_cache_build')

    body = client.get('/api/cache/pipeline-status').json
    assert body['catalog_sync']['job_id'] == sync
    assert body['stack_detect']['job_id'] == sd
    assert body['catalog_similarity']['job_id'] == sim
    assert body['prepare_catalog']['job_id'] == pc
    assert body['catalog_cache_build']['job_id'] == chain
    assert body['embed_catalog'] is None
    assert body['embed_catalog_and_instagram'] is None


def test_pipeline_status_splits_batch_embed_image_by_image_type(client):
    cat_only = _create(client, 'batch_embed_image', {'image_type': 'catalog'})
    cat_ig = _create(
        client, 'batch_embed_image', {'image_type': 'catalog_and_instagram'},
    )

    body = client.get('/api/cache/pipeline-status').json
    assert body['embed_catalog']['job_id'] == cat_only
    assert body['embed_catalog_and_instagram']['job_id'] == cat_ig


def test_pipeline_status_legacy_embed_without_image_type_maps_to_catalog(client):
    legacy = _create(client, 'batch_embed_image', {})

    body = client.get('/api/cache/pipeline-status').json
    assert body['embed_catalog']['job_id'] == legacy
    assert body['embed_catalog_and_instagram'] is None


def test_pipeline_status_returns_most_recent_per_bucket(client):
    older = _create(client, 'batch_stack_detect')
    newer = _create(client, 'batch_stack_detect')

    body = client.get('/api/cache/pipeline-status').json
    assert body['stack_detect']['job_id'] == newer
    # Sanity: older one is still in the table but not surfaced.
    assert body['stack_detect']['job_id'] != older


def test_pipeline_status_includes_status_and_timestamps(client):
    sd = _create(client, 'batch_stack_detect')

    body = client.get('/api/cache/pipeline-status').json
    entry = body['stack_detect']
    assert entry['job_id'] == sd
    assert entry['type'] == 'batch_stack_detect'
    assert entry['status'] == 'pending'
    assert entry['created_at']
    # started_at / completed_at are NULL until the runner picks the job up.
    assert entry['started_at'] is None
    assert entry['completed_at'] is None


def test_pipeline_status_propagates_status_transitions(client):
    sd = _create(client, 'batch_stack_detect')

    # Simulate runner lifecycle by writing directly to the DB. Going through
    # the API route would require booting the processor which is out of scope.
    from flask import current_app
    with create_app().app_context():
        pass  # noop — we already have ``client.application`` configured

    update_job_status(client.application.db, sd, 'completed')
    body = client.get('/api/cache/pipeline-status').json
    assert body['stack_detect']['status'] == 'completed'

    update_job_status(client.application.db, sd, 'failed')
    body = client.get('/api/cache/pipeline-status').json
    assert body['stack_detect']['status'] == 'failed'


def test_pipeline_status_returns_failed_or_cancelled_jobs_too(client):
    """Status filter is intentionally absent — users want to see "last attempted",
    even if it failed or was cancelled, so they know the pipeline state."""
    sd = _create(client, 'batch_stack_detect')
    update_job_status(client.application.db, sd, 'cancelled')
    body = client.get('/api/cache/pipeline-status').json
    assert body['stack_detect']['status'] == 'cancelled'
    assert body['stack_detect']['job_id'] == sd
