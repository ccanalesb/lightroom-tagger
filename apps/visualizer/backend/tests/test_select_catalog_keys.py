"""Tests for :func:`jobs.handlers.common._select_catalog_keys` ordering."""
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
            PRIMARY KEY (image_key, image_type)
        );
        """
    )
    return conn


def _insert(
    conn,
    key,
    *,
    date_taken='2024-06-15',
    rating=0,
    filepath=None,
    described=False,
):
    if filepath is None:
        filepath = f'/photos/{key}.jpg'
    conn.execute(
        "INSERT INTO images (key, filepath, date_taken, rating) VALUES (?, ?, ?, ?)",
        (key, filepath, date_taken, rating),
    )
    if described:
        conn.execute(
            "INSERT INTO image_descriptions (image_key, image_type) VALUES (?, 'catalog')",
            (key,),
        )


def _call(conn, **kwargs):
    from jobs.handlers.common import _select_catalog_keys

    defaults = {
        'months': None,
        'year': None,
        'min_rating': None,
        'undescribed_only': False,
    }
    defaults.update(kwargs)
    return _select_catalog_keys(conn, **defaults)


class TestCatalogKeyOrdering:
    def test_newest_first_among_dated_rows(self):
        conn = _make_db()
        _insert(conn, 'key-old', date_taken='2024-01-10')
        _insert(conn, 'key-new', date_taken='2024-06-20')
        _insert(conn, 'key-mid', date_taken='2024-03-15')

        keys = [k for k, _ in _call(conn)]
        assert keys == ['key-new', 'key-mid', 'key-old']

    def test_undated_rows_first(self):
        conn = _make_db()
        _insert(conn, 'dated', date_taken='2024-06-20')
        conn.execute(
            "INSERT INTO images (key, filepath, date_taken, rating) "
            "VALUES ('undated', '/photos/undated.jpg', NULL, 0)"
        )

        keys = [k for k, _ in _call(conn)]
        assert keys[0] == 'undated'
        assert keys[1:] == ['dated']

    def test_equal_date_tiebreaker_key_desc(self):
        conn = _make_db()
        _insert(conn, 'aaa-same', date_taken='2024-05-01')
        _insert(conn, 'zzz-same', date_taken='2024-05-01')

        keys = [k for k, _ in _call(conn)]
        assert keys == ['zzz-same', 'aaa-same']

    def test_ordering_under_months_filter(self):
        from datetime import datetime, timedelta

        conn = _make_db()
        recent = datetime.now().strftime('%Y-%m-%d')
        older = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
        stale = (datetime.now() - timedelta(days=400)).strftime('%Y-%m-%d')
        _insert(conn, 'in-window-new', date_taken=recent)
        _insert(conn, 'in-window-old', date_taken=older)
        _insert(conn, 'out-window', date_taken=stale)

        keys = [k for k, _ in _call(conn, months=12)]
        assert keys == ['in-window-new', 'in-window-old']

    def test_ordering_under_year_filter(self):
        conn = _make_db()
        _insert(conn, 'y2024-b', date_taken='2024-03-01')
        _insert(conn, 'y2024-a', date_taken='2024-08-01')
        _insert(conn, 'y2023', date_taken='2023-12-31')

        keys = [k for k, _ in _call(conn, year='2024')]
        assert keys == ['y2024-a', 'y2024-b']

    def test_ordering_under_min_rating_filter(self):
        conn = _make_db()
        _insert(conn, 'low-rated-new', date_taken='2024-06-20', rating=1)
        _insert(conn, 'high-rated-old', date_taken='2024-01-01', rating=4)
        _insert(conn, 'high-rated-new', date_taken='2024-06-15', rating=5)

        keys = [k for k, _ in _call(conn, min_rating=3)]
        assert keys == ['high-rated-new', 'high-rated-old']

    def test_undescribed_only_preserves_order(self):
        conn = _make_db()
        _insert(conn, 'undesc-new', date_taken='2024-06-20')
        _insert(conn, 'undesc-old', date_taken='2024-01-01')
        _insert(conn, 'described', date_taken='2024-08-01', described=True)

        keys = [k for k, _ in _call(conn, undescribed_only=True)]
        assert keys == ['undesc-new', 'undesc-old']
