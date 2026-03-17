import unittest
from unittest.mock import patch, MagicMock
import sqlite3
from lightroom_tagger.lightroom.writer import (
    connect_catalog,
    get_keyword_id,
    keyword_exists,
    create_keyword,
    get_or_create_keyword,
    image_has_keyword,
    add_keyword_to_image,
)


class TestWriter(unittest.TestCase):
    """Tests for lightroom writer functions."""

    def setUp(self):
        """Create mock database connection."""
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_conn.cursor.return_value = self.mock_cursor

    @patch('lightroom_tagger.lightroom.writer.sqlite3.connect')
    def test_connect_catalog(self, mock_connect):
        """Test connecting to catalog."""
        mock_connect.return_value = self.mock_conn
        
        conn = connect_catalog('/test/catalog.lrcat')
        
        mock_connect.assert_called_once_with('/test/catalog.lrcat')
        self.assertEqual(conn.row_factory, sqlite3.Row)

    def test_get_keyword_id_exists(self):
        """Test getting existing keyword ID."""
        self.mock_cursor.fetchone.return_value = (42,)
        
        result = get_keyword_id(self.mock_conn, 'Nature')
        
        self.assertEqual(result, 42)
        self.mock_cursor.execute.assert_called_once()

    def test_get_keyword_id_not_exists(self):
        """Test getting non-existent keyword ID."""
        self.mock_cursor.fetchone.return_value = None
        
        result = get_keyword_id(self.mock_conn, 'NonExistent')
        
        self.assertIsNone(result)

    def test_keyword_exists_true(self):
        """Test keyword exists returns True."""
        with patch('lightroom_tagger.lightroom.writer.get_keyword_id', return_value=42):
            result = keyword_exists(self.mock_conn, 'Nature')
            self.assertTrue(result)

    def test_keyword_exists_false(self):
        """Test keyword exists returns False."""
        with patch('lightroom_tagger.lightroom.writer.get_keyword_id', return_value=None):
            result = keyword_exists(self.mock_conn, 'NonExistent')
            self.assertFalse(result)

    def test_create_keyword(self):
        """Test creating new keyword."""
        self.mock_cursor.lastrowid = 99
        
        result = create_keyword(self.mock_conn, 'NewKeyword')
        
        self.assertEqual(result, 99)
        self.mock_conn.commit.assert_called_once()

    def test_get_or_create_keyword_existing(self):
        """Test getting existing keyword."""
        with patch('lightroom_tagger.lightroom.writer.get_keyword_id', return_value=42):
            result = get_or_create_keyword(self.mock_conn, 'Existing')
            self.assertEqual(result, 42)

    def test_get_or_create_keyword_new(self):
        """Test creating new keyword when not exists."""
        with patch('lightroom_tagger.lightroom.writer.get_keyword_id', return_value=None):
            with patch('lightroom_tagger.lightroom.writer.create_keyword', return_value=99):
                result = get_or_create_keyword(self.mock_conn, 'New')
                self.assertEqual(result, 99)

    def test_image_has_keyword_true(self):
        """Test image has keyword returns True."""
        self.mock_cursor.fetchone.return_value = (1,)
        
        result = image_has_keyword(self.mock_conn, 1, 42)
        
        self.assertTrue(result)

    def test_image_has_keyword_false(self):
        """Test image has keyword returns False."""
        self.mock_cursor.fetchone.return_value = (0,)
        
        result = image_has_keyword(self.mock_conn, 1, 42)
        
        self.assertFalse(result)

    def test_add_keyword_to_image_already_exists(self):
        """Test adding keyword when already exists."""
        with patch('lightroom_tagger.lightroom.writer.image_has_keyword', return_value=True):
            result = add_keyword_to_image(self.mock_conn, 1, 42)
            self.assertFalse(result)

    def test_add_keyword_to_image_success(self):
        """Test successfully adding keyword."""
        with patch('lightroom_tagger.lightroom.writer.image_has_keyword', return_value=False):
            result = add_keyword_to_image(self.mock_conn, 1, 42)
            self.assertTrue(result)
            self.mock_conn.commit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
