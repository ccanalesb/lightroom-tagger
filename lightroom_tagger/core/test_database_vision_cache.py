"""Tests for vision comparison cache accessors."""

import os
import tempfile
import unittest

from lightroom_tagger.core.database import (
    get_vision_comparison,
    init_database,
    init_vision_comparisons_table,
    store_vision_comparison,
)
class TestVisionComparisonCache(unittest.TestCase):
    """Tests for vision comparison cache functions."""

    def setUp(self):
        """Create temporary database."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as tf:
            self.temp_db_path = tf.name
        self.db = init_database(self.temp_db_path)
        init_vision_comparisons_table(self.db)

    def tearDown(self):
        """Clean up."""
        self.db.close()
        os.unlink(self.temp_db_path)

    def test_store_vision_comparison(self):
        """Test storing a vision comparison result."""
        result = store_vision_comparison(
            self.db,
            catalog_key='cat_001',
            insta_key='insta_001',
            result='SAME',
            vision_score=1.0,
            model_used='gemma3:27b'
        )
        self.assertTrue(result)

        # Retrieve cached result
        cached = get_vision_comparison(self.db, 'cat_001', 'insta_001')
        self.assertIsNotNone(cached)
        self.assertEqual(cached['result'], 'SAME')
        self.assertEqual(cached['vision_score'], 1.0)
        self.assertEqual(cached['model_used'], 'gemma3:27b')
        self.assertIn('compared_at', cached)

    def test_get_vision_comparison_not_found(self):
        """Test retrieving non-existent comparison."""
        cached = get_vision_comparison(self.db, 'cat_999', 'insta_999')
        self.assertIsNone(cached)

    def test_vision_comparison_is_idempotent(self):
        """Test that storing the same comparison twice updates it."""
        # Store first time
        store_vision_comparison(
            self.db,
            catalog_key='cat_001',
            insta_key='insta_001',
            result='UNCERTAIN',
            vision_score=0.5,
            model_used='gemma3:27b'
        )

        # Store again with different result
        store_vision_comparison(
            self.db,
            catalog_key='cat_001',
            insta_key='insta_001',
            result='SAME',
            vision_score=1.0,
            model_used='gemma3:27b-cloud'
        )

        # Should have updated result
        cached = get_vision_comparison(self.db, 'cat_001', 'insta_001')
        self.assertEqual(cached['result'], 'SAME')
        self.assertEqual(cached['vision_score'], 1.0)
        self.assertEqual(cached['model_used'], 'gemma3:27b-cloud')

    def test_multiple_comparisons(self):
        """Test storing multiple comparisons."""
        store_vision_comparison(self.db, 'cat_001', 'insta_001', 'SAME', 1.0, 'gemma3:27b')
        store_vision_comparison(self.db, 'cat_001', 'insta_002', 'DIFFERENT', 0.0, 'gemma3:27b')
        store_vision_comparison(self.db, 'cat_002', 'insta_001', 'UNCERTAIN', 0.5, 'gemma3:27b')

        # Each should be retrievable
        c1 = get_vision_comparison(self.db, 'cat_001', 'insta_001')
        self.assertEqual(c1['result'], 'SAME')

        c2 = get_vision_comparison(self.db, 'cat_001', 'insta_002')
        self.assertEqual(c2['result'], 'DIFFERENT')

        c3 = get_vision_comparison(self.db, 'cat_002', 'insta_001')
        self.assertEqual(c3['result'], 'UNCERTAIN')
