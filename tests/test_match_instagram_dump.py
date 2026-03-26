import os
import tempfile
from unittest.mock import patch

from PIL import Image


def test_match_dump_media():
    """Test matching Instagram dump media against catalog."""
    from lightroom_tagger.core.database import (
        init_catalog_table,
        init_database,
        init_instagram_dump_table,
        store_catalog_image,
        store_instagram_dump_media,
    )
    from lightroom_tagger.scripts.match_instagram_dump import match_dump_media

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create database
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_database(db_path)
        init_instagram_dump_table(db)
        init_catalog_table(db)

        # Create dummy Instagram dump image
        dump_img_path = os.path.join(tmpdir, 'dump_123.jpg')
        img = Image.new('RGB', (100, 100), color='blue')
        img.save(dump_img_path)

        # Store in dump table
        store_instagram_dump_media(db, {
            'media_key': '202603/123',
            'file_path': dump_img_path,
            'filename': '123.jpg',
        })

        # Create mock catalog image
        catalog_record = {
            'key': 'catalog_123',
            'filepath': dump_img_path,  # Same file for testing
            'filename': 'catalog_123.jpg',
            'date_taken': '2025-03-15',
            'phash': None,
        }
        store_catalog_image(db, catalog_record)

        # Mock the matcher
        with patch('lightroom_tagger.scripts.match_instagram_dump.score_candidates_with_vision') as mock_score:
            mock_score.return_value = [
                {
                    'catalog_key': 'catalog_123',
                    'vision_result': 'SAME',
                    'vision_score': 1.0,
                    'total_score': 0.95,
                }
            ]

            # Run matching
            stats = match_dump_media(db, batch_size=10)

            assert stats['processed'] == 1
            assert stats['matched'] == 1

        db.close()
