"""Tests for ``batch_score`` / ``single_score`` job handlers."""

from unittest.mock import MagicMock, patch

from jobs.checkpoint import fingerprint_batch_score
from lightroom_tagger.core.vision_op import VisionOpOutcome

_WRITTEN = VisionOpOutcome(status='written')


def _make_runner():
    runner = MagicMock()
    runner.db = MagicMock()
    runner.is_cancelled.return_value = False
    return runner


@patch('jobs.handlers.analyze.add_job_log')
@patch('jobs.handlers.analyze.init_database')
@patch('jobs.handlers.analyze.load_config')
@patch('jobs.handlers.analyze.os.getenv', return_value='/tmp/library.db')
@patch('jobs.handlers.common.require_library_db', return_value='/tmp/library.db')
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


@patch('jobs.handlers.analyze.add_job_log')
@patch('jobs.handlers.analyze._score_single_image')
@patch('jobs.handlers.analyze.get_job')
@patch('jobs.handlers.analyze.init_database')
@patch('jobs.handlers.analyze.load_config')
@patch('jobs.handlers.analyze.os.getenv', return_value='/tmp/library.db')
@patch('jobs.handlers.common.require_library_db', return_value='/tmp/library.db')
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


@patch('jobs.handlers.analyze.add_job_log')
@patch('jobs.handlers.analyze.fingerprint_batch_score', return_value='fp-score-stable')
@patch('jobs.handlers.analyze._score_single_image')
@patch('jobs.handlers.analyze.get_job')
@patch('jobs.handlers.analyze.init_database')
@patch('jobs.handlers.analyze.load_config')
@patch('jobs.handlers.analyze.os.getenv', return_value='/tmp/library.db')
@patch('jobs.handlers.common.require_library_db', return_value='/tmp/library.db')
def test_batch_score_fingerprint_mismatch_resets_and_reprocesses(
    _mock_exists,
    mock_getenv,
    mock_config,
    mock_init_db,
    mock_get_job,
    mock_score,
    _mock_fp,
    mock_add_log,
):
    from jobs.handlers import handle_batch_score

    metadata = {
        'image_type': 'catalog',
        'date_filter': 'all',
        'force': False,
        'max_workers': 1,
        'perspective_slugs': ['p1'],
    }

    mock_config.return_value = MagicMock(db_path='/tmp/library.db')
    mock_db = MagicMock()

    def _exec(sql, params=()):
        m = MagicMock()
        q = ' '.join(sql.split())
        if 'FROM images' in q and 'image_scores' not in q:
            m.fetchall.return_value = [{'key': 'img1'}]
        elif 'image_scores' in q:
            m.fetchall.return_value = []
        else:
            m.fetchall.return_value = []
        return m

    mock_db.execute.side_effect = _exec
    mock_init_db.return_value = mock_db

    mock_get_job.return_value = {
        'status': 'running',
        'metadata': {
            'checkpoint': {
                'checkpoint_version': 1,
                'job_type': 'batch_score',
                'fingerprint': 'fp-score-stale-old',
                'processed_triplets': ['img1|catalog|p1'],
                'total_at_start': 1,
            },
        },
    }
    mock_score.return_value = _WRITTEN

    runner = _make_runner()
    handle_batch_score(runner, 'job-fpm-score', metadata)

    log_messages = [c.args[3] for c in mock_add_log.call_args_list if len(c.args) >= 4]
    assert any(
        'checkpoint mismatch: batch_score fingerprint changed, starting fresh' in m
        for m in log_messages
    ), log_messages
    mock_score.assert_called_once()
    runner.complete_job.assert_called_once()
    res = runner.complete_job.call_args[0][1]
    assert res['scored'] == 1
    assert res['total'] == 1


@patch('jobs.handlers.analyze.add_job_log')
@patch('jobs.handlers.analyze._score_single_image')
@patch('jobs.handlers.analyze.get_job')
@patch('jobs.handlers.analyze.init_database')
@patch('jobs.handlers.analyze.load_config')
@patch('jobs.handlers.analyze.os.getenv', return_value='/tmp/library.db')
@patch('jobs.handlers.common.require_library_db', return_value='/tmp/library.db')
def test_batch_score_stale_checkpoint_all_processed_completes(
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

    triples = [
        ('img_z', 'catalog', 'p1'),
        ('img_a', 'catalog', 'p1'),
    ]
    fp = fingerprint_batch_score(metadata, triples)

    mock_config.return_value = MagicMock(db_path='/tmp/library.db')
    mock_db = MagicMock()

    def _exec(sql, params=()):
        m = MagicMock()
        q = ' '.join(sql.split())
        if 'FROM images' in q and 'image_scores' not in q:
            m.fetchall.return_value = [{'key': 'img_z'}, {'key': 'img_a'}]
        elif 'image_scores' in q:
            m.fetchall.return_value = []
        else:
            m.fetchall.return_value = []
        return m

    mock_db.execute.side_effect = _exec
    mock_init_db.return_value = mock_db

    mock_get_job.return_value = {
        'status': 'running',
        'metadata': {
            'checkpoint': {
                'checkpoint_version': 1,
                'job_type': 'batch_score',
                'fingerprint': fp,
                'processed_triplets': ['img_a|catalog|p1', 'img_z|catalog|p1'],
                'total_at_start': 2,
            },
        },
    }

    runner = _make_runner()
    handle_batch_score(runner, 'job-stale-score', metadata)

    mock_score.assert_not_called()
    runner.complete_job.assert_called_once()
    res = runner.complete_job.call_args[0][1]
    assert res['scored'] == 0
    assert res['total'] == 2


@patch('jobs.handlers.analyze.add_job_log')
@patch('jobs.handlers.analyze._score_single_image')
@patch('jobs.handlers.analyze.init_database')
@patch('jobs.handlers.analyze.load_config')
@patch('jobs.handlers.analyze.os.getenv', return_value='/tmp/library.db')
@patch('jobs.handlers.common.require_library_db', return_value='/tmp/library.db')
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
    mock_score.return_value = _WRITTEN

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


@patch('jobs.handlers.analyze.add_job_log')
@patch('jobs.handlers.analyze._score_single_image')
@patch('lightroom_tagger.core.database.get_undescribed_catalog_images')
@patch('jobs.handlers.analyze.init_database')
@patch('jobs.handlers.analyze.load_config')
@patch('jobs.handlers.analyze.os.getenv', return_value='/tmp/library.db')
@patch('jobs.handlers.common.require_library_db', return_value='/tmp/library.db')
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
        if 'FROM images' in q and 'image_scores' not in q:
            m.fetchall.return_value = [{'key': 'img1'}, {'key': 'img2'}]
        elif 'image_scores' in q:
            m.fetchall.return_value = []
        else:
            m.fetchall.return_value = []
        return m

    mock_db.execute.side_effect = _execute_side_effect
    mock_init_db.return_value = mock_db
    mock_score.return_value = _WRITTEN

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


_FAILED_INVALID = VisionOpOutcome(status='failed', reason='model returned empty or invalid score response')


@patch('jobs.handlers.analyze.add_job_log')
@patch('jobs.handlers.analyze._score_single_image')
@patch('jobs.handlers.analyze.get_job')
@patch('jobs.handlers.analyze.init_database')
@patch('jobs.handlers.analyze.load_config')
@patch('jobs.handlers.analyze.os.getenv', return_value='/tmp/library.db')
@patch('jobs.handlers.common.require_library_db', return_value='/tmp/library.db')
def test_batch_score_invalid_model_result_excluded_from_checkpoint(
    _mock_exists,
    mock_getenv,
    mock_config,
    mock_init_db,
    mock_get_job,
    mock_score,
    _mock_add_log,
):
    from jobs.checkpoint import fingerprint_batch_score
    from jobs.handlers import handle_batch_score

    metadata = {
        'image_type': 'catalog',
        'date_filter': 'all',
        'force': False,
        'max_workers': 1,
        'perspective_slugs': ['p1'],
    }
    triples = [('img_ok', 'catalog', 'p1'), ('img_bad', 'catalog', 'p1')]
    fp = fingerprint_batch_score(metadata, triples)

    mock_config.return_value = MagicMock(db_path='/tmp/library.db')
    mock_db = MagicMock()

    def _exec(sql, params=()):
        m = MagicMock()
        q = ' '.join(sql.split())
        if 'FROM images' in q and 'image_scores' not in q:
            m.fetchall.return_value = [{'key': 'img_ok'}, {'key': 'img_bad'}]
        elif 'image_scores' in q:
            m.fetchall.return_value = []
        else:
            m.fetchall.return_value = []
        return m

    mock_db.execute.side_effect = _exec
    mock_init_db.return_value = mock_db

    def score_side_effect(*args, **_kwargs):
        key = args[1]
        if key == 'img_ok':
            return _WRITTEN
        return _FAILED_INVALID

    mock_score.side_effect = score_side_effect

    runner = _make_runner()
    handle_batch_score(runner, 'job-score-invalid-first', metadata)

    first_result = runner.complete_job.call_args[0][1]
    assert first_result['scored'] == 1
    assert first_result['failed'] == 1
    last_cp = runner.persist_checkpoint.call_args_list[-1][0][1]
    assert last_cp['processed_triplets'] == ['img_ok|catalog|p1']
    assert 'img_bad|catalog|p1' not in last_cp['processed_triplets']

    mock_score.reset_mock()
    mock_score.side_effect = None
    mock_score.return_value = _WRITTEN
    mock_get_job.return_value = {
        'status': 'running',
        'metadata': {
            'checkpoint': {
                'checkpoint_version': 1,
                'job_type': 'batch_score',
                'fingerprint': fp,
                'processed_triplets': ['img_ok|catalog|p1'],
                'total_at_start': 2,
            },
        },
    }

    handle_batch_score(runner, 'job-score-invalid-resume', metadata)

    mock_score.assert_called_once()
    assert mock_score.call_args[0][1] == 'img_bad'
    resume_result = runner.complete_job.call_args[0][1]
    assert resume_result['scored'] == 1
    assert resume_result['total'] == 2
