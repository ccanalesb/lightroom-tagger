import unittest
from unittest.mock import patch, MagicMock
import sys
from lightroom_tagger.core import hasher


class TestHasher(unittest.TestCase):
    """Tests for hasher functions."""

    @patch('PIL.Image.open')
    @patch('imagehash.phash')
    def test_compute_phash_success(self, mock_phash, mock_open):
        """Test successful pHash computation."""
        mock_img = MagicMock()
        mock_open.return_value = mock_img
        mock_phash.return_value = 'abc12345'

        result = hasher.compute_phash('/test/image.jpg')

        self.assertEqual(result, 'abc12345')
        mock_open.assert_called_once_with('/test/image.jpg')
        mock_phash.assert_called_once_with(mock_img, hash_size=8)

    @patch('PIL.Image.open')
    def test_compute_phash_file_not_found(self, mock_open):
        """Test pHash computation when file doesn't exist."""
        mock_open.side_effect = FileNotFoundError("File not found")

        result = hasher.compute_phash('/nonexistent/image.jpg')

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
