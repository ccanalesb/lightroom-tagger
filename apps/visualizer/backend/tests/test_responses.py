# apps/visualizer/backend/tests/test_responses.py
import pytest
from utils.responses import error_not_found, error_bad_request, error_server_error, success_paginated


class TestErrorResponses:
    """Tests for error response utilities."""

    def test_error_not_found_image(self):
        """Test image not found error."""
        response, status = error_not_found('image')
        assert status == 404
        assert 'Image not found' in response.json['error']

    def test_error_not_found_file(self):
        """Test file not found error."""
        response, status = error_not_found('file')
        assert status == 404
        assert 'Image file not found' in response.json['error']

    def test_error_not_found_database(self):
        """Test database not found error."""
        response, status = error_not_found('database')
        assert status == 404
        assert 'Library database not found' in response.json['error']

    def test_error_not_found_default(self):
        """Test generic not found error."""
        response, status = error_not_found('unknown')
        assert status == 404
        assert 'unknown not found' in response.json['error']

    def test_error_bad_request(self):
        """Test bad request error."""
        response, status = error_bad_request('Custom error message')
        assert status == 400
        assert response.json['error'] == 'Custom error message'

    def test_error_server_error_default(self):
        """Test server error with default message."""
        response, status = error_server_error()
        assert status == 500
        assert response.json['error'] == 'Internal server error'

    def test_error_server_error_custom(self):
        """Test server error with custom message."""
        response, status = error_server_error('Custom server error')
        assert status == 500
        assert response.json['error'] == 'Custom server error'


class TestSuccessResponses:
    """Tests for success response utilities."""

    def test_success_paginated(self):
        """Test paginated success response."""
        data = [{'id': 1}, {'id': 2}]
        response, status = success_paginated(data, 10, 0, 5)

        assert status == 200
        assert response.json['total'] == 10
        assert response.json['data'] == data
        assert response.json['pagination']['has_more'] == True
        assert response.json['pagination']['current_page'] == 1
        assert response.json['pagination']['total_pages'] == 2

    def test_success_paginated_has_more_false(self):
        """Test paginated response when has_more is false."""
        data = [{'id': 1}, {'id': 2}]
        response, status = success_paginated(data, 10, 5, 5)

        assert status == 200
        assert response.json['pagination']['has_more'] == False
        assert response.json['pagination']['current_page'] == 2
