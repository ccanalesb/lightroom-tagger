"""Tests for catalog CRUD and query_catalog_images."""

import os
import tempfile
import unittest

from lightroom_tagger.core.database import (
    clear_all,
    delete_image,
    generate_key,
    get_all_images,
    get_image,
    get_image_count,
    init_database,
    query_catalog_images,
    store_image,
    store_images_batch,
)
class TestDatabaseCatalogCrud(unittest.TestCase):
    """Tests for catalog CRUD helpers."""

    def setUp(self):
        """Create temporary database for each test."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as tf:
            self.temp_db_path = tf.name
        self.db = init_database(self.temp_db_path)

    def tearDown(self):
        """Clean up temporary database."""
        self.db.close()
        bak = self.temp_db_path + ".pre-key-migration.bak"
        if os.path.exists(bak):
            os.unlink(bak)
        os.unlink(self.temp_db_path)

    def test_generate_key(self):
        """Test key generation."""
        record = {'date_taken': '2024-01-15', 'filename': 'photo.jpg'}
        key = generate_key(record)
        self.assertEqual(key, '2024-01-15_photo.jpg')

    def test_generate_key_truncates_iso_datetime(self):
        """ISO datetime date_taken yields YYYY-MM-DD portion only in key."""
        key = generate_key({'date_taken': '2024-01-15T14:30:00', 'filename': 'x.jpg'})
        self.assertEqual(key, '2024-01-15_x.jpg')

    def test_store_image(self):
        """Test storing a single image."""
        record = {
            'date_taken': '2024-01-15',
            'filename': 'photo.jpg',
            'rating': 5
        }
        key = store_image(self.db, record)
        self.assertEqual(key, '2024-01-15_photo.jpg')
        self.assertEqual(get_image_count(self.db), 1)

    def test_store_image_upsert(self):
        """Test upsert behavior - same key updates."""
        record1 = {
            'date_taken': '2024-01-15',
            'filename': 'photo.jpg',
            'rating': 5
        }
        store_image(self.db, record1)

        record2 = {
            'date_taken': '2024-01-15',
            'filename': 'photo.jpg',
            'rating': 3
        }
        store_image(self.db, record2)

        self.assertEqual(get_image_count(self.db), 1)
        img = get_image(self.db, '2024-01-15_photo.jpg')
        self.assertEqual(img['rating'], 3)

    def test_store_image_upsert_refreshes_id_column(self):
        """Upsert on same composite key updates Lightroom id_local column."""
        store_image(self.db, {
            'date_taken': '2024-01-15',
            'filename': 'photo.jpg',
            'id': '1',
        })
        store_image(self.db, {
            'date_taken': '2024-01-15',
            'filename': 'photo.jpg',
            'id': '2',
        })
        img = get_image(self.db, '2024-01-15_photo.jpg')
        self.assertEqual(img['id'], '2')

    def test_store_images_batch(self):
        """Test batch storing images."""
        records = [
            {'date_taken': '2024-01-15', 'filename': 'photo1.jpg'},
            {'date_taken': '2024-01-16', 'filename': 'photo2.jpg'},
            {'date_taken': '2024-01-17', 'filename': 'photo3.jpg'},
        ]
        count = store_images_batch(self.db, records)
        self.assertEqual(count, 3)
        self.assertEqual(get_image_count(self.db), 3)

    def test_get_image(self):
        """Test retrieving an image."""
        record = {'date_taken': '2024-01-15', 'filename': 'photo.jpg'}
        store_image(self.db, record)

        img = get_image(self.db, '2024-01-15_photo.jpg')
        self.assertIsNotNone(img)
        self.assertEqual(img['filename'], 'photo.jpg')

    def test_get_image_not_found(self):
        """Test retrieving non-existent image."""
        img = get_image(self.db, 'nonexistent_key')
        self.assertIsNone(img)

    def test_get_all_images(self):
        """Test getting all images."""
        records = [
            {'date_taken': '2024-01-15', 'filename': 'photo1.jpg'},
            {'date_taken': '2024-01-16', 'filename': 'photo2.jpg'},
        ]
        store_images_batch(self.db, records)

        all_images = get_all_images(self.db)
        self.assertEqual(len(all_images), 2)

    def test_delete_image(self):
        """Test deleting an image."""
        record = {'date_taken': '2024-01-15', 'filename': 'photo.jpg'}
        store_image(self.db, record)

        deleted = delete_image(self.db, '2024-01-15_photo.jpg')
        self.assertTrue(deleted)
        self.assertEqual(get_image_count(self.db), 0)

    def test_clear_all(self):
        """Test clearing all images."""
        records = [
            {'date_taken': '2024-01-15', 'filename': 'photo1.jpg'},
            {'date_taken': '2024-01-16', 'filename': 'photo2.jpg'},
        ]
        store_images_batch(self.db, records)

        count = clear_all(self.db)
        self.assertEqual(count, 2)
        self.assertEqual(get_image_count(self.db), 0)


class TestQueryCatalogImages(unittest.TestCase):
    """Tests for query_catalog_images."""

    def setUp(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tf:
            self.temp_db_path = tf.name
        self.db = init_database(self.temp_db_path)
        store_image(self.db, {
            'date_taken': '2024-03-10',
            'filename': 'low_rating.jpg',
            'rating': 2,
            'color_label': 'Red',
            'keywords': ['foo'],
            'instagram_posted': False,
        })
        store_image(self.db, {
            'date_taken': '2024-04-20T12:00:00',
            'filename': 'beta_unique.jpg',
            'rating': 4,
            'color_label': 'Blue',
            'keywords': ['bar'],
            'instagram_posted': True,
        })
        store_image(self.db, {
            'date_taken': '2025-01-10',
            'filename': 'high.jpg',
            'rating': 5,
            'color_label': 'Green',
            'keywords': ['baz'],
            'instagram_posted': False,
        })

    def tearDown(self):
        self.db.close()
        bak = self.temp_db_path + ".pre-key-migration.bak"
        if os.path.exists(bak):
            os.unlink(bak)
        os.unlink(self.temp_db_path)

    def test_min_rating_filter(self):
        rows, total = query_catalog_images(self.db, min_rating=3)
        self.assertEqual(total, 2)
        keys = {r['key'] for r in rows}
        self.assertEqual(
            keys,
            {'2024-04-20_beta_unique.jpg', '2025-01-10_high.jpg'},
        )

    def test_keyword_matches_filename(self):
        rows, total = query_catalog_images(self.db, keyword='beta_unique')
        self.assertEqual(total, 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['filename'], 'beta_unique.jpg')

    def test_month_filter(self):
        rows, total = query_catalog_images(self.db, month='202404')
        self.assertEqual(total, 1)
        self.assertEqual(rows[0]['filename'], 'beta_unique.jpg')
