from contextlib import ExitStack
from unittest.mock import MagicMock, patch

from lightroom_tagger.core.database import init_database, store_image, store_image_description, get_image_description
from lightroom_tagger.core.provider_registry import ProviderRegistry
from lightroom_tagger.core.provider_resolution import ResolvedModel, resolve_model
from lightroom_tagger.core.vision_op import VisionOpOutcome


def _written() -> VisionOpOutcome:
    return VisionOpOutcome(status='written')


def _fake_registry(
    *,
    defaults: dict | None = None,
    fallback_order: list[str] | None = None,
) -> MagicMock:
    registry = MagicMock(spec=ProviderRegistry)
    registry.defaults = defaults or {}
    registry.fallback_order = fallback_order or []
    return registry


def _describe_patches(
    *,
    mock_registry: MagicMock,
    mock_dispatcher: MagicMock,
    provider_id: str = "ollama",
    model: str = "test-model",
):
    """Patch resolve_model + vision path helpers for description integration tests."""
    return (
        patch(
            "lightroom_tagger.core.vision_op.resolve_model",
            return_value=ResolvedModel(provider_id, model, mock_registry),
        ),
        patch(
            "lightroom_tagger.core.vision_op.FallbackDispatcher",
            return_value=mock_dispatcher,
        ),
        patch(
            "lightroom_tagger.core.analyzer.description.get_viewable_path_managed",
            side_effect=lambda p: (p, False),
        ),
        patch(
            "lightroom_tagger.core.analyzer.description.compress_image",
            side_effect=lambda p: p,
        ),
    )


def _shortlist_passthrough(_db, _mk, cand_keys, top_k):
    return cand_keys[:top_k]


def _make_db(tmp_path):
    db_path = str(tmp_path / 'test.db')
    return init_database(db_path)


class TestDescribeMatchedImage:
    def test_generates_description_end_to_end_with_fake_provider(self, tmp_path):
        """describe_matched_image runs through the vision op with one injected registry."""
        import json

        from lightroom_tagger.core.description_service import describe_matched_image

        db = _make_db(tmp_path)
        filepath = str(tmp_path / 'photo.jpg')
        open(filepath, 'w').close()
        catalog_key = store_image(db, {'filepath': filepath, 'filename': 'photo.jpg'})

        raw_json = json.dumps({
            'summary': 'A street scene',
            'composition': {'depth': 'shallow'},
            'technical': {'mood': 'gritty'},
            'subjects': ['person'],
        })
        mock_registry = _fake_registry(
            defaults={"description": {"provider": "ollama", "model": "test-model"}},
            fallback_order=["ollama"],
        )
        mock_dispatcher = MagicMock()
        mock_dispatcher.call_with_fallback.return_value = (raw_json, "ollama", "test-model")

        with ExitStack() as stack:
            for p in _describe_patches(
                mock_registry=mock_registry,
                mock_dispatcher=mock_dispatcher,
            ):
                stack.enter_context(p)
            result = describe_matched_image(db, catalog_key)

        assert result.wrote
        desc = get_image_description(db, catalog_key)
        assert desc is not None
        assert desc['summary'] == 'A street scene'
        assert desc.get('perspectives') in (None, {})
        score_count = db.execute(
            "SELECT COUNT(*) AS n FROM image_scores WHERE image_key = ?",
            (catalog_key,),
        ).fetchone()['n']
        assert score_count == 0
        assert mock_dispatcher.call_with_fallback.call_args.kwargs["model"] == "test-model"

    def test_describe_matched_image_honors_description_vision_model_env(self, tmp_path, monkeypatch):
        """the vision op must use resolve_model so DESCRIPTION_VISION_MODEL env is honoured."""
        import json

        from lightroom_tagger.core.description_service import describe_matched_image

        monkeypatch.setenv("DESCRIPTION_VISION_MODEL", "env-desc-model")

        db = _make_db(tmp_path)
        filepath = str(tmp_path / 'photo.jpg')
        open(filepath, 'w').close()
        catalog_key = store_image(db, {'filepath': filepath, 'filename': 'photo.jpg'})

        raw_json = json.dumps({
            'summary': 'Env model scene',
            'composition': {},
            'technical': {},
            'subjects': [],
        })
        registry = _fake_registry(
            defaults={"description": {"provider": "ollama", "model": "json-default"}},
            fallback_order=["ollama"],
        )
        mock_dispatcher = MagicMock()
        mock_dispatcher.call_with_fallback.return_value = (raw_json, "ollama", "env-desc-model")

        with (
            patch(
                "lightroom_tagger.core.provider_resolution.ProviderRegistry",
                return_value=registry,
            ),
            patch(
                "lightroom_tagger.core.vision_op.resolve_model",
                wraps=resolve_model,
            ),
            patch(
                "lightroom_tagger.core.vision_op.FallbackDispatcher",
                return_value=mock_dispatcher,
            ),
            patch(
                "lightroom_tagger.core.analyzer.description.get_viewable_path_managed",
                side_effect=lambda p: (p, False),
            ),
            patch(
                "lightroom_tagger.core.analyzer.description.compress_image",
                side_effect=lambda p: p,
            ),
        ):
            result = describe_matched_image(
                db, catalog_key, provider_id="ollama", model=None,
            )

        assert result.wrote
        assert mock_dispatcher.call_with_fallback.call_args.kwargs["model"] == "env-desc-model"

    def test_generates_description_when_missing(self, tmp_path):
        from lightroom_tagger.core.description_service import describe_matched_image

        db = _make_db(tmp_path)
        filepath = str(tmp_path / 'photo.jpg')
        open(filepath, 'w').close()
        catalog_key = store_image(db, {'filepath': filepath, 'filename': 'photo.jpg'})

        with patch('lightroom_tagger.core.vision_op.run_vision_op') as mock_run, \
             patch('lightroom_tagger.core.description_service.get_description_model', return_value='test-model'):
            mock_run.return_value = ({
                'summary': 'A street scene', 'composition': {'depth': 'shallow'},
                'technical': {'mood': 'gritty'},
                'subjects': ['person'],
            }, 'ollama', 'test-model')
            result = describe_matched_image(db, catalog_key)

        assert result.wrote
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
            'composition': {}, 'technical': {},
            'subjects': [], 'model_used': 'old',
        })

        with patch('lightroom_tagger.core.vision_op.run_vision_op') as mock_run:
            result = describe_matched_image(db, catalog_key)

        assert not result.wrote
        mock_run.assert_not_called()

    def test_regenerates_when_force_is_true(self, tmp_path):
        from lightroom_tagger.core.description_service import describe_matched_image

        db = _make_db(tmp_path)
        filepath = str(tmp_path / 'photo.jpg')
        open(filepath, 'w').close()
        catalog_key = store_image(db, {'filepath': filepath, 'filename': 'photo.jpg'})
        store_image_description(db, {
            'image_key': catalog_key, 'image_type': 'catalog', 'summary': 'old summary',
            'composition': {}, 'technical': {},
            'subjects': [], 'model_used': 'old',
        })

        with patch('lightroom_tagger.core.vision_op.run_vision_op') as mock_run, \
             patch('lightroom_tagger.core.description_service.get_description_model', return_value='new-model'):
            mock_run.return_value = ({
                'summary': 'Updated summary', 'composition': {},
                'technical': {}, 'subjects': [],
            }, 'ollama', 'new-model')
            result = describe_matched_image(db, catalog_key, force=True)

        assert result.wrote
        desc = get_image_description(db, catalog_key)
        assert desc['summary'] == 'Updated summary'

    def test_returns_false_when_image_not_found(self, tmp_path):
        from lightroom_tagger.core.description_service import describe_matched_image

        db = _make_db(tmp_path)
        result = describe_matched_image(db, 'NONEXISTENT')
        assert not result.wrote

    def test_returns_false_when_file_missing(self, tmp_path):
        from lightroom_tagger.core.description_service import describe_matched_image

        db = _make_db(tmp_path)
        catalog_key = store_image(db, {'filepath': '/no/such/file.jpg', 'filename': 'file.jpg'})
        result = describe_matched_image(db, catalog_key)
        assert not result.wrote

    def test_skips_video_without_calling_provider(self, tmp_path):
        """Video files must never reach the vision op — the vision pipeline
        cannot process them and would otherwise wedge the worker pool on
        multi-minute retry backoffs."""
        from lightroom_tagger.core.description_service import describe_matched_image

        db = _make_db(tmp_path)
        filepath = str(tmp_path / 'clip.mov')
        open(filepath, 'w').close()
        catalog_key = store_image(db, {'filepath': filepath, 'filename': 'clip.mov'})

        with patch('lightroom_tagger.core.vision_op.run_vision_op') as mock_run, \
             patch('lightroom_tagger.core.description_service.get_or_create_cached_image') as mock_cache:
            result = describe_matched_image(db, catalog_key)

        assert not result.wrote
        mock_run.assert_not_called()
        mock_cache.assert_not_called()
        assert get_image_description(db, catalog_key) is None

    def test_uses_silent_compression_when_vision_cache_hit_without_provider(self, tmp_path):
        """Default-provider describe still skips redundant compression on cache hit."""
        from lightroom_tagger.core.description_service import describe_matched_image
        from PIL import Image

        db = _make_db(tmp_path)
        orig = str(tmp_path / 'photo.jpg')
        cached = str(tmp_path / 'c.jpg')
        Image.new('RGB', (2, 2)).save(orig, 'JPEG')
        Image.new('RGB', (2, 2)).save(cached, 'JPEG')
        catalog_key = store_image(db, {'filepath': orig, 'filename': 'photo.jpg'})

        with patch('lightroom_tagger.core.description_service.build_description_op_spec') as mock_spec, \
             patch('lightroom_tagger.core.description_service.run_vision_op_persist', return_value=_written()), \
             patch(
                 'lightroom_tagger.core.description_service.get_or_create_cached_image',
                 return_value=cached,
             ), \
             patch('lightroom_tagger.core.description_service.get_description_model', return_value='test-model'):
            mock_spec.return_value = MagicMock()
            describe_matched_image(db, catalog_key)

        mock_spec.assert_called_once()
        _, kwargs = mock_spec.call_args
        assert kwargs.get('silent_compression') is True

    def test_uses_silent_compression_when_vision_cache_hit_and_provider(self, tmp_path):
        """Catalog cache hit + provider describe passes silent_compression=True."""
        from lightroom_tagger.core.description_service import describe_matched_image
        from PIL import Image

        db = _make_db(tmp_path)
        orig = str(tmp_path / 'photo.jpg')
        cached = str(tmp_path / 'c.jpg')
        Image.new('RGB', (2, 2)).save(orig, 'JPEG')
        Image.new('RGB', (2, 2)).save(cached, 'JPEG')
        catalog_key = store_image(db, {'filepath': orig, 'filename': 'photo.jpg'})

        with patch('lightroom_tagger.core.description_service.build_description_op_spec') as mock_spec, \
             patch('lightroom_tagger.core.description_service.run_vision_op_persist', return_value=_written()), \
             patch(
                 'lightroom_tagger.core.description_service.get_or_create_cached_image',
                 return_value=cached,
             ), \
             patch('lightroom_tagger.core.description_service.get_description_model', return_value='test-model'):
            mock_spec.return_value = MagicMock()
            describe_matched_image(db, catalog_key, provider_id='test-prov')

        mock_spec.assert_called_once()
        _, kwargs = mock_spec.call_args
        assert kwargs.get('silent_compression') is True

    def test_skips_video_even_with_force(self, tmp_path):
        """force=True must not override the video short-circuit — the provider
        still cannot describe video bytes."""
        from lightroom_tagger.core.description_service import describe_matched_image

        db = _make_db(tmp_path)
        filepath = str(tmp_path / 'clip.mp4')
        open(filepath, 'w').close()
        catalog_key = store_image(db, {'filepath': filepath, 'filename': 'clip.mp4'})

        with patch('lightroom_tagger.core.vision_op.run_vision_op') as mock_run:
            result = describe_matched_image(db, catalog_key, force=True)

        assert not result.wrote
        mock_run.assert_not_called()

    def test_does_not_store_empty_summary(self, tmp_path):
        from lightroom_tagger.core.description_service import describe_matched_image

        db = _make_db(tmp_path)
        filepath = str(tmp_path / 'photo.jpg')
        open(filepath, 'w').close()
        catalog_key = store_image(db, {'filepath': filepath, 'filename': 'photo.jpg'})

        with patch('lightroom_tagger.core.vision_op.run_vision_op') as mock_run:
            mock_run.return_value = ({
                'summary': '', 'composition': {},
                'technical': {}, 'subjects': [],
            }, 'ollama', 'test-model')
            result = describe_matched_image(db, catalog_key)

        assert not result.wrote
        assert get_image_description(db, catalog_key) is None

    def test_force_does_not_overwrite_with_empty_summary(self, tmp_path):
        from lightroom_tagger.core.description_service import describe_matched_image

        db = _make_db(tmp_path)
        filepath = str(tmp_path / 'photo.jpg')
        open(filepath, 'w').close()
        catalog_key = store_image(db, {'filepath': filepath, 'filename': 'photo.jpg'})
        store_image_description(db, {
            'image_key': catalog_key, 'image_type': 'catalog', 'summary': 'keep me',
            'composition': {}, 'technical': {},
            'subjects': [], 'model_used': 'old',
        })

        with patch('lightroom_tagger.core.vision_op.run_vision_op') as mock_run:
            mock_run.return_value = ({
                'summary': '   ', 'composition': {},
                'technical': {}, 'subjects': [],
            }, 'ollama', 'test-model')
            result = describe_matched_image(db, catalog_key, force=True)

        assert not result.wrote
        assert get_image_description(db, catalog_key)['summary'] == 'keep me'


class TestDescribeInstagramImage:
    def test_skips_video_without_calling_provider(self, tmp_path):
        from lightroom_tagger.core.database import store_instagram_dump_media
        from lightroom_tagger.core.description_service import describe_instagram_image

        db = _make_db(tmp_path)
        filepath = str(tmp_path / 'story.mov')
        open(filepath, 'w').close()
        store_instagram_dump_media(db, {
            'media_key': 'IGVID', 'file_path': filepath, 'caption': '',
            'timestamp': None, 'taken_at': None,
        })

        with patch('lightroom_tagger.core.vision_op.run_vision_op') as mock_run:
            result = describe_instagram_image(db, 'IGVID')

        assert not result.wrote
        mock_run.assert_not_called()


class TestMatchDumpMediaDescriptions:
    """Verify match_dump_media triggers description generation for matches."""

    @patch('lightroom_tagger.scripts.match_instagram_dump.shortlist_catalog_candidates_by_clip')
    @patch('lightroom_tagger.scripts.match_instagram_dump.describe_matched_image')
    @patch('lightroom_tagger.scripts.match_instagram_dump.score_candidates_with_vision')
    @patch('lightroom_tagger.scripts.match_instagram_dump.find_candidates_by_date')
    @patch('lightroom_tagger.scripts.match_instagram_dump.get_unprocessed_dump_media')
    def test_generates_description_on_match(self, mock_unprocessed, mock_candidates,
                                             mock_score, mock_describe, mock_shortlist, tmp_path):
        from lightroom_tagger.scripts.match_instagram_dump import match_dump_media

        db = _make_db(tmp_path)
        store_image(db, {'key': 'CAT1', 'filepath': '/p/a.jpg', 'filename': 'a.jpg'})

        mock_unprocessed.return_value = [{'media_key': 'IG1', 'file_path': '/ig/1.jpg', 'caption': ''}]
        mock_candidates.return_value = [{'key': 'CAT1', 'filepath': '/p/a.jpg', 'phash': 'abc', 'description': ''}]
        mock_score.return_value = [{'catalog_key': 'CAT1', 'total_score': 0.9, 'vision_result': 'same', 'vision_score': 0.9}]
        mock_describe.return_value = _written()
        mock_shortlist.side_effect = _shortlist_passthrough

        with patch('lightroom_tagger.scripts.match_instagram_dump.mark_dump_media_processed'), \
             patch('lightroom_tagger.scripts.match_instagram_dump.init_instagram_dump_table'), \
             patch('lightroom_tagger.scripts.match_instagram_dump.init_catalog_table'):
            stats, matches = match_dump_media(db)

        mock_describe.assert_called_once_with(db, 'CAT1', force=False)
        assert stats['descriptions_generated'] == 1

    @patch('lightroom_tagger.scripts.match_instagram_dump.shortlist_catalog_candidates_by_clip')
    @patch('lightroom_tagger.scripts.match_instagram_dump.describe_matched_image')
    @patch('lightroom_tagger.scripts.match_instagram_dump.score_candidates_with_vision')
    @patch('lightroom_tagger.scripts.match_instagram_dump.find_candidates_by_date')
    @patch('lightroom_tagger.scripts.match_instagram_dump.get_unprocessed_dump_media')
    def test_passes_force_flag(self, mock_unprocessed, mock_candidates,
                                mock_score, mock_describe, mock_shortlist, tmp_path):
        from lightroom_tagger.scripts.match_instagram_dump import match_dump_media

        db = _make_db(tmp_path)
        store_image(db, {'key': 'CAT2', 'filepath': '/p/b.jpg', 'filename': 'b.jpg'})

        mock_unprocessed.return_value = [{'media_key': 'IG2', 'file_path': '/ig/2.jpg', 'caption': ''}]
        mock_candidates.return_value = [{'key': 'CAT2', 'filepath': '/p/b.jpg', 'phash': 'def', 'description': ''}]
        mock_score.return_value = [{'catalog_key': 'CAT2', 'total_score': 0.85, 'vision_result': 'same', 'vision_score': 0.85}]
        mock_describe.return_value = _written()
        mock_shortlist.side_effect = _shortlist_passthrough

        with patch('lightroom_tagger.scripts.match_instagram_dump.mark_dump_media_processed'), \
             patch('lightroom_tagger.scripts.match_instagram_dump.init_instagram_dump_table'), \
             patch('lightroom_tagger.scripts.match_instagram_dump.init_catalog_table'):
            stats, matches = match_dump_media(db, force_descriptions=True)

        mock_describe.assert_called_once_with(db, 'CAT2', force=True)

    @patch('lightroom_tagger.scripts.match_instagram_dump.shortlist_catalog_candidates_by_clip')
    @patch('lightroom_tagger.scripts.match_instagram_dump.describe_matched_image')
    @patch('lightroom_tagger.scripts.match_instagram_dump.score_candidates_with_vision')
    @patch('lightroom_tagger.scripts.match_instagram_dump.find_candidates_by_date')
    @patch('lightroom_tagger.scripts.match_instagram_dump.get_unprocessed_dump_media')
    def test_description_exception_logs_without_callback(self, mock_unprocessed, mock_candidates,
                                                           mock_score, mock_describe, mock_shortlist, tmp_path):
        from lightroom_tagger.scripts import match_instagram_dump
        from lightroom_tagger.scripts.match_instagram_dump import match_dump_media

        db = _make_db(tmp_path)
        store_image(db, {'key': 'CAT3', 'filepath': '/p/c.jpg', 'filename': 'c.jpg'})

        mock_unprocessed.return_value = [{'media_key': 'IG3', 'file_path': '/ig/3.jpg', 'caption': ''}]
        mock_candidates.return_value = [{'key': 'CAT3', 'filepath': '/p/c.jpg', 'phash': 'ghi', 'description': ''}]
        mock_score.return_value = [{'catalog_key': 'CAT3', 'total_score': 0.9, 'vision_result': 'same', 'vision_score': 0.9}]
        mock_describe.side_effect = RuntimeError('model down')
        mock_shortlist.side_effect = _shortlist_passthrough

        with patch('lightroom_tagger.scripts.match_instagram_dump.mark_dump_media_processed'), \
             patch('lightroom_tagger.scripts.match_instagram_dump.init_instagram_dump_table'), \
             patch('lightroom_tagger.scripts.match_instagram_dump.init_catalog_table'), \
             patch.object(match_instagram_dump.logger, 'warning') as mock_warn:
            match_dump_media(db, log_callback=None)

        mock_warn.assert_called_once()
        assert 'CAT3' in mock_warn.call_args[0][0]


class TestStoreStructuredVisualMapping:
    """_store_structured fallbacks and persistence for VIS-01 columns."""

    def test_mood_fallback_from_technical_mood_without_mood_tags(self, tmp_path):
        from lightroom_tagger.core.description_service import _store_structured

        db = _make_db(tmp_path)
        filepath = str(tmp_path / 'photo.jpg')
        open(filepath, 'w').close()
        catalog_key = store_image(db, {'filepath': filepath, 'filename': 'photo.jpg'})

        structured = {
            'summary': 'A scene',
            'composition': {},
            'technical': {'mood': 'gloomy'},
            'subjects': [],
        }
        _store_structured(db, catalog_key, 'catalog', structured, 'test-model')

        desc = get_image_description(db, catalog_key)
        assert desc['mood_tags'] == ['gloomy']

    def test_dominant_colors_fallback_from_technical(self, tmp_path):
        from lightroom_tagger.core.description_service import _store_structured

        db = _make_db(tmp_path)
        filepath = str(tmp_path / 'photo.jpg')
        open(filepath, 'w').close()
        catalog_key = store_image(db, {'filepath': filepath, 'filename': 'photo.jpg'})

        structured = {
            'summary': 'Colors',
            'composition': {},
            'technical': {'dominant_colors': ['#aabbcc']},
            'subjects': [],
        }
        _store_structured(db, catalog_key, 'catalog', structured, 'test-model')

        desc = get_image_description(db, catalog_key)
        assert desc['dominant_colors'] == ['#aabbcc']

    def test_root_dominant_colors_mood_tags_has_repetition_round_trip(self, tmp_path):
        from lightroom_tagger.core.description_service import _store_structured

        db = _make_db(tmp_path)
        filepath = str(tmp_path / 'photo.jpg')
        open(filepath, 'w').close()
        catalog_key = store_image(db, {'filepath': filepath, 'filename': 'photo.jpg'})

        structured = {
            'summary': 'Full visual row',
            'composition': {},
            'technical': {},
            'subjects': ['x'],
            'dominant_colors': ['#112233', '#445566'],
            'mood_tags': ['calm', 'cool'],
            'has_repetition': True,
        }
        _store_structured(db, catalog_key, 'catalog', structured, 'm9')

        desc = get_image_description(db, catalog_key)
        assert desc['dominant_colors'] == ['#112233', '#445566']
        assert desc['mood_tags'] == ['calm', 'cool']
        assert desc['has_repetition'] == 1
