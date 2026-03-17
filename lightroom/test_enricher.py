import pytest
from unittest.mock import Mock, patch
from lightroom.enricher import enrich_catalog_images

def test_enrich_skips_already_analyzed():
    """Should skip images that already have phash."""
    mock_db = Mock()
    mock_db.table.return_value.search.return_value = []  # No images needing analysis
    
    with patch('lightroom.enricher.get_catalog_images_needing_analysis', return_value=[]):
        result = enrich_catalog_images(mock_db, limit=10)
    
    assert result['processed'] == 0
    assert result['skipped'] == 0

def test_enrich_processes_images():
    """Should analyze images without phash."""
    mock_db = Mock()
    mock_db.table.return_value.search.return_value = [
        {'key': '2024-01-15_sunset.jpg', 'filepath': '/tmp/test.jpg'}
    ]
    
    with patch('lightroom.enricher.get_catalog_images_needing_analysis', return_value=[
        {'key': '2024-01-15_sunset.jpg', 'filepath': '/tmp/test.jpg'}
    ]), \
    patch('lightroom.enricher.analyze_image', return_value={
        'phash': 'a1b2c3d4e5f6g7h8',
        'exif': {'camera': 'Canon'},
        'description': 'Sunset'
    }) as analyze_mock, \
    patch('lightroom.enricher.store_catalog_image') as store_mock:
        
        result = enrich_catalog_images(mock_db)
    
    analyze_mock.assert_called_once()
    store_mock.assert_called_once()
    assert result['processed'] == 1
