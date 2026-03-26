"""Database utilities for Flask routes."""
import os
import sqlite3
from functools import wraps

from config import LIBRARY_DB
from constants.errors import ERROR_DB_NOT_FOUND
from flask import jsonify


class DatabaseError(Exception):
    pass


def _dict_factory(cursor, row):
    fields = [column[0] for column in cursor.description]
    return dict(zip(fields, row))


def _make_json_response(data, status_code):
    try:
        return jsonify(data), status_code
    except RuntimeError:
        class MockResponse:
            def __init__(self, data_dict):
                self._json = data_dict
            @property
            def json(self):
                return self._json
        return MockResponse(data), status_code


def with_db(handler_func=None, *, require_exists=True):
    """Decorator that provides SQLite database connection to route handlers."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            db_path = LIBRARY_DB

            if require_exists and not os.path.exists(db_path):
                return _make_json_response({'error': ERROR_DB_NOT_FOUND}, 404)

            db = None
            try:
                db = sqlite3.connect(db_path)
                db.row_factory = _dict_factory
                db.execute("PRAGMA journal_mode=WAL")
                db.execute("PRAGMA busy_timeout=5000")
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
