import pytest
from unittest.mock import Mock, patch, MagicMock
from instagram.crawler import crawl_and_analyze

def test_crawl_analyzes_fetched_images():
    """Should analyze each fetched Instagram image."""
    mock_db = Mock()
    
    mock_post = Mock()
    mock_post.post_url = 'https://instagram.com/p/abc123'
    mock_post.index = 0
    
    with patch('instagram.scraper.crawl_instagram', return_value=([mock_post], {'https://instagram.com/p/abc123': ['/tmp/insta1.jpg']})), \
         patch('instagram.crawler.analyze_image', return_value={'phash': 'abc', 'exif': {}, 'description': 'test'}) as analyze_mock, \
         patch('instagram.crawler.store_instagram_image') as store_mock:
        
        result = crawl_and_analyze(mock_db, 'testuser', '/tmp', limit=10)
    
    analyze_mock.assert_called()
    store_mock.assert_called()
    assert result['processed'] == 1
