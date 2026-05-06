"""Tests for match row persistence."""

from lightroom_tagger.core.database import init_database, store_match


def test_store_match_with_rank(tmp_path):
    """store_match persists rank column."""
    db = init_database(str(tmp_path / 'test.db'))
    record = {
        'catalog_key': 'cat1', 'insta_key': 'ig1',
        'phash_distance': 5, 'phash_score': 0.8, 'desc_similarity': 0.7,
        'vision_result': 'SAME', 'vision_score': 0.9, 'total_score': 0.85,
        'rank': 2,
    }
    store_match(db, record)
    row = db.execute(
        "SELECT rank FROM matches WHERE catalog_key = ? AND insta_key = ?",
        ('cat1', 'ig1'),
    ).fetchone()
    assert row is not None
    assert row['rank'] == 2
    db.close()
