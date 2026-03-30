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


def _seed_match(db, validated=False):
    db.execute(
        "INSERT INTO images (key, filename, filepath, date_taken) VALUES (?, ?, ?, ?)",
        ('cat_001', 'photo.jpg', '/fake/photo.jpg', '2024-01-15'),
    )
    db.execute(
        "INSERT INTO instagram_dump_media (media_key, filename, file_path, created_at) VALUES (?, ?, ?, ?)",
        ('ig_001', 'insta.jpg', '/fake/insta.jpg', '2024-01-15'),
    )
    validated_at = '2024-06-01T00:00:00' if validated else None
    db.execute(
        "INSERT INTO matches (catalog_key, insta_key, total_score, vision_result, validated_at) VALUES (?, ?, ?, ?, ?)",
        ('cat_001', 'ig_001', 0.85, 'SAME', validated_at),
    )
    db.commit()


def test_validate_match_should_set_validated():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_database(db_path)
        _seed_match(db)
        db.close()

        client = _make_client(db_path)
        resp = client.patch('/api/images/matches/cat_001/ig_001/validate')
        assert resp.status_code == 200
        assert resp.get_json()['validated'] is True


def test_unvalidate_match_should_clear_validated():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_database(db_path)
        _seed_match(db, validated=True)
        db.close()

        client = _make_client(db_path)
        resp = client.patch('/api/images/matches/cat_001/ig_001/validate')
        assert resp.status_code == 200
        assert resp.get_json()['validated'] is False


def test_validate_nonexistent_match_should_return_404():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_database(db_path)
        db.close()

        client = _make_client(db_path)
        resp = client.patch('/api/images/matches/no_cat/no_ig/validate')
        assert resp.status_code == 404


def test_reject_match_should_delete_and_blocklist():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_database(db_path)
        _seed_match(db)
        db.close()

        client = _make_client(db_path)
        resp = client.patch('/api/images/matches/cat_001/ig_001/reject')
        assert resp.status_code == 200
        assert resp.get_json()['rejected'] is True

        db = init_database(db_path)
        match = db.execute("SELECT * FROM matches WHERE catalog_key = 'cat_001'").fetchone()
        assert match is None
        rejected = db.execute("SELECT * FROM rejected_matches WHERE catalog_key = 'cat_001'").fetchone()
        assert rejected is not None
        db.close()


def test_reject_validated_match_should_return_409():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_database(db_path)
        _seed_match(db, validated=True)
        db.close()

        client = _make_client(db_path)
        resp = client.patch('/api/images/matches/cat_001/ig_001/reject')
        assert resp.status_code == 409
        assert resp.get_json()['rejected'] is False


def test_reject_nonexistent_match_should_return_404():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_database(db_path)
        db.close()

        client = _make_client(db_path)
        resp = client.patch('/api/images/matches/no_cat/no_ig/reject')
        assert resp.status_code == 404
