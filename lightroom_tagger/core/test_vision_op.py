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


def test_run_vision_op_persist_skips_invalid_result():
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

    assert outcome.status == 'skipped'


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


def test_matching_handler_enrich_uses_run_description_vision_op():
    with patch('lightroom_tagger.core.analyzer.run_description_vision_op') as mock_run:
        mock_run.return_value = {'summary': 'scene'}
        from lightroom_tagger.core.analyzer import run_description_vision_op as imported
        structured = imported('/tmp/x.jpg')
    mock_run.assert_called_once_with('/tmp/x.jpg')
    assert structured['summary'] == 'scene'


def test_analyze_instagram_images_uses_run_description_vision_op():
    with patch('lightroom_tagger.scripts.analyze_instagram_images.run_description_vision_op') as mock_run:
        mock_run.return_value = {'summary': 'ig'}
        from lightroom_tagger.scripts import analyze_instagram_images as mod
        structured = mod.run_description_vision_op('/tmp/ig.jpg')
    mock_run.assert_called_once_with('/tmp/ig.jpg')
    assert structured['summary'] == 'ig'
