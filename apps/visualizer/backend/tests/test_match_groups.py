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


def test_matches_include_instagram_image_from_dump_only():
    """Dump-backed insta_key has instagram_image when row exists only in instagram_dump_media."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_database(db_path)
        db.execute(
            "INSERT INTO images (key, filename, filepath, date_taken) VALUES (?, ?, ?, ?)",
            ('2024-01-10_cat.jpg', 'cat.jpg', '/fake/cat.jpg', '2024-01-10'),
        )
        db.execute(
            "INSERT INTO instagram_dump_media (media_key, file_path, date_folder, filename, processed) "
            "VALUES (?, ?, ?, ?, ?)",
            ('202603/ig_dump_only', '/tmp/fake/posts/x.jpg', '202603', 'x.jpg', 0),
        )
        db.execute(
            "INSERT INTO matches (catalog_key, insta_key, phash_distance, phash_score, desc_similarity, "
            "vision_result, vision_score, total_score, rank) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ('2024-01-10_cat.jpg', '202603/ig_dump_only', 0, 0.0, 0.0, 'SAME', 0.0, 0.9, 1),
        )
        db.commit()
        db.close()

        client = _make_client(db_path)
        resp = client.get('/api/images/matches?limit=50&offset=0')
        assert resp.status_code == 200
        data = resp.get_json()
        keys_seen = []
        for g in data['match_groups']:
            ig = g.get('instagram_image')
            if ig:
                keys_seen.append(ig.get('key'))
        for m in data.get('matches', []):
            ig = m.get('instagram_image')
            if ig:
                keys_seen.append(ig.get('key'))
        assert '202603/ig_dump_only' in keys_seen
