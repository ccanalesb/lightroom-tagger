"""Contract tests for Descriptions pydantic models."""

from __future__ import annotations

import os
import tempfile

import pytest
from app import create_app

from api.descriptions import _deserialize
from api.schemas.descriptions import (
    DescriptionGenerateResponse,
    DescriptionGetResponse,
    DescriptionItem,
    DescriptionsListResponse,
    ImageDescription,
    validate_description_item,
    validate_image_description,
)
from lightroom_tagger.core.database import init_database, store_image_description


def _make_client(db_path):
    import config
    import utils.db as db_utils

    config.LIBRARY_DB = db_path
    db_utils.LIBRARY_DB = db_path
    return create_app().test_client()


def _seed_described_image(db, key='cat_001', image_type='catalog'):
    if image_type == 'catalog':
        db.execute(
            "INSERT OR IGNORE INTO images (key, filename, filepath, date_taken) VALUES (?, ?, ?, ?)",
            (key, 'photo.jpg', '/fake/photo.jpg', '2024-01-15'),
        )
    else:
        db.execute(
            "INSERT OR IGNORE INTO instagram_dump_media (media_key, filename, file_path, created_at) VALUES (?, ?, ?, ?)",
            (key, 'insta.jpg', '/fake/insta.jpg', '2024-01-15'),
        )
    db.execute(
        "INSERT INTO image_descriptions (image_key, image_type, summary, best_perspective, model_used, described_at) VALUES (?, ?, ?, ?, ?, ?)",
        (key, image_type, 'A test summary', 'street', 'gemma3:27b', '2024-06-01T00:00:00'),
    )
    db.commit()


def test_descriptions_list_round_trip_from_handler():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_database(db_path)
        _seed_described_image(db, 'cat_001', 'catalog')
        _seed_described_image(db, 'ig_001', 'instagram')
        db.close()

        client = _make_client(db_path)
        payload = client.get('/api/descriptions/').get_json()
        assert payload is not None

        validated = DescriptionsListResponse.model_validate(payload)
        assert validated.total >= 2
        assert len(validated.items) >= 2
        assert validated.pagination.current_page == 1

        row = validate_description_item(payload['items'][0])
        assert DescriptionItem.model_validate(row).image_key


def test_description_get_round_trip_from_handler():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_database(db_path)
        _seed_described_image(db, 'cat_001', 'catalog')
        db.close()

        client = _make_client(db_path)
        payload = client.get('/api/descriptions/cat_001').get_json()
        validated = DescriptionGetResponse.model_validate(payload)
        assert validated.description is not None
        assert validated.description.summary == 'A test summary'


def test_description_get_null_round_trip():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        init_database(db_path).close()

        client = _make_client(db_path)
        payload = client.get('/api/descriptions/missing').get_json()
        validated = DescriptionGetResponse.model_validate(payload)
        assert validated.description is None


def test_image_description_round_trip_from_deserialize():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_database(db_path)
        store_image_description(
            db,
            {
                'image_key': 'cat_001',
                'image_type': 'catalog',
                'summary': 'Street scene',
                'composition': {'layers': ['fg', 'bg'], 'techniques': ['rule_of_thirds']},
                'perspectives': {
                    'street': {'analysis': 'Strong geometry', 'score': 7},
                },
                'technical': {'mood': 'gritty', 'dominant_colors': ['#112233']},
                'subjects': ['person'],
                'best_perspective': 'street',
                'model_used': 'gemma3:27b',
            },
        )
        from lightroom_tagger.core.database import get_image_description

        row = get_image_description(db, 'cat_001')
        assert row is not None
        payload = _deserialize(row)
        validated = ImageDescription.model_validate(validate_image_description(payload))
        assert validated.summary == 'Street scene'
        assert validated.subjects == ['person']


def test_description_generate_response_accepts_existing_only_shape():
    payload = {
        'generated': False,
        'description': {
            'image_key': 'cat_001',
            'image_type': 'catalog',
            'summary': 'Cached',
            'composition': {},
            'perspectives': {},
            'technical': {},
            'subjects': [],
            'best_perspective': 'street',
            'model_used': 'gemma3:27b',
        },
    }
    validated = DescriptionGenerateResponse.model_validate(payload)
    assert validated.generated is False
    assert validated.description is not None


def test_description_item_rejects_wrong_shape():
    with pytest.raises(Exception):
        validate_description_item({'image_key': 'only-key'})
