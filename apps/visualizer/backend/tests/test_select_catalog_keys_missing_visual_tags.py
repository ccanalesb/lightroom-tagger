"""Tests for :func:`jobs.handlers.analyze._select_catalog_keys_missing_visual_tags` ordering."""
from __future__ import annotations

import sqlite3


def _make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE images (
            key TEXT PRIMARY KEY,
            filepath TEXT,
            date_taken TEXT,
            rating INTEGER
        );
        CREATE TABLE image_descriptions (
            image_key TEXT,
            image_type TEXT,
            dominant_colors TEXT,
            PRIMARY KEY (image_key, image_type)
        );
        """
    )
    return conn


def _insert(conn, key, *, date_taken='2024-06-15', rating=0, missing_visual=True):
    conn.execute(
        "INSERT INTO images (key, filepath, date_taken, rating) VALUES (?, ?, ?, ?)",
        (key, f'/photos/{key}.jpg', date_taken, rating),
    )
    if missing_visual:
        conn.execute(
            "INSERT INTO image_descriptions (image_key, image_type, dominant_colors) "
            "VALUES (?, 'catalog', NULL)",
            (key,),
        )
    else:
        conn.execute(
            "INSERT INTO image_descriptions (image_key, image_type, dominant_colors) "
            "VALUES (?, 'catalog', ?)",
            (key, '["#000"]'),
        )


def _call(conn, **kwargs):
    from jobs.handlers.analyze import _select_catalog_keys_missing_visual_tags

    defaults = {
        'months': None,
        'year': None,
        'min_rating': None,
    }
    defaults.update(kwargs)
    return _select_catalog_keys_missing_visual_tags(conn, **defaults)


class TestMissingVisualTagOrdering:
    def test_newest_first_among_dated_rows(self):
        conn = _make_db()
        _insert(conn, 'old', date_taken='2024-01-10')
        _insert(conn, 'new', date_taken='2024-06-20')

        keys = [k for k, _ in _call(conn)]
        assert keys == ['new', 'old']

    def test_undated_rows_first(self):
        conn = _make_db()
        _insert(conn, 'dated', date_taken='2024-06-20')
        conn.execute(
            "INSERT INTO images (key, filepath, date_taken, rating) "
            "VALUES ('undated', '/photos/undated.jpg', NULL, 0)"
        )
        conn.execute(
            "INSERT INTO image_descriptions (image_key, image_type, dominant_colors) "
            "VALUES ('undated', 'catalog', NULL)"
        )

        keys = [k for k, _ in _call(conn)]
        assert keys[0] == 'undated'
        assert keys[1:] == ['dated']

    def test_equal_date_tiebreaker_key_desc(self):
        conn = _make_db()
        _insert(conn, 'aaa', date_taken='2024-05-01')
        _insert(conn, 'zzz', date_taken='2024-05-01')

        keys = [k for k, _ in _call(conn)]
        assert keys == ['zzz', 'aaa']

    def test_ordering_under_filters(self):
        conn = _make_db()
        _insert(conn, 'in-new', date_taken='2024-06-20', rating=4)
        _insert(conn, 'in-old', date_taken='2024-06-01', rating=5)
        _insert(conn, 'low-rating', date_taken='2024-08-01', rating=1)
        _insert(conn, 'has-colors', date_taken='2024-09-01', missing_visual=False)

        keys = [k for k, _ in _call(conn, year='2024', min_rating=3)]
        assert keys == ['in-new', 'in-old']
