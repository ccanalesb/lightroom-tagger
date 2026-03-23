"""Standardized response utilities for Flask routes."""
from flask import jsonify
from constants.errors import (
    ERROR_IMAGE_NOT_FOUND,
    ERROR_IMAGE_FILE_NOT_FOUND,
    ERROR_DB_NOT_FOUND,
    ERROR_INTERNAL_SERVER,
)


class _MockResponse:
    """Mock response for testing outside Flask context."""
    def __init__(self, data_dict):
        self._json = data_dict

    @property
    def json(self):
        return self._json


def _make_json_response(data, status_code):
    """Create a JSON response that works with or without Flask app context."""
    try:
        return jsonify(data), status_code
    except RuntimeError:
        # Outside Flask context, return tuple for testing
        return _MockResponse(data), status_code


def error_not_found(resource_type='resource'):
    """Return 404 error for resource not found."""
    messages = {
        'image': ERROR_IMAGE_NOT_FOUND,
        'media': ERROR_IMAGE_NOT_FOUND,
        'database': ERROR_DB_NOT_FOUND,
        'file': ERROR_IMAGE_FILE_NOT_FOUND,
    }
    return _make_json_response(
        {'error': messages.get(resource_type, f'{resource_type} not found')},
        404
    )


def error_bad_request(message='Invalid request'):
    """Return 400 error."""
    return _make_json_response({'error': message}, 400)


def error_server_error(message=None):
    """Return 500 error."""
    return _make_json_response(
        {'error': message or ERROR_INTERNAL_SERVER},
        500
    )


def success_paginated(data, total, offset, limit):
    """Return standardized paginated response."""
    has_more = (offset + limit) < total
    current_page = (offset // limit) + 1
    total_pages = (total + limit - 1) // limit

    return _make_json_response({
        'total': total,
        'data': data,
        'pagination': {
            'offset': offset,
            'limit': limit,
            'current_page': current_page,
            'total_pages': total_pages,
            'has_more': has_more,
        }
    }, 200)
