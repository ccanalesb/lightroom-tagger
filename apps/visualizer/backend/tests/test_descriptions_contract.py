"""Contract tests for Descriptions pydantic models."""

from __future__ import annotations

import os
import tempfile

import pytest

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
from lightroom_tagger.core.database import get_all_images_with_descriptions, get_image_description, init_database


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


@pytest.fixture
def library_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        conn = init_database(db_path)
        yield conn
        conn.close()


def test_description_item_round_trip_from_list_row(library_db):
    _seed_described_image(library_db, 'cat_001', 'catalog')
    items, _total = get_all_images_with_descriptions(
        library_db, image_type='catalog', limit=10, offset=0,
    )
    assert items

    payload = items[0]
    validated = DescriptionItem.model_validate(validate_description_item(payload))
    assert validated.image_key == 'cat_001'
    assert validated.image_type == 'catalog'
    assert validated.has_description == 1


def test_descriptions_list_response_round_trip(library_db):
    _seed_described_image(library_db, 'cat_001', 'catalog')
    items, total = get_all_images_with_descriptions(
        library_db, image_type='catalog', limit=50, offset=0,
    )
    payload = {
        'total': total,
        'items': items,
        'pagination': {
            'offset': 0,
            'limit': 50,
            'current_page': 1,
            'total_pages': max(1, (total + 49) // 50) if total else 0,
            'has_more': 50 < total,
        },
    }
    validated = DescriptionsListResponse.model_validate(payload)
    assert validated.total >= 1
    assert len(validated.items) >= 1


def test_image_description_round_trip_from_get_row(library_db):
    _seed_described_image(library_db, 'cat_001', 'catalog')
    row = get_image_description(library_db, 'cat_001')
    assert row is not None

    payload = _deserialize(row)
    validated = ImageDescription.model_validate(validate_image_description(payload))
    assert validated.summary == 'A test summary'
    assert validated.best_perspective == 'street'


def test_description_get_response_round_trip(library_db):
    _seed_described_image(library_db, 'cat_001', 'catalog')
    row = get_image_description(library_db, 'cat_001')
    payload = {'description': _deserialize(row) if row else None}
    validated = DescriptionGetResponse.model_validate(payload)
    assert validated.description is not None
    assert validated.description.summary == 'A test summary'


def test_description_generate_response_round_trip():
    payload = {
        'generated': True,
        'description': {
            'image_key': 'cat_001',
            'image_type': 'catalog',
            'summary': 'Generated',
            'best_perspective': 'street',
            'model_used': 'gemma3:27b',
        },
    }
    validated = DescriptionGenerateResponse.model_validate(payload)
    assert validated.generated is True
    assert validated.description is not None


def test_description_item_rejects_wrong_shape():
    with pytest.raises(Exception):
        validate_description_item({'image_key': 'only-key'})
