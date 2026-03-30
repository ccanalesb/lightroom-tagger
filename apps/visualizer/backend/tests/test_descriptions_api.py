import json
import os
import tempfile

from lightroom_tagger.core.database import init_database


def _make_client(db_path):
    import config
    import utils.db as db_utils
    config.LIBRARY_DB = db_path
    db_utils.LIBRARY_DB = db_path

    from app import create_app
    app = create_app()
    return app.test_client()


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


def test_list_descriptions_should_return_paginated_results():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_database(db_path)
        _seed_described_image(db, 'cat_001', 'catalog')
        _seed_described_image(db, 'ig_001', 'instagram')
        db.close()

        client = _make_client(db_path)
        resp = client.get('/api/descriptions/')
        assert resp.status_code == 200

        data = resp.get_json()
        assert data['total'] >= 2
        assert 'items' in data
        assert 'pagination' in data
        assert data['pagination']['current_page'] == 1


def test_list_descriptions_should_filter_by_image_type():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_database(db_path)
        _seed_described_image(db, 'cat_001', 'catalog')
        _seed_described_image(db, 'ig_001', 'instagram')
        db.close()

        client = _make_client(db_path)
        resp = client.get('/api/descriptions/?image_type=catalog')
        assert resp.status_code == 200
        items = resp.get_json()['items']
        for item in items:
            assert item['image_type'] == 'catalog'


def test_list_descriptions_should_support_described_only_filter():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_database(db_path)
        db.execute(
            "INSERT INTO images (key, filename, filepath, date_taken) VALUES (?, ?, ?, ?)",
            ('undescribed', 'undesc.jpg', '/fake/undesc.jpg', '2024-01-15'),
        )
        db.commit()
        _seed_described_image(db, 'cat_001', 'catalog')
        db.close()

        client = _make_client(db_path)
        resp = client.get('/api/descriptions/?described_only=true&image_type=catalog')
        assert resp.status_code == 200
        items = resp.get_json()['items']
        for item in items:
            assert item['has_description'] == 1


def test_get_description_should_return_description():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_database(db_path)
        _seed_described_image(db, 'cat_001', 'catalog')
        db.close()

        client = _make_client(db_path)
        resp = client.get('/api/descriptions/cat_001')
        assert resp.status_code == 200
        desc = resp.get_json()['description']
        assert desc is not None
        assert desc['summary'] == 'A test summary'
        assert desc['best_perspective'] == 'street'


def test_get_description_should_return_null_when_not_found():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_database(db_path)
        db.close()

        client = _make_client(db_path)
        resp = client.get('/api/descriptions/nonexistent_key')
        assert resp.status_code == 200
        assert resp.get_json()['description'] is None


def test_generate_should_reject_invalid_image_type():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_database(db_path)
        db.close()

        client = _make_client(db_path)
        resp = client.post(
            '/api/descriptions/cat_001/generate',
            json={'image_type': 'invalid'},
        )
        assert resp.status_code == 400
        assert 'error' in resp.get_json()


def test_list_descriptions_should_paginate():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_database(db_path)
        for i in range(5):
            db.execute(
                "INSERT INTO images (key, filename, filepath, date_taken) VALUES (?, ?, ?, ?)",
                (f'cat_{i:03d}', f'photo_{i}.jpg', f'/fake/photo_{i}.jpg', '2024-01-15'),
            )
            db.execute(
                "INSERT INTO image_descriptions (image_key, image_type, summary, best_perspective, model_used, described_at) VALUES (?, ?, ?, ?, ?, ?)",
                (f'cat_{i:03d}', 'catalog', f'Summary {i}', 'street', 'gemma3:27b', '2024-06-01T00:00:00'),
            )
        db.commit()
        db.close()

        client = _make_client(db_path)
        resp = client.get('/api/descriptions/?limit=2&offset=0&image_type=catalog&described_only=true')
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data['items']) == 2
        assert data['pagination']['has_more'] is True
        assert data['pagination']['total_pages'] == 3
