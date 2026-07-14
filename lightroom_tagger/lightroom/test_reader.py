import os
import sqlite3
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from lightroom_tagger.lightroom.reader import (
    connect_catalog,
    generate_record_key,
    resolve_catalog_locking_mode,
)


_CATALOG_ENV_KEYS = (
    'LIGHTROOM_CATALOG_READONLY_URI',
    'LIGHTRoom_CATALOG_READONLY_URI',
    'LIGHTROOM_CATALOG_LOCKING_MODE',
    'LIGHTRoom_CATALOG_LOCKING_MODE',
)


def _env_without_catalog_keys() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if k not in _CATALOG_ENV_KEYS}


class TestReader(unittest.TestCase):
    """Tests for lightroom reader functions."""

    @patch('lightroom_tagger.lightroom.reader.sqlite3.connect')
    def test_connect_catalog_uses_read_only_uri_by_default(self, mock_connect):
        """Default path opens catalog via SQLite URI with mode=ro."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        with patch.dict(os.environ, _env_without_catalog_keys(), clear=True):
            conn = connect_catalog('/test/catalog.lrcat')

        mock_connect.assert_called_once()
        args, kwargs = mock_connect.call_args
        self.assertIn('mode=ro', args[0])
        self.assertTrue(kwargs.get('uri'))
        self.assertEqual(kwargs.get('timeout'), 30.0)
        mock_conn.execute.assert_not_called()
        self.assertEqual(conn.row_factory, sqlite3.Row)

    @patch.dict(os.environ, {'LIGHTROOM_CATALOG_READONLY_URI': '0'}, clear=False)
    @patch('lightroom_tagger.lightroom.reader.sqlite3.connect')
    def test_connect_catalog_plain_path_when_readonly_uri_disabled(self, mock_connect):
        """LIGHTROOM_CATALOG_READONLY_URI=0 uses plain path connect (no uri=True)."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        conn = connect_catalog('/test/catalog.lrcat')

        mock_connect.assert_called_once_with('/test/catalog.lrcat', timeout=30.0)
        self.assertNotEqual(mock_connect.call_args.kwargs.get('uri'), True)
        mock_conn.execute.assert_called_once_with("PRAGMA locking_mode=EXCLUSIVE")
        self.assertEqual(conn.row_factory, sqlite3.Row)

    @patch.dict(os.environ, {'LIGHTRoom_CATALOG_READONLY_URI': '0'}, clear=False)
    @patch('lightroom_tagger.lightroom.reader.sqlite3.connect')
    def test_connect_catalog_legacy_readonly_uri_alias(self, mock_connect):
        """Legacy LIGHTRoom_CATALOG_READONLY_URI=0 alias is honored."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        connect_catalog('/test/catalog.lrcat')

        mock_connect.assert_called_once_with('/test/catalog.lrcat', timeout=30.0)

    def test_read_only_default_locking_mode_is_normal(self):
        """Read-only URI opens default to NORMAL locking (no EXCLUSIVE pragma)."""
        self.assertEqual(resolve_catalog_locking_mode(read_only=True), 'NORMAL')

    def test_read_write_default_locking_mode_is_exclusive(self):
        """Legacy read-write opens still default to EXCLUSIVE for NAS/WAL."""
        self.assertEqual(resolve_catalog_locking_mode(read_only=False), 'EXCLUSIVE')

    @patch.dict(os.environ, {'LIGHTROOM_CATALOG_LOCKING_MODE': 'NORMAL'}, clear=False)
    def test_locking_mode_env_override(self):
        self.assertEqual(resolve_catalog_locking_mode(read_only=True), 'NORMAL')
        self.assertEqual(resolve_catalog_locking_mode(read_only=False), 'NORMAL')

    @patch.dict(os.environ, {'LIGHTRoom_CATALOG_LOCKING_MODE': 'NORMAL'}, clear=False)
    def test_locking_mode_legacy_env_alias(self):
        self.assertEqual(resolve_catalog_locking_mode(read_only=False), 'NORMAL')

    def test_connect_catalog_read_only_opens_without_exclusive(self):
        """Opening a read-only catalog with default settings does not raise."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tf:
            path = tf.name
        try:
            setup = sqlite3.connect(path)
            setup.execute('CREATE TABLE t (id INTEGER)')
            setup.execute('INSERT INTO t (id) VALUES (1)')
            setup.commit()
            setup.close()

            with patch.dict(os.environ, _env_without_catalog_keys(), clear=True):
                conn = connect_catalog(path)
            try:
                mode = conn.execute('PRAGMA locking_mode').fetchone()[0]
                self.assertEqual(mode.lower(), 'normal')
                count = conn.execute('SELECT COUNT(*) FROM t').fetchone()[0]
                self.assertEqual(count, 1)
            finally:
                conn.close()
        finally:
            os.unlink(path)

    @patch('lightroom_tagger.lightroom.reader.logger')
    @patch('lightroom_tagger.lightroom.reader.sqlite3.connect')
    def test_connect_catalog_exclusive_fallback_on_read_only_io_error(self, mock_connect, mock_logger):
        """EXCLUSIVE on read-only falls back to NORMAL when pragma raises disk I/O error."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        def execute_side_effect(sql, *args, **kwargs):
            if 'locking_mode=EXCLUSIVE' in sql:
                raise sqlite3.OperationalError('disk I/O error')
            return MagicMock()

        mock_conn.execute.side_effect = execute_side_effect

        env = _env_without_catalog_keys()
        env['LIGHTROOM_CATALOG_LOCKING_MODE'] = 'EXCLUSIVE'
        with patch.dict(os.environ, env, clear=True):
            connect_catalog('/test/catalog.lrcat')

        mock_logger.warning.assert_called_once()

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
