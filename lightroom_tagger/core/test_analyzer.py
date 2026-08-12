import importlib
import json
import os
import tempfile
from unittest.mock import patch

from lightroom_tagger.core.analyzer import (
    compress_image,
    run_description_vision_op,
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


def test_compress_image_creates_temp_file():
    """Compress should create a temporary JPEG file."""
    from PIL import Image
    fd, test_path = tempfile.mkstemp(suffix='.png')
    os.close(fd)

    try:
        img = Image.new('RGB', (2000, 2000), color='red')
        img.save(test_path, 'PNG')

        compressed_path = compress_image(test_path, max_size=(500, 500), quality=80)

        assert compressed_path != test_path
        assert compressed_path.endswith('.jpg')
        assert os.path.exists(compressed_path)

        with Image.open(compressed_path) as compressed:
            assert compressed.width <= 500
            assert compressed.height <= 500

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
        img = Image.new('RGBA', (100, 100), color=(255, 0, 0, 128))
        img.save(test_path, 'PNG')

        compressed_path = compress_image(test_path)

        with Image.open(compressed_path) as compressed:
            assert compressed.mode == 'RGB'

        if compressed_path != test_path and os.path.exists(compressed_path):
            os.unlink(compressed_path)
    finally:
        if os.path.exists(test_path):
            os.unlink(test_path)


def test_vision_config_environment_variables():
    """Vision compression should respect environment variables."""
    import lightroom_tagger.core.analyzer as analyzer_module
    import lightroom_tagger.core.analyzer.image_prep as image_prep_module

    assert analyzer_module.VISION_MAX_DIMENSION == 1024
    assert analyzer_module.VISION_COMPRESS_QUALITY == 80

    original_dim = os.environ.get('VISION_MAX_DIMENSION')
    original_qual = os.environ.get('VISION_COMPRESS_QUALITY')

    try:
        os.environ['VISION_MAX_DIMENSION'] = '2048'
        os.environ['VISION_COMPRESS_QUALITY'] = '90'

        importlib.reload(image_prep_module)
        importlib.reload(analyzer_module)

        assert analyzer_module.VISION_MAX_DIMENSION == 2048
        assert analyzer_module.VISION_COMPRESS_QUALITY == 90
    finally:
        if original_dim is not None:
            os.environ['VISION_MAX_DIMENSION'] = original_dim
        else:
            os.environ.pop('VISION_MAX_DIMENSION', None)

        if original_qual is not None:
            os.environ['VISION_COMPRESS_QUALITY'] = original_qual
        else:
            os.environ.pop('VISION_COMPRESS_QUALITY', None)

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
