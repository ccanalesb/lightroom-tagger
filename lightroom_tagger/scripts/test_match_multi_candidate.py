from unittest.mock import patch

from lightroom_tagger.core.database import init_database
from lightroom_tagger.scripts.match_instagram_dump import match_dump_media


def _seed_db(db):
    db.execute(
        "INSERT INTO instagram_dump_media (media_key, file_path, date_folder, processed) "
        "VALUES (?, ?, ?, 0)",
        ('ig1', '/tmp/ig1.jpg', '202603'),
    )
    db.execute(
        "INSERT INTO images (key, filename, filepath, date_taken) VALUES (?, ?, ?, ?)",
        ('cat_a', 'a.jpg', '/tmp/a.jpg', '2026-03-10T12:00:00'),
    )
    db.execute(
        "INSERT INTO images (key, filename, filepath, date_taken) VALUES (?, ?, ?, ?)",
        ('cat_b', 'b.jpg', '/tmp/b.jpg', '2026-03-11T12:00:00'),
    )
    db.commit()


def test_stores_multiple_candidates_above_threshold(tmp_path):
    db = init_database(str(tmp_path / 'test.db'))
    _seed_db(db)

    fake_results = [
        {'catalog_key': 'cat_a', 'insta_key': 'ig1', 'phash_distance': 3,
         'phash_score': 0.9, 'desc_similarity': 0.8, 'vision_result': 'SAME',
         'vision_score': 0.95, 'total_score': 0.90},
        {'catalog_key': 'cat_b', 'insta_key': 'ig1', 'phash_distance': 5,
         'phash_score': 0.7, 'desc_similarity': 0.6, 'vision_result': 'UNCERTAIN',
         'vision_score': 0.75, 'total_score': 0.75},
    ]

    with patch('lightroom_tagger.scripts.match_instagram_dump.score_candidates_with_vision', return_value=fake_results), \
         patch('lightroom_tagger.scripts.match_instagram_dump.find_candidates_by_date', return_value=[
             {'key': 'cat_a', 'filepath': '/tmp/a.jpg', 'phash': '', 'description': ''},
             {'key': 'cat_b', 'filepath': '/tmp/b.jpg', 'phash': '', 'description': ''},
         ]), \
         patch('lightroom_tagger.scripts.match_instagram_dump.compute_phash', return_value='abc'), \
         patch('lightroom_tagger.scripts.match_instagram_dump.describe_matched_image', return_value=False), \
         patch('lightroom_tagger.scripts.match_instagram_dump.describe_instagram_image', return_value=False), \
         patch('lightroom_tagger.scripts.match_instagram_dump.resolve_catalog_path', side_effect=lambda x: x), \
         patch('os.path.exists', return_value=True):

        stats, matches = match_dump_media(db, threshold=0.7)

    rows = db.execute(
        "SELECT catalog_key, rank FROM matches WHERE insta_key = ? ORDER BY rank",
        ('ig1',),
    ).fetchall()
    assert len(rows) == 2
    assert rows[0]['catalog_key'] == 'cat_a'
    assert rows[0]['rank'] == 1
    assert rows[1]['catalog_key'] == 'cat_b'
    assert rows[1]['rank'] == 2
    assert stats['matched'] == 1
    db.close()


def test_only_best_stored_when_single_above_threshold(tmp_path):
    db = init_database(str(tmp_path / 'test.db'))
    _seed_db(db)

    fake_results = [
        {'catalog_key': 'cat_a', 'insta_key': 'ig1', 'phash_distance': 3,
         'phash_score': 0.9, 'desc_similarity': 0.8, 'vision_result': 'SAME',
         'vision_score': 0.95, 'total_score': 0.90},
        {'catalog_key': 'cat_b', 'insta_key': 'ig1', 'phash_distance': 10,
         'phash_score': 0.3, 'desc_similarity': 0.2, 'vision_result': 'DIFFERENT',
         'vision_score': 0.2, 'total_score': 0.25},
    ]

    with patch('lightroom_tagger.scripts.match_instagram_dump.score_candidates_with_vision', return_value=fake_results), \
         patch('lightroom_tagger.scripts.match_instagram_dump.find_candidates_by_date', return_value=[
             {'key': 'cat_a', 'filepath': '/tmp/a.jpg', 'phash': '', 'description': ''},
             {'key': 'cat_b', 'filepath': '/tmp/b.jpg', 'phash': '', 'description': ''},
         ]), \
         patch('lightroom_tagger.scripts.match_instagram_dump.compute_phash', return_value='abc'), \
         patch('lightroom_tagger.scripts.match_instagram_dump.describe_matched_image', return_value=False), \
         patch('lightroom_tagger.scripts.match_instagram_dump.describe_instagram_image', return_value=False), \
         patch('lightroom_tagger.scripts.match_instagram_dump.resolve_catalog_path', side_effect=lambda x: x), \
         patch('os.path.exists', return_value=True):

        stats, matches = match_dump_media(db, threshold=0.7)

    rows = db.execute("SELECT catalog_key FROM matches WHERE insta_key = ?", ('ig1',)).fetchall()
    assert len(rows) == 1
    assert rows[0]['catalog_key'] == 'cat_a'
    db.close()
