from unittest.mock import patch, MagicMock


@patch('database.add_job_log')
@patch('jobs.handlers.init_database')
@patch('jobs.handlers.load_config')
@patch('jobs.handlers.os.getenv', return_value='/tmp/library.db')
def test_batch_describe_should_complete_with_zero_images(
    mock_getenv, mock_config, mock_init_db, _mock_add_log,
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


@patch('database.add_job_log')
@patch('lightroom_tagger.core.description_service.describe_matched_image')
@patch('lightroom_tagger.core.database.get_undescribed_catalog_images')
@patch('jobs.handlers.init_database')
@patch('jobs.handlers.load_config')
@patch('jobs.handlers.os.getenv', return_value='/tmp/library.db')
def test_batch_describe_should_describe_catalog_images(
    mock_getenv, mock_config, mock_init_db, mock_get, mock_describe, _mock_add_log,
):
    from jobs.handlers import handle_batch_describe

    mock_config.return_value = MagicMock(db_path='/tmp/library.db')
    mock_init_db.return_value = MagicMock()
    mock_get.return_value = [{'key': 'img_001'}, {'key': 'img_002'}]
    mock_describe.return_value = True

    runner = MagicMock()
    runner.db = MagicMock()

    handle_batch_describe(runner, 'test-job', {'image_type': 'catalog'})

    assert mock_describe.call_count == 2
    runner.complete_job.assert_called_once()
    result = runner.complete_job.call_args[0][1]
    assert result['described'] == 2
    assert result['failed'] == 0


@patch('database.add_job_log')
@patch('lightroom_tagger.core.description_service.describe_matched_image')
@patch('lightroom_tagger.core.database.get_undescribed_catalog_images')
@patch('jobs.handlers.init_database')
@patch('jobs.handlers.load_config')
@patch('jobs.handlers.os.getenv', return_value='/tmp/library.db')
def test_batch_describe_should_count_failures(
    mock_getenv, mock_config, mock_init_db, mock_get, mock_describe, _mock_add_log,
):
    from jobs.handlers import handle_batch_describe

    mock_config.return_value = MagicMock(db_path='/tmp/library.db')
    mock_init_db.return_value = MagicMock()
    mock_get.return_value = [{'key': 'img_001'}, {'key': 'img_002'}]
    mock_describe.side_effect = [True, Exception('API error')]

    runner = MagicMock()
    runner.db = MagicMock()

    handle_batch_describe(runner, 'test-job', {'image_type': 'catalog'})

    result = runner.complete_job.call_args[0][1]
    assert result['described'] == 1
    assert result['failed'] == 1


@patch('database.add_job_log')
@patch('lightroom_tagger.core.description_service.describe_matched_image')
@patch('lightroom_tagger.core.database.get_undescribed_catalog_images')
@patch('jobs.handlers.init_database')
@patch('jobs.handlers.load_config')
@patch('jobs.handlers.os.getenv', return_value='/tmp/library.db')
def test_batch_describe_should_stop_after_consecutive_failures(
    mock_getenv, mock_config, mock_init_db, mock_get, mock_describe, mock_add_log,
):
    from jobs.handlers import handle_batch_describe

    mock_config.return_value = MagicMock(db_path='/tmp/library.db')
    mock_init_db.return_value = MagicMock()
    mock_get.return_value = [{'key': f'img_{i:03d}'} for i in range(15)]
    mock_describe.side_effect = Exception('rate limit')

    runner = MagicMock()
    runner.db = MagicMock()

    handle_batch_describe(runner, 'test-job', {'image_type': 'catalog'})

    assert mock_describe.call_count == 10
    result = runner.complete_job.call_args[0][1]
    assert result['failed'] == 10


@patch('database.add_job_log')
@patch('lightroom_tagger.core.database.get_undescribed_catalog_images')
@patch('jobs.handlers.init_database')
@patch('jobs.handlers.load_config')
@patch('jobs.handlers.os.getenv', return_value='/tmp/library.db')
def test_batch_describe_should_set_vision_model_env(
    mock_getenv, mock_config, mock_init_db, mock_get, _mock_add_log,
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

    runner = MagicMock()
    runner.db = MagicMock()

    handle_batch_describe(runner, 'test-job', {
        'image_type': 'catalog',
        'vision_model': 'custom-model',
    })

    assert captured_env.get('model') == 'custom-model'
    assert os.environ.get('DESCRIPTION_VISION_MODEL') is None


@patch('database.add_job_log')
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

    runner.fail_job.assert_called_once_with('test-job', 'config broken')
