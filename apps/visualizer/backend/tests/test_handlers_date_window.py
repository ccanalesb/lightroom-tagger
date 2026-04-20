"""Unit tests for the shared date-window parsing helper used by the batch
describe/score/analyze handlers.

See :func:`jobs.handlers._resolve_date_window` for the contract these tests
pin down. The helper is small but critical: every batch handler routes its
date filtering through it, so regressions here silently widen or narrow the
image selection and corrupt result counts.
"""
from unittest.mock import MagicMock, patch

import pytest


def _resolve(metadata):
    from jobs.handlers import _resolve_date_window

    return _resolve_date_window(metadata)


class TestResolveDateWindow:
    def test_empty_metadata_returns_no_window(self):
        assert _resolve({}) == (None, None)

    def test_legacy_date_filter_all_is_no_window(self):
        assert _resolve({'date_filter': 'all'}) == (None, None)

    @pytest.mark.parametrize(
        'label,months',
        [('3months', 3), ('6months', 6), ('12months', 12)],
    )
    def test_legacy_date_filter_labels_map_to_months(self, label, months):
        assert _resolve({'date_filter': label}) == (months, None)

    def test_last_months_int_wins_over_legacy_label(self):
        # ``last_months`` lets new clients request arbitrary granularity
        # (e.g. 9 months) without expanding the legacy enum map.
        assert _resolve({'date_filter': '3months', 'last_months': 9}) == (9, None)

    @pytest.mark.parametrize('value', [1, 2, 9, 18, 24, 48])
    def test_last_months_accepts_positive_ints(self, value):
        assert _resolve({'last_months': value}) == (value, None)

    @pytest.mark.parametrize('value', [0, -3, 'abc', None, True, False])
    def test_last_months_rejects_invalid_values(self, value):
        # Invalid ``last_months`` should not silently widen the window; it
        # falls through to the legacy ``date_filter`` path (here: absent).
        assert _resolve({'last_months': value}) == (None, None)

    def test_last_months_accepts_numeric_strings(self):
        assert _resolve({'last_months': '9'}) == (9, None)

    @pytest.mark.parametrize('value', ['2024', '2025', '2026'])
    def test_year_string_is_returned_as_is(self, value):
        assert _resolve({'year': value}) == (None, value)

    def test_year_int_is_stringified(self):
        assert _resolve({'year': 2025}) == (None, '2025')

    @pytest.mark.parametrize('value', ['', '25', 'abcd', '2025a', 0, None])
    def test_year_rejects_non_four_digit_values(self, value):
        assert _resolve({'year': value}) == (None, None)

    def test_last_months_wins_over_year_when_both_set(self):
        # This is an intentional precedence choice: numeric windows win over
        # year windows when a client accidentally sends both.
        assert _resolve({'last_months': 6, 'year': '2024'}) == (6, None)


# ---------------------------------------------------------------------------
# End-to-end checks that the helper is actually honored inside each batch
# handler. These exercise the catalog selection SQL path only (the instagram
# arm uses the same helper and is covered by existing integration tests).
# ---------------------------------------------------------------------------


def _patched_handler_env(handler_name):
    """Common patcher stack for batch handlers.

    Each handler shares the same external surface: ``load_config`` returns a
    config with the library path, ``require_library_db`` resolves the DB file,
    and ``init_database`` hands back a mock SQLite connection. We use this
    helper to cut down on copy-pasted decorators in the tests below.
    """
    return patch('jobs.handlers.init_database')


@patch('jobs.handlers.add_job_log')
@patch('jobs.handlers.init_database')
@patch('jobs.handlers.load_config')
@patch('jobs.handlers.require_library_db', return_value='/tmp/library.db')
def test_batch_describe_honors_last_months_int(
    _mock_db_path, mock_config, mock_init_db, _mock_add_log,
):
    """New-style ``last_months: 9`` runs the catalog SQL with ``-9 months``."""
    from jobs.handlers import handle_batch_describe

    mock_config.return_value = MagicMock(db_path='/tmp/library.db')
    mock_db = MagicMock()
    mock_db.execute.return_value.fetchall.return_value = []
    mock_init_db.return_value = mock_db

    runner = MagicMock()
    runner.db = MagicMock()
    runner.is_cancelled.return_value = False

    handle_batch_describe(runner, 'job-9m', {
        'image_type': 'catalog',
        'last_months': 9,
        'force': True,  # force exercises the SQL path we want to observe
    })

    # Find the SELECT that actually queried the images table (there are
    # auxiliary execute() calls in the pipeline — we filter for the one we
    # care about).
    image_selects = [
        call for call in mock_db.execute.call_args_list
        if 'FROM images' in call.args[0]
    ]
    assert image_selects, "expected at least one SELECT against images"
    first = image_selects[0]
    sql, params = first.args
    assert "date_taken >= date('now', ?)" in sql
    assert '-9 months' in params


@patch('jobs.handlers.add_job_log')
@patch('jobs.handlers.init_database')
@patch('jobs.handlers.load_config')
@patch('jobs.handlers.require_library_db', return_value='/tmp/library.db')
def test_batch_describe_honors_year_window(
    _mock_db_path, mock_config, mock_init_db, _mock_add_log,
):
    """``year: '2024'`` should translate to ``strftime('%Y', ...) = '2024'``."""
    from jobs.handlers import handle_batch_describe

    mock_config.return_value = MagicMock(db_path='/tmp/library.db')
    mock_db = MagicMock()
    mock_db.execute.return_value.fetchall.return_value = []
    mock_init_db.return_value = mock_db

    runner = MagicMock()
    runner.db = MagicMock()
    runner.is_cancelled.return_value = False

    handle_batch_describe(runner, 'job-2024', {
        'image_type': 'catalog',
        'year': '2024',
        'force': True,
    })

    image_selects = [
        call for call in mock_db.execute.call_args_list
        if 'FROM images' in call.args[0]
    ]
    assert image_selects
    sql, params = image_selects[0].args
    assert "strftime('%Y'," in sql
    assert '2024' in params


@patch('jobs.handlers.add_job_log')
@patch('jobs.handlers.init_database')
@patch('jobs.handlers.load_config')
@patch('jobs.handlers.require_library_db', return_value='/tmp/library.db')
def test_batch_score_honors_last_months_int(
    _mock_db_path, mock_config, mock_init_db, _mock_add_log,
):
    """Score path shares the helper — spot-check ``last_months: 18``."""
    from jobs.handlers import handle_batch_score

    mock_config.return_value = MagicMock(db_path='/tmp/library.db')
    mock_db = MagicMock()
    mock_db.execute.return_value.fetchall.return_value = []
    mock_init_db.return_value = mock_db

    runner = MagicMock()
    runner.db = MagicMock()
    runner.is_cancelled.return_value = False

    handle_batch_score(runner, 'job-18m', {
        'image_type': 'catalog',
        'last_months': 18,
    })

    image_selects = [
        call for call in mock_db.execute.call_args_list
        if 'FROM images' in call.args[0]
    ]
    assert image_selects
    sql, params = image_selects[0].args
    assert '-18 months' in params
