"""Tests for :func:`jobs.handlers._select_instagram_keys`.

Motivation: historical Instagram dump imports left ``created_at`` NULL when
``posts_1.json`` had no entry for a given media file (most commonly for older
rolls). The previous SQL filtered purely on ``created_at``, silently dropping
those rows from any date-windowed describe/score/analyze job. The selector now
falls back to ``date_folder`` ("YYYYMM") so the same media becomes selectable.

These tests pin down that fallback using a real in-memory SQLite database
(rather than mocks) so the actual SQL expression — including date() arithmetic
— is exercised end-to-end.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

import pytest


def _make_db() -> sqlite3.Connection:
    """Minimal schema needed by ``_select_instagram_keys``.

    We only build the two tables the selector touches; the rest of the
    Instagram / catalog schema is irrelevant for these tests.

    ``file_path`` is included because the selector applies an extension-based
    video filter (``_INSTAGRAM_NOT_VIDEO_SQL``) on ``m.file_path``.
    """
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE instagram_dump_media (
            media_key TEXT PRIMARY KEY,
            file_path TEXT,
            date_folder TEXT,
            created_at TEXT
        );
        CREATE TABLE image_descriptions (
            image_key TEXT,
            image_type TEXT,
            PRIMARY KEY (image_key, image_type)
        );
        """
    )
    return conn


def _insert(conn, key, *, created_at=None, date_folder=None, file_path=None):
    """Insert a media row.

    ``file_path`` defaults to ``"<key>.jpg"`` so the video-extension filter
    keeps the row visible. Tests that exercise the video filter pass an
    explicit value (e.g. ``"clip.mp4"``).
    """
    if file_path is None:
        file_path = f'{key}.jpg'
    conn.execute(
        "INSERT INTO instagram_dump_media (media_key, file_path, date_folder, created_at) "
        "VALUES (?, ?, ?, ?)",
        (key, file_path, date_folder, created_at),
    )


def _call(conn, *, months=None, year=None, undescribed_only=False):
    from jobs.handlers.common import _select_instagram_keys

    return {
        key
        for key, kind in _select_instagram_keys(
            conn,
            months=months,
            year=year,
            undescribed_only=undescribed_only,
        )
    }


def _call_ordered(conn, *, months=None, year=None, undescribed_only=False):
    from jobs.handlers.common import _select_instagram_keys

    return [
        key
        for key, kind in _select_instagram_keys(
            conn,
            months=months,
            year=year,
            undescribed_only=undescribed_only,
        )
    ]


class TestCreatedAtFallback:
    """Verify that NULL/empty created_at rows are rescued via date_folder."""

    def test_missing_created_at_is_visible_when_date_folder_in_window(self):
        """A row with NULL created_at but a recent date_folder should match
        a months-window that covers that folder's month."""
        conn = _make_db()
        current_month = datetime.now().strftime('%Y%m')
        _insert(conn, 'recent/no-created-at', date_folder=current_month, created_at=None)

        assert _call(conn, months=3) == {'recent/no-created-at'}

    def test_missing_created_at_with_empty_string_also_fallbacks(self):
        """Some legacy rows store '' instead of NULL; COALESCE + NULLIF should
        treat both identically."""
        conn = _make_db()
        current_month = datetime.now().strftime('%Y%m')
        _insert(conn, 'empty/created-at', date_folder=current_month, created_at='')

        assert _call(conn, months=3) == {'empty/created-at'}

    def test_old_date_folder_is_excluded_by_months_window(self):
        """Fallback must not silently widen the window: a 3-year-old
        date_folder should be rejected by a 12-month filter."""
        conn = _make_db()
        three_years_ago = (datetime.now() - timedelta(days=365 * 3)).strftime('%Y%m')
        _insert(conn, 'old/folder', date_folder=three_years_ago, created_at=None)

        assert _call(conn, months=12) == set()

    def test_unparseable_date_folder_is_excluded(self):
        """A non-YYYYMM folder ("other", "unknown") has no derivable date and
        must not sneak through the filter."""
        conn = _make_db()
        _insert(conn, 'other/bad-folder', date_folder='other', created_at=None)

        assert _call(conn, months=12) == set()

    def test_year_filter_honors_date_folder_fallback(self):
        """The year branch must also see the date_folder fallback."""
        conn = _make_db()
        _insert(conn, 'y/2024-a', date_folder='202403', created_at=None)
        _insert(conn, 'y/2023-b', date_folder='202305', created_at=None)

        assert _call(conn, year='2024') == {'y/2024-a'}

    def test_created_at_wins_over_date_folder_when_present(self):
        """If created_at exists, it must be authoritative — date_folder only
        fills in when created_at is NULL/empty."""
        conn = _make_db()
        # created_at says 2022 (outside window) but date_folder says current
        # month; created_at must win, keeping the row excluded from a 6-month
        # filter.
        _insert(
            conn,
            'conflict/row',
            date_folder=datetime.now().strftime('%Y%m'),
            created_at='2022-01-15T00:00:00',
        )

        assert _call(conn, months=6) == set()


class TestUndescribedOnlyBranch:
    """The same fallback must work under ``undescribed_only=True`` (the path
    used by batch_describe / batch_analyze). This guards against divergence
    between the two SQL templates."""

    def test_undescribed_missing_created_at_still_matches(self):
        conn = _make_db()
        current_month = datetime.now().strftime('%Y%m')
        _insert(conn, 'undesc/no-ca', date_folder=current_month, created_at=None)
        # No row in image_descriptions → counts as undescribed

        assert _call(conn, months=6, undescribed_only=True) == {'undesc/no-ca'}

    def test_undescribed_excludes_already_described_even_with_fallback(self):
        conn = _make_db()
        current_month = datetime.now().strftime('%Y%m')
        _insert(conn, 'undesc/done', date_folder=current_month, created_at=None)
        conn.execute(
            "INSERT INTO image_descriptions (image_key, image_type) VALUES (?, 'instagram')",
            ('undesc/done',),
        )

        assert _call(conn, months=6, undescribed_only=True) == set()


class TestNoFilter:
    """Sanity: with no window, every row is returned regardless of
    created_at / date_folder state."""

    @pytest.mark.parametrize(
        'created_at,date_folder',
        [
            ('2024-05-01T00:00:00', '202405'),
            (None, '202403'),
            ('', '202312'),
            (None, 'other'),
        ],
    )
    def test_no_window_returns_all(self, created_at, date_folder):
        conn = _make_db()
        _insert(conn, 'any/row', created_at=created_at, date_folder=date_folder)

        assert _call(conn) == {'any/row'}


class TestInstagramKeyOrdering:
    """Newest-first ordering via the COALESCE(created_at, date_folder) sort key."""

    def test_newest_first_by_created_at(self):
        conn = _make_db()
        _insert(conn, 'ig/old', created_at='2024-01-10T00:00:00')
        _insert(conn, 'ig/new', created_at='2024-06-20T00:00:00')

        assert _call_ordered(conn) == ['ig/new', 'ig/old']

    def test_undated_effective_date_first(self):
        conn = _make_db()
        _insert(conn, 'ig/dated', created_at='2024-06-20T00:00:00')
        _insert(conn, 'ig/undated', date_folder='other', created_at=None)

        keys = _call_ordered(conn)
        assert keys[0] == 'ig/undated'
        assert keys[1:] == ['ig/dated']

    def test_date_folder_fallback_sorts_newest_first(self):
        conn = _make_db()
        _insert(conn, 'ig/folder-old', date_folder='202401', created_at=None)
        _insert(conn, 'ig/folder-new', date_folder='202406', created_at=None)

        assert _call_ordered(conn) == ['ig/folder-new', 'ig/folder-old']

    def test_equal_effective_date_tiebreaker_media_key_desc(self):
        conn = _make_db()
        _insert(conn, 'ig/aaa', created_at='2024-05-01T00:00:00')
        _insert(conn, 'ig/zzz', created_at='2024-05-01T00:00:00')

        assert _call_ordered(conn) == ['ig/zzz', 'ig/aaa']

    def test_ordering_under_year_filter_with_date_folder_fallback(self):
        conn = _make_db()
        _insert(conn, 'ig/y24-new', date_folder='202408', created_at=None)
        _insert(conn, 'ig/y24-old', date_folder='202403', created_at=None)
        _insert(conn, 'ig/y23', date_folder='202312', created_at=None)

        assert _call_ordered(conn, year='2024') == ['ig/y24-new', 'ig/y24-old']

    def test_undescribed_only_preserves_order(self):
        conn = _make_db()
        _insert(conn, 'ig/undesc-new', created_at='2024-06-20T00:00:00')
        _insert(conn, 'ig/undesc-old', created_at='2024-01-01T00:00:00')
        _insert(conn, 'ig/described', created_at='2024-08-01T00:00:00')
        conn.execute(
            "INSERT INTO image_descriptions (image_key, image_type) VALUES (?, 'instagram')",
            ('ig/described',),
        )

        assert _call_ordered(conn, undescribed_only=True) == [
            'ig/undesc-new',
            'ig/undesc-old',
        ]
