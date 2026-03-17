import unittest
from unittest.mock import patch, MagicMock
import sqlite3
from lightroom_tagger.lightroom.reader import (
    connect_catalog,
    generate_record_key,
)


class TestReader(unittest.TestCase):
    """Tests for lightroom reader functions."""

    @patch('lightroom_tagger.lightroom.reader.sqlite3.connect')
    def test_connect_catalog(self, mock_connect):
        """Test connecting to catalog."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        
        conn = connect_catalog('/test/catalog.lrcat')
        
        mock_connect.assert_called_once_with('/test/catalog.lrcat')
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
