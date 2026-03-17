import pytest
from unittest.mock import Mock, patch, MagicMock
from core.analyzer import analyze_image, describe_image

def test_analyze_image_returns_all_signals():
    """Analyzer should return phash, exif, and description."""
    with patch('core.analyzer.compute_phash', return_value='a1b2c3d4e5f6g7h8'), \
         patch('core.analyzer.extract_exif', return_value={'camera': 'Canon EOS R5'}), \
         patch('core.analyzer.describe_image', return_value='A sunset photo'):
        
        result = analyze_image('/fake/path.jpg')
    
    assert result['phash'] == 'a1b2c3d4e5f6g7h8'
    assert result['exif']['camera'] == 'Canon EOS R5'
    assert result['description'] == 'A sunset photo'

def test_describe_image_uses_configured_agent():
    """Should use local or external agent based on config."""
    with patch('core.analyzer.run_local_agent', return_value='local desc') as local_mock, \
         patch('core.analyzer.run_external_agent', return_value='external desc') as ext_mock:
        
        # Test local agent
        describe_image('/fake/path.jpg', agent_type='local')
        local_mock.assert_called_once()
        
        # Test external agent
        describe_image('/fake/path.jpg', agent_type='external')
        ext_mock.assert_called_once()
