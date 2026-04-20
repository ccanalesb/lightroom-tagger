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
    """
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE instagram_dump_media (
            media_key TEXT PRIMARY KEY,
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


def _insert(conn, key, *, created_at=None, date_folder=None):
    conn.execute(
        "INSERT INTO instagram_dump_media (media_key, date_folder, created_at) "
        "VALUES (?, ?, ?)",
        (key, date_folder, created_at),
    )


def _call(conn, *, months=None, year=None, undescribed_only=False):
    from jobs.handlers import _select_instagram_keys

    return {
        key
        for key, kind in _select_instagram_keys(
            conn,
            months=months,
            year=year,
            undescribed_only=undescribed_only,
        )
    }


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
