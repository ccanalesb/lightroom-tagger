import unittest
from unittest.mock import patch, MagicMock
import sqlite3
import pytest
from lightroom_tagger.lightroom.writer import (
    connect_catalog,
    get_keyword_id,
    keyword_exists,
    create_keyword,
    get_or_create_keyword,
    image_has_keyword,
    add_keyword_to_image,
    get_image_local_id,
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


def test_get_image_local_id_returns_adobe_image_id(tmp_path):
    """Should return Adobe_images.id_local, NOT AgLibraryFile.id_local."""
    import sqlite3
    from lightroom_tagger.lightroom.writer import get_image_local_id
    
    catalog = tmp_path / "test.lrcat"
    conn = sqlite3.connect(str(catalog))
    
    # Create schema matching actual Lightroom
    conn.execute("""
        CREATE TABLE AgLibraryFile (
            id_local INTEGER PRIMARY KEY,
            baseName TEXT,
            extension TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE Adobe_images (
            id_local INTEGER PRIMARY KEY,
            rootFile INTEGER
        )
    """)
    
    # Insert test data
    # File ID 5648, image ID 3733 (like real data)
    conn.execute("INSERT INTO AgLibraryFile (id_local, baseName, extension) VALUES (5648, 'R0000034', 'JPG')")
    conn.execute("INSERT INTO Adobe_images (id_local, rootFile) VALUES (3733, 5648)")
    conn.commit()
    
    # Test: should return IMAGE id (3733), not FILE id (5648)
    result = get_image_local_id(conn, "2026-01-15_R0000034.JPG")
    
    assert result == 3733, f"Expected Adobe_images.id_local (3733), got {result}"
    
    conn.close()


def test_get_image_local_id_with_dng(tmp_path):
    """Should correctly resolve DNG files to Adobe_images."""
    import sqlite3
    from lightroom_tagger.lightroom.writer import get_image_local_id
    
    catalog = tmp_path / "test.lrcat"
    conn = sqlite3.connect(str(catalog))
    
    conn.execute("""
        CREATE TABLE AgLibraryFile (
            id_local INTEGER PRIMARY KEY,
            baseName TEXT,
            extension TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE Adobe_images (
            id_local INTEGER PRIMARY KEY,
            rootFile INTEGER
        )
    """)
    
    # File ID 303, image ID 265
    conn.execute("INSERT INTO AgLibraryFile (id_local, baseName, extension) VALUES (303, 'L1007324', 'DNG')")
    conn.execute("INSERT INTO Adobe_images (id_local, rootFile) VALUES (265, 303)")
    conn.commit()
    
    result = get_image_local_id(conn, "L1007324.DNG")
    
    assert result == 265, f"Expected Adobe_images.id_local (265), got {result}"
    
    conn.close()


def test_get_image_local_id_not_found_returns_none(tmp_path):
    """Should return None if image not found."""
    import sqlite3
    from lightroom_tagger.lightroom.writer import get_image_local_id
    
    catalog = tmp_path / "test.lrcat"
    conn = sqlite3.connect(str(catalog))
    
    conn.execute("""
        CREATE TABLE AgLibraryFile (
            id_local INTEGER PRIMARY KEY,
            baseName TEXT,
            extension TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE Adobe_images (
            id_local INTEGER PRIMARY KEY,
            rootFile INTEGER
        )
    """)
    conn.commit()
    
    result = get_image_local_id(conn, "NonExistent.DNG")
    
    assert result is None
    
    conn.close()


if __name__ == "__main__":
    unittest.main()
