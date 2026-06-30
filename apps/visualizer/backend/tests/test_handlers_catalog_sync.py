"""Tests for catalog_sync job handler."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from lightroom_tagger.core.catalog_sync import CatalogSyncError, CatalogSyncResult


def _make_runner() -> MagicMock:
    runner = MagicMock()
    runner.db = MagicMock()
    runner.is_cancelled.return_value = False
    return runner


@patch('jobs.handlers.catalog.os.path.exists', return_value=True)
@patch('jobs.handlers.catalog.init_database')
@patch('jobs.handlers.catalog.load_config')
@patch('jobs.handlers.catalog.sync_catalog')
@patch('jobs.handlers.catalog._resolve_library_db_or_fail', return_value='/tmp/library.db')
def test_standalone_sync_maps_result_to_job_completion(
    _mock_db: MagicMock,
    mock_sync: MagicMock,
    mock_cfg: MagicMock,
    mock_init_db: MagicMock,
    _mock_exists: MagicMock,
) -> None:
    from jobs.handlers import handle_catalog_sync

    mock_cfg.return_value.catalog_path = '/tmp/catalog.lrcat'
    mock_init_db.return_value = MagicMock()
    mock_sync.return_value = CatalogSyncResult(
        added=3,
        stale=1,
        locking_mode='EXCLUSIVE',
        catalog_total=10,
        library_total=7,
        missing_ids_count=3,
    )

    runner = _make_runner()
    handle_catalog_sync(runner, 'job-sync', {})

    runner.complete_job.assert_called_once()
    payload = runner.complete_job.call_args[0][1]
    assert payload['added'] == 3
    assert payload['stale'] == 1
    assert payload['locking_mode'] == 'EXCLUSIVE'


@patch('jobs.handlers.catalog.os.path.exists', return_value=True)
@patch('jobs.handlers.catalog.init_database')
@patch('jobs.handlers.catalog.load_config')
@patch('jobs.handlers.catalog.sync_catalog')
@patch('jobs.handlers.catalog._resolve_library_db_or_fail', return_value='/tmp/library.db')
def test_standalone_sync_fails_loudly_on_catalog_lock(
    _mock_db: MagicMock,
    mock_sync: MagicMock,
    mock_cfg: MagicMock,
    mock_init_db: MagicMock,
    _mock_exists: MagicMock,
) -> None:
    from jobs.handlers import handle_catalog_sync

    mock_cfg.return_value.catalog_path = '/tmp/catalog.lrcat'
    mock_init_db.return_value = MagicMock()
    mock_sync.side_effect = CatalogSyncError('locked')

    runner = _make_runner()
    handle_catalog_sync(runner, 'job-sync', {})

    runner.fail_job.assert_called_once_with('job-sync', 'locked', severity='warning')
    runner.complete_job.assert_not_called()


@patch('jobs.handlers.stacks._resolve_library_db_or_fail', return_value='/tmp/library.db')
@patch('jobs.handlers.stacks.list_instagram_dump_keys_needing_clip_embedding', return_value=[])
@patch('jobs.handlers.stacks.list_catalog_keys_needing_clip_embedding', return_value=[])
@patch('jobs.handlers.stacks._handle_catalog_similarity_inner')
@patch('jobs.handlers.stacks._handle_batch_stack_detect_inner')
@patch('jobs.handlers.stacks._handle_batch_embed_image_inner')
@patch('jobs.handlers.stacks._handle_catalog_sync_inner')
def test_chain_continues_when_sync_fails(
    mock_sync: MagicMock,
    mock_embed: MagicMock,
    mock_stack: MagicMock,
    mock_sim: MagicMock,
    _mock_cat_need: MagicMock,
    _mock_ig_need: MagicMock,
    _mock_db: MagicMock,
) -> None:
    from jobs.handlers import handle_catalog_cache_build

    mock_sync.return_value = {'failed': True, 'error': 'locked', 'added': 0, 'stale': 0}

    def finish(runner: MagicMock, jid: str, metadata: dict) -> None:
        runner.complete_job(jid, {})

    mock_embed.side_effect = finish
    mock_stack.side_effect = finish
    mock_sim.side_effect = finish

    runner = _make_runner()
    handle_catalog_cache_build(runner, 'job-chain', {})

    mock_embed.assert_called_once()
    mock_stack.assert_called_once()
    mock_sim.assert_called_once()
    payload = runner.complete_job.call_args[0][1]
    assert payload['sync']['failed'] is True
    assert 'embed' in payload


@patch('jobs.handlers.stacks._resolve_library_db_or_fail', return_value='/tmp/library.db')
@patch('jobs.handlers.stacks.list_instagram_dump_keys_needing_clip_embedding', return_value=[])
@patch('jobs.handlers.stacks.list_catalog_keys_needing_clip_embedding', return_value=[])
@patch('jobs.handlers.stacks._handle_catalog_similarity_inner')
@patch('jobs.handlers.stacks._handle_batch_stack_detect_inner')
@patch('jobs.handlers.stacks._handle_batch_embed_image_inner')
@patch('jobs.handlers.stacks._handle_catalog_sync_inner')
def test_chain_runs_sync_before_embed(
    mock_sync: MagicMock,
    mock_embed: MagicMock,
    mock_stack: MagicMock,
    mock_sim: MagicMock,
    _mock_cat_need: MagicMock,
    _mock_ig_need: MagicMock,
    _mock_db: MagicMock,
) -> None:
    from jobs.handlers import handle_catalog_cache_build

    order: list[str] = []

    def mark_sync(*_args, **_kwargs) -> dict:
        order.append('sync')
        return {'added': 0, 'stale': 0, 'locking_mode': 'EXCLUSIVE'}

    def mark_embed(runner: MagicMock, jid: str, metadata: dict) -> None:
        order.append('embed')
        runner.complete_job(jid, {})

    mock_sync.side_effect = mark_sync
    mock_embed.side_effect = mark_embed
    mock_stack.side_effect = lambda r, j, m: (order.append('stack'), r.complete_job(j, {}))
    mock_sim.side_effect = lambda r, j, m: (order.append('similarity'), r.complete_job(j, {}))

    runner = _make_runner()
    handle_catalog_cache_build(runner, 'job-chain', {})

    assert order == ['sync', 'embed', 'stack', 'similarity']


def test_catalog_sync_registered_in_job_handlers() -> None:
    from jobs.handlers import JOB_HANDLERS, handle_catalog_sync

    assert JOB_HANDLERS['catalog_sync'] is handle_catalog_sync
