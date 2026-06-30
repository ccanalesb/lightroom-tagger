"""Tests for incremental catalog sync (set-difference, additions-only)."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from lightroom_tagger.core.catalog_sync import (
    CATALOG_LOCK_ACTIONABLE_MSG,
    CatalogSyncError,
    list_library_catalog_ids,
    sync_catalog,
)
from lightroom_tagger.core.database import get_image_count, init_database


def _insert_library_image(db: sqlite3.Connection, *, key: str, catalog_id: str | None) -> None:
    db.execute(
        """
        INSERT INTO images (key, id, filename, filepath, date_taken, rating, pick)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (key, catalog_id, 'photo.jpg', '/tmp/photo.jpg', '2024-01-01', 0, 0),
    )
    db.commit()


class TestCatalogSync(unittest.TestCase):
    def setUp(self) -> None:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tf:
            self.temp_db_path = tf.name
        self.db = init_database(self.temp_db_path)

    def tearDown(self) -> None:
        self.db.close()
        if os.path.exists(self.temp_db_path):
            os.unlink(self.temp_db_path)

    def test_list_library_catalog_ids_skips_empty_and_non_numeric(self) -> None:
        _insert_library_image(self.db, key='a', catalog_id='100')
        _insert_library_image(self.db, key='b', catalog_id='')
        _insert_library_image(self.db, key='c', catalog_id=None)
        _insert_library_image(self.db, key='d', catalog_id='not-a-number')
        _insert_library_image(self.db, key='e', catalog_id='9999')

        ids = list_library_catalog_ids(self.db)
        self.assertEqual(ids, {100, 9999})

    @patch('lightroom_tagger.core.catalog_sync.get_image_by_id')
    @patch('lightroom_tagger.core.catalog_sync.list_catalog_file_ids')
    @patch('lightroom_tagger.core.catalog_sync.connect_catalog')
    def test_sync_fetches_only_missing_ids(
        self,
        mock_connect: MagicMock,
        mock_list_ids: MagicMock,
        mock_get_by_id: MagicMock,
    ) -> None:
        _insert_library_image(self.db, key='existing', catalog_id='1')
        _insert_library_image(self.db, key='gap', catalog_id='5')

        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_list_ids.return_value = [1, 2, 3, 5, 99999]

        def fake_record(image_id: int, _conn: MagicMock) -> dict:
            return {
                'id': image_id,
                'filename': f'img{image_id}.jpg',
                'date_taken': '2024-06-01',
                'filepath': f'/tmp/img{image_id}.jpg',
            }

        mock_get_by_id.side_effect = lambda conn, image_id: fake_record(image_id, conn)

        result = sync_catalog('/fake/catalog.lrcat', self.db)

        self.assertEqual(result.added, 3)
        self.assertEqual(result.stale, 0)
        self.assertEqual(result.missing_ids_count, 3)
        self.assertEqual(mock_get_by_id.call_count, 3)
        fetched_ids = sorted(call.args[1] for call in mock_get_by_id.call_args_list)
        self.assertEqual(fetched_ids, [2, 3, 99999])
        self.assertEqual(get_image_count(self.db), 5)

    @patch('lightroom_tagger.core.catalog_sync.get_image_by_id')
    @patch('lightroom_tagger.core.catalog_sync.list_catalog_file_ids')
    @patch('lightroom_tagger.core.catalog_sync.connect_catalog')
    def test_sync_reports_stale_library_ids(
        self,
        mock_connect: MagicMock,
        mock_list_ids: MagicMock,
        mock_get_by_id: MagicMock,
    ) -> None:
        _insert_library_image(self.db, key='gone', catalog_id='42')

        mock_connect.return_value = MagicMock()
        mock_list_ids.return_value = []
        mock_get_by_id.return_value = None

        result = sync_catalog('/fake/catalog.lrcat', self.db)

        self.assertEqual(result.added, 0)
        self.assertEqual(result.stale, 1)
        mock_get_by_id.assert_not_called()
        self.assertEqual(get_image_count(self.db), 1)

    @patch('lightroom_tagger.core.catalog_sync.list_catalog_file_ids')
    @patch('lightroom_tagger.core.catalog_sync.connect_catalog')
    def test_sync_uses_numeric_not_lexicographic_ids(
        self,
        mock_connect: MagicMock,
        mock_list_ids: MagicMock,
    ) -> None:
        _insert_library_image(self.db, key='high', catalog_id='38887')

        mock_connect.return_value = MagicMock()
        mock_list_ids.return_value = [38887, 99999]

        with patch('lightroom_tagger.core.catalog_sync.get_image_by_id') as mock_get:
            mock_get.return_value = {
                'id': 99999,
                'filename': 'new.jpg',
                'date_taken': '2024-06-02',
                'filepath': '/tmp/new.jpg',
            }
            result = sync_catalog('/fake/catalog.lrcat', self.db)

        self.assertEqual(result.added, 1)
        self.assertEqual(result.missing_ids_count, 1)
        mock_get.assert_called_once()
        self.assertEqual(mock_get.call_args[0][1], 99999)

    @patch('lightroom_tagger.core.catalog_sync.connect_catalog')
    def test_sync_raises_actionable_error_when_catalog_locked(self, mock_connect: MagicMock) -> None:
        mock_connect.side_effect = sqlite3.OperationalError('database is locked')

        with self.assertRaises(CatalogSyncError) as ctx:
            sync_catalog('/fake/catalog.lrcat', self.db)

        self.assertEqual(str(ctx.exception), CATALOG_LOCK_ACTIONABLE_MSG)


if __name__ == '__main__':
    unittest.main()
