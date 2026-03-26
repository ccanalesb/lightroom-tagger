import json
import os
import tempfile

from PIL import Image


def test_import_instagram_dump():
    """Test importing Instagram dump into database."""
    from lightroom_tagger.core.database import (
        get_instagram_dump_media,
        init_database,
        init_instagram_dump_table,
    )
    from lightroom_tagger.scripts.import_instagram_dump import import_dump

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create mock dump structure
        posts_dir = os.path.join(tmpdir, 'media', 'posts', '202603')
        os.makedirs(posts_dir)

        # Create image file
        img_path = os.path.join(posts_dir, '17940060624158613.jpg')
        img = Image.new('RGB', (100, 100), color='red')
        img.save(img_path)

        # Create posts_1.json
        media_dir = os.path.join(tmpdir, 'your_instagram_activity', 'media')
        os.makedirs(media_dir)
        posts_data = [
            {
                "media": [
                    {
                        "uri": "media/posts/202603/17940060624158613.jpg",
                        "creation_timestamp": 1773179890,
                        "title": "Test caption"
                    }
                ],
                "creation_timestamp": 1773179891
            }
        ]
        with open(os.path.join(media_dir, 'posts_1.json'), 'w') as f:
            json.dump(posts_data, f)

        # Create database
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_database(db_path)
        init_instagram_dump_table(db)

        # Import
        count = import_dump(db, tmpdir)

        assert count == 1

        # Verify stored
        media = get_instagram_dump_media(db, '202603/17940060624158613')
        assert media is not None
        assert media['caption'] == "Test caption"

        db.close()
