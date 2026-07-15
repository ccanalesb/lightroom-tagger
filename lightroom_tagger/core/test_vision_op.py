"""Tests for the vision-op engine and description op-spec."""

import os
import tempfile
from unittest.mock import MagicMock, patch

from lightroom_tagger.core.analyzer import build_description_op_spec, run_description_vision_op
from lightroom_tagger.core.provider_registry import ProviderRegistry
from lightroom_tagger.core.provider_resolution import ResolvedModel, resolve_model
from lightroom_tagger.core.vision_op import VisionOpOutcome, run_vision_op, run_vision_op_persist


def test_vision_op_outcome_wrote_property():
    assert VisionOpOutcome(status='written').wrote is True
    assert VisionOpOutcome(status='skipped').wrote is False
    assert VisionOpOutcome(status='failed').wrote is False


def test_run_vision_op_persist_skips_on_pre_check():
    spec = MagicMock()
    outcome = run_vision_op_persist(
        spec,
        pre_check=lambda: VisionOpOutcome(status='skipped', reason='early'),
        accept_result=lambda _p: True,
        persist=lambda *_a: None,
    )
    assert outcome.status == 'skipped'
    spec.fn_factory.assert_not_called()


def test_run_vision_op_persist_writes_when_accepted():
    spec = MagicMock()
    spec.registry = None
    spec.resolve_kind = 'description'
    spec.provider_id = 'ollama'
    spec.model = 'm1'
    spec.operation = 'describe'
    spec.log_callback = None
    spec.error_policy = None
    spec._cleanup = None
    spec.parse_response = lambda raw: {'summary': raw}
    spec.fn_factory.return_value = MagicMock()

    with patch('lightroom_tagger.core.vision_op.resolve_model') as mock_resolve, \
         patch('lightroom_tagger.core.vision_op.FallbackDispatcher') as mock_disp:
        mock_registry = MagicMock()
        mock_resolve.return_value = ResolvedModel('ollama', 'm1', mock_registry)
        mock_disp.return_value.call_with_fallback.return_value = ('ok', 'ollama', 'm1')
        stored = {}

        def persist(parsed, provider, model):
            stored['parsed'] = parsed
            stored['provider'] = provider
            stored['model'] = model

        outcome = run_vision_op_persist(
            spec,
            accept_result=lambda p: p.get('summary') == 'ok',
            persist=persist,
        )

    assert outcome.wrote is True
    assert stored['provider'] == 'ollama'


def test_run_vision_op_persist_fails_invalid_result():
    spec = MagicMock()
    spec.registry = None
    spec.resolve_kind = 'description'
    spec.provider_id = 'ollama'
    spec.model = 'm1'
    spec.operation = 'describe'
    spec.log_callback = None
    spec.error_policy = None
    spec._cleanup = None
    spec.parse_response = lambda _raw: {'summary': ''}
    spec.fn_factory.return_value = MagicMock()

    with patch('lightroom_tagger.core.vision_op.resolve_model') as mock_resolve, \
         patch('lightroom_tagger.core.vision_op.FallbackDispatcher') as mock_disp:
        mock_registry = MagicMock()
        mock_resolve.return_value = ResolvedModel('ollama', 'm1', mock_registry)
        mock_disp.return_value.call_with_fallback.return_value = ('{}', 'ollama', 'm1')
        outcome = run_vision_op_persist(
            spec,
            accept_result=lambda p: bool(p.get('summary')),
            persist=lambda *_a: None,
        )

    assert outcome.status == 'failed'
    assert outcome.reason == 'invalid result'


def test_run_vision_op_parse_response_accepts_provider_and_model():
    spec = MagicMock()
    spec.registry = None
    spec.resolve_kind = 'description'
    spec.provider_id = 'ollama'
    spec.model = 'm1'
    spec.operation = 'score'
    spec.log_callback = None
    spec.error_policy = None
    spec._cleanup = None
    spec.parse_response = lambda raw, provider, model: (raw, provider, model)
    spec.fn_factory.return_value = MagicMock()

    with patch('lightroom_tagger.core.vision_op.resolve_model') as mock_resolve, \
         patch('lightroom_tagger.core.vision_op.FallbackDispatcher') as mock_disp:
        mock_registry = MagicMock()
        mock_resolve.return_value = ResolvedModel('ollama', 'm1', mock_registry)
        mock_disp.return_value.call_with_fallback.return_value = ('parsed', 'ollama', 'm1')
        parsed, provider, model = run_vision_op(spec)

    assert parsed == ('parsed', 'ollama', 'm1')
    assert provider == 'ollama'
    assert model == 'm1'


def test_run_vision_op_parse_response_falls_back_to_single_arg():
    spec = MagicMock()
    spec.registry = None
    spec.resolve_kind = 'description'
    spec.provider_id = 'ollama'
    spec.model = 'm1'
    spec.operation = 'describe'
    spec.log_callback = None
    spec.error_policy = None
    spec._cleanup = None
    spec.parse_response = lambda raw: {'summary': raw}
    spec.fn_factory.return_value = MagicMock()

    with patch('lightroom_tagger.core.vision_op.resolve_model') as mock_resolve, \
         patch('lightroom_tagger.core.vision_op.FallbackDispatcher') as mock_disp:
        mock_registry = MagicMock()
        mock_resolve.return_value = ResolvedModel('ollama', 'm1', mock_registry)
        mock_disp.return_value.call_with_fallback.return_value = ('ok', 'ollama', 'm1')
        parsed, provider, model = run_vision_op(spec)

    assert parsed == {'summary': 'ok'}


def test_description_op_spec_silent_compression_skips_recompress():
    """Vision-cache resume path must not call compress_image again."""
    from PIL import Image

    fd, test_path = tempfile.mkstemp(suffix='.jpg')
    os.close(fd)
    try:
        Image.new('RGB', (64, 64)).save(test_path, 'JPEG')
        mock_desc = {
            'summary': 'ok',
            'composition': {},
            'perspectives': {},
            'technical': {},
            'subjects': [],
            'best_perspective': 'street',
        }
        with patch('lightroom_tagger.core.analyzer.description.compress_image') as mock_compress, \
             patch('lightroom_tagger.core.analyzer.description.get_viewable_path_managed', return_value=(test_path, False)), \
             patch('lightroom_tagger.core.vision_op.resolve_model') as mock_resolve, \
             patch('lightroom_tagger.core.vision_op.FallbackDispatcher') as mock_disp, \
             patch('lightroom_tagger.core.analyzer.description.parse_description_response', return_value=mock_desc):
            mock_registry = MagicMock()
            mock_resolve.return_value = ResolvedModel('ollama', 'vision-model', mock_registry)
            mock_disp.return_value.call_with_fallback.return_value = ('{}', 'ollama', 'vision-model')
            run_description_vision_op(test_path, provider_id='ollama', silent_compression=True)

        mock_compress.assert_not_called()
    finally:
        if os.path.exists(test_path):
            os.unlink(test_path)


def test_run_description_vision_op_honors_description_vision_model_env(monkeypatch):
    """run_description_vision_op must use resolve_model so DESCRIPTION_VISION_MODEL env is honoured."""
    registry = MagicMock(spec=ProviderRegistry)
    registry.defaults = {"description": {"provider": "ollama", "model": "json-default"}}
    registry.fallback_order = ["ollama"]

    mock_dispatcher = MagicMock()
    mock_dispatcher.call_with_fallback.return_value = (
        '{"summary": "ok", "composition": {}, "perspectives": {}, '
        '"technical": {}, "subjects": [], "best_perspective": "street"}',
        "ollama",
        "env-desc-model",
    )

    monkeypatch.setenv("DESCRIPTION_VISION_MODEL", "env-desc-model")

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
            return_value=("/fake/path.jpg", False),
        ),
        patch(
            "lightroom_tagger.core.analyzer.description.compress_image",
            side_effect=lambda p: p,
        ),
    ):
        result = run_description_vision_op("/fake/path.jpg", provider_id="ollama", model=None)

    assert result["summary"] == "ok"
    assert mock_dispatcher.call_with_fallback.call_args.kwargs["model"] == "env-desc-model"


def test_run_description_vision_op_constructs_registry_once(monkeypatch):
    """ProviderRegistry must be built at most once per run_description_vision_op call."""
    registry = MagicMock(spec=ProviderRegistry)
    registry.defaults = {"description": {"provider": "ollama", "model": "vision-model"}}
    registry.fallback_order = ["ollama"]

    mock_dispatcher = MagicMock()
    mock_dispatcher.call_with_fallback.return_value = (
        '{"summary": "ok", "composition": {}, "perspectives": {}, '
        '"technical": {}, "subjects": [], "best_perspective": "street"}',
        "ollama",
        "vision-model",
    )

    with (
        patch(
            "lightroom_tagger.core.provider_resolution.ProviderRegistry",
            return_value=registry,
        ) as mock_reg_ctor,
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
            return_value=("/fake/path.jpg", False),
        ),
        patch(
            "lightroom_tagger.core.analyzer.description.compress_image",
            side_effect=lambda p: p,
        ),
    ):
        run_description_vision_op("/fake/path.jpg", provider_id="ollama")

    mock_reg_ctor.assert_called_once()


def test_enricher_uses_run_description_vision_op():
    from lightroom_tagger.lightroom import enricher

    with patch('lightroom_tagger.lightroom.enricher.run_description_vision_op') as mock_run, \
         patch('lightroom_tagger.lightroom.enricher.compute_phash', return_value='phash'), \
         patch('lightroom_tagger.lightroom.enricher.extract_exif', return_value={}), \
         patch('lightroom_tagger.lightroom.enricher.get_catalog_images_needing_analysis', return_value=[{'filepath': '/a.jpg'}]), \
         patch('lightroom_tagger.lightroom.enricher.store_catalog_image'):
        mock_run.return_value = {'summary': 'scene'}
        enricher.enrich_catalog_images(MagicMock())
    mock_run.assert_called_once_with('/a.jpg')


def test_matching_handler_enrich_uses_run_description_vision_op(tmp_path):
    """handle_enrich_catalog must run the description core op per image and
    persist its summary."""
    import sys

    backend = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        'apps', 'visualizer', 'backend',
    )
    if backend not in sys.path:
        sys.path.insert(0, backend)

    from jobs.handlers.matching import handle_enrich_catalog

    from lightroom_tagger.core.database import (
        get_image,
        init_catalog_table,
        init_database,
        store_catalog_image,
    )

    db_path = str(tmp_path / 'library.db')
    db = init_database(db_path)
    init_catalog_table(db)
    filepath = str(tmp_path / 'photo.jpg')
    open(filepath, 'w').close()
    store_catalog_image(db, {'key': 'CAT1', 'filepath': filepath, 'filename': 'photo.jpg'})
    db.close()

    runner = MagicMock()
    runner.db = MagicMock()
    runner.is_cancelled.return_value = False

    with patch('jobs.handlers.matching._resolve_library_db_or_fail', return_value=db_path), \
         patch('jobs.handlers.matching.get_job', return_value=None), \
         patch('jobs.handlers.matching.load_resume_state', return_value=set()), \
         patch('jobs.handlers.matching.add_job_log'), \
         patch('lightroom_tagger.core.config.load_config', return_value=MagicMock(vision_cache_enabled=False)), \
         patch('lightroom_tagger.core.analyzer.compute_phash', return_value='phash'), \
         patch('lightroom_tagger.core.analyzer.extract_exif', return_value={}), \
         patch('lightroom_tagger.core.analyzer.run_description_vision_op', return_value={'summary': 'scene'}) as mock_run:
        handle_enrich_catalog(runner, 'job-enrich', {})

    mock_run.assert_called_once_with(filepath)
    verify = init_database(db_path)
    assert get_image(verify, 'CAT1')['description'] == 'scene'
    verify.close()


def test_analyze_instagram_images_uses_run_description_vision_op(tmp_path):
    """The analyze_instagram_images script must route describe through the core op."""
    from lightroom_tagger.scripts import analyze_instagram_images as mod

    img = tmp_path / 'ig.jpg'
    img.write_text('')

    with patch.object(mod, 'init_database', return_value=MagicMock()), \
         patch.object(mod, 'init_instagram_table'), \
         patch.object(mod, 'store_instagram_image', return_value='IG1'), \
         patch.object(mod, 'scan_instagram_folder', return_value=[{
             'post_id': 'p1', 'local_path': str(img), 'filename': 'ig.jpg',
             'post_url': 'https://instagram.com/p/p1/',
         }]), \
         patch.object(mod, 'compute_phash', return_value='phash'), \
         patch.object(mod, 'extract_exif', return_value={}), \
         patch.object(mod, 'run_description_vision_op', return_value={'summary': 'ig'}) as mock_run:
        mod.main()

    mock_run.assert_called_once_with(str(img))
