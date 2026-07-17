import importlib
import json
import os
import tempfile
from unittest.mock import MagicMock, patch

from lightroom_tagger.core.analyzer import (
    compare_with_vision,
    compress_image,
    run_description_vision_op,
    vision_score,
)
from lightroom_tagger.core.provider_registry import ProviderRegistry
from lightroom_tagger.core.provider_resolution import ResolvedModel, resolve_model
from lightroom_tagger.core.test_vision_helpers import (
    fake_compare_client,
    fake_vision_registry,
    vision_compare_test_context,
)


def test_composed_catalog_analysis_returns_all_signals():
    """Phash, exif, description, and structured description match the former monolithic pipeline."""
    mock_desc = {
        'summary': 'A sunset photo',
        'composition': {},
        'perspectives': {
            'street': {'analysis': 'Good light', 'score': 6},
            'documentary': {'analysis': 'Weak story', 'score': 4},
            'publisher': {'analysis': 'Stock use', 'score': 5},
        },
        'technical': {},
        'subjects': [],
        'best_perspective': 'street',
    }
    with patch('lightroom_tagger.core.analyzer.compute_phash', return_value='a1b2c3d4e5f6g7h8'), \
         patch('lightroom_tagger.core.analyzer.extract_exif', return_value={'camera': 'Canon EOS R5'}), \
         patch('lightroom_tagger.core.analyzer.run_description_vision_op', return_value=mock_desc):

        from lightroom_tagger.core.analyzer import compute_phash, extract_exif, run_description_vision_op

        path = '/fake/path.jpg'
        phash = compute_phash(path)
        exif = extract_exif(path)
        structured = run_description_vision_op(path)
        result = {
            'phash': phash,
            'exif': exif,
            'description': structured.get('summary', ''),
            'structured_description': structured,
        }

    assert result['phash'] == 'a1b2c3d4e5f6g7h8'
    assert result['exif']['camera'] == 'Canon EOS R5'
    assert result['description'] == 'A sunset photo'
    assert result['structured_description'] == mock_desc


def test_compare_with_vision_returns_result():
    """Vision comparison should return dict with verdict and confidence."""
    with vision_compare_test_context() as (_registry, _client):
        result = compare_with_vision('/tmp/local.jpg', '/tmp/insta.jpg')

    assert result['verdict'] in ['SAME', 'DIFFERENT', 'UNCERTAIN']
    assert 0 <= result['confidence'] <= 100
    assert result['_provider'] == 'ollama'
    assert result['_model'] == 'vision-model'


def test_vision_score_converts_correctly():
    """Vision score should convert result to float."""

    assert vision_score('SAME') == 1.0
    assert vision_score('DIFFERENT') == 0.0
    assert vision_score('UNCERTAIN') == 0.5


def test_vision_score_converts_confidence():
    """vision_score should return confidence as 0.0-1.0 float."""
    assert vision_score(85) == 0.85
    assert vision_score(0) == 0.0
    assert vision_score(100) == 1.0


def test_vision_score_clamps():
    """vision_score clamps out-of-range values."""
    assert vision_score(150) == 1.0
    assert vision_score(-10) == 0.0


def test_vision_score_legacy_strings():
    """vision_score still handles legacy string results for cached comparisons."""
    assert vision_score('SAME') == 1.0
    assert vision_score('DIFFERENT') == 0.0
    assert vision_score('UNCERTAIN') == 0.5


def test_parse_vision_response_json():
    """parse_vision_response extracts confidence and verdict from JSON."""
    from lightroom_tagger.core.analyzer import parse_vision_response

    result = parse_vision_response('{"confidence": 85, "reasoning": "Same building"}')
    assert result['confidence'] == 85
    assert result['verdict'] == 'SAME'

    result = parse_vision_response('{"confidence": 30, "reasoning": "Different scene"}')
    assert result['confidence'] == 30
    assert result['verdict'] == 'DIFFERENT'

    result = parse_vision_response('{"confidence": 55, "reasoning": "Unclear"}')
    assert result['confidence'] == 55
    assert result['verdict'] == 'UNCERTAIN'


def test_parse_vision_response_fallback():
    """parse_vision_response falls back for non-JSON responses."""
    from lightroom_tagger.core.analyzer import parse_vision_response

    result = parse_vision_response('SAME')
    assert result['confidence'] == 100
    assert result['verdict'] == 'SAME'

    result = parse_vision_response('DIFFERENT')
    assert result['confidence'] == 0
    assert result['verdict'] == 'DIFFERENT'

    result = parse_vision_response('UNCERTAIN')
    assert result['confidence'] == 50
    assert result['verdict'] == 'UNCERTAIN'


def test_compare_with_vision_returns_dict():
    """Vision comparison returns dict with confidence and verdict."""
    with vision_compare_test_context(
        compare_result={"confidence": 85, "verdict": "SAME"},
    ) as (_registry, _client):
        result = compare_with_vision('/tmp/local.jpg', '/tmp/insta.jpg')

    assert isinstance(result, dict)
    assert result['confidence'] == 85
    assert result['verdict'] == 'SAME'


def test_compress_image_creates_temp_file():
    """Compress should create a temporary JPEG file."""
    # Create a test image
    from PIL import Image
    fd, test_path = tempfile.mkstemp(suffix='.png')
    os.close(fd)

    try:
        # Create a 2000x2000 PNG image
        img = Image.new('RGB', (2000, 2000), color='red')
        img.save(test_path, 'PNG')

        # Compress it
        compressed_path = compress_image(test_path, max_size=(500, 500), quality=80)

        # Verify it created a temp file
        assert compressed_path != test_path
        assert compressed_path.endswith('.jpg')
        assert os.path.exists(compressed_path)

        # Verify it was resized
        with Image.open(compressed_path) as compressed:
            assert compressed.width <= 500
            assert compressed.height <= 500

        # Cleanup
        if compressed_path != test_path and os.path.exists(compressed_path):
            os.unlink(compressed_path)
    finally:
        if os.path.exists(test_path):
            os.unlink(test_path)


def test_compress_image_silent_suppresses_prints(capsys):
    """silent=True must not emit the `` Compressed:`` stdout line."""
    from PIL import Image

    fd, test_path = tempfile.mkstemp(suffix='.png')
    os.close(fd)

    try:
        img = Image.new('RGB', (2000, 2000), color='red')
        img.save(test_path, 'PNG')

        compressed_path = compress_image(
            test_path, max_size=(500, 500), quality=80, silent=True,
        )
        assert compressed_path != test_path
        out = capsys.readouterr().out
        assert 'Compressed:' not in out

        if compressed_path != test_path and os.path.exists(compressed_path):
            os.unlink(compressed_path)
    finally:
        if os.path.exists(test_path):
            os.unlink(test_path)


def test_compress_image_handles_rgba():
    """Compress should convert RGBA to RGB."""
    from PIL import Image
    fd, test_path = tempfile.mkstemp(suffix='.png')
    os.close(fd)

    try:
        # Create an RGBA image
        img = Image.new('RGBA', (100, 100), color=(255, 0, 0, 128))
        img.save(test_path, 'PNG')

        compressed_path = compress_image(test_path)

        # Verify it saved as JPEG (RGB)
        with Image.open(compressed_path) as compressed:
            assert compressed.mode == 'RGB'

        # Cleanup
        if compressed_path != test_path and os.path.exists(compressed_path):
            os.unlink(compressed_path)
    finally:
        if os.path.exists(test_path):
            os.unlink(test_path)


def test_compare_with_vision_uses_compression():
    """Vision comparison should compress images before sending to model."""
    from PIL import Image

    # Create test images
    fd1, local_path = tempfile.mkstemp(suffix='.jpg')
    os.close(fd1)
    fd2, insta_path = tempfile.mkstemp(suffix='.jpg')
    os.close(fd2)

    try:
        # Create small test images
        img = Image.new('RGB', (100, 100), color='blue')
        img.save(local_path)
        img.save(insta_path)

        compressed_paths = []

        def track_compress(path):
            result = compress_image(path)
            compressed_paths.append(result)
            return result

        registry = fake_vision_registry(
            fake_compare_client(provider_id="ollama"),
            provider_id="ollama",
            model="vision-model",
        )
        with (
            patch(
                'lightroom_tagger.core.analyzer.vision_compare.compress_image',
                side_effect=track_compress,
            ),
            vision_compare_test_context(
                registry=registry,
                patch_compression=False,
            ),
        ):
            result = compare_with_vision(local_path, insta_path)

        # Should have compressed both images
        assert len(compressed_paths) == 2
        assert result['verdict'] == 'SAME'

    finally:
        if os.path.exists(local_path):
            os.unlink(local_path)
        if os.path.exists(insta_path):
            os.unlink(insta_path)


def test_compare_with_vision_cleans_up_temp_files():
    """Vision comparison should clean up all temporary files."""
    with vision_compare_test_context() as (_registry, _client):
        result = compare_with_vision('/tmp/local.jpg', '/tmp/insta.jpg')

    assert result['verdict'] == 'SAME'


def test_compare_with_vision_honors_vision_model_env(monkeypatch):
    """Vision comparison must use resolve_model so VISION_MODEL env is honoured."""
    monkeypatch.setenv("VISION_MODEL", "env-vision-model")

    registry = MagicMock(spec=ProviderRegistry)
    registry.defaults = {"vision_comparison": {"provider": "ollama", "model": "json-default"}}
    registry.fallback_order = ["ollama"]
    registry.list_providers.return_value = [{"id": "ollama", "name": "ollama", "available": True}]
    registry.list_models.return_value = [{"id": "env-vision-model", "vision": True, "source": "config"}]
    registry.get_retry_config.return_value = {
        "max_retries": 0,
        "backoff_seconds": [],
        "respect_retry_after": False,
    }
    client = fake_compare_client(
        provider_id="ollama",
        compare_result={"confidence": 80, "verdict": "SAME", "reasoning": "ok"},
    )
    registry.get_client.return_value = client

    with (
        patch(
            "lightroom_tagger.core.provider_resolution.ProviderRegistry",
            return_value=registry,
        ),
        patch(
            "lightroom_tagger.core.analyzer.vision_compare.resolve_model",
            wraps=resolve_model,
        ),
        patch(
            "lightroom_tagger.core.analyzer.vision_compare.compress_image",
            side_effect=lambda p: p,
        ),
        patch(
            "lightroom_tagger.core.analyzer.vision_compare.get_viewable_path_managed",
            side_effect=lambda p: (p, False),
        ),
        patch("os.path.exists", return_value=True),
        patch("lightroom_tagger.core.vision_client._encode_image", return_value="abc"),
    ):
        result = compare_with_vision(
            "/tmp/local.jpg",
            "/tmp/insta.jpg",
            provider_id="ollama",
            model=None,
        )

    assert result["verdict"] == "SAME"
    assert result["_model"] == "env-vision-model"


def test_vision_config_environment_variables():
    """Vision compression should respect environment variables."""
    import lightroom_tagger.core.analyzer as analyzer_module
    import lightroom_tagger.core.analyzer.image_prep as image_prep_module

    # Test default values
    assert analyzer_module.VISION_MAX_DIMENSION == 1024
    assert analyzer_module.VISION_COMPRESS_QUALITY == 80

    # Test custom values via env vars
    original_dim = os.environ.get('VISION_MAX_DIMENSION')
    original_qual = os.environ.get('VISION_COMPRESS_QUALITY')

    try:
        os.environ['VISION_MAX_DIMENSION'] = '2048'
        os.environ['VISION_COMPRESS_QUALITY'] = '90'

        # Constants live in ``image_prep`` — reload submodule chain, then the barrel.
        importlib.reload(image_prep_module)
        importlib.reload(analyzer_module)

        assert analyzer_module.VISION_MAX_DIMENSION == 2048
        assert analyzer_module.VISION_COMPRESS_QUALITY == 90
    finally:
        # Restore original values
        if original_dim is not None:
            os.environ['VISION_MAX_DIMENSION'] = original_dim
        else:
            os.environ.pop('VISION_MAX_DIMENSION', None)

        if original_qual is not None:
            os.environ['VISION_COMPRESS_QUALITY'] = original_qual
        else:
            os.environ.pop('VISION_COMPRESS_QUALITY', None)

        # Reload again to restore
        importlib.reload(image_prep_module)
        importlib.reload(analyzer_module)


def test_build_description_prompt_returns_string():
    from lightroom_tagger.core.analyzer import build_description_prompt
    prompt = build_description_prompt()
    assert isinstance(prompt, str)
    assert len(prompt) > 100
    assert 'composition' in prompt.lower()
    assert 'JSON' in prompt
    assert '"perspectives"' not in prompt
    assert '"score"' not in prompt


def test_parse_description_response_valid_json():
    from lightroom_tagger.core.analyzer import parse_description_response
    raw = json.dumps({
        'summary': 'A street photo',
        'composition': {'layers': ['fg', 'bg'], 'techniques': ['rule_of_thirds']},
        'perspectives': {
            'street': {'analysis': 'Strong geometry', 'score': 7},
            'documentary': {'analysis': 'Fair story', 'score': 5},
            'publisher': {'analysis': 'Editorial use', 'score': 6},
        },
        'technical': {'dominant_colors': ['#000'], 'mood': 'calm', 'lighting': 'natural'},
        'subjects': ['person'],
        'best_perspective': 'street',
    })
    result = parse_description_response(raw)
    assert result['summary'] == 'A street photo'
    assert result['perspectives']['street']['score'] == 7
    assert 'person' in result['subjects']


def test_parse_description_response_extracts_json_from_markdown():
    from lightroom_tagger.core.analyzer import parse_description_response
    raw = (
        'Here is the analysis:\n```json\n'
        '{"summary": "A sunset", "composition": {}, "perspectives": {}, '
        '"technical": {}, "subjects": [], "best_perspective": "street"}\n'
        '```\n'
    )
    result = parse_description_response(raw)
    assert result['summary'] == 'A sunset'


def test_parse_description_response_handles_garbage():
    from lightroom_tagger.core.analyzer import parse_description_response
    result = parse_description_response('This is not JSON at all')
    assert result['summary'] == ''
    assert 'best_perspective' not in result


def test_get_description_model_prefers_env_override():
    from lightroom_tagger.core.analyzer import get_description_model
    with patch.dict(os.environ, {'DESCRIPTION_VISION_MODEL': 'llava:13b', 'VISION_MODEL': 'gemma3:27b'}):
        assert get_description_model() == 'llava:13b'


def test_get_description_model_falls_back_to_vision_model_env():
    from lightroom_tagger.core.analyzer import get_description_model
    with patch.dict(os.environ, {'VISION_MODEL': 'gemma3:27b'}):
        os.environ.pop('DESCRIPTION_VISION_MODEL', None)
        assert get_description_model() == 'gemma3:27b'


@patch("time.sleep")
def test_cancel_mid_backoff_short_circuits_sequential_compare(mock_sleep):
    """Sequential compare path honours cancel during retry backoff."""
    import pytest
    import openai as openai_sdk
    from lightroom_tagger.core.retry import CancelledRetryError

    flag = {"cancel": False}

    def create_side_effect(**_kwargs):
        flag["cancel"] = True
        raise openai_sdk.RateLimitError("429", response=MagicMock(), body=None)

    client = fake_compare_client(provider_id="ollama", create_side_effect=create_side_effect)
    registry = fake_vision_registry(client, provider_id="ollama", model="gemma3:27b")
    registry.get_retry_config.return_value = {
        "max_retries": 2,
        "backoff_seconds": [5],
        "respect_retry_after": False,
    }

    with (
        patch(
            "lightroom_tagger.core.analyzer.vision_compare.resolve_model",
            return_value=ResolvedModel("ollama", "gemma3:27b", registry),
        ),
        patch(
            "lightroom_tagger.core.analyzer.get_viewable_path_managed",
            side_effect=lambda p: (p, False),
        ),
        patch(
            "lightroom_tagger.core.analyzer.compress_image",
            side_effect=lambda p: p,
        ),
        patch("os.path.exists", return_value=True),
        patch("lightroom_tagger.core.vision_client._encode_image", return_value="abc"),
    ):
        with pytest.raises(CancelledRetryError):
            compare_with_vision(
                "/tmp/local.jpg",
                "/tmp/insta.jpg",
                cancel_check=lambda: flag["cancel"],
            )

