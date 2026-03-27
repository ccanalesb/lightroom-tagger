from unittest.mock import patch, MagicMock
from lightroom_tagger.scripts.match_instagram_dump import match_dump_media


@patch('lightroom_tagger.scripts.match_instagram_dump.init_catalog_table')
@patch('lightroom_tagger.scripts.match_instagram_dump.init_instagram_dump_table')
@patch('lightroom_tagger.scripts.match_instagram_dump.get_unprocessed_dump_media')
@patch('lightroom_tagger.scripts.match_instagram_dump.find_candidates_by_date')
@patch('lightroom_tagger.scripts.match_instagram_dump.mark_dump_media_attempted')
def test_media_key_filters_to_single_image(
    mock_mark_attempted, mock_find, mock_get_unprocessed, mock_init_insta, mock_init_catalog
):
    """When media_key is provided, only that image is processed."""
    db = MagicMock()
    target_row = {
        'media_key': '202603/12345',
        'file_path': '/tmp/test.jpg',
        'caption': '',
        'date_folder': '202603',
    }
    db.execute.return_value.fetchone.return_value = target_row

    mock_find.return_value = []

    stats, matches = match_dump_media(db, media_key='202603/12345')

    mock_get_unprocessed.assert_not_called()
    assert stats['processed'] == 1
