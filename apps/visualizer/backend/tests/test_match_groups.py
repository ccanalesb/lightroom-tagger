import os
import tempfile

from lightroom_tagger.core.database import init_database, store_match


def _make_client(db_path):
    """Create test client with LIBRARY_DB pointed at the given path."""
    import config
    import utils.db as db_utils
    config.LIBRARY_DB = db_path
    db_utils.LIBRARY_DB = db_path
    from app import create_app
    app = create_app()
    return app.test_client()


def test_matches_grouped_by_insta_key():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_database(db_path)
        store_match(db, {
            'catalog_key': 'cat_a', 'insta_key': 'ig1',
            'phash_distance': 3, 'phash_score': 0.9, 'desc_similarity': 0.8,
            'vision_result': 'SAME', 'vision_score': 0.95, 'total_score': 0.90,
            'rank': 1,
        })
        store_match(db, {
            'catalog_key': 'cat_b', 'insta_key': 'ig1',
            'phash_distance': 5, 'phash_score': 0.7, 'desc_similarity': 0.6,
            'vision_result': 'UNCERTAIN', 'vision_score': 0.75, 'total_score': 0.75,
            'rank': 2,
        })
        db.close()

        client = _make_client(db_path)
        resp = client.get('/api/images/matches')
        assert resp.status_code == 200
        data = resp.get_json()
        groups = data['match_groups']
        assert len(groups) == 1
        assert groups[0]['instagram_key'] == 'ig1'
        assert len(groups[0]['candidates']) == 2
        assert groups[0]['candidates'][0]['rank'] == 1
        assert groups[0]['candidates'][1]['rank'] == 2
        assert groups[0]['candidate_count'] == 2
        assert data['total_groups'] == 1
        assert data['total_matches'] == 2
        assert len(data['matches']) == 2


def test_single_match_still_grouped():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_database(db_path)
        store_match(db, {
            'catalog_key': 'cat_x', 'insta_key': 'ig2',
            'phash_distance': 2, 'phash_score': 0.95, 'desc_similarity': 0.9,
            'vision_result': 'SAME', 'vision_score': 0.98, 'total_score': 0.95,
            'rank': 1,
        })
        db.close()

        client = _make_client(db_path)
        resp = client.get('/api/images/matches')
        data = resp.get_json()
        assert len(data['match_groups']) == 1
        assert data['match_groups'][0]['candidate_count'] == 1
        assert data['total_matches'] == 1
        assert len(data['matches']) == 1
