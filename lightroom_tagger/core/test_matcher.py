from contextlib import nullcontext
from unittest.mock import Mock, MagicMock, patch

import lightroom_tagger.core.matcher as matcher_mod
from lightroom_tagger.core.matcher import match_batch, match_image, score_candidates_with_vision, find_candidates_by_date
from lightroom_tagger.core.matcher.description_batch import _compute_desc_scores_for_candidates
from lightroom_tagger.core.provider_registry import ProviderRegistry
from lightroom_tagger.core.provider_resolution import ResolvedModel, resolve_model


def _fake_registry(
    *,
    defaults: dict | None = None,
    fallback_order: list[str] | None = None,
    models_by_provider: dict[str, list[dict]] | None = None,
) -> MagicMock:
    registry = MagicMock(spec=ProviderRegistry)
    registry.defaults = defaults or {}
    registry.fallback_order = fallback_order or ["ollama"]
    fallback_order = fallback_order or ["ollama"]
    if models_by_provider is None:
        models_by_provider = {
            pid: [{"id": "test-model", "vision": True, "source": "config"}]
            for pid in fallback_order
        }

    def list_models(provider_id: str) -> list[dict]:
        return models_by_provider.get(provider_id, [])

    registry.list_models.side_effect = list_models
    registry.get_client.return_value = Mock()
    registry.list_providers.return_value = [
        {"id": pid, "name": pid, "available": True}
        for pid in fallback_order
    ]
    registry.get_retry_config.return_value = {
        "max_retries": 0,
        "backoff_seconds": [],
        "respect_retry_after": False,
    }
    return registry


def _matcher_resolve_patch(
    *,
    provider_id: str = "ollama",
    model: str = "gemma3:27b",
    registry: MagicMock | None = None,
):
    registry = registry or _fake_registry(
        fallback_order=[provider_id],
        models_by_provider={
            provider_id: [{"id": model, "vision": True, "source": "config"}],
        },
    )
    return patch(
        "lightroom_tagger.core.provider_resolution.resolve_model",
        return_value=ResolvedModel(provider_id, model, registry),
    )


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
         _matcher_resolve_patch(), \
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
         _matcher_resolve_patch(), \
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
         _matcher_resolve_patch(), \
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


def test_batch_skips_oversized_cache_misses_with_zero_vision():
    """Candidates with get_or_create_cached_image None are omitted from batch API and scored 0.0."""
    mock_db = Mock()
    insta_image = {
        'key': 'insta_test',
        'image_hash': 'a' * 16,
        'description': 'test',
        'local_path': '/tmp/insta.jpg',
    }
    candidates = [
        {'key': 'cat0', 'image_hash': 'a' * 16, 'description': 'test', 'local_path': '/tmp/c0.jpg'},
        {'key': 'cat1', 'image_hash': 'a' * 16, 'description': 'test', 'local_path': '/tmp/c1.jpg'},
    ]

    def fake_goc(db, key, path):
        if key == 'cat0':
            return None
        return '/tmp/small.jpg'

    batches_seen = []

    def mock_batch(client, model, ref, cands, log_callback=None, max_tokens=4096):
        batches_seen.append(list(cands))
        return {cid: 50.0 for cid, _ in cands}

    def mock_chunk(
        registry,
        provider_id,
        model,
        reference_path,
        chunk,
        log_callback,
        insta_filename,
        chunk_num,
        num_chunks,
        error_policy=None,
        cancel_check=None,
        abort_tracker=None,
    ):
        batches_seen.append(list(chunk))
        return {cid: 50.0 for cid, _ in chunk}

    chunk_patch = (
        patch.object(matcher_mod, '_call_batch_chunk', side_effect=mock_chunk)
        if hasattr(matcher_mod, '_call_batch_chunk')
        else nullcontext()
    )

    with patch('lightroom_tagger.core.vision_client.compare_images_batch', side_effect=mock_batch), \
         chunk_patch, \
         patch('lightroom_tagger.core.matcher.get_or_create_cached_image', side_effect=fake_goc), \
         patch('lightroom_tagger.core.matcher.get_cached_phash', return_value=None), \
         patch('lightroom_tagger.core.matcher.store_vision_comparison'), \
         patch('lightroom_tagger.core.matcher.InstagramCache') as mock_ic, \
         _matcher_resolve_patch(provider_id='ollama', model='test-model'), \
         patch('lightroom_tagger.core.phash.hamming_distance', return_value=0), \
         patch('os.path.exists', return_value=True):
        mock_ic.return_value.compress_instagram_image.return_value = '/tmp/insta.jpg'
        mock_ic.return_value.cleanup.return_value = None

        results = score_candidates_with_vision(
            mock_db, insta_image, candidates,
            batch_size=10, batch_threshold=2,
            provider_id='ollama', model='test-model',
        )

    assert batches_seen == [[(1, '/tmp/small.jpg')]]
    by_key = {r['catalog_key']: r for r in results}
    assert by_key['cat0']['vision_score'] == 0.0
    assert by_key['cat0']['vision_result'] == 'DIFFERENT'
    assert by_key['cat1']['vision_score'] == 0.5


class TestFindCandidatesByDate:
    def test_excludes_video_files(self):
        """Video files (.mov, .mp4, etc.) should never appear as candidates."""
        db = MagicMock()
        rows = [
            {'key': 'img1', 'date_taken': '2025-01-15T12:00:00', 'filepath': '/photos/img1.arw'},
            {'key': 'vid1', 'date_taken': '2025-01-15T12:00:00', 'filepath': '/photos/vid1.mov'},
            {'key': 'vid2', 'date_taken': '2025-01-15T12:00:00', 'filepath': '/photos/vid2.MP4'},
            {'key': 'img2', 'date_taken': '2025-01-15T12:00:00', 'filepath': '/photos/img2.jpg'},
        ]
        db.execute.return_value.fetchall.return_value = rows

        insta_image = {'date_folder': '202502'}
        candidates = find_candidates_by_date(db, insta_image, days_before=90)

        keys = [c['key'] for c in candidates]
        assert 'img1' in keys
        assert 'img2' in keys
        assert 'vid1' not in keys
        assert 'vid2' not in keys


def test_vision_weight_zero_skips_compare_images_and_compression():
    """vision_weight=0 must not call compare_images_batch or compress_instagram_image."""
    mock_db = Mock()
    insta_image = {
        'key': 'insta_test',
        'image_hash': 'a' * 16,
        'description': 'x',
        'local_path': '/tmp/insta.jpg',
        'ai_summary': 'reference summary text',
    }
    candidates = [
        {
            'key': 'cat1',
            'image_hash': 'a' * 16,
            'description': 'y',
            'local_path': '/tmp/c1.jpg',
            'ai_summary': 'candidate summary',
        },
    ]
    with patch('lightroom_tagger.core.vision_client.compare_images_batch') as mock_compare_images, \
         patch('lightroom_tagger.core.matcher.compare_descriptions_batch', return_value={0: 80.0}), \
         patch('lightroom_tagger.core.matcher.InstagramCache') as mock_ic, \
         patch('lightroom_tagger.core.matcher.get_cached_phash', return_value=None), \
         patch('lightroom_tagger.core.phash.hamming_distance', return_value=0), \
         patch('os.path.exists', return_value=True):
        compress = MagicMock()
        mock_ic.return_value.compress_instagram_image = compress
        mock_ic.return_value.cleanup.return_value = None
        score_candidates_with_vision(
            mock_db, insta_image, candidates,
            phash_weight=0.4, desc_weight=0.3, vision_weight=0.0,
            batch_threshold=1,
            batch_size=10,
        )
    mock_compare_images.assert_not_called()
    compress.assert_not_called()


def test_desc_weight_zero_skips_compare_descriptions_batch():
    """desc_weight=0 must not call compare_descriptions_batch."""
    mock_db = Mock()
    insta_image = {
        'key': 'insta_test',
        'image_hash': 'a' * 16,
        'description': 'sunset',
        'local_path': '/tmp/insta.jpg',
        'ai_summary': 'ref',
    }
    candidates = [
        {'key': 'cat1', 'image_hash': 'a' * 16, 'description': 'sunset', 'local_path': '/tmp/local1.jpg', 'ai_summary': 'x'},
    ]
    with patch('lightroom_tagger.core.matcher.compare_descriptions_batch') as mock_desc, \
         patch('lightroom_tagger.core.matcher.get_vision_comparison', return_value=None), \
         patch('lightroom_tagger.core.analyzer.compare_with_vision',
               return_value={'confidence': 100, 'verdict': 'SAME', 'reasoning': ''}), \
         patch('lightroom_tagger.core.analyzer.vision_score', return_value=1.0), \
         patch('lightroom_tagger.core.matcher.store_vision_comparison'), \
         _matcher_resolve_patch(), \
         patch('lightroom_tagger.core.matcher.get_cached_phash', return_value=None), \
         patch('lightroom_tagger.core.matcher.get_or_create_cached_image', return_value=None), \
         patch('lightroom_tagger.core.matcher.InstagramCache') as mock_insta_cache, \
         patch('lightroom_tagger.core.phash.hamming_distance', return_value=0):
        mock_insta_cache.return_value.compress_instagram_image.return_value = '/tmp/insta.jpg'
        mock_insta_cache.return_value.cleanup.return_value = None
        score_candidates_with_vision(
            mock_db, insta_image, candidates,
            phash_weight=0.0, desc_weight=0.0, vision_weight=1.0,
        )
    mock_desc.assert_not_called()


def test_backward_compat_phash_zero_desc_zero_vision_only_total():
    """phash=0, desc=0, vision=1: total_score equals vision_score_val (SC-7)."""
    mock_db = Mock()
    insta_image = {
        'key': 'insta_test',
        'image_hash': 'a' * 16,
        'description': 'sunset',
        'local_path': '/tmp/insta.jpg',
    }
    candidates = [
        {'key': 'cat1', 'image_hash': 'a' * 16, 'description': 'sunset', 'local_path': '/tmp/local1.jpg'},
    ]
    with patch('lightroom_tagger.core.matcher.get_vision_comparison', return_value=None), \
         patch('lightroom_tagger.core.analyzer.compare_with_vision',
               return_value={'confidence': 85, 'verdict': 'SAME', 'reasoning': ''}), \
         patch('lightroom_tagger.core.analyzer.vision_score', return_value=0.85), \
         patch('lightroom_tagger.core.matcher.store_vision_comparison'), \
         _matcher_resolve_patch(), \
         patch('lightroom_tagger.core.matcher.get_cached_phash', return_value=None), \
         patch('lightroom_tagger.core.matcher.get_or_create_cached_image', return_value=None), \
         patch('lightroom_tagger.core.matcher.InstagramCache') as mock_insta_cache, \
         patch('lightroom_tagger.core.phash.hamming_distance', return_value=0):
        mock_insta_cache.return_value.compress_instagram_image.return_value = '/tmp/insta.jpg'
        mock_insta_cache.return_value.cleanup.return_value = None
        results = score_candidates_with_vision(
            mock_db, insta_image, candidates,
            phash_weight=0.0, desc_weight=0.0, vision_weight=1.0,
        )
    assert len(results) == 1
    assert abs(results[0]['total_score'] - results[0]['vision_score']) < 1e-9


def test_nominal_weighted_merge_all_ones():
    """Weights 0.4/0.3/0.3 with phash/desc/vision contributions 1.0 yield total 1.0."""
    mock_db = Mock()
    insta_image = {
        'key': 'insta_test',
        'image_hash': 'a' * 16,
        'description': 'a',
        'local_path': '/tmp/insta.jpg',
        'ai_summary': 'ref',
    }
    candidates = [
        {'key': 'cat1', 'image_hash': 'a' * 16, 'description': 'b', 'local_path': '/tmp/local1.jpg', 'ai_summary': 'cand'},
    ]
    with patch('lightroom_tagger.core.matcher.compare_descriptions_batch', return_value={0: 100.0}), \
         patch('lightroom_tagger.core.matcher.get_vision_comparison', return_value=None), \
         patch('lightroom_tagger.core.analyzer.compare_with_vision',
               return_value={'confidence': 100, 'verdict': 'SAME', 'reasoning': ''}), \
         patch('lightroom_tagger.core.analyzer.vision_score', return_value=1.0), \
         patch('lightroom_tagger.core.matcher.store_vision_comparison'), \
         _matcher_resolve_patch(), \
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
    assert abs(results[0]['total_score'] - 1.0) < 1e-9


def test_skip_undescribed_true_empty_summaries_no_desc_batch_call():
    """Empty ai_summary with skip_undescribed=True: no compare_descriptions_batch payload."""
    mock_db = Mock()
    insta_image = {
        'key': 'insta_test',
        'image_hash': 'a' * 16,
        'description': 'cap',
        'local_path': '/tmp/insta.jpg',
        'ai_summary': 'instagram has summary',
    }
    candidates = [
        {'key': 'cat1', 'image_hash': 'a' * 16, 'description': 'd', 'local_path': '/tmp/c1.jpg', 'ai_summary': ''},
    ]
    with patch('lightroom_tagger.core.matcher.compare_descriptions_batch') as mock_desc, \
         patch('lightroom_tagger.core.matcher.get_vision_comparison', return_value=None), \
         patch('lightroom_tagger.core.analyzer.compare_with_vision',
               return_value={'confidence': 50, 'verdict': 'UNCERTAIN', 'reasoning': ''}), \
         patch('lightroom_tagger.core.analyzer.vision_score', return_value=0.5), \
         patch('lightroom_tagger.core.matcher.store_vision_comparison'), \
         _matcher_resolve_patch(), \
         patch('lightroom_tagger.core.matcher.get_cached_phash', return_value=None), \
         patch('lightroom_tagger.core.matcher.get_or_create_cached_image', return_value=None), \
         patch('lightroom_tagger.core.matcher.InstagramCache') as mock_insta_cache, \
         patch('lightroom_tagger.core.phash.hamming_distance', return_value=0), \
         patch('os.path.exists', return_value=True):
        mock_insta_cache.return_value.compress_instagram_image.return_value = '/tmp/insta.jpg'
        mock_insta_cache.return_value.cleanup.return_value = None
        results = score_candidates_with_vision(
            mock_db, insta_image, candidates,
            phash_weight=0.0, desc_weight=0.3, vision_weight=0.7,
            skip_undescribed=True,
        )
    mock_desc.assert_not_called()
    assert results[0]['desc_similarity'] == 0.0


def test_description_batch_runs_before_vision_batch():
    """Per chunk, compare_descriptions_batch is invoked before compare_images_batch (SC-3)."""
    mock_db = Mock()
    insta_image = {
        'key': 'insta_test',
        'image_hash': 'a' * 16,
        'description': 'c',
        'local_path': '/tmp/insta.jpg',
        'ai_summary': 'ref summary for batch',
    }
    candidates = [
        {'key': 'c0', 'image_hash': 'a' * 16, 'description': 'd', 'local_path': '/tmp/p0.jpg', 'ai_summary': 's0'},
        {'key': 'c1', 'image_hash': 'a' * 16, 'description': 'd', 'local_path': '/tmp/p1.jpg', 'ai_summary': 's1'},
    ]
    order = []

    def desc_side_effect(*args, **kwargs):
        order.append('desc')
        return {0: 90.0, 1: 90.0}

    def vision_side_effect(client, model, ref, cands, log_callback=None, max_tokens=4096):
        order.append('vision')
        return {cid: 80.0 for cid, _ in cands}

    with patch('lightroom_tagger.core.matcher.compare_descriptions_batch', side_effect=desc_side_effect), \
         patch('lightroom_tagger.core.vision_client.compare_images_batch', side_effect=vision_side_effect), \
         patch('lightroom_tagger.core.matcher.get_cached_phash', return_value=None), \
         patch('lightroom_tagger.core.matcher.get_or_create_cached_image', return_value='/tmp/small.jpg'), \
         patch('lightroom_tagger.core.matcher.store_vision_comparison'), \
         patch('lightroom_tagger.core.matcher.InstagramCache') as mock_ic, \
         _matcher_resolve_patch(provider_id='ollama', model='m'), \
         patch('lightroom_tagger.core.phash.hamming_distance', return_value=0), \
         patch('os.path.exists', return_value=True):
        mock_ic.return_value.compress_instagram_image.return_value = '/tmp/insta.jpg'
        mock_ic.return_value.cleanup.return_value = None
        score_candidates_with_vision(
            mock_db, insta_image, candidates,
            phash_weight=0.2, desc_weight=0.3, vision_weight=0.5,
            batch_size=10,
            batch_threshold=1,
            provider_id='ollama',
            model='m',
        )
    assert order[0] == 'desc'
    assert order[1] == 'vision'


def test_all_empty_ai_summary_skip_no_redistribution():
    """All candidates lack ai_summary; desc batch skipped; nominal 0.3/0.7 merge (D-10)."""
    mock_db = Mock()
    insta_image = {
        'key': 'insta_test',
        'image_hash': 'a' * 16,
        'description': 'c',
        'local_path': '/tmp/insta.jpg',
        'ai_summary': 'ref',
    }
    candidates = [
        {'key': 'c0', 'image_hash': 'a' * 16, 'description': 'd', 'local_path': '/tmp/p0.jpg', 'ai_summary': ''},
        {'key': 'c1', 'image_hash': 'a' * 16, 'description': 'd', 'local_path': '/tmp/p1.jpg', 'ai_summary': ''},
        {'key': 'c2', 'image_hash': 'a' * 16, 'description': 'd', 'local_path': '/tmp/p2.jpg', 'ai_summary': ''},
    ]
    with patch('lightroom_tagger.core.matcher.compare_descriptions_batch') as mock_desc, \
         patch('lightroom_tagger.core.matcher.get_vision_comparison', return_value=None), \
         patch('lightroom_tagger.core.analyzer.compare_with_vision',
               return_value={'confidence': 100, 'verdict': 'SAME', 'reasoning': ''}), \
         patch('lightroom_tagger.core.analyzer.vision_score', return_value=1.0), \
         patch('lightroom_tagger.core.matcher.store_vision_comparison'), \
         _matcher_resolve_patch(), \
         patch('lightroom_tagger.core.matcher.get_cached_phash', return_value=None), \
         patch('lightroom_tagger.core.matcher.get_or_create_cached_image', return_value=None), \
         patch('lightroom_tagger.core.matcher.InstagramCache') as mock_insta_cache, \
         patch('lightroom_tagger.core.phash.hamming_distance', return_value=0), \
         patch('os.path.exists', return_value=True):
        mock_insta_cache.return_value.compress_instagram_image.return_value = '/tmp/insta.jpg'
        mock_insta_cache.return_value.cleanup.return_value = None
        results = score_candidates_with_vision(
            mock_db, insta_image, candidates,
            phash_weight=0.0, desc_weight=0.3, vision_weight=0.7,
            skip_undescribed=True,
        )
    mock_desc.assert_not_called()
    assert len(results) == 3
    for r in results:
        assert abs(r['total_score'] - 0.7 * r['vision_score']) < 1e-9


def test_matcher_selection_prefers_providers_json_vision_comparison_over_config(monkeypatch):
    """Description batch selection uses providers.json defaults before config.yaml."""
    monkeypatch.delenv("VISION_MODEL", raising=False)
    registry = _fake_registry(
        defaults={"vision_comparison": {"provider": "vc-p", "model": "json-vision-model"}},
        fallback_order=["vc-p"],
        models_by_provider={"vc-p": [{"id": "listed-model"}]},
    )
    captured_models: list[str] = []

    def capture_batch(client, model, ref, cands, log_callback=None, max_tokens=4096):
        captured_models.append(model)
        return {idx: 80.0 for idx, _ in cands}

    with patch(
        "lightroom_tagger.core.provider_resolution.get_vision_model",
        return_value="config-vision-model",
    ), patch(
        "lightroom_tagger.core.matcher.compare_descriptions_batch",
        side_effect=capture_batch,
    ):
        _compute_desc_scores_for_candidates(
            insta_image={"ai_summary": "reference summary"},
            candidates=[{"ai_summary": "candidate summary"}],
            batch_size=10,
            desc_weight=0.3,
            skip_undescribed=True,
            provider_id=None,
            model=None,
            log_callback=None,
            registry=registry,
        )

    assert captured_models == ["json-vision-model"]


def test_matcher_selection_falls_back_to_config_when_providers_json_unset(monkeypatch):
    """When providers.json has no vision_comparison model, selection uses config.yaml."""
    monkeypatch.delenv("VISION_MODEL", raising=False)
    registry = _fake_registry(
        defaults={"vision_comparison": {"provider": "vc-p", "model": None}},
        fallback_order=["vc-p"],
        models_by_provider={"vc-p": [{"id": "listed-model"}]},
    )
    captured_models: list[str] = []

    def capture_batch(client, model, ref, cands, log_callback=None, max_tokens=4096):
        captured_models.append(model)
        return {idx: 80.0 for idx, _ in cands}

    with patch(
        "lightroom_tagger.core.provider_resolution.get_vision_model",
        return_value="config-vision-model",
    ), patch(
        "lightroom_tagger.core.matcher.compare_descriptions_batch",
        side_effect=capture_batch,
    ):
        _compute_desc_scores_for_candidates(
            insta_image={"ai_summary": "reference summary"},
            candidates=[{"ai_summary": "candidate summary"}],
            batch_size=10,
            desc_weight=0.3,
            skip_undescribed=True,
            provider_id=None,
            model=None,
            log_callback=None,
            registry=registry,
        )

    assert captured_models == ["config-vision-model"]


def test_score_candidates_resolves_model_once_for_all_candidates():
    """Provider/model selection must not reconstruct registry per candidate."""
    mock_db = Mock()
    insta_image = {
        'key': 'insta_test',
        'image_hash': 'a' * 16,
        'description': 'sunset',
        'local_path': '/tmp/insta.jpg',
    }
    candidates = [
        {'key': f'cat{i}', 'image_hash': 'a' * 16, 'description': 'sunset', 'local_path': f'/tmp/local{i}.jpg'}
        for i in range(3)
    ]

    with patch('lightroom_tagger.core.matcher.get_vision_comparison', return_value=None), \
         patch('lightroom_tagger.core.analyzer.compare_with_vision',
               return_value={'confidence': 100, 'verdict': 'SAME', 'reasoning': ''}), \
         patch('lightroom_tagger.core.analyzer.vision_score', return_value=1.0), \
         patch('lightroom_tagger.core.matcher.store_vision_comparison'), \
         _matcher_resolve_patch() as mock_resolve, \
         patch('lightroom_tagger.core.matcher.get_cached_phash', return_value=None), \
         patch('lightroom_tagger.core.matcher.get_or_create_cached_image', return_value=None), \
         patch('lightroom_tagger.core.matcher.InstagramCache') as mock_insta_cache, \
         patch('lightroom_tagger.core.phash.hamming_distance', return_value=0):
        mock_insta_cache.return_value.compress_instagram_image.return_value = '/tmp/insta.jpg'
        mock_insta_cache.return_value.cleanup.return_value = None
        score_candidates_with_vision(
            mock_db, insta_image, candidates,
            phash_weight=0.4, desc_weight=0.0, vision_weight=0.6,
        )

    mock_resolve.assert_called_once()


def test_sequential_abort_after_consecutive_rate_limits():
    """Fourth candidate is marked RATE_LIMITED without another API call."""
    from lightroom_tagger.core.exceptions import RateLimitError

    mock_db = Mock()
    insta_image = {
        'key': 'insta_test',
        'image_hash': 'a' * 16,
        'description': 'sunset',
        'local_path': '/tmp/insta.jpg',
    }
    candidates = [
        {'key': f'cat{i}', 'image_hash': 'a' * 16, 'description': 'd', 'local_path': f'/tmp/c{i}.jpg'}
        for i in range(4)
    ]
    compare_calls = {'n': 0}

    def compare_side_effect(*args, **kwargs):
        compare_calls['n'] += 1
        raise RateLimitError('429')

    registry = _fake_registry(
        fallback_order=['ollama'],
        models_by_provider={
            'ollama': [{'id': 'gemma3:27b', 'vision': True, 'source': 'config'}],
        },
    )
    registry.get_retry_config.return_value = {
        'max_retries': 0,
        'backoff_seconds': [],
        'respect_retry_after': False,
    }
    client = MagicMock(_provider_id='ollama')
    registry.get_client.return_value = client
    resolved = ResolvedModel('ollama', 'gemma3:27b', registry)

    with patch('lightroom_tagger.core.vision_client.compare_images', side_effect=compare_side_effect), \
         patch('lightroom_tagger.core.matcher.get_vision_comparison', return_value=None), \
         patch('lightroom_tagger.core.analyzer.vision_score', return_value=0.0), \
         _matcher_resolve_patch(registry=registry), \
         patch('lightroom_tagger.core.analyzer.vision_compare.resolve_model', return_value=resolved), \
         patch('lightroom_tagger.core.matcher.get_cached_phash', return_value=None), \
         patch('lightroom_tagger.core.matcher.get_or_create_cached_image', return_value='/tmp/c.jpg'), \
         patch('lightroom_tagger.core.matcher.InstagramCache') as mock_insta_cache, \
         patch('lightroom_tagger.core.analyzer.get_viewable_path_managed', side_effect=lambda p: (p, False)), \
         patch('lightroom_tagger.core.analyzer.compress_image', side_effect=lambda p: p), \
         patch('lightroom_tagger.core.phash.hamming_distance', return_value=0), \
         patch('os.path.exists', return_value=True):
        mock_insta_cache.return_value.compress_instagram_image.return_value = '/tmp/insta.jpg'
        mock_insta_cache.return_value.cleanup.return_value = None
        results = score_candidates_with_vision(
            mock_db, insta_image, candidates,
            phash_weight=0.0, desc_weight=0.0, vision_weight=1.0,
            batch_threshold=999,
        )

    assert compare_calls['n'] == 3
    assert len(results) == 4
    assert all(r['vision_result'] == 'RATE_LIMITED' for r in results)


def test_sequential_abort_after_consecutive_fatal_errors():
    """Loop stops after three fatal errors — remaining candidates are not scored."""
    from lightroom_tagger.core.exceptions import InvalidRequestError

    mock_db = Mock()
    insta_image = {
        'key': 'insta_test',
        'image_hash': 'a' * 16,
        'description': 'sunset',
        'local_path': '/tmp/insta.jpg',
    }
    candidates = [
        {'key': f'cat{i}', 'image_hash': 'a' * 16, 'description': 'd', 'local_path': f'/tmp/c{i}.jpg'}
        for i in range(5)
    ]
    compare_calls = {'n': 0}

    def compare_side_effect(*args, **kwargs):
        compare_calls['n'] += 1
        raise InvalidRequestError('400 bad request')

    registry = _fake_registry(
        fallback_order=['ollama'],
        models_by_provider={
            'ollama': [{'id': 'gemma3:27b', 'vision': True, 'source': 'config'}],
        },
    )
    registry.get_retry_config.return_value = {
        'max_retries': 0,
        'backoff_seconds': [],
        'respect_retry_after': False,
    }
    client = MagicMock(_provider_id='ollama')
    registry.get_client.return_value = client
    resolved = ResolvedModel('ollama', 'gemma3:27b', registry)

    with patch('lightroom_tagger.core.vision_client.compare_images', side_effect=compare_side_effect), \
         patch('lightroom_tagger.core.matcher.get_vision_comparison', return_value=None), \
         patch('lightroom_tagger.core.analyzer.vision_score', return_value=0.0), \
         _matcher_resolve_patch(registry=registry), \
         patch('lightroom_tagger.core.analyzer.vision_compare.resolve_model', return_value=resolved), \
         patch('lightroom_tagger.core.matcher.get_cached_phash', return_value=None), \
         patch('lightroom_tagger.core.matcher.get_or_create_cached_image', return_value='/tmp/c.jpg'), \
         patch('lightroom_tagger.core.matcher.InstagramCache') as mock_insta_cache, \
         patch('lightroom_tagger.core.analyzer.get_viewable_path_managed', side_effect=lambda p: (p, False)), \
         patch('lightroom_tagger.core.analyzer.compress_image', side_effect=lambda p: p), \
         patch('lightroom_tagger.core.phash.hamming_distance', return_value=0), \
         patch('os.path.exists', return_value=True):
        mock_insta_cache.return_value.compress_instagram_image.return_value = '/tmp/insta.jpg'
        mock_insta_cache.return_value.cleanup.return_value = None
        results = score_candidates_with_vision(
            mock_db, insta_image, candidates,
            phash_weight=0.0, desc_weight=0.0, vision_weight=1.0,
            batch_threshold=999,
        )

    assert compare_calls['n'] == 3
    assert len(results) == 3
    assert all(r['vision_result'] == 'ERROR' for r in results)
