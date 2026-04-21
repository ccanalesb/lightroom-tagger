from unittest.mock import patch, MagicMock


# log_callback imports add_job_log; real add_job_log + MagicMock runner.db breaks json.dumps(logs).
@patch('database.add_job_log')
@patch('jobs.handlers.match_dump_media')
@patch('jobs.handlers.init_database')
@patch('jobs.handlers.load_config')
@patch('jobs.handlers.update_job_field')
@patch('jobs.handlers.require_library_db', return_value='/tmp/library.db')
@patch('jobs.handlers.os.getenv', return_value='/tmp/library.db')
def test_handle_vision_match_passes_media_key(mock_getenv, mock_exists, mock_update_field,
                                               mock_config, mock_init_db, mock_match, _mock_add_log):
    from jobs.handlers import handle_vision_match

    mock_config.return_value = MagicMock(
        vision_model='gemma3:27b', match_threshold=0.7,
        phash_weight=0.4, desc_weight=0.3, vision_weight=0.3,
        ollama_host='http://localhost:11434'
    )
    mock_match.return_value = ({'processed': 1, 'matched': 1, 'skipped': 0}, [])
    mock_init_db.return_value = MagicMock()

    runner = MagicMock()
    runner.db = MagicMock()

    handle_vision_match(runner, 'test-job-id', {'media_key': '202603/12345'})

    _, kwargs = mock_match.call_args
    assert kwargs.get('media_key') == '202603/12345'


@patch('database.add_job_log')
@patch('jobs.handlers.match_dump_media')
@patch('jobs.handlers.init_database')
@patch('jobs.handlers.load_config')
@patch('jobs.handlers.update_job_field')
@patch('jobs.handlers.require_library_db', return_value='/tmp/library.db')
@patch('jobs.handlers.os.getenv', return_value='/tmp/library.db')
def test_handle_vision_match_passes_custom_weights(mock_getenv, mock_exists, mock_update_field,
                                                    mock_config, mock_init_db, mock_match, _mock_add_log):
    from jobs.handlers import handle_vision_match

    mock_config.return_value = MagicMock(
        vision_model='gemma3:27b', match_threshold=0.7,
        phash_weight=0.4, desc_weight=0.3, vision_weight=0.3,
        ollama_host='http://localhost:11434',
        matching_workers=4,
    )
    mock_match.return_value = ({'processed': 1, 'matched': 0, 'skipped': 0}, [])
    mock_init_db.return_value = MagicMock()

    runner = MagicMock()
    runner.db = MagicMock()

    custom_weights = {'phash': 0.0, 'description': 0.0, 'vision': 1.0}
    handle_vision_match(runner, 'test-job-id', {'weights': custom_weights})

    _, kwargs = mock_match.call_args
    assert kwargs.get('weights') == custom_weights, (
        f"Expected weights={custom_weights}, got weights={kwargs.get('weights')}"
    )


@patch('database.add_job_log')
@patch('jobs.handlers.match_dump_media')
@patch('jobs.handlers.init_database')
@patch('jobs.handlers.load_config')
@patch('jobs.handlers.update_job_field')
@patch('jobs.handlers.require_library_db', return_value='/tmp/library.db')
@patch('jobs.handlers.os.getenv', return_value='/tmp/library.db')
def test_handle_vision_match_passes_skip_undescribed(mock_getenv, mock_exists, mock_update_field,
                                               mock_config, mock_init_db, mock_match, _mock_add_log):
    from jobs.handlers import handle_vision_match

    mock_config.return_value = MagicMock(
        vision_model='gemma3:27b', match_threshold=0.7,
        phash_weight=0.4, desc_weight=0.3, vision_weight=0.3,
        ollama_host='http://localhost:11434'
    )
    mock_match.return_value = ({'processed': 1, 'matched': 1, 'skipped': 0}, [])
    mock_init_db.return_value = MagicMock()

    runner = MagicMock()
    runner.db = MagicMock()

    handle_vision_match(runner, 'test-job-id', {'skip_undescribed': False})
    assert mock_match.call_args.kwargs.get('skip_undescribed') is False

    handle_vision_match(runner, 'test-job-id', {})
    assert mock_match.call_args.kwargs.get('skip_undescribed') is True
