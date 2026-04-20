from unittest.mock import patch, MagicMock


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
@patch('jobs.handlers.require_library_db', return_value='/tmp/library.db')
def test_batch_describe_should_complete_with_zero_images(
    _mock_exists, mock_getenv, mock_config, mock_init_db, _mock_add_log,
):
    from jobs.handlers import handle_batch_describe

    mock_config.return_value = MagicMock(db_path='/tmp/library.db')
    mock_db = MagicMock()
    mock_db.execute.return_value.fetchall.return_value = []
    mock_init_db.return_value = mock_db

    runner = MagicMock()
    runner.db = MagicMock()

    handle_batch_describe(runner, 'test-job', {'image_type': 'catalog'})

    runner.complete_job.assert_called_once()
    result = runner.complete_job.call_args[0][1]
    assert result['described'] == 0
    assert result['total'] == 0


@patch('jobs.handlers.add_job_log')
@patch('lightroom_tagger.core.description_service.describe_matched_image')
@patch('lightroom_tagger.core.database.get_undescribed_catalog_images')
@patch('jobs.handlers.init_database')
@patch('jobs.handlers.load_config')
@patch('jobs.handlers.os.getenv', return_value='/tmp/library.db')
@patch('jobs.handlers.require_library_db', return_value='/tmp/library.db')
def test_batch_describe_should_describe_catalog_images(
    _mock_exists, mock_getenv, mock_config, mock_init_db, mock_get, mock_describe, _mock_add_log,
):
    from jobs.handlers import handle_batch_describe

    mock_config.return_value = MagicMock(db_path='/tmp/library.db')
    mock_init_db.return_value = MagicMock()
    mock_get.return_value = [{'key': 'img_001'}, {'key': 'img_002'}]
    mock_describe.return_value = True

    runner = _make_runner()

    handle_batch_describe(runner, 'test-job', {'image_type': 'catalog'})

    assert mock_describe.call_count == 2
    runner.complete_job.assert_called_once()
    result = runner.complete_job.call_args[0][1]
    assert result['described'] == 2
    assert result['failed'] == 0


@patch('jobs.handlers.add_job_log')
@patch('lightroom_tagger.core.description_service.describe_matched_image')
@patch('lightroom_tagger.core.database.get_undescribed_catalog_images')
@patch('jobs.handlers.init_database')
@patch('jobs.handlers.load_config')
@patch('jobs.handlers.os.getenv', return_value='/tmp/library.db')
@patch('jobs.handlers.require_library_db', return_value='/tmp/library.db')
def test_batch_describe_should_count_failures(
    _mock_exists, mock_getenv, mock_config, mock_init_db, mock_get, mock_describe, _mock_add_log,
):
    from jobs.handlers import handle_batch_describe

    mock_config.return_value = MagicMock(db_path='/tmp/library.db')
    mock_init_db.return_value = MagicMock()
    mock_get.return_value = [{'key': 'img_001'}, {'key': 'img_002'}]
    mock_describe.side_effect = [True, Exception('API error')]

    runner = _make_runner()

    handle_batch_describe(runner, 'test-job', {'image_type': 'catalog'})

    result = runner.complete_job.call_args[0][1]
    assert result['described'] == 1
    assert result['failed'] == 1


@patch('jobs.handlers.add_job_log')
@patch('lightroom_tagger.core.description_service.describe_matched_image')
@patch('lightroom_tagger.core.database.get_undescribed_catalog_images')
@patch('jobs.handlers.init_database')
@patch('jobs.handlers.load_config')
@patch('jobs.handlers.os.getenv', return_value='/tmp/library.db')
@patch('jobs.handlers.require_library_db', return_value='/tmp/library.db')
def test_batch_describe_should_stop_after_consecutive_failures(
    _mock_exists, mock_getenv, mock_config, mock_init_db, mock_get, mock_describe, mock_add_log,
):
    from jobs.handlers import handle_batch_describe

    mock_config.return_value = MagicMock(db_path='/tmp/library.db')
    mock_init_db.return_value = MagicMock()
    mock_get.return_value = [{'key': f'img_{i:03d}'} for i in range(15)]
    mock_describe.side_effect = Exception('rate limit')

    runner = _make_runner()

    handle_batch_describe(
        runner,
        'test-job',
        {'image_type': 'catalog', 'max_workers': 1},
    )

    assert mock_describe.call_count == 10
    runner.fail_job.assert_called_once()
    msg = runner.fail_job.call_args[0][1]
    assert '10 consecutive failures' in msg


@patch('jobs.handlers.add_job_log')
@patch('lightroom_tagger.core.database.get_undescribed_catalog_images')
@patch('jobs.handlers.init_database')
@patch('jobs.handlers.load_config')
@patch('jobs.handlers.os.getenv', return_value='/tmp/library.db')
@patch('jobs.handlers.require_library_db', return_value='/tmp/library.db')
def test_batch_describe_legacy_vision_model_metadata_does_not_set_env(
    _mock_exists, mock_getenv, mock_config, mock_init_db, mock_get, _mock_add_log,
):
    from jobs.handlers import handle_batch_describe
    import os

    mock_config.return_value = MagicMock(db_path='/tmp/library.db')
    mock_init_db.return_value = MagicMock()

    captured_env = {}

    def capture_env(*args, **kwargs):
        captured_env['model'] = os.environ.get('DESCRIPTION_VISION_MODEL')
        return []

    mock_get.side_effect = capture_env

    runner = _make_runner()

    handle_batch_describe(runner, 'test-job', {
        'image_type': 'catalog',
        'vision_model': 'custom-model',
    })

    assert captured_env.get('model') is None
    assert os.environ.get('DESCRIPTION_VISION_MODEL') is None


@patch('jobs.handlers.add_job_log')
@patch('jobs.handlers.init_database')
@patch('jobs.handlers.load_config')
@patch('jobs.handlers.os.getenv', return_value='/tmp/library.db')
def test_batch_describe_should_fail_job_on_exception(
    mock_getenv, mock_config, mock_init_db, _mock_add_log,
):
    from jobs.handlers import handle_batch_describe

    mock_config.side_effect = Exception('config broken')

    runner = MagicMock()
    runner.db = MagicMock()

    handle_batch_describe(runner, 'test-job', {})

    runner.fail_job.assert_called_once_with(
        'test-job', 'config broken', severity='error',
    )


@patch('jobs.handlers.add_job_log')
@patch('lightroom_tagger.core.database.get_undescribed_catalog_images')
@patch('jobs.handlers.init_database')
@patch('jobs.handlers.load_config')
@patch('jobs.handlers.os.getenv', return_value='/tmp/library.db')
@patch('jobs.handlers.require_library_db', return_value='/tmp/library.db')
def test_batch_describe_passes_months_12_for_12months_date_filter(
    _mock_exists, mock_getenv, mock_config, mock_init_db, mock_get_undescribed, _mock_add_log,
):
    from jobs.handlers import handle_batch_describe

    mock_config.return_value = MagicMock(db_path='/tmp/library.db')
    mock_init_db.return_value = MagicMock()
    mock_get_undescribed.return_value = []

    runner = MagicMock()
    runner.db = MagicMock()

    handle_batch_describe(runner, 'job-12m', {
        'image_type': 'catalog',
        'date_filter': '12months',
        'force': False,
    })

    mock_get_undescribed.assert_called_once()
    assert mock_get_undescribed.call_args.kwargs['months'] == 12


@patch('jobs.handlers.add_job_log')
@patch('lightroom_tagger.core.database.get_undescribed_catalog_images')
@patch('jobs.handlers.init_database')
@patch('jobs.handlers.load_config')
@patch('jobs.handlers.os.getenv', return_value='/tmp/library.db')
@patch('jobs.handlers.require_library_db', return_value='/tmp/library.db')
def test_batch_describe_passes_min_rating_for_catalog_selection(
    _mock_exists, mock_getenv, mock_config, mock_init_db, mock_get_undescribed, _mock_add_log,
):
    from jobs.handlers import handle_batch_describe

    mock_config.return_value = MagicMock(db_path='/tmp/library.db')
    mock_init_db.return_value = MagicMock()
    mock_get_undescribed.return_value = []

    runner = MagicMock()
    runner.db = MagicMock()

    handle_batch_describe(runner, 'job-rating', {
        'image_type': 'catalog',
        'min_rating': 3,
    })

    mock_get_undescribed.assert_called_once()
    assert mock_get_undescribed.call_args.kwargs['min_rating'] == 3
