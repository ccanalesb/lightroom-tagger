import os
import sqlite3
import unittest
from unittest.mock import MagicMock, patch

from lightroom_tagger.lightroom.reader import (
    connect_catalog,
    generate_record_key,
)


class TestReader(unittest.TestCase):
    """Tests for lightroom reader functions."""

    @patch('lightroom_tagger.lightroom.reader.sqlite3.connect')
    def test_connect_catalog_uses_read_only_uri_by_default(self, mock_connect):
        """Default path opens catalog via SQLite URI with mode=ro."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        env = {k: v for k, v in os.environ.items() if k != 'LIGHTRoom_CATALOG_READONLY_URI'}
        with patch.dict(os.environ, env, clear=True):
            conn = connect_catalog('/test/catalog.lrcat')

        mock_connect.assert_called_once()
        args, kwargs = mock_connect.call_args
        self.assertIn('mode=ro', args[0])
        self.assertTrue(kwargs.get('uri'))
        self.assertEqual(kwargs.get('timeout'), 30.0)
        self.assertEqual(conn.row_factory, sqlite3.Row)

    @patch.dict(os.environ, {'LIGHTRoom_CATALOG_READONLY_URI': '0'}, clear=False)
    @patch('lightroom_tagger.lightroom.reader.sqlite3.connect')
    def test_connect_catalog_plain_path_when_readonly_uri_disabled(self, mock_connect):
        """LIGHTRoom_CATALOG_READONLY_URI=0 uses plain path connect (no uri=True)."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        conn = connect_catalog('/test/catalog.lrcat')

        mock_connect.assert_called_once_with('/test/catalog.lrcat', timeout=30.0)
        self.assertNotEqual(mock_connect.call_args.kwargs.get('uri'), True)
        self.assertEqual(conn.row_factory, sqlite3.Row)

    def test_generate_record_key(self):
        """Test record key generation."""
        record = {'date_taken': '2024-01-15T10:30:00', 'filename': 'photo.jpg'}
        key = generate_record_key(record)
        self.assertEqual(key, '2024-01-15_photo.jpg')

    def test_generate_record_key_no_date(self):
        """Test record key with missing date."""
        record = {'filename': 'photo.jpg'}
        key = generate_record_key(record)
        self.assertEqual(key, 'unknown_photo.jpg')

    def test_generate_record_key_no_filename(self):
        """Test record key with missing filename."""
        record = {'date_taken': '2024-01-15'}
        key = generate_record_key(record)
        self.assertEqual(key, '2024-01-15_unknown')


if __name__ == "__main__":
    unittest.main()
