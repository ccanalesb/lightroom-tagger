"""Tests for visual duplicate detection module."""
import unittest
from unittest.mock import MagicMock, patch

from lightroom_tagger.instagram import deduplicator


class TestComputeImageHash(unittest.TestCase):
    """Tests for compute_image_hash function."""

    @patch('lightroom_tagger.instagram.deduplicator.Image.open')
    @patch('imagehash.phash')
    def test_compute_hash_success(self, mock_phash, mock_open):
        """Test successful hash computation."""
        mock_img = MagicMock()
        mock_open.return_value = mock_img
        mock_phash.return_value = 'abc123def456'

        result = deduplicator.compute_image_hash('/test/image.jpg')

        self.assertEqual(result, 'abc123def456')
        mock_open.assert_called_once_with('/test/image.jpg')
        mock_phash.assert_called_once_with(mock_img)
        mock_img.close.assert_called_once()

    @patch('lightroom_tagger.instagram.deduplicator.Image.open')
    def test_compute_hash_file_not_found(self, mock_open):
        """Test hash computation when file doesn't exist."""
        mock_open.side_effect = FileNotFoundError("File not found")

        result = deduplicator.compute_image_hash('/nonexistent.jpg')

        self.assertIsNone(result)


class TestGroupByHash(unittest.TestCase):
    """Tests for group_by_hash function."""

    def test_group_by_hash(self):
        """Test grouping media by hash."""
        media = [
            {'file_path': '/posts/202307/a.jpg', 'image_hash': 'hash1'},
            {'file_path': '/archived/202307/b.jpg', 'image_hash': 'hash1'},  # Duplicate
            {'file_path': '/posts/202307/c.jpg', 'image_hash': 'hash2'},
            {'file_path': '/posts/202307/d.jpg', 'image_hash': None},  # No hash
        ]

        groups = deduplicator.group_by_hash(media)

        # Should have 3 groups: hash1, hash2, and one for no_hash
        self.assertEqual(len(groups), 3)
        self.assertEqual(len(groups['hash1']), 2)
        self.assertEqual(len(groups['hash2']), 1)

        # Check hash1 group contains both files
        hash1_files = [m['file_path'] for m in groups['hash1']]
        self.assertIn('/posts/202307/a.jpg', hash1_files)
        self.assertIn('/archived/202307/b.jpg', hash1_files)


class TestSelectBestVersion(unittest.TestCase):
    """Tests for select_best_version function."""

    def test_select_posts_over_archived(self):
        """Test that posts folder is preferred over archived."""
        group = [
            {'file_path': '/archived_posts/202307/a.jpg', 'image_hash': 'hash1'},
            {'file_path': '/posts/202307/b.jpg', 'image_hash': 'hash1'},
        ]

        best = deduplicator.select_best_version(group)

        self.assertIn('/posts/', best['file_path'])

    def test_select_first_when_only_archived(self):
        """Test selection when only archived versions exist."""
        group = [
            {'file_path': '/archived_posts/202307/a.jpg', 'image_hash': 'hash1'},
            {'file_path': '/archived_posts/202307/b.jpg', 'image_hash': 'hash1'},
        ]

        best = deduplicator.select_best_version(group)

        # Should pick first one
        self.assertEqual(best['file_path'], '/archived_posts/202307/a.jpg')

    def test_single_item_returns_itself(self):
        """Test that single item is returned as-is."""
        group = [{'file_path': '/posts/202307/a.jpg', 'image_hash': 'hash1'}]

        best = deduplicator.select_best_version(group)

        self.assertEqual(best['file_path'], '/posts/202307/a.jpg')


class TestIsFromPostsFolder(unittest.TestCase):
    """Tests for is_from_posts_folder function."""

    def test_posts_path_returns_true(self):
        """Test that posts path is recognized."""
        self.assertTrue(deduplicator.is_from_posts_folder('/media/posts/202307/a.jpg'))
        self.assertTrue(deduplicator.is_from_posts_folder('/some/path/media/posts/202307/a.jpg'))

    def test_archived_path_returns_false(self):
        """Test that archived path is not recognized as posts."""
        self.assertFalse(deduplicator.is_from_posts_folder('/media/archived_posts/202307/a.jpg'))
        self.assertFalse(deduplicator.is_from_posts_folder('/media/other/202307/a.jpg'))


class TestMergeExifData(unittest.TestCase):
    """Tests for merge_exif_data function."""

    def test_merge_exif_from_archived(self):
        """Test that EXIF is merged from archived into posts."""
        best = {
            'file_path': '/posts/202307/a.jpg',
            'exif_data': None,
        }
        duplicates = [
            best,
            {
                'file_path': '/archived_posts/202307/b.jpg',
                'exif_data': {'date_time_original': '2023-07-15 10:30:00'},
                'exif_latitude': 40.7128,
            }
        ]

        merged = deduplicator.merge_exif_data(best, duplicates)

        self.assertEqual(merged['exif_data']['date_time_original'], '2023-07-15 10:30:00')
        self.assertEqual(merged['exif_latitude'], 40.7128)

    def test_keep_best_version_exif(self):
        """Test that best version's EXIF is preserved if it exists."""
        best = {
            'file_path': '/posts/202307/a.jpg',
            'exif_data': {'date_time_original': '2023-07-15 12:00:00'},
        }
        duplicates = [
            best,
            {
                'file_path': '/archived_posts/202307/b.jpg',
                'exif_data': {'date_time_original': '2023-07-15 10:30:00'},
            }
        ]

        merged = deduplicator.merge_exif_data(best, duplicates)

        # Should keep posts version
        self.assertEqual(merged['exif_data']['date_time_original'], '2023-07-15 12:00:00')


class TestDeduplicateMedia(unittest.TestCase):
    """Integration test for full deduplication flow."""

    @patch('lightroom_tagger.instagram.deduplicator.compute_image_hashes')
    def test_full_deduplication(self, mock_compute_hashes):
        """Test complete deduplication flow."""
        # Mock the result of compute_image_hashes
        media_files = [
            {'file_path': '/posts/202307/a.jpg', 'media_key': '202307/a'},
            {'file_path': '/archived_posts/202307/b.jpg', 'media_key': '202307/b',
             'exif_data': {'date': '2023-07-15'}},
            {'file_path': '/posts/202307/c.jpg', 'media_key': '202307/c'},
        ]

        # Return files with pre-computed hashes
        mock_compute_hashes.return_value = [
            {'file_path': '/posts/202307/a.jpg', 'media_key': '202307/a', 'image_hash': 'hash1'},
            {'file_path': '/archived_posts/202307/b.jpg', 'media_key': '202307/b',
             'exif_data': {'date': '2023-07-15'}, 'image_hash': 'hash1'},
            {'file_path': '/posts/202307/c.jpg', 'media_key': '202307/c', 'image_hash': 'hash2'},
        ]

        result = deduplicator.deduplicate_media(media_files)

        # Should have 2 unique images
        self.assertEqual(len(result), 2)

        # Check that posts version of hash1 was kept with EXIF merged
        hash1_results = [r for r in result if r.get('image_hash') == 'hash1']
        self.assertEqual(len(hash1_results), 1)
        self.assertIn('/posts/', hash1_results[0]['file_path'])
        self.assertEqual(hash1_results[0]['exif_data']['date'], '2023-07-15')


if __name__ == '__main__':
    unittest.main()
