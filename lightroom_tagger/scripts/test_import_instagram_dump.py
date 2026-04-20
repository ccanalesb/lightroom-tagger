"""Tests for :func:`derive_created_at_from_date_folder`.

Imports from Instagram dumps occasionally leave ``created_at`` unset (JSON
metadata missing). The helper rescues those rows by synthesizing an ISO date
from the ``YYYYMM`` folder, so date-window filters don't silently drop them.

See :func:`apps.visualizer.backend.jobs.handlers._select_instagram_keys` for
the consumer-side fallback that shares this convention.
"""
from __future__ import annotations

import pytest

from lightroom_tagger.scripts.import_instagram_dump import (
    derive_created_at_from_date_folder,
)


@pytest.mark.parametrize(
    'folder,expected',
    [
        ('202603', '2026-03-01T00:00:00'),
        ('202001', '2020-01-01T00:00:00'),
        ('202412', '2024-12-01T00:00:00'),
    ],
)
def test_derives_iso_date_from_six_digit_folder(folder, expected):
    assert derive_created_at_from_date_folder(folder) == expected


@pytest.mark.parametrize(
    'folder',
    [
        None,  # dump_reader leaves date_folder unset for media outside YYYYMM dirs
        '',
        'other',  # legacy fallback bucket for unknown folders
        '20260',  # truncated (5 digits)
        '2026033',  # too long
        '202a03',  # mixed
        '   ',
    ],
)
def test_returns_none_for_unparseable_folders(folder):
    """Callers rely on ``None`` meaning "leave created_at unset" so the
    importer doesn't fabricate bogus timestamps."""
    assert derive_created_at_from_date_folder(folder) is None


def test_trims_surrounding_whitespace():
    # Defensive: some JSON sources have leading whitespace; we still accept
    # the folder once stripped.
    assert derive_created_at_from_date_folder('  202603  ') == '2026-03-01T00:00:00'
