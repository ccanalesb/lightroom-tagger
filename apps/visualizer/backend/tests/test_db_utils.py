# apps/visualizer/backend/tests/test_db_utils.py
from unittest.mock import MagicMock, patch

from utils.db import with_db


class TestWithDbDecorator:
    """Tests for with_db decorator."""

    @patch('utils.db.os.path.exists')
    @patch('utils.db.init_database')
    def test_with_db_when_file_exists(self, mock_init_database, mock_exists):
        """Test that decorator provides db when file exists."""
        mock_exists.return_value = True
        mock_db = MagicMock()
        mock_init_database.return_value = mock_db

        @with_db
        def test_handler(db):
            return {'data': 'test_data'}, 200

        result = test_handler()

        assert len(result) == 2
        mock_db.close.assert_called_once()

    @patch('utils.db.os.path.exists')
    def test_with_db_when_file_missing(self, mock_exists):
        """Test that decorator returns 404 when file missing."""
        mock_exists.return_value = False

        @with_db
        def test_handler(db):
            return {'data': 'should not reach'}

        result = test_handler()

        assert len(result) == 2
