"""Tests for Instagram status and dump-media helpers."""

import os
import tempfile
import unittest
from datetime import datetime, timedelta

import sqlite_vec

from lightroom_tagger.core.database import (
    batch_update_hashes,
    get_dump_media_by_hash,
    get_image,
    get_images_without_hash,
    get_instagram_by_date_filter,
    get_instagram_dump_media,
    get_unprocessed_dump_media,
    init_database,
    init_instagram_dump_table,
    library_write,
    list_instagram_dump_keys_needing_clip_embedding,
    mark_dump_media_attempted,
    mark_dump_media_processed,
    store_image,
    store_images_batch,
    store_instagram_dump_media,
    update_image_hash,
    update_instagram_status,
    upsert_image_clip_embedding,
)


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

        init_instagram_dump_table(self.db)
        row = self.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='instagram_dump_media'"
        ).fetchone()
        self.assertIsNotNone(row)

    def test_store_instagram_dump_media(self):
        """Test storing Instagram dump media record."""

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

    def test_list_instagram_dump_keys_needing_clip_embedding_anti_join(self):
        """SQL anti-join returns only missing embedding keys in date_folder/media_key order (WR-08-02)."""

        init_instagram_dump_table(self.db)
        row = self.db.execute("PRAGMA user_version").fetchone()
        self.assertGreaterEqual(int(row["user_version"]), 5)

        base = {'file_path': '/p/a.jpg', 'filename': 'a.jpg', 'date_folder': '202603'}
        store_instagram_dump_media(self.db, {**base, 'media_key': '202603/z'})
        store_instagram_dump_media(self.db, {**base, 'media_key': '202603/m'})
        store_instagram_dump_media(self.db, {**base, 'media_key': '202603/a'})

        blob = sqlite_vec.serialize_float32([0.0] * 512)
        with library_write(self.db):
            upsert_image_clip_embedding(self.db, '202603/m', blob)

        need = list_instagram_dump_keys_needing_clip_embedding(
            self.db, months=None, year=None, min_rating=None
        )
        self.assertEqual(need, ['202603/z', '202603/a'])

        with library_write(self.db):
            upsert_image_clip_embedding(self.db, '202603/z', blob)
            upsert_image_clip_embedding(self.db, '202603/a', blob)

        need_empty = list_instagram_dump_keys_needing_clip_embedding(
            self.db, months=None, year=None, min_rating=None
        )
        self.assertEqual(need_empty, [])

    def test_get_unprocessed_dump_media(self):
        """Test getting unprocessed media."""

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
