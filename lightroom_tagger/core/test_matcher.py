from unittest.mock import Mock, patch

from lightroom_tagger.core.matcher import match_batch, match_image, score_candidates_with_vision


def test_match_filters_by_exif():
    """Should filter candidates by EXIF first."""
    mock_db = Mock()

    insta_image = {
        'key': 'insta_test',
        'phash': 'a1b2c3d4e5f6g7h8',
        'exif': {'camera': 'Canon EOS R5', 'lens': 'RF 24-70mm'}
    }

    catalog_candidates = [
        {'key': 'cat1', 'phash': 'a1b2c3d4e5f6g7h8', 'exif': {'camera': 'Canon EOS R5', 'lens': 'RF 24-70mm'}, 'description': 'sunset'},
        {'key': 'cat2', 'phash': 'xyzxyzxyzxyzxy', 'exif': {'camera': 'Sony A7', 'lens': '24-70mm'}, 'description': 'portrait'},
    ]

    with patch('lightroom_tagger.core.matcher.query_by_exif', return_value=[catalog_candidates[0]]), \
         patch('lightroom_tagger.core.matcher.score_candidates_with_vision', return_value=[{'catalog_key': 'cat1', 'total_score': 0.9}]):

        result = match_image(mock_db, insta_image, threshold=0.7)

    assert len(result) == 1
    assert result[0]['catalog_key'] == 'cat1'


def test_match_batch():
    """Should match multiple Instagram images."""
    mock_db = Mock()

    insta_images = [
        {'key': 'insta1', 'phash': 'abc', 'exif': {'camera': 'Canon'}},
        {'key': 'insta2', 'phash': 'xyz', 'exif': {'camera': 'Sony'}},
    ]

    with patch('lightroom_tagger.core.matcher.match_image', return_value=[{'catalog_key': 'cat1'}]):
        result = match_batch(mock_db, insta_images, threshold=0.7)

    assert result['total_matches'] == 2


def test_score_candidates_includes_vision():
    """Should include vision score when comparing."""
    mock_db = Mock()

    insta_image = {
        'key': 'insta_test',
        'image_hash': 'a1b2c3d4e5f6g7h8',
        'description': 'sunset over bay',
        'local_path': '/tmp/insta.jpg'
    }

    candidates = [
        {'key': 'cat1', 'image_hash': 'a1b2c3d4e5f6g7h8', 'description': 'sunset', 'local_path': '/tmp/local1.jpg'},
    ]

    with patch('lightroom_tagger.core.matcher.get_vision_comparison', return_value=None), \
         patch('lightroom_tagger.core.analyzer.compare_with_vision',
               return_value={'confidence': 100, 'verdict': 'SAME', 'reasoning': ''}), \
         patch('lightroom_tagger.core.analyzer.vision_score', return_value=1.0), \
         patch('lightroom_tagger.core.matcher.store_vision_comparison') as store_mock, \
         patch('lightroom_tagger.core.analyzer.get_vision_model', return_value='gemma3:27b'), \
         patch('lightroom_tagger.core.matcher.get_cached_phash', return_value=None), \
         patch('lightroom_tagger.core.matcher.get_or_create_cached_image', return_value=None), \
         patch('lightroom_tagger.core.matcher.InstagramCache') as mock_insta_cache, \
         patch('lightroom_tagger.core.phash.hamming_distance', return_value=0):
        mock_insta_cache.return_value.compress_instagram_image.return_value = '/tmp/insta.jpg'
        mock_insta_cache.return_value.cleanup.return_value = None

        results = score_candidates_with_vision(
            mock_db, insta_image, candidates,
            phash_weight=0.4, desc_weight=0.3, vision_weight=0.3
        )

    assert len(results) == 1
    assert results[0]['vision_result'] == 'SAME'
    assert results[0]['vision_score'] == 1.0
    # Should have cached the result
    store_mock.assert_called_once()


def test_score_candidates_stores_actual_provider_model_in_cache():
    """After vision success, cache row uses _provider/_model from response, not requested default."""
    mock_db = Mock()

    insta_image = {
        'key': 'insta_test',
        'image_hash': 'a1b2c3d4e5f6g7h8',
        'description': 'sunset over bay',
        'local_path': '/tmp/insta.jpg',
    }

    candidates = [
        {'key': 'cat1', 'image_hash': 'a1b2c3d4e5f6g7h8', 'description': 'sunset', 'local_path': '/tmp/local1.jpg'},
    ]

    vision_payload = {
        'confidence': 100,
        'verdict': 'SAME',
        'reasoning': '',
        '_provider': 'nvidia_nim',
        '_model': 'google/paligemma',
    }

    with patch('lightroom_tagger.core.matcher.get_vision_comparison', return_value=None), \
         patch('lightroom_tagger.core.analyzer.compare_with_vision', return_value=vision_payload), \
         patch('lightroom_tagger.core.analyzer.vision_score', return_value=1.0), \
         patch('lightroom_tagger.core.matcher.store_vision_comparison') as store_mock, \
         patch('lightroom_tagger.core.analyzer.get_vision_model', return_value='gemma3:27b'), \
         patch('lightroom_tagger.core.matcher.get_cached_phash', return_value=None), \
         patch('lightroom_tagger.core.matcher.get_or_create_cached_image', return_value=None), \
         patch('lightroom_tagger.core.matcher.InstagramCache') as mock_insta_cache, \
         patch('lightroom_tagger.core.phash.hamming_distance', return_value=0):
        mock_insta_cache.return_value.compress_instagram_image.return_value = '/tmp/insta.jpg'
        mock_insta_cache.return_value.cleanup.return_value = None

        results = score_candidates_with_vision(
            mock_db, insta_image, candidates,
            phash_weight=0.4, desc_weight=0.3, vision_weight=0.3,
            provider_id='ollama',
            model=None,
        )

    assert len(results) == 1
    assert results[0]['model_used'] == 'nvidia_nim:google/paligemma'
    store_mock.assert_called_once()
    _db, cat, insta, _result, _score, model_used = store_mock.call_args[0]
    assert model_used == 'nvidia_nim:google/paligemma'


def test_score_candidates_uses_cache():
    """Should use cached vision comparison when available."""
    mock_db = Mock()

    insta_image = {
        'key': 'insta_test',
        'image_hash': 'a1b2c3d4e5f6g7h8',
        'description': 'sunset',
        'local_path': '/tmp/insta.jpg'
    }

    candidates = [
        {'key': 'cat1', 'image_hash': 'a1b2c3d4e5f6g7h8', 'description': 'sunset', 'local_path': '/tmp/local1.jpg'},
    ]

    # Simulate cached result
    cached_result = {
        'result': 'DIFFERENT',
        'vision_score': 0.0,
        'model_used': 'gemma3:27b'
    }

    with patch('lightroom_tagger.core.matcher.get_vision_comparison', return_value=cached_result), \
         patch('lightroom_tagger.core.analyzer.compare_with_vision') as vision_mock, \
         patch('lightroom_tagger.core.matcher.get_cached_phash', return_value=None), \
         patch('lightroom_tagger.core.matcher.get_or_create_cached_image', return_value=None), \
         patch('lightroom_tagger.core.matcher.InstagramCache') as mock_insta_cache, \
         patch('lightroom_tagger.core.phash.hamming_distance', return_value=0):
        mock_insta_cache.return_value.compress_instagram_image.return_value = '/tmp/insta.jpg'
        mock_insta_cache.return_value.cleanup.return_value = None

        results = score_candidates_with_vision(
            mock_db, insta_image, candidates,
            phash_weight=0.4, desc_weight=0.3, vision_weight=0.3
        )

    assert len(results) == 1
    assert results[0]['vision_result'] == 'DIFFERENT'
    assert results[0]['vision_score'] == 0.0
    # Should NOT have called vision model (used cache)
    vision_mock.assert_not_called()


def test_score_candidates_does_not_cache_on_vision_error():
    """should not cache vision result when compare_with_vision raises."""
    mock_db = Mock()

    insta_image = {
        'key': 'insta_test',
        'image_hash': 'a1b2c3d4e5f6g7h8',
        'description': 'sunset',
        'local_path': '/tmp/insta.jpg',
    }

    candidates = [
        {'key': 'cat1', 'image_hash': 'a1b2c3d4e5f6g7h8', 'description': 'sunset', 'local_path': '/tmp/local1.jpg'},
    ]

    with patch('lightroom_tagger.core.matcher.get_vision_comparison', return_value=None), \
         patch('lightroom_tagger.core.analyzer.compare_with_vision', side_effect=RuntimeError('model not found')), \
         patch('lightroom_tagger.core.matcher.store_vision_comparison') as store_mock, \
         patch('lightroom_tagger.core.matcher.get_cached_phash', return_value=None), \
         patch('lightroom_tagger.core.matcher.get_or_create_cached_image', return_value=None), \
         patch('lightroom_tagger.core.matcher.InstagramCache') as mock_insta_cache, \
         patch('lightroom_tagger.core.phash.hamming_distance', return_value=0):
        mock_insta_cache.return_value.compress_instagram_image.return_value = '/tmp/insta.jpg'
        mock_insta_cache.return_value.cleanup.return_value = None

        results = score_candidates_with_vision(
            mock_db, insta_image, candidates,
            phash_weight=0.4, desc_weight=0.3, vision_weight=0.3,
        )

    assert len(results) == 1
    assert results[0]['vision_result'] == 'ERROR'
    assert results[0]['vision_score'] == 0.0
    store_mock.assert_not_called()
