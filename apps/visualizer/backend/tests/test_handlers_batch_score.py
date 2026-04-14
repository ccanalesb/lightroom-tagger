"""Tests for ``batch_score`` / ``single_score`` job handlers."""

from unittest.mock import MagicMock, patch

from jobs.checkpoint import fingerprint_batch_score


def _make_runner():
    runner = MagicMock()
    runner.db = MagicMock()
    runner.is_cancelled.return_value = False
    return runner


@patch('jobs.handlers.add_job_log')
@patch('jobs.handlers.init_database')
@patch('jobs.handlers.load_config')
@patch('jobs.handlers.os.getenv', return_value='/tmp/library.db')
@patch('jobs.handlers.os.path.exists', return_value=True)
def test_batch_score_should_complete_with_zero_units(
    _mock_exists, mock_getenv, mock_config, mock_init_db, _mock_add_log,
):
    from jobs.handlers import handle_batch_score

    mock_config.return_value = MagicMock(db_path='/tmp/library.db')
    mock_db = MagicMock()
    mock_db.execute.return_value.fetchall.return_value = []
    mock_init_db.return_value = mock_db

    runner = MagicMock()
    runner.db = MagicMock()

    handle_batch_score(runner, 'test-job', {'image_type': 'catalog'})

    runner.complete_job.assert_called_once()
    result = runner.complete_job.call_args[0][1]
    assert result['scored'] == 0
    assert result['skipped'] == 0
    assert result['failed'] == 0
    assert result['total'] == 0


@patch('jobs.handlers.add_job_log')
@patch('jobs.handlers._score_single_image')
@patch('jobs.handlers.get_job')
@patch('jobs.handlers.init_database')
@patch('jobs.handlers.load_config')
@patch('jobs.handlers.os.getenv', return_value='/tmp/library.db')
@patch('jobs.handlers.os.path.exists', return_value=True)
def test_batch_score_checkpoint_skips_already_processed_triplets(
    _mock_exists,
    mock_getenv,
    mock_config,
    mock_init_db,
    mock_get_job,
    mock_score,
    _mock_add_log,
):
    from jobs.handlers import handle_batch_score

    metadata = {
        'image_type': 'catalog',
        'date_filter': 'all',
        'force': False,
        'max_workers': 1,
        'perspective_slugs': ['p1'],
    }
    triples = [('img1', 'catalog', 'p1')]
    fp = fingerprint_batch_score(metadata, triples)

    mock_config.return_value = MagicMock(db_path='/tmp/library.db')
    mock_db = MagicMock()
    mock_db.execute.return_value.fetchall.return_value = [{'key': 'img1'}]
    mock_init_db.return_value = mock_db
    mock_get_job.return_value = {
        'status': 'running',
        'metadata': {
            'checkpoint': {
                'checkpoint_version': 1,
                'job_type': 'batch_score',
                'fingerprint': fp,
                'processed_triplets': ['img1|catalog|p1'],
                'total_at_start': 1,
            },
        },
    }

    runner = _make_runner()
    handle_batch_score(runner, 'job-resume', metadata)

    mock_score.assert_not_called()
    runner.complete_job.assert_called_once()
    res = runner.complete_job.call_args[0][1]
    assert res['total'] == 1
    assert res['scored'] == 0


@patch('jobs.handlers.add_job_log')
@patch('jobs.handlers._score_single_image')
@patch('jobs.handlers.init_database')
@patch('jobs.handlers.load_config')
@patch('jobs.handlers.os.getenv', return_value='/tmp/library.db')
@patch('jobs.handlers.os.path.exists', return_value=True)
def test_batch_score_should_call_score_for_each_triplet(
    _mock_exists, mock_getenv, mock_config, mock_init_db, mock_score, _mock_add_log,
):
    from jobs.handlers import handle_batch_score

    mock_config.return_value = MagicMock(db_path='/tmp/library.db')
    mock_db = MagicMock()
    mock_db.execute.return_value.fetchall.return_value = [
        {'key': 'img1'},
        {'key': 'img2'},
    ]
    mock_init_db.return_value = mock_db
    mock_score.return_value = ('scored', True, None)

    runner = _make_runner()

    handle_batch_score(
        runner,
        'job-smoke',
        {
            'image_type': 'catalog',
            'max_workers': 1,
            'perspective_slugs': ['a', 'b'],
        },
    )

    assert mock_score.call_count == 4
    runner.complete_job.assert_called_once()
    assert runner.complete_job.call_args[0][1]['scored'] == 4


@patch('jobs.handlers.add_job_log')
@patch('jobs.handlers._score_single_image')
@patch('lightroom_tagger.core.database.get_undescribed_catalog_images')
@patch('jobs.handlers.init_database')
@patch('jobs.handlers.load_config')
@patch('jobs.handlers.os.getenv', return_value='/tmp/library.db')
@patch('jobs.handlers.os.path.exists', return_value=True)
@patch('lightroom_tagger.core.database.get_perspective_by_slug')
def test_batch_score_non_force_never_calls_get_undescribed_catalog_images(
    mock_get_perspective,
    _mock_exists,
    mock_getenv,
    mock_config,
    mock_init_db,
    mock_undescribed,
    mock_score,
    _mock_add_log,
):
    from jobs.handlers import handle_batch_score

    mock_get_perspective.side_effect = lambda _db, slug: {
        'slug': slug,
        'prompt_markdown': '',
    }

    mock_config.return_value = MagicMock(db_path='/tmp/library.db')
    mock_db = MagicMock()

    def _execute_side_effect(sql, params=()):
        m = MagicMock()
        q = ' '.join(sql.split())
        if 'SELECT key FROM images' in q:
            m.fetchall.return_value = [{'key': 'img1'}, {'key': 'img2'}]
        elif 'image_scores' in q:
            m.fetchall.return_value = []
        else:
            m.fetchall.return_value = []
        return m

    mock_db.execute.side_effect = _execute_side_effect
    mock_init_db.return_value = mock_db
    mock_score.return_value = ('scored', True, None)

    runner = _make_runner()

    handle_batch_score(
        runner,
        'job-smoke',
        {
            'image_type': 'catalog',
            'force': False,
            'max_workers': 1,
            'perspective_slugs': ['a', 'b'],
        },
    )

    assert mock_undescribed.call_count == 0
    assert mock_score.call_count == 4
