"""Tests for vision cache accessors."""

import os
import tempfile
import unittest

from lightroom_tagger.core.database import (
    get_cache_stats,
    get_vision_cached_image,
    init_database,
    init_vision_cache_table,
    is_vision_cache_valid,
    store_vision_cached_image,
)


class TestVisionCache(unittest.TestCase):
    """Tests for vision cache functions."""

    def setUp(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tf:
            self.temp_db_path = tf.name
        self.db = init_database(self.temp_db_path)
        init_vision_cache_table(self.db)

    def tearDown(self):
        self.db.close()
        os.unlink(self.temp_db_path)

    def test_store_and_get_vision_cached_image(self):
        result = store_vision_cached_image(
            self.db,
            catalog_key='cat_001',
            compressed_path='/cache/cat_001.jpg',
            phash='abc',
            original_mtime=1.0,
        )
        self.assertTrue(result)
        cached = get_vision_cached_image(self.db, 'cat_001')
        self.assertIsNotNone(cached)
        self.assertEqual(cached['compressed_path'], '/cache/cat_001.jpg')
        self.assertEqual(cached['phash'], 'abc')

    def test_get_cache_stats_empty(self):
        stats = get_cache_stats(self.db)
        self.assertEqual(stats['total'], 0)
        self.assertEqual(stats['cached'], 0)

    def test_is_vision_cache_valid_missing_entry(self):
        self.assertFalse(
            is_vision_cache_valid(self.db, 'missing', '/path/photo.jpg')
        )
