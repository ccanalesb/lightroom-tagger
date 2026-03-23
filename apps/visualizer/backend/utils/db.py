"""Database utilities for Flask routes."""
from functools import wraps
from flask import jsonify, Flask
from tinydb import TinyDB
import os
import json
from config import LIBRARY_DB
from constants.errors import ERROR_DB_NOT_FOUND


class DatabaseError(Exception):
    """Custom exception for database errors."""
    pass


def _make_json_response(data, status_code):
    """Create a JSON response that works with or without Flask app context."""
    try:
        return jsonify(data), status_code
    except RuntimeError:
        # Outside Flask context, return tuple for testing
        class MockResponse:
            def __init__(self, data_dict):
                self._json = data_dict
            @property
            def json(self):
                return self._json
        return MockResponse(data), status_code


def with_db(handler_func=None, *, require_exists=True):
    """Decorator that provides database connection to route handlers.

    Usage:
    @with_db
    def my_route(db):
        # db is TinyDB instance, already validated
        pass

    @with_db(require_exists=False)
    def optional_route(db):
        # db may not exist
        pass
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            db_path = LIBRARY_DB

            if require_exists and not os.path.exists(db_path):
                return _make_json_response({'error': ERROR_DB_NOT_FOUND}, 404)

            db = None
            try:
                db = TinyDB(db_path)
                return f(db, *args, **kwargs)
            except DatabaseError as e:
                return _make_json_response({'error': str(e)}, 500)
            except Exception as e:
                return _make_json_response({'error': str(e)}, 500)
            finally:
                if db:
                    db.close()
        return wrapper

    if handler_func is not None:
        return decorator(handler_func)
    return decorator
