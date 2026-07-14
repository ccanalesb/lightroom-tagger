"""Path preflight + skip_reason_counts tests for path-dependent job handlers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import jobs.handlers.analyze as analyze_mod
import jobs.handlers.embed as embed_mod
import jobs.handlers.path_diagnostics as path_diag_mod
from lightroom_tagger.core.database import init_database, store_image
from lightroom_tagger.core.vision_op import VisionOpOutcome


def _make_runner() -> MagicMock:
    runner = MagicMock()
    runner.db = MagicMock()
    runner.is_cancelled.return_value = False
    return runner


def _seed_bad_catalog(conn, count: int, *, prefix: str = 'bad') -> list[str]:
    keys: list[str] = []
    for i in range(count):
        keys.append(
            store_image(
                conn,
                {
                    'date_taken': f'2024-03-{i + 1:02d}',
                    'filename': f'{prefix}-{i}.jpg',
                    'filepath': f'/definitely/missing-{prefix}-{i}.jpg',
                    'rating': 1,
                },
            )
        )
    return keys


@patch('database.add_job_log')
@patch('jobs.handlers.analyze._describe_single_image')
def test_batch_describe_preflight_fails_fast_when_paths_inaccessible(
    mock_describe, _mock_add_log, tmp_path, monkeypatch,
) -> None:
    from jobs.handlers import handle_batch_describe

    db_path = tmp_path / 'library.db'
    conn = init_database(str(db_path))
    keys = _seed_bad_catalog(conn, 4)
    conn.close()

    monkeypatch.setattr(path_diag_mod, 'PREFLIGHT_SAMPLE_SIZE', 4)
    monkeypatch.setattr(
        analyze_mod,
        '_select_catalog_keys',
        lambda *args, **kwargs: [(k, 'catalog') for k in keys],
    )
    monkeypatch.setenv('LIBRARY_DB', str(db_path))
    runner = _make_runner()
    handle_batch_describe(runner, 'job-bd-preflight', {'image_type': 'catalog'})

    runner.fail_job.assert_called_once()
    fail_message = str(runner.fail_job.call_args[0][1])
    assert 'network share' in fail_message
    assert 'sampled paths unreachable' in fail_message
    runner.complete_job.assert_not_called()
    mock_describe.assert_not_called()


@patch('database.add_job_log')
@patch('jobs.handlers.analyze._describe_single_image')
def test_batch_describe_preflight_continues_in_chain_mode(
    mock_describe, mock_add_log, tmp_path, monkeypatch,
) -> None:
    from jobs.handlers import handle_batch_describe

    db_path = tmp_path / 'library.db'
    conn = init_database(str(db_path))
    keys = _seed_bad_catalog(conn, 3)
    conn.close()

    mock_describe.return_value = ('skipped', False, 'File not found')
    monkeypatch.setattr(path_diag_mod, 'PREFLIGHT_SAMPLE_SIZE', 4)
    monkeypatch.setattr(
        analyze_mod,
        '_select_catalog_keys',
        lambda *args, **kwargs: [(k, 'catalog') for k in keys],
    )
    monkeypatch.setenv('LIBRARY_DB', str(db_path))
    runner = _make_runner()
    handle_batch_describe(
        runner,
        'job-bd-chain',
        {'image_type': 'catalog', '_catalog_cache_chain': True, 'force': True},
    )

    runner.fail_job.assert_not_called()
    runner.complete_job.assert_called_once()
    result = runner.complete_job.call_args[0][1]
    assert result['skipped'] == 3
    assert result['skip_reason_counts']['unresolved_or_missing'] == 3
    warnings = [
        str(c.args[3])
        for c in mock_add_log.call_args_list
        if len(c.args) > 3 and c.args[2] == 'warning'
    ]
    assert any('batch_describe preflight' in msg for msg in warnings), warnings


@patch('database.add_job_log')
@patch('jobs.handlers.analyze._describe_single_image')
def test_batch_describe_reports_grouped_skip_reason_counts(
    mock_describe, _mock_add_log, tmp_path, monkeypatch,
) -> None:
    from jobs.handlers import handle_batch_describe

    db_path = tmp_path / 'library.db'
    conn = init_database(str(db_path))
    key_empty = store_image(
        conn,
        {'date_taken': '2024-04-01', 'filename': 'e.jpg', 'filepath': '', 'rating': 1},
    )
    key_missing = store_image(
        conn,
        {
            'date_taken': '2024-04-02',
            'filename': 'm.jpg',
            'filepath': '/missing/path.jpg',
            'rating': 1,
        },
    )
    conn.close()

    def _describe_side_effect(_db, key, *_args, **_kwargs):
        if key == missing_key:
            return ('skipped', False, 'Image key not found in catalog')
        if key == key_empty:
            return ('skipped', False, 'No filepath in catalog record')
        if key == key_missing:
            return ('skipped', False, 'File not found')
        return ('described', True, None)

    mock_describe.side_effect = _describe_side_effect
    missing_key = 'missing-no-row-key'
    monkeypatch.setattr(
        analyze_mod,
        '_select_catalog_keys',
        lambda *args, **kwargs: [
            (missing_key, 'catalog'),
            (key_empty, 'catalog'),
            (key_missing, 'catalog'),
        ],
    )
    monkeypatch.setattr(path_diag_mod, 'PREFLIGHT_SAMPLE_SIZE', 0)
    monkeypatch.setenv('LIBRARY_DB', str(db_path))
    runner = _make_runner()
    handle_batch_describe(runner, 'job-bd-grouped', {'image_type': 'catalog', 'force': True})

    runner.complete_job.assert_called_once()
    result = runner.complete_job.call_args[0][1]
    assert result['skip_reason_counts'] == {
        'no_row': 1,
        'empty_path': 1,
        'unresolved_or_missing': 1,
        'encode_failed': 0,
    }


@patch('database.add_job_log')
@patch('jobs.handlers.analyze._score_single_image')
def test_batch_score_preflight_aborts_when_majority_unreachable(
    mock_score, _mock_add_log, tmp_path, monkeypatch,
) -> None:
    from jobs.handlers import handle_batch_score

    db_path = tmp_path / 'library.db'
    conn = init_database(str(db_path))
    bad_keys = _seed_bad_catalog(conn, 5, prefix='score-bad')
    good_jpg = tmp_path / 'good.jpg'
    good_jpg.write_bytes(b'fake')
    good_keys = [
        store_image(
            conn,
            {
                'date_taken': f'2024-06-{i + 10:02d}',
                'filename': f'good-{i}.jpg',
                'filepath': str(good_jpg),
                'rating': 1,
            },
        )
        for i in range(3)
    ]
    conn.close()

    monkeypatch.setattr(
        analyze_mod,
        '_select_catalog_keys',
        lambda *args, **kwargs: [(k, 'catalog') for k in bad_keys + good_keys],
    )
    monkeypatch.setattr(
        'lightroom_tagger.core.database.list_perspectives',
        lambda *_a, **_k: [{'slug': 'test-p'}],
    )
    monkeypatch.setattr(path_diag_mod, 'PREFLIGHT_SAMPLE_SIZE', 8)
    monkeypatch.setenv('LIBRARY_DB', str(db_path))
    runner = _make_runner()
    handle_batch_score(runner, 'job-bs-majority', {'image_type': 'catalog'})

    runner.fail_job.assert_called_once()
    runner.complete_job.assert_not_called()
    mock_score.assert_not_called()


@patch('database.add_job_log')
@patch('jobs.handlers.analyze._run_describe_pass')
@patch('jobs.handlers.analyze._run_score_pass')
def test_batch_analyze_merges_skip_reason_counts(
    mock_score_pass, mock_describe_pass, _mock_add_log, tmp_path, monkeypatch,
) -> None:
    from jobs.handlers import handle_batch_analyze

    mock_describe_pass.return_value = {
        'described': 0,
        'skipped': 2,
        'failed': 0,
        'total': 2,
        'skip_reason_counts': {
            'no_row': 0,
            'empty_path': 1,
            'unresolved_or_missing': 1,
            'encode_failed': 0,
        },
    }
    mock_score_pass.return_value = {
        'scored': 0,
        'skipped': 1,
        'failed': 0,
        'total': 1,
        'skip_reason_counts': {
            'no_row': 0,
            'empty_path': 0,
            'unresolved_or_missing': 1,
            'encode_failed': 0,
        },
    }

    db_path = tmp_path / 'library.db'
    init_database(str(db_path)).close()
    monkeypatch.setattr(
        analyze_mod,
        '_select_catalog_keys',
        lambda *args, **kwargs: [('k1', 'catalog')],
    )
    monkeypatch.setenv('LIBRARY_DB', str(db_path))
    runner = _make_runner()
    handle_batch_analyze(runner, 'job-ba-merge', {'image_type': 'catalog'})

    runner.complete_job.assert_called_once()
    result = runner.complete_job.call_args[0][1]
    assert result['skip_reason_counts'] == {
        'no_row': 0,
        'empty_path': 1,
        'unresolved_or_missing': 2,
        'encode_failed': 0,
    }


@patch('database.add_job_log')
@patch('jobs.handlers.analyze._describe_single_image')
def test_single_describe_preflight_fails_on_unreachable_path(
    mock_describe, _mock_add_log, tmp_path, monkeypatch,
) -> None:
    from jobs.handlers import handle_single_describe

    db_path = tmp_path / 'library.db'
    conn = init_database(str(db_path))
    key = store_image(
        conn,
        {
            'date_taken': '2024-05-01',
            'filename': 'missing.jpg',
            'filepath': '/definitely/missing.jpg',
            'rating': 1,
        },
    )
    conn.close()

    monkeypatch.setenv('LIBRARY_DB', str(db_path))
    runner = _make_runner()
    handle_single_describe(
        runner,
        'job-sd-preflight',
        {'image_key': key, 'image_type': 'catalog'},
    )

    runner.fail_job.assert_called_once()
    mock_describe.assert_not_called()


@patch('database.add_job_log')
@patch('jobs.handlers.analyze._score_single_image')
def test_single_score_includes_skip_reason_counts(
    mock_score, _mock_add_log, tmp_path, monkeypatch,
) -> None:
    from jobs.handlers import handle_single_score

    db_path = tmp_path / 'library.db'
    conn = init_database(str(db_path))
    key = store_image(
        conn,
        {
            'date_taken': '2024-05-02',
            'filename': 'ok.jpg',
            'filepath': str(tmp_path / 'ok.jpg'),
            'rating': 1,
        },
    )
    (tmp_path / 'ok.jpg').write_bytes(b'fake')
    conn.close()

    mock_score.return_value = VisionOpOutcome(status='written')
    monkeypatch.setenv('LIBRARY_DB', str(db_path))
    runner = _make_runner()
    handle_single_score(
        runner,
        'job-ss-counts',
        {'image_key': key, 'image_type': 'catalog', 'perspective_slugs': ['p1']},
    )

    runner.complete_job.assert_called_once()
    result = runner.complete_job.call_args[0][1]
    assert 'skip_reason_counts' in result
    assert result['skip_reason_counts']['unresolved_or_missing'] == 0


@patch('database.add_job_log')
@patch('jobs.handlers.matching.match_dump_media')
@patch('jobs.handlers.matching.init_database')
@patch('jobs.handlers.matching.load_config')
@patch('jobs.handlers.matching.update_job_field')
@patch('jobs.handlers.matching.require_library_db')
def test_vision_match_preflight_fails_when_paths_inaccessible(
    mock_require_db,
    _mock_update_field,
    mock_config,
    mock_init_db,
    mock_match,
    _mock_add_log,
    tmp_path,
    monkeypatch,
) -> None:
    from jobs.handlers import handle_vision_match

    db_path = tmp_path / 'library.db'
    conn = init_database(str(db_path))
    from lightroom_tagger.core.database import store_instagram_dump_media

    keys = []
    for i in range(4):
        keys.append(
            store_instagram_dump_media(
                conn,
                {
                    'media_key': f'ig/missing-{i}',
                    'file_path': f'/definitely/missing-{i}.jpg',
                    'filename': f'missing-{i}.jpg',
                    'date_folder': '202603',
                },
            )
        )
    conn.close()

    mock_config.return_value = MagicMock(
        match_threshold=0.7,
        phash_weight=0.4,
        desc_weight=0.3,
        vision_weight=0.3,
        catalog_path=None,
        small_catalog_path=None,
        matching_workers=4,
    )
    mock_init_db.return_value = init_database(str(db_path))
    mock_require_db.return_value = str(db_path)
    monkeypatch.setattr(path_diag_mod, 'PREFLIGHT_SAMPLE_SIZE', 4)

    runner = _make_runner()
    handle_vision_match(runner, 'job-vm-preflight', {'media_key': keys[0]})

    runner.fail_job.assert_called_once()
    mock_match.assert_not_called()
