import unittest
import tempfile
import os
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
    init_vision_comparisons_table,
    get_vision_comparison,
    store_vision_comparison,
    get_instagram_by_date_filter,
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


class TestVisionComparisonCache(unittest.TestCase):
    """Tests for vision comparison cache functions."""

    def setUp(self):
        """Create temporary database."""
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        self.temp_file.close()
        self.db = init_database(self.temp_file.name)
        init_vision_comparisons_table(self.db)

    def tearDown(self):
        """Clean up."""
        self.db.close()
        os.unlink(self.temp_file.name)

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


class TestInstagramDumpMedia(unittest.TestCase):
    """Tests for Instagram dump media functions."""

    def setUp(self):
        """Create temporary database."""
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        self.temp_file.close()
        self.db = init_database(self.temp_file.name)

    def tearDown(self):
        """Clean up."""
        self.db.close()
        os.unlink(self.temp_file.name)

    def test_init_instagram_dump_table(self):
        """Test instagram_dump_media table initialization."""
        from lightroom_tagger.core.database import init_instagram_dump_table

        init_instagram_dump_table(self.db)
        # Table is created lazily in TinyDB - verify by inserting and retrieving
        table = self.db.table('instagram_dump_media')
        table.insert({'test': True})
        self.assertIn('instagram_dump_media', self.db.tables())

    def test_store_instagram_dump_media(self):
        """Test storing Instagram dump media record."""
        from lightroom_tagger.core.database import (
            init_instagram_dump_table, store_instagram_dump_media, get_instagram_dump_media
        )

        init_instagram_dump_table(self.db)

        record = {
            'media_key': '202603/17940060624158613',
            'file_path': '/home/cristian/instagram-dump/media/posts/202603/17940060624158613.jpg',
            'caption': 'Spring is just around the corner',
            'created_at': '2025-03-15T10:00:00',
        }

        store_instagram_dump_media(self.db, record)

        # Verify stored
        stored = get_instagram_dump_media(self.db, '202603/17940060624158613')
        self.assertIsNotNone(stored)
        self.assertEqual(stored['media_key'], '202603/17940060624158613')
        self.assertEqual(stored['file_path'], '/home/cristian/instagram-dump/media/posts/202603/17940060624158613.jpg')
        self.assertEqual(stored['processed'], False)

    def test_get_unprocessed_dump_media(self):
        """Test getting unprocessed media."""
        from lightroom_tagger.core.database import (
            init_instagram_dump_table, store_instagram_dump_media, get_unprocessed_dump_media, mark_dump_media_processed
        )

        init_instagram_dump_table(self.db)

        # Store processed and unprocessed
        store_instagram_dump_media(self.db, {
            'media_key': '202603/17940060624158613',
            'file_path': '/path/to/file1.jpg',
            'filename': 'file1.jpg',
        })

        store_instagram_dump_media(self.db, {
            'media_key': '202603/17940060624158614',
            'file_path': '/path/to/file2.jpg',
            'filename': 'file2.jpg',
        })

        # Mark first as processed
        mark_dump_media_processed(self.db, '202603/17940060624158613', matched_catalog_key='catalog_123')

        # Verify only unprocessed returned
        unprocessed = get_unprocessed_dump_media(self.db)
        self.assertEqual(len(unprocessed), 1)
        self.assertEqual(unprocessed[0]['media_key'], '202603/17940060624158614')

    def test_mark_dump_media_processed(self):
        """Test marking media as processed."""
        from lightroom_tagger.core.database import (
            init_instagram_dump_table, store_instagram_dump_media, get_instagram_dump_media, mark_dump_media_processed
        )

        init_instagram_dump_table(self.db)

        # Store media
        store_instagram_dump_media(self.db, {
            'media_key': '202603/17940060624158613',
            'file_path': '/path/to/file.jpg',
            'filename': 'file.jpg',
        })

        # Mark as processed with match info
        mark_dump_media_processed(
            self.db, '202603/17940060624158613',
            matched_catalog_key='catalog_123',
            vision_result='SAME',
            vision_score=0.95
        )

        # Verify updated
        stored = get_instagram_dump_media(self.db, '202603/17940060624158613')
        self.assertTrue(stored['processed'])
        self.assertEqual(stored['matched_catalog_key'], 'catalog_123')
        self.assertEqual(stored['vision_result'], 'SAME')
        self.assertEqual(stored['vision_score'], 0.95)
        self.assertIsNotNone(stored['processed_at'])

    def test_store_instagram_dump_media_idempotent(self):
        """Test that storing same media_key updates existing record."""
        from lightroom_tagger.core.database import (
            init_instagram_dump_table, store_instagram_dump_media, get_instagram_dump_media
        )

        init_instagram_dump_table(self.db)

        # Store first time
        store_instagram_dump_media(self.db, {
            'media_key': '202603/17940060624158613',
            'file_path': '/path/to/file.jpg',
            'caption': 'Original caption',
        })

        # Store again with different caption
        store_instagram_dump_media(self.db, {
            'media_key': '202603/17940060624158613',
            'file_path': '/path/to/file.jpg',
            'caption': 'Updated caption',
        })

        # Verify updated
        stored = get_instagram_dump_media(self.db, '202603/17940060624158613')
        self.assertEqual(stored['caption'], 'Updated caption')

    def test_store_instagram_dump_media_with_hash(self):
        """Test storing media with image_hash."""
        from lightroom_tagger.core.database import (
            init_instagram_dump_table, store_instagram_dump_media, get_instagram_dump_media,
            get_dump_media_by_hash
        )

        init_instagram_dump_table(self.db)

        # Store with hash
        store_instagram_dump_media(self.db, {
            'media_key': '202603/111',
            'file_path': '/path/to/file1.jpg',
            'image_hash': 'abc123def456',
        })

        store_instagram_dump_media(self.db, {
            'media_key': '202603/222',
            'file_path': '/path/to/file2.jpg',
            'image_hash': 'abc123def456',  # Same hash - duplicate
        })

        # Verify stored
        stored1 = get_instagram_dump_media(self.db, '202603/111')
        self.assertEqual(stored1['image_hash'], 'abc123def456')

        # Verify get by hash returns both
        by_hash = get_dump_media_by_hash(self.db, 'abc123def456')
        self.assertEqual(len(by_hash), 2)

    def test_get_instagram_by_month_filter(self):
        """Test filtering Instagram images by month."""
        from lightroom_tagger.core.database import (
            init_instagram_dump_table, store_instagram_dump_media
        )

        init_instagram_dump_table(self.db)

        # Insert test data
        store_instagram_dump_media(self.db, {
            'media_key': '202603/123',
            'date_folder': '202603',
            'file_path': '/path/to/test1.jpg'
        })
        store_instagram_dump_media(self.db, {
            'media_key': '202604/456',
            'date_folder': '202604',
            'file_path': '/path/to/test2.jpg'
        })

        # Test month filter
        result = get_instagram_by_date_filter(self.db, month='202603')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['media_key'], '202603/123')


if __name__ == "__main__":
    unittest.main()
