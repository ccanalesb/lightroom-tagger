import unittest
from unittest.mock import MagicMock, patch

from lightroom_tagger.instagram.browser import BrowserAgent, BrowserPost


class TestBrowserAgent(unittest.TestCase):
    """Tests for BrowserAgent class."""

    @patch('subprocess.run')
    def test_open_url(self, mock_run):
        """Test opening a URL in browser."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        agent = BrowserAgent()
        result = agent.open_url("https://example.com")

        self.assertTrue(result)
        mock_run.assert_called_once()

    @patch('subprocess.run')
    def test_open_url_failure(self, mock_run):
        """Test URL open failure."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Error")

        agent = BrowserAgent()
        result = agent.open_url("https://example.com")

        self.assertFalse(result)

    @patch('subprocess.run')
    def test_snapshot(self, mock_run):
        """Test getting page snapshot."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='Page content here',
            stderr=""
        )

        agent = BrowserAgent()
        result = agent.snapshot()

        self.assertEqual(result, 'Page content here')

    @patch('subprocess.run')
    def test_scroll(self, mock_run):
        """Test scrolling the page."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        agent = BrowserAgent()
        result = agent.scroll("down")

        self.assertTrue(result)

    @patch('subprocess.run')
    def test_close(self, mock_run):
        """Test closing browser."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        agent = BrowserAgent()
        result = agent.close()

        self.assertTrue(result)

    @patch('subprocess.run')
    def test_wait(self, mock_run):
        """Test waiting."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        agent = BrowserAgent()
        result = agent.wait(2)

        self.assertTrue(result)

    def test_ensure_output_dir(self):
        """Test output directory creation."""
        import os
        import tempfile

        temp_dir = tempfile.mkdtemp()
        BrowserAgent(temp_dir)

        self.assertTrue(os.path.exists(temp_dir))
        os.rmdir(temp_dir)

    def test_browser_post_dataclass(self):
        """Test BrowserPost dataclass."""
        post = BrowserPost(
            post_url='https://instagram.com/p/abc',
            image_url='https://instagram.com/media/abc.jpg',
            index=0
        )
        self.assertEqual(post.post_url, 'https://instagram.com/p/abc')
        self.assertEqual(post.image_url, 'https://instagram.com/media/abc.jpg')
        self.assertEqual(post.index, 0)

    @patch('subprocess.run')
    def test_extract_posts(self, mock_run):
        """Test extracting posts from page via JS eval."""
        # JS eval returns JSON array of URLs
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='["https://instagram.com/p/abc123", "https://instagram.com/p/def456", "https://instagram.com/p/ghi789"]',
            stderr=""
        )

        agent = BrowserAgent()
        posts = agent.extract_posts(limit=10)

        self.assertEqual(len(posts), 3)
        self.assertEqual(posts[0].post_url, 'https://instagram.com/p/abc123')

    @patch('subprocess.run')
    def test_extract_posts_reels(self, mock_run):
        """Test extracting reel posts from page via JS eval."""
        # JS eval returns JSON array of reel URLs
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='["https://instagram.com/reel/abc123", "https://instagram.com/reel/def456"]',
            stderr=""
        )

        agent = BrowserAgent()
        posts = agent.extract_posts(limit=10)

        self.assertEqual(len(posts), 2)
        self.assertIn('/reel/', posts[0].post_url)


if __name__ == "__main__":
    unittest.main()
