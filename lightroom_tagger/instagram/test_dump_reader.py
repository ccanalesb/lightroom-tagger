"""Tests for Instagram dump reader."""
import pytest
import tempfile
import os
import json
from unittest.mock import patch, MagicMock
from PIL import Image


def test_discover_media_files():
    """Test discovering media files in dump directory."""
    from lightroom_tagger.instagram.dump_reader import discover_media_files

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create mock media structure
        posts_dir = os.path.join(tmpdir, 'media', 'posts', '202603')
        os.makedirs(posts_dir)

        # Create dummy image files
        img1_path = os.path.join(posts_dir, '17940060624158613.jpg')
        img2_path = os.path.join(posts_dir, '17963439135052555.jpg')

        # Create actual image files (needed for Image.open)
        img = Image.new('RGB', (100, 100), color='red')
        img.save(img1_path)
        img.save(img2_path)

        # Create a Zone.Identifier file (should be ignored)
        with open(os.path.join(posts_dir, 'test.jpg:Zone.Identifier'), 'w') as f:
            f.write('ZoneID=3')

        files = discover_media_files(tmpdir)

        assert len(files) == 2
        keys = [f['media_key'] for f in files]
        assert '202603/17940060624158613' in keys
        assert '202603/17963439135052555' in keys


def test_parse_posts_metadata():
    """Test parsing posts_1.json metadata."""
    from lightroom_tagger.instagram.dump_reader import parse_posts_metadata

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create mock posts_1.json
        posts_json = os.path.join(tmpdir, 'your_instagram_activity', 'media', 'posts_1.json')
        os.makedirs(os.path.dirname(posts_json))

        data = [
            {
                "media": [
                    {
                        "uri": "media/posts/202603/17940060624158613.jpg",
                        "creation_timestamp": 1773179890,
                        "title": "Spring is just around the corner"
                    }
                ],
                "title": "Spring is just around the corner",
                "creation_timestamp": 1773179891
            }
        ]

        with open(posts_json, 'w') as f:
            json.dump(data, f)

        metadata = parse_posts_metadata(tmpdir)

        assert '202603/17940060624158613' in metadata
        assert metadata['202603/17940060624158613']['caption'] == "Spring is just around the corner"
        assert metadata['202603/17940060624158613']['creation_timestamp'] == 1773179890
