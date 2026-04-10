import os
import tempfile
import unittest

from lightroom_tagger.core.database import (
    batch_update_hashes,
    clear_all,
    delete_image,
    generate_key,
    get_all_images,
    get_image,
    get_image_count,
    get_image_description,
    get_images_without_hash,
    get_instagram_by_date_filter,
    get_undescribed_catalog_images,
    get_vision_comparison,
    init_database,
    init_image_descriptions_table,
    init_vision_comparisons_table,
    migrate_unified_image_keys,
    query_catalog_images,
    store_image,
    store_image_description,
    store_images_batch,
    store_match,
    store_vision_comparison,
    update_image_hash,
    update_instagram_status,
)


class TestDatabase(unittest.TestCase):
    """Tests for database functions."""

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

    def test_init_database(self):
        """Test database initialization."""
        row = self.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='images'"
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(get_image_count(self.db), 0)

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

    def test_migrate_unified_image_keys_rewrites_legacy_key(self):
        """Legacy full-datetime composite keys remap to YYYY-MM-DD_filename."""
        self.db.execute("PRAGMA user_version = 0")
        self.db.execute(
            """
            INSERT INTO images (key, id, filename, filepath, date_taken)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "2024-01-15T00:00:00_photo.jpg",
                "0",
                "photo.jpg",
                "",
                "2024-01-15T00:00:00",
            ),
        )
        self.db.commit()
        migrate_unified_image_keys(self.db)
        self.db.commit()
        row = self.db.execute("SELECT key FROM images").fetchone()
        self.assertEqual(row["key"], "2024-01-15_photo.jpg")


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


class TestInstagramStatus(unittest.TestCase):
    """Tests for Instagram status functions."""

    def setUp(self):
        """Create temporary database."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as tf:
            self.temp_db_path = tf.name
        self.db = init_database(self.temp_db_path)
        store_image(self.db, {
            'date_taken': '2024-01-15',
            'filename': 'photo.jpg'
        })

    def tearDown(self):
        """Clean up."""
        self.db.close()
        os.unlink(self.temp_db_path)

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


class TestInstagramDumpMedia(unittest.TestCase):
    """Tests for Instagram dump media functions."""

    def setUp(self):
        """Create temporary database."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as tf:
            self.temp_db_path = tf.name
        self.db = init_database(self.temp_db_path)

    def tearDown(self):
        """Clean up."""
        self.db.close()
        os.unlink(self.temp_db_path)

    def test_init_instagram_dump_table(self):
        """Test instagram_dump_media table initialization."""
        from lightroom_tagger.core.database import init_instagram_dump_table

        init_instagram_dump_table(self.db)
        row = self.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='instagram_dump_media'"
        ).fetchone()
        self.assertIsNotNone(row)

    def test_store_instagram_dump_media(self):
        """Test storing Instagram dump media record."""
        from lightroom_tagger.core.database import (
            get_instagram_dump_media,
            init_instagram_dump_table,
            store_instagram_dump_media,
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
            get_unprocessed_dump_media,
            init_instagram_dump_table,
            mark_dump_media_processed,
            store_instagram_dump_media,
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
            get_instagram_dump_media,
            init_instagram_dump_table,
            mark_dump_media_processed,
            store_instagram_dump_media,
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
            get_instagram_dump_media,
            init_instagram_dump_table,
            store_instagram_dump_media,
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
            get_dump_media_by_hash,
            get_instagram_dump_media,
            init_instagram_dump_table,
            store_instagram_dump_media,
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
            init_instagram_dump_table,
            store_instagram_dump_media,
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

    def test_mark_dump_media_attempted_keeps_unprocessed(self):
        """Attempted images stay unprocessed and are retryable in future runs."""
        from lightroom_tagger.core.database import (
            get_instagram_dump_media,
            get_unprocessed_dump_media,
            init_instagram_dump_table,
            mark_dump_media_attempted,
            store_instagram_dump_media,
        )

        init_instagram_dump_table(self.db)
        store_instagram_dump_media(self.db, {
            'media_key': '202603/attempt_test',
            'file_path': '/path/to/file.jpg',
            'filename': 'file.jpg',
        })

        mark_dump_media_attempted(self.db, '202603/attempt_test',
                                   vision_result='DIFFERENT', vision_score=0.3)

        stored = get_instagram_dump_media(self.db, '202603/attempt_test')
        self.assertFalse(stored['processed'])
        self.assertIsNotNone(stored['last_attempted_at'])
        self.assertEqual(stored['vision_result'], 'DIFFERENT')

        # Still returned by get_unprocessed (no run_start filter)
        unprocessed = get_unprocessed_dump_media(self.db)
        self.assertEqual(len(unprocessed), 1)

    def test_run_start_skips_recently_attempted(self):
        """Images attempted in the current run are skipped via run_start."""
        from datetime import datetime, timedelta

        from lightroom_tagger.core.database import (
            get_instagram_by_date_filter,
            get_unprocessed_dump_media,
            init_instagram_dump_table,
            mark_dump_media_attempted,
            store_instagram_dump_media,
        )

        init_instagram_dump_table(self.db)

        store_instagram_dump_media(self.db, {
            'media_key': '202603/fresh',
            'date_folder': '202603',
            'file_path': '/path/fresh.jpg',
        })
        store_instagram_dump_media(self.db, {
            'media_key': '202603/attempted',
            'date_folder': '202603',
            'file_path': '/path/attempted.jpg',
        })

        run_start = datetime.now().isoformat()
        mark_dump_media_attempted(self.db, '202603/attempted')

        # With run_start, the attempted one is skipped
        result = get_unprocessed_dump_media(self.db, run_start=run_start)
        keys = [r['media_key'] for r in result]
        self.assertIn('202603/fresh', keys)
        self.assertNotIn('202603/attempted', keys)

        # Without run_start (new run), both are returned
        result_all = get_unprocessed_dump_media(self.db)
        self.assertEqual(len(result_all), 2)

        # Same behavior via date filter
        result_date = get_instagram_by_date_filter(self.db, month='202603', run_start=run_start)
        keys_date = [r['media_key'] for r in result_date]
        self.assertIn('202603/fresh', keys_date)
        self.assertNotIn('202603/attempted', keys_date)


    def test_include_processed_returns_all_media(self):
        """include_processed=True returns both processed and unprocessed rows."""
        from lightroom_tagger.core.database import (
            get_unprocessed_dump_media,
            init_instagram_dump_table,
            mark_dump_media_processed,
            store_instagram_dump_media,
        )

        init_instagram_dump_table(self.db)

        store_instagram_dump_media(self.db, {
            'media_key': '202603/processed_one',
            'file_path': '/path/processed.jpg',
        })
        store_instagram_dump_media(self.db, {
            'media_key': '202603/unprocessed_one',
            'file_path': '/path/unprocessed.jpg',
        })

        mark_dump_media_processed(self.db, '202603/processed_one',
                                   matched_catalog_key='cat_1')

        without = get_unprocessed_dump_media(self.db, include_processed=False)
        self.assertEqual(len(without), 1)

        with_all = get_unprocessed_dump_media(self.db, include_processed=True)
        self.assertEqual(len(with_all), 2)

    def test_include_processed_with_date_filter(self):
        """include_processed works with get_instagram_by_date_filter too."""
        from lightroom_tagger.core.database import (
            init_instagram_dump_table,
            mark_dump_media_processed,
            store_instagram_dump_media,
        )

        init_instagram_dump_table(self.db)

        store_instagram_dump_media(self.db, {
            'media_key': '202603/processed_date',
            'date_folder': '202603',
            'file_path': '/path/processed.jpg',
        })
        store_instagram_dump_media(self.db, {
            'media_key': '202603/unprocessed_date',
            'date_folder': '202603',
            'file_path': '/path/unprocessed.jpg',
        })

        mark_dump_media_processed(self.db, '202603/processed_date',
                                   matched_catalog_key='cat_1')

        without = get_instagram_by_date_filter(self.db, month='202603',
                                                include_processed=False)
        self.assertEqual(len(without), 1)

        with_all = get_instagram_by_date_filter(self.db, month='202603',
                                                 include_processed=True)
        self.assertEqual(len(with_all), 2)


class TestImageDescriptions(unittest.TestCase):
    """Tests for image_descriptions table functions."""

    def setUp(self):
        fd, self.temp_db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        self.db = init_database(self.temp_db_path)

    def tearDown(self):
        self.db.close()
        os.unlink(self.temp_db_path)

    def test_init_descriptions_table(self):
        init_image_descriptions_table(self.db)
        # Should not raise - table already exists from init_database
        self.db.execute("SELECT COUNT(*) FROM image_descriptions")

    def test_store_image_description(self):
        record = {
            'image_key': '2024-01-15_photo.jpg',
            'image_type': 'catalog',
            'summary': 'A street scene at golden hour',
            'composition': {'layers': ['foreground', 'background'], 'techniques': ['rule_of_thirds']},
            'perspectives': {
                'street': {'analysis': 'Strong geometry', 'score': 7},
                'documentary': {'analysis': 'Fair story', 'score': 5},
                'publisher': {'analysis': 'Editorial use', 'score': 6},
            },
            'technical': {'dominant_colors': ['#2b3a4c'], 'mood': 'contemplative'},
            'subjects': ['person', 'architecture'],
            'best_perspective': 'street',
            'model_used': 'gemma3:27b',
        }
        key = store_image_description(self.db, record)
        self.assertEqual(key, '2024-01-15_photo.jpg')

        stored = get_image_description(self.db, '2024-01-15_photo.jpg')
        self.assertIsNotNone(stored)
        self.assertEqual(stored['summary'], 'A street scene at golden hour')
        self.assertEqual(stored['perspectives']['street']['score'], 7)
        self.assertIn('described_at', stored)

    def test_get_image_description_not_found(self):
        self.assertIsNone(get_image_description(self.db, 'nonexistent'))

    def test_store_description_is_idempotent(self):
        store_image_description(self.db, {
            'image_key': 'key1', 'image_type': 'catalog',
            'summary': 'First', 'model_used': 'gemma3:27b',
        })
        store_image_description(self.db, {
            'image_key': 'key1', 'image_type': 'catalog',
            'summary': 'Updated', 'model_used': 'gemma3:27b',
        })
        stored = get_image_description(self.db, 'key1')
        self.assertEqual(stored['summary'], 'Updated')

    def test_get_undescribed_images(self):
        store_image(self.db, {'date_taken': '2024-01-15', 'filename': 'a.jpg'})
        store_image(self.db, {'date_taken': '2024-01-16', 'filename': 'b.jpg'})
        store_image_description(self.db, {
            'image_key': '2024-01-15_a.jpg', 'image_type': 'catalog',
            'summary': 'Described', 'model_used': 'gemma3:27b',
        })
        undescribed = get_undescribed_catalog_images(self.db)
        keys = [img['key'] for img in undescribed]
        self.assertIn('2024-01-16_b.jpg', keys)
        self.assertNotIn('2024-01-15_a.jpg', keys)


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


if __name__ == "__main__":
    unittest.main()
