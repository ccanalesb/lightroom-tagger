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
