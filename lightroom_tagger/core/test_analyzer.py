import importlib
import json
import os
import tempfile
from unittest.mock import patch

from lightroom_tagger.core.analyzer import (
    analyze_image,
    compare_with_vision,
    compress_image,
    describe_image,
    vision_score,
)


def test_analyze_image_returns_all_signals():
    """Analyzer should return phash, exif, and description."""
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
         patch('lightroom_tagger.core.analyzer.describe_image', return_value=mock_desc):

        result = analyze_image('/fake/path.jpg')

    assert result['phash'] == 'a1b2c3d4e5f6g7h8'
    assert result['exif']['camera'] == 'Canon EOS R5'
    assert result['description'] == 'A sunset photo'
    assert result['structured_description'] == mock_desc


def test_describe_image_uses_configured_agent():
    """Should use local or external agent based on config."""
    with patch('lightroom_tagger.core.analyzer.run_local_agent', return_value='local desc') as local_mock, \
         patch('lightroom_tagger.core.analyzer.run_external_agent', return_value='external desc') as ext_mock:

        # Test local agent
        describe_image('/fake/path.jpg', agent_type='local')
        local_mock.assert_called_once()

        # Test external agent
        describe_image('/fake/path.jpg', agent_type='external')
        ext_mock.assert_called_once()


def test_compare_with_vision_returns_result():
    """Vision comparison should return SAME, DIFFERENT, or UNCERTAIN."""
    with patch('lightroom_tagger.core.analyzer.compress_image', side_effect=lambda x: x), \
         patch('lightroom_tagger.core.analyzer.get_viewable_path', side_effect=lambda x: x), \
         patch('lightroom_tagger.core.analyzer.run_vision_ollama', return_value='SAME'):

        result = compare_with_vision('/tmp/local.jpg', '/tmp/insta.jpg')

    assert result in ['SAME', 'DIFFERENT', 'UNCERTAIN']
    assert result == 'SAME'


def test_vision_score_converts_correctly():
    """Vision score should convert result to float."""

    assert vision_score('SAME') == 1.0
    assert vision_score('DIFFERENT') == 0.0
    assert vision_score('UNCERTAIN') == 0.5


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

        with patch('lightroom_tagger.core.analyzer.get_viewable_path', side_effect=lambda x: x), \
             patch('lightroom_tagger.core.analyzer.compress_image', side_effect=track_compress), \
             patch('lightroom_tagger.core.analyzer.run_vision_ollama', return_value='SAME'):

            result = compare_with_vision(local_path, insta_path)

        # Should have compressed both images
        assert len(compressed_paths) == 2
        assert result == 'SAME'

    finally:
        if os.path.exists(local_path):
            os.unlink(local_path)
        if os.path.exists(insta_path):
            os.unlink(insta_path)


def test_compare_with_vision_cleans_up_temp_files():
    """Vision comparison should clean up all temporary files."""
    with patch('lightroom_tagger.core.analyzer.compress_image', side_effect=lambda x: x), \
         patch('lightroom_tagger.core.analyzer.get_viewable_path', side_effect=lambda x: x), \
         patch('lightroom_tagger.core.analyzer.run_vision_ollama', return_value='SAME'):

        # Track temp files in a real scenario
        # This test verifies the cleanup logic runs without error
        result = compare_with_vision('/tmp/local.jpg', '/tmp/insta.jpg')

        assert result == 'SAME'


def test_vision_config_environment_variables():
    """Vision compression should respect environment variables."""
    import lightroom_tagger.core.analyzer as analyzer_module

    # Test default values
    assert analyzer_module.VISION_MAX_DIMENSION == 1024
    assert analyzer_module.VISION_COMPRESS_QUALITY == 80

    # Test custom values via env vars
    original_dim = os.environ.get('VISION_MAX_DIMENSION')
    original_qual = os.environ.get('VISION_COMPRESS_QUALITY')

    try:
        os.environ['VISION_MAX_DIMENSION'] = '2048'
        os.environ['VISION_COMPRESS_QUALITY'] = '90'

        # Reimport to pick up new values
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
        importlib.reload(analyzer_module)


def test_build_description_prompt_returns_string():
    from lightroom_tagger.core.analyzer import build_description_prompt
    prompt = build_description_prompt()
    assert isinstance(prompt, str)
    assert len(prompt) > 100
    assert 'street photographer' in prompt.lower()
    assert 'documentary' in prompt.lower()
    assert 'publisher' in prompt.lower()
    assert 'composition' in prompt.lower()
    assert 'JSON' in prompt


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
    assert result['best_perspective'] == ''


def test_run_local_agent_calls_ollama():
    from unittest.mock import MagicMock
    mock_response = MagicMock()
    mock_response.message.content = json.dumps({
        'summary': 'test',
        'composition': {},
        'perspectives': {},
        'technical': {},
        'subjects': [],
        'best_perspective': 'street',
    })
    with patch('lightroom_tagger.core.analyzer.ollama') as mock_ollama:
        mock_ollama.chat.return_value = mock_response
        from lightroom_tagger.core.analyzer import run_local_agent
        run_local_agent('/fake/image.jpg')
    mock_ollama.chat.assert_called_once()
    call_kwargs = mock_ollama.chat.call_args
    assert call_kwargs[1]['model'] or call_kwargs[0][0]
