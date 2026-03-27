import json
import os
import tempfile

from lightroom_tagger.core.database import init_database


def _make_client(db_path):
    """Create test client with LIBRARY_DB pointed at the given path."""
    import config
    import utils.db as db_utils
    config.LIBRARY_DB = db_path
    db_utils.LIBRARY_DB = db_path

    from app import create_app
    app = create_app()
    return app.test_client()


def test_matches_include_descriptions():
    """Matches endpoint should include description data when available."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_database(db_path)

        db.execute(
            "INSERT INTO images (key, filename, filepath, date_taken) VALUES (?, ?, ?, ?)",
            ('cat_001', 'photo.jpg', '/fake/photo.jpg', '2024-01-15'),
        )
        db.execute(
            "INSERT INTO matches (catalog_key, insta_key, total_score, vision_result) VALUES (?, ?, ?, ?)",
            ('cat_001', 'ig_001', 0.85, 'SAME'),
        )
        db.execute(
            "INSERT INTO image_descriptions (image_key, image_type, summary, perspectives, best_perspective, model_used) VALUES (?, ?, ?, ?, ?, ?)",
            (
                'cat_001', 'catalog', 'A street scene at golden hour',
                json.dumps({
                    'street': {'analysis': 'Strong geometry', 'score': 7},
                    'documentary': {'analysis': 'Fair story', 'score': 5},
                    'publisher': {'analysis': 'Editorial use', 'score': 6},
                }),
                'street', 'gemma3:27b',
            ),
        )
        db.commit()
        db.close()

        client = _make_client(db_path)
        response = client.get('/api/images/matches?limit=50&offset=0')
        assert response.status_code == 200

        data = response.get_json()
        match = data['matches'][0]
        assert 'catalog_description' in match
        assert match['catalog_description']['summary'] == 'A street scene at golden hour'
        assert match['catalog_description']['best_perspective'] == 'street'
        assert match['catalog_description']['perspectives']['street']['score'] == 7
        assert match.get('insta_description') is None


def test_matches_work_without_descriptions():
    """Matches endpoint should work when no descriptions exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_database(db_path)

        db.execute(
            "INSERT INTO matches (catalog_key, insta_key, total_score, vision_result) VALUES (?, ?, ?, ?)",
            ('cat_001', 'ig_001', 0.85, 'SAME'),
        )
        db.commit()
        db.close()

        client = _make_client(db_path)
        response = client.get('/api/images/matches?limit=50&offset=0')
        assert response.status_code == 200
        match = response.get_json()['matches'][0]
        assert match.get('catalog_description') is None
