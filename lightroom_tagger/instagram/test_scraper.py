import unittest
from unittest.mock import MagicMock

from lightroom_tagger.instagram.scraper import (
    InstagramPost,
    get_session_headers,
)


class TestInstagramScraper(unittest.TestCase):
    """Tests for Instagram scraper functions."""

    def test_instagram_post_dataclass(self):
        """Test InstagramPost dataclass creation."""
        from datetime import datetime
        post = InstagramPost(
            post_url='https://instagram.com/p/abc123',
            image_url='https://instagram.com/media/abc.jpg',
            timestamp=datetime(2024, 1, 15),
            index=0,
            caption='Test caption'
        )
        self.assertEqual(post.post_url, 'https://instagram.com/p/abc123')
        self.assertEqual(post.image_url, 'https://instagram.com/media/abc.jpg')
        self.assertEqual(post.index, 0)

    def test_get_session_headers(self):
        """Test session headers generation."""
        mock_config = MagicMock()
        mock_config.instagram_session_id = 'test_session_123'

        headers = get_session_headers(mock_config)

        self.assertIn('User-Agent', headers)
        self.assertIn('Cookie', headers)
        self.assertIn('test_session_123', headers['Cookie'])


class TestInstagramPost(unittest.TestCase):
    """Tests for InstagramPost dataclass."""

    def test_default_values(self):
        """Test default values for optional fields."""
        from datetime import datetime
        post = InstagramPost(
            post_url='https://instagram.com/p/abc',
            image_url='https://instagram.com/img.jpg',
            timestamp=datetime.now()
        )
        self.assertEqual(post.index, 0)
        self.assertEqual(post.caption, "")


if __name__ == "__main__":
    unittest.main()
