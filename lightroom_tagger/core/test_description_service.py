from unittest.mock import patch

from lightroom_tagger.core.database import init_database, store_image, store_image_description, get_image_description


def _make_db(tmp_path):
    db_path = str(tmp_path / 'test.db')
    return init_database(db_path)


class TestDescribeMatchedImage:
    def test_generates_description_when_missing(self, tmp_path):
        from lightroom_tagger.core.description_service import describe_matched_image

        db = _make_db(tmp_path)
        filepath = str(tmp_path / 'photo.jpg')
        open(filepath, 'w').close()
        catalog_key = store_image(db, {'filepath': filepath, 'filename': 'photo.jpg'})

        with patch('lightroom_tagger.core.description_service.describe_image') as mock_desc, \
             patch('lightroom_tagger.core.description_service.get_description_model', return_value='test-model'):
            mock_desc.return_value = {
                'summary': 'A street scene', 'composition': {'depth': 'shallow'},
                'perspectives': {'street': {'score': 7}}, 'technical': {'mood': 'gritty'},
                'subjects': ['person'], 'best_perspective': 'street',
            }
            result = describe_matched_image(db, catalog_key)

        assert result is True
        desc = get_image_description(db, catalog_key)
        assert desc is not None
        assert desc['summary'] == 'A street scene'

    def test_skips_when_description_exists(self, tmp_path):
        from lightroom_tagger.core.description_service import describe_matched_image

        db = _make_db(tmp_path)
        filepath = str(tmp_path / 'photo.jpg')
        open(filepath, 'w').close()
        catalog_key = store_image(db, {'filepath': filepath, 'filename': 'photo.jpg'})
        store_image_description(db, {
            'image_key': catalog_key, 'image_type': 'catalog', 'summary': 'existing',
            'composition': {}, 'perspectives': {}, 'technical': {},
            'subjects': [], 'best_perspective': 'street', 'model_used': 'old',
        })

        with patch('lightroom_tagger.core.description_service.describe_image') as mock_desc:
            result = describe_matched_image(db, catalog_key)

        assert result is False
        mock_desc.assert_not_called()

    def test_regenerates_when_force_is_true(self, tmp_path):
        from lightroom_tagger.core.description_service import describe_matched_image

        db = _make_db(tmp_path)
        filepath = str(tmp_path / 'photo.jpg')
        open(filepath, 'w').close()
        catalog_key = store_image(db, {'filepath': filepath, 'filename': 'photo.jpg'})
        store_image_description(db, {
            'image_key': catalog_key, 'image_type': 'catalog', 'summary': 'old summary',
            'composition': {}, 'perspectives': {}, 'technical': {},
            'subjects': [], 'best_perspective': 'street', 'model_used': 'old',
        })

        with patch('lightroom_tagger.core.description_service.describe_image') as mock_desc, \
             patch('lightroom_tagger.core.description_service.get_description_model', return_value='new-model'):
            mock_desc.return_value = {
                'summary': 'Updated summary', 'composition': {}, 'perspectives': {},
                'technical': {}, 'subjects': [], 'best_perspective': 'documentary',
            }
            result = describe_matched_image(db, catalog_key, force=True)

        assert result is True
        desc = get_image_description(db, catalog_key)
        assert desc['summary'] == 'Updated summary'

    def test_returns_false_when_image_not_found(self, tmp_path):
        from lightroom_tagger.core.description_service import describe_matched_image

        db = _make_db(tmp_path)
        result = describe_matched_image(db, 'NONEXISTENT')
        assert result is False

    def test_returns_false_when_file_missing(self, tmp_path):
        from lightroom_tagger.core.description_service import describe_matched_image

        db = _make_db(tmp_path)
        catalog_key = store_image(db, {'filepath': '/no/such/file.jpg', 'filename': 'file.jpg'})
        result = describe_matched_image(db, catalog_key)
        assert result is False


class TestMatchDumpMediaDescriptions:
    """Verify match_dump_media triggers description generation for matches."""

    @patch('lightroom_tagger.scripts.match_instagram_dump.describe_matched_image')
    @patch('lightroom_tagger.scripts.match_instagram_dump.score_candidates_with_vision')
    @patch('lightroom_tagger.scripts.match_instagram_dump.find_candidates_by_date')
    @patch('lightroom_tagger.scripts.match_instagram_dump.get_unprocessed_dump_media')
    def test_generates_description_on_match(self, mock_unprocessed, mock_candidates,
                                             mock_score, mock_describe, tmp_path):
        from lightroom_tagger.scripts.match_instagram_dump import match_dump_media

        db = _make_db(tmp_path)
        store_image(db, {'key': 'CAT1', 'filepath': '/p/a.jpg', 'filename': 'a.jpg'})

        mock_unprocessed.return_value = [{'media_key': 'IG1', 'file_path': '/ig/1.jpg', 'caption': ''}]
        mock_candidates.return_value = [{'key': 'CAT1', 'filepath': '/p/a.jpg', 'phash': 'abc', 'description': ''}]
        mock_score.return_value = [{'catalog_key': 'CAT1', 'total_score': 0.9, 'vision_result': 'same', 'vision_score': 0.9}]
        mock_describe.return_value = True

        with patch('lightroom_tagger.scripts.match_instagram_dump.mark_dump_media_processed'), \
             patch('lightroom_tagger.scripts.match_instagram_dump.update_instagram_status'), \
             patch('lightroom_tagger.scripts.match_instagram_dump.init_instagram_dump_table'), \
             patch('lightroom_tagger.scripts.match_instagram_dump.init_catalog_table'):
            stats, matches = match_dump_media(db)

        mock_describe.assert_called_once_with(db, 'CAT1', force=False)
        assert stats['descriptions_generated'] == 1

    @patch('lightroom_tagger.scripts.match_instagram_dump.describe_matched_image')
    @patch('lightroom_tagger.scripts.match_instagram_dump.score_candidates_with_vision')
    @patch('lightroom_tagger.scripts.match_instagram_dump.find_candidates_by_date')
    @patch('lightroom_tagger.scripts.match_instagram_dump.get_unprocessed_dump_media')
    def test_passes_force_flag(self, mock_unprocessed, mock_candidates,
                                mock_score, mock_describe, tmp_path):
        from lightroom_tagger.scripts.match_instagram_dump import match_dump_media

        db = _make_db(tmp_path)
        store_image(db, {'key': 'CAT2', 'filepath': '/p/b.jpg', 'filename': 'b.jpg'})

        mock_unprocessed.return_value = [{'media_key': 'IG2', 'file_path': '/ig/2.jpg', 'caption': ''}]
        mock_candidates.return_value = [{'key': 'CAT2', 'filepath': '/p/b.jpg', 'phash': 'def', 'description': ''}]
        mock_score.return_value = [{'catalog_key': 'CAT2', 'total_score': 0.85, 'vision_result': 'same', 'vision_score': 0.85}]
        mock_describe.return_value = True

        with patch('lightroom_tagger.scripts.match_instagram_dump.mark_dump_media_processed'), \
             patch('lightroom_tagger.scripts.match_instagram_dump.update_instagram_status'), \
             patch('lightroom_tagger.scripts.match_instagram_dump.init_instagram_dump_table'), \
             patch('lightroom_tagger.scripts.match_instagram_dump.init_catalog_table'):
            stats, matches = match_dump_media(db, force_descriptions=True)

        mock_describe.assert_called_once_with(db, 'CAT2', force=True)
