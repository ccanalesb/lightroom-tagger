"""Tests for the unified ``batch_analyze`` job handler (Phase 03)."""

from unittest.mock import MagicMock, patch


def _make_runner():
    """MagicMock runner with non-truthy is_cancelled (bare MagicMock is truthy when called)."""
    runner = MagicMock()
    runner.db = MagicMock()
    runner.is_cancelled.return_value = False
    return runner


@patch('jobs.handlers.add_job_log')
@patch('jobs.handlers.init_database')
@patch('jobs.handlers.load_config')
@patch('jobs.handlers.os.getenv', return_value='/tmp/library.db')
@patch('jobs.handlers.os.path.exists', return_value=True)
def test_batch_analyze_completes_with_zero_images(
    _mock_exists, _mock_getenv, mock_config, mock_init_db, _mock_add_log,
):
    from jobs.handlers import handle_batch_analyze

    mock_config.return_value = MagicMock(db_path='/tmp/library.db')
    mock_db = MagicMock()
    mock_db.execute.return_value.fetchall.return_value = []
    mock_init_db.return_value = mock_db

    runner = _make_runner()

    handle_batch_analyze(runner, 'job-zero', {'image_type': 'catalog'})

    runner.complete_job.assert_called_once()
    payload = runner.complete_job.call_args[0][1]
    for key in (
        'describe_total',
        'describe_succeeded',
        'describe_failed',
        'score_total',
        'score_succeeded',
        'score_failed',
    ):
        assert key in payload, f'missing combined key {key!r}'
        assert isinstance(payload[key], int)
        assert payload[key] == 0


@patch('jobs.handlers.add_job_log')
@patch('jobs.handlers._score_single_image')
@patch('lightroom_tagger.core.description_service.describe_matched_image')
@patch('lightroom_tagger.core.database.get_undescribed_catalog_images')
@patch('jobs.handlers.init_database')
@patch('jobs.handlers.load_config')
@patch('jobs.handlers.os.getenv', return_value='/tmp/library.db')
@patch('jobs.handlers.os.path.exists', return_value=True)
def test_batch_analyze_runs_describe_then_score(
    _mock_exists,
    _mock_getenv,
    mock_config,
    mock_init_db,
    mock_get_undescribed,
    mock_describe,
    mock_score,
    _mock_add_log,
):
    from jobs.handlers import handle_batch_analyze

    mock_config.return_value = MagicMock(db_path='/tmp/library.db')
    mock_db = MagicMock()
    mock_db.execute.return_value.fetchall.return_value = []
    mock_init_db.return_value = mock_db

    mock_get_undescribed.return_value = [{'key': 'img_001'}, {'key': 'img_002'}]
    mock_describe.return_value = True
    mock_score.return_value = ('scored', True, None)

    runner = _make_runner()

    handle_batch_analyze(
        runner,
        'job-happy',
        {
            'image_type': 'catalog',
            'max_workers': 1,
            'perspective_slugs': ['p1'],
        },
    )

    assert mock_describe.call_count == 2
    assert mock_score.call_count == 2
    runner.complete_job.assert_called_once()
    payload = runner.complete_job.call_args[0][1]
    assert payload['describe_succeeded'] == 2
    assert payload['describe_total'] == 2
    assert payload['score_succeeded'] == 2
    assert payload['score_total'] == 2


@patch('jobs.handlers.add_job_log')
@patch('jobs.handlers._score_single_image')
@patch('lightroom_tagger.core.description_service.describe_matched_image')
@patch('lightroom_tagger.core.database.get_undescribed_catalog_images')
@patch('jobs.handlers.init_database')
@patch('jobs.handlers.load_config')
@patch('jobs.handlers.os.getenv', return_value='/tmp/library.db')
@patch('jobs.handlers.os.path.exists', return_value=True)
def test_batch_analyze_describe_failures_still_invoke_score(
    _mock_exists,
    _mock_getenv,
    mock_config,
    mock_init_db,
    mock_get_undescribed,
    mock_describe,
    mock_score,
    _mock_add_log,
):
    from jobs.handlers import handle_batch_analyze

    mock_config.return_value = MagicMock(db_path='/tmp/library.db')
    mock_db = MagicMock()
    mock_db.execute.return_value.fetchall.return_value = []
    mock_init_db.return_value = mock_db

    mock_get_undescribed.return_value = [{'key': 'img_a'}, {'key': 'img_b'}]
    mock_describe.side_effect = [True, Exception('transient')]
    mock_score.return_value = ('scored', True, None)

    runner = _make_runner()

    handle_batch_analyze(
        runner,
        'job-partial',
        {
            'image_type': 'catalog',
            'max_workers': 1,
            'perspective_slugs': ['p1'],
        },
    )

    runner.complete_job.assert_called_once()
    payload = runner.complete_job.call_args[0][1]
    assert payload['describe_failed'] >= 1
    assert payload['score_succeeded'] == 2
    assert mock_score.call_count == 2


@patch('jobs.handlers.add_job_log')
@patch('jobs.handlers._score_single_image')
@patch('lightroom_tagger.core.description_service.describe_matched_image')
@patch('lightroom_tagger.core.database.get_undescribed_catalog_images')
@patch('jobs.handlers.update_job_field')
@patch('jobs.handlers.init_database')
@patch('jobs.handlers.load_config')
@patch('jobs.handlers.os.getenv', return_value='/tmp/library.db')
@patch('jobs.handlers.os.path.exists', return_value=True)
def test_batch_analyze_sets_current_step_describing_then_scoring(
    _mock_exists,
    _mock_getenv,
    mock_config,
    mock_init_db,
    mock_update_field,
    mock_get_undescribed,
    mock_describe,
    mock_score,
    _mock_add_log,
):
    from jobs.handlers import handle_batch_analyze

    mock_config.return_value = MagicMock(db_path='/tmp/library.db')
    mock_db = MagicMock()
    mock_db.execute.return_value.fetchall.return_value = []
    mock_init_db.return_value = mock_db

    mock_get_undescribed.return_value = [{'key': 'img_x'}]
    mock_describe.return_value = True
    mock_score.return_value = ('scored', True, None)

    runner = _make_runner()

    handle_batch_analyze(
        runner,
        'job-steps',
        {
            'image_type': 'catalog',
            'max_workers': 1,
            'perspective_slugs': ['p1'],
        },
    )

    current_step_calls = [
        c for c in mock_update_field.call_args_list
        if len(c.args) >= 3 and c.args[2] == 'current_step'
    ]
    values = [c.args[3] for c in current_step_calls]
    assert values == ['Describing', 'Scoring'], f'unexpected current_step order: {values!r}'


@patch('jobs.handlers.add_job_log')
@patch('jobs.handlers._score_single_image')
@patch('lightroom_tagger.core.description_service.describe_matched_image')
@patch('lightroom_tagger.core.database.get_undescribed_catalog_images')
@patch('jobs.handlers.fingerprint_batch_describe', return_value='fp-describe-constant')
@patch('jobs.handlers.get_job')
@patch('jobs.handlers.init_database')
@patch('jobs.handlers.load_config')
@patch('jobs.handlers.os.getenv', return_value='/tmp/library.db')
@patch('jobs.handlers.os.path.exists', return_value=True)
def test_batch_analyze_resume_skips_describe_when_stage_score(
    _mock_exists,
    _mock_getenv,
    mock_config,
    mock_init_db,
    mock_get_job,
    _mock_fp_describe,
    mock_get_undescribed,
    mock_describe,
    mock_score,
    _mock_add_log,
):
    from jobs.handlers import handle_batch_analyze

    mock_config.return_value = MagicMock(db_path='/tmp/library.db')
    mock_db = MagicMock()
    mock_db.execute.return_value.fetchall.return_value = []
    mock_init_db.return_value = mock_db

    mock_get_undescribed.return_value = [{'key': 'img_r'}]
    mock_describe.return_value = True
    mock_score.return_value = ('scored', True, None)

    mock_get_job.return_value = {
        'status': 'running',
        'metadata': {
            'checkpoint': {
                'checkpoint_version': 1,
                'job_type': 'batch_analyze',
                'stage': 'score',
                'describe': {
                    'fingerprint': 'fp-describe-constant',
                    'processed_pairs': ['img_r|catalog'],
                    'total_at_start': 1,
                },
                'score': {
                    'fingerprint': 'fp-score-other',
                    'processed_triplets': [],
                    'total_at_start': 1,
                },
            },
        },
    }

    runner = _make_runner()

    handle_batch_analyze(
        runner,
        'job-resume',
        {
            'image_type': 'catalog',
            'max_workers': 1,
            'perspective_slugs': ['p1'],
        },
    )

    mock_describe.assert_not_called()
    assert mock_score.call_count == 1


@patch('jobs.handlers.add_job_log')
@patch('jobs.handlers._score_single_image')
@patch('lightroom_tagger.core.description_service.describe_matched_image')
@patch('lightroom_tagger.core.database.get_undescribed_catalog_images')
@patch('jobs.handlers.fingerprint_batch_describe', return_value='fp-live-value')
@patch('jobs.handlers.get_job')
@patch('jobs.handlers.init_database')
@patch('jobs.handlers.load_config')
@patch('jobs.handlers.os.getenv', return_value='/tmp/library.db')
@patch('jobs.handlers.os.path.exists', return_value=True)
def test_batch_analyze_describe_fingerprint_mismatch_resets_pairs(
    _mock_exists,
    _mock_getenv,
    mock_config,
    mock_init_db,
    mock_get_job,
    _mock_fp_describe,
    mock_get_undescribed,
    mock_describe,
    mock_score,
    mock_add_log,
):
    from jobs.handlers import handle_batch_analyze

    mock_config.return_value = MagicMock(db_path='/tmp/library.db')
    mock_db = MagicMock()
    mock_db.execute.return_value.fetchall.return_value = []
    mock_init_db.return_value = mock_db

    mock_get_undescribed.return_value = [{'key': 'img_m'}]
    mock_describe.return_value = True
    mock_score.return_value = ('scored', True, None)

    mock_get_job.return_value = {
        'status': 'running',
        'metadata': {
            'checkpoint': {
                'checkpoint_version': 1,
                'job_type': 'batch_analyze',
                'stage': 'describe',
                'describe': {
                    'fingerprint': 'fp-stale-old',
                    'processed_pairs': ['img_m|catalog'],
                    'total_at_start': 1,
                },
                'score': {},
            },
        },
    }

    runner = _make_runner()

    handle_batch_analyze(
        runner,
        'job-fpmismatch',
        {
            'image_type': 'catalog',
            'max_workers': 1,
            'perspective_slugs': ['p1'],
        },
    )

    log_messages = [c.args[3] for c in mock_add_log.call_args_list if len(c.args) >= 4]
    assert any(
        'checkpoint mismatch: batch_analyze describe fingerprint changed, starting describe fresh' in m
        for m in log_messages
    ), f'expected mismatch log, got: {log_messages!r}'
    mock_describe.assert_called()
