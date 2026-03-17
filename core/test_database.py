import unittest
import tempfile
import os
from tinydb import Query
from lightroom_tagger.core.database import (
    init_database,
    generate_key,
    store_image,
    store_images_batch,
    get_image,
    get_all_images,
    get_image_count,
    delete_image,
    clear_all,
    update_instagram_status,
    get_images_without_hash,
    update_image_hash,
    batch_update_hashes,
    store_catalog_image,
    store_instagram_image,
    store_match,
)


class TestDatabase(unittest.TestCase):
    """Tests for database functions."""

    def setUp(self):
        """Create temporary database for each test."""
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        self.temp_file.close()
        self.db = init_database(self.temp_file.name)

    def tearDown(self):
        """Clean up temporary database."""
        self.db.close()
        os.unlink(self.temp_file.name)

    def test_init_database(self):
        """Test database initialization."""
        self.assertEqual(self.db.default_table_name, 'images')
        self.assertEqual(get_image_count(self.db), 0)

    def test_generate_key(self):
        """Test key generation."""
        record = {'date_taken': '2024-01-15', 'filename': 'photo.jpg'}
        key = generate_key(record)
        self.assertEqual(key, '2024-01-15_photo.jpg')

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


class TestInstagramStatus(unittest.TestCase):
    """Tests for Instagram status functions."""

    def setUp(self):
        """Create temporary database."""
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        self.temp_file.close()
        self.db = init_database(self.temp_file.name)
        store_image(self.db, {
            'date_taken': '2024-01-15',
            'filename': 'photo.jpg'
        })

    def tearDown(self):
        """Clean up."""
        self.db.close()
        os.unlink(self.temp_file.name)

    def test_update_instagram_status(self):
        """Test updating Instagram status."""
        result = update_instagram_status(
            self.db,
            '2024-01-15_photo.jpg',
            posted=True,
            post_date='2024-02-01',
            url='https://instagram.com/p/abc123',
            index=0
        )
        self.assertTrue(result)
        
        img = get_image(self.db, '2024-01-15_photo.jpg')
        self.assertTrue(img['instagram_posted'])
        self.assertEqual(img['instagram_post_date'], '2024-02-01')
        self.assertEqual(img['instagram_url'], 'https://instagram.com/p/abc123')

    def test_get_images_without_hash(self):
        """Test finding images without hash."""
        records = [
            {'date_taken': '2024-01-15', 'filename': 'photo1.jpg'},
            {'date_taken': '2024-01-16', 'filename': 'photo2.jpg', 'image_hash': 'abc123'},
        ]
        store_images_batch(self.db, records)
        
        without_hash = get_images_without_hash(self.db)
        self.assertEqual(len(without_hash), 2)

    def test_update_image_hash(self):
        """Test updating image hash."""
        result = update_image_hash(self.db, '2024-01-15_photo.jpg', 'abc123def456')
        self.assertTrue(result)
        
        img = get_image(self.db, '2024-01-15_photo.jpg')
        self.assertEqual(img['image_hash'], 'abc123def456')

    def test_batch_update_hashes(self):
        """Test batch updating hashes."""
        store_image(self.db, {'date_taken': '2024-01-16', 'filename': 'photo2.jpg'})
        
        updates = [
            {'key': '2024-01-15_photo.jpg', 'image_hash': 'hash1'},
            {'key': '2024-01-16_photo2.jpg', 'image_hash': 'hash2'},
        ]
        count = batch_update_hashes(self.db, updates)
        self.assertEqual(count, 2)

    def test_store_catalog_image(self):
        """Store catalog image with analysis data."""
        from lightroom_tagger.core.database import store_catalog_image
        
        key = store_catalog_image(self.db, {
            'key': '2024-01-15_sunset.jpg',
            'filepath': '/mnt/nas/photos/sunset.jpg',
            'phash': 'a1b2c3d4e5f6g7h8',
            'exif': {'camera': 'Canon EOS R5', 'lens': 'RF 24-70mm'},
            'description': 'Golden hour sunset'
        })
        
        self.assertEqual(key, '2024-01-15_sunset.jpg')
        Catalog = Query()
        result = self.db.table('catalog_images').search(Catalog.key == key)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['phash'], 'a1b2c3d4e5f6g7h8')

    def test_store_instagram_image(self):
        """Store Instagram image with analysis data."""
        from lightroom_tagger.core.database import store_instagram_image
        
        key = store_instagram_image(self.db, {
            'post_url': 'https://instagram.com/p/abc123',
            'local_path': '/tmp/insta.jpg',
            'phash': 'a1b2c3d4e5f6g7h8',
            'exif': {'camera': 'Canon EOS R5'},
            'description': 'Beautiful sunset'
        })
        
        self.assertTrue(key.startswith('insta_'))
        Insta = Query()
        result = self.db.table('instagram_images').search(Insta.post_url == 'https://instagram.com/p/abc123')
        self.assertEqual(len(result), 1)

    def test_store_match(self):
        """Store match between catalog and Instagram image."""
        from lightroom_tagger.core.database import store_match
        
        store_match(self.db, {
            'catalog_key': '2024-01-15_sunset.jpg',
            'insta_key': 'insta_2024-01-16_post123',
            'phash_distance': 2,
            'phash_score': 0.875,
            'desc_similarity': 0.82,
            'exif_camera_match': True,
            'exif_lens_match': True,
            'total_score': 0.85
        })
        
        Match = Query()
        result = self.db.table('matches').search(Match.catalog_key == '2024-01-15_sunset.jpg')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['total_score'], 0.85)


if __name__ == "__main__":
    unittest.main()
