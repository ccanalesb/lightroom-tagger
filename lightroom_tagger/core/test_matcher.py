import pytest
from unittest.mock import Mock, patch
from lightroom_tagger.core.matcher import match_image, match_batch, score_candidates_with_vision


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
    
    with patch('core.matcher.query_by_exif', return_value=[catalog_candidates[0]]), \
         patch('core.matcher.score_candidates_with_vision', return_value=[{'catalog_key': 'cat1', 'total_score': 0.9}]):
        
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
    
    with patch('core.matcher.match_image', return_value=[{'catalog_key': 'cat1'}]):
        result = match_batch(mock_db, insta_images, threshold=0.7)
    
    assert result['total_matches'] == 2


def test_score_candidates_includes_vision():
    """Should include vision score when comparing."""
    insta_image = {
        'key': 'insta_test',
        'image_hash': 'a1b2c3d4e5f6g7h8',
        'description': 'sunset over bay',
        'local_path': '/tmp/insta.jpg'
    }
    
    candidates = [
        {'key': 'cat1', 'image_hash': 'a1b2c3d4e5f6g7h8', 'description': 'sunset', 'local_path': '/tmp/local1.jpg'},
    ]
    
    with patch('core.analyzer.compare_with_vision', return_value='SAME') as vision_mock:
        results = score_candidates_with_vision(
            insta_image, candidates,
            phash_weight=0.4, desc_weight=0.3, vision_weight=0.3
        )
    
    assert len(results) == 1
    assert results[0]['vision_result'] == 'SAME'
    assert results[0]['vision_score'] == 1.0
