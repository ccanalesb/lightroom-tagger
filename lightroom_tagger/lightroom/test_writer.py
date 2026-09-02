"""Integration tests for reversible Lightroom keyword writes."""

from __future__ import annotations

import io
import sqlite3
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

from lightroom_tagger.lightroom.writer import (
    CULL_KEYWORD,
    add_keyword_by_key,
    add_keyword_to_image,
    connect_catalog,
    create_keyword,
    get_keyword_id,
    get_or_create_keyword,
    image_has_keyword,
    keyword_exists,
    raise_if_catalog_locked,
    remove_keyword_by_key,
    remove_keyword_from_image,
)


def _make_catalog(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE AgLibraryKeyword (
            id_local INTEGER PRIMARY KEY AUTOINCREMENT,
            id_global TEXT,
            name TEXT,
            lc_name TEXT,
            dateCreated TEXT,
            keywordType INTEGER
        );
        CREATE TABLE AgLibraryFile (
            id_local INTEGER PRIMARY KEY,
            baseName TEXT
        );
        CREATE TABLE Adobe_images (
            id_local INTEGER PRIMARY KEY,
            rootFile INTEGER
        );
        CREATE TABLE AgLibraryKeywordImage (
            id_local INTEGER PRIMARY KEY AUTOINCREMENT,
            image INTEGER,
            tag INTEGER
        );
        INSERT INTO AgLibraryFile (id_local, baseName) VALUES (1, 'L1007324');
        INSERT INTO Adobe_images (id_local, rootFile) VALUES (100, 1);
        """
    )
    conn.commit()
    return conn


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
        with (
            patch('lightroom_tagger.lightroom.writer.get_keyword_id', return_value=None),
            patch('lightroom_tagger.lightroom.writer.create_keyword', return_value=99),
        ):
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


class TestWriterIntegration(unittest.TestCase):
    """Catalog-backed tests for add/remove keyword behavior."""

    def setUp(self):
        import tempfile

        self.tmp = Path(tempfile.mkdtemp(prefix="writer-test-"))
        self.catalog_path = self.tmp / "test.lrcat"
        self.conn = _make_catalog(self.catalog_path)
        self.image_key = "2026-01-01_L1007324.JPG"

    def tearDown(self):
        self.conn.close()
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_add_reports_three_outcomes(self):
        self.assertEqual(add_keyword_by_key(self.conn, self.image_key, CULL_KEYWORD), "added")
        self.assertEqual(add_keyword_by_key(self.conn, self.image_key, CULL_KEYWORD), "already_present")
        self.assertEqual(
            add_keyword_by_key(self.conn, "2026-01-01_missing.jpg", CULL_KEYWORD),
            "image_not_found",
        )

    def test_remove_untags_image_and_leaves_keyword_row(self):
        add_keyword_by_key(self.conn, self.image_key, CULL_KEYWORD)
        kw_id = get_keyword_id(self.conn, CULL_KEYWORD)
        assert kw_id is not None

        self.assertEqual(remove_keyword_by_key(self.conn, self.image_key, CULL_KEYWORD), "removed")
        self.assertEqual(remove_keyword_by_key(self.conn, self.image_key, CULL_KEYWORD), "not_present")
        self.assertIsNotNone(get_keyword_id(self.conn, CULL_KEYWORD))

    def test_add_remove_add_toggle(self):
        self.assertEqual(add_keyword_by_key(self.conn, self.image_key, CULL_KEYWORD), "added")
        self.assertEqual(remove_keyword_by_key(self.conn, self.image_key, CULL_KEYWORD), "removed")
        self.assertEqual(add_keyword_by_key(self.conn, self.image_key, CULL_KEYWORD), "added")

    def test_remove_keyword_from_image_noop_when_absent(self):
        kw_id = get_or_create_keyword(self.conn, CULL_KEYWORD)
        self.assertFalse(remove_keyword_from_image(self.conn, 100, kw_id))

    def test_write_path_does_not_print_to_stdout(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            add_keyword_by_key(self.conn, self.image_key, CULL_KEYWORD)
            add_keyword_by_key(self.conn, "missing-key", CULL_KEYWORD)
            remove_keyword_by_key(self.conn, self.image_key, CULL_KEYWORD)
        self.assertEqual(buf.getvalue(), "")

    def test_locked_catalog_raises_clear_error(self):
        lock_path = self.catalog_path.parent / f"{self.catalog_path.stem}.lrcat-lock"
        lock_path.write_text("locked")
        try:
            with self.assertRaises(RuntimeError) as ctx:
                raise_if_catalog_locked(str(self.catalog_path))
            self.assertIn("Close Lightroom", str(ctx.exception))
        finally:
            lock_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
