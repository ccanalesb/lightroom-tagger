"""Tests for catalog_cache_build composite job (Phase 08 CACHE-01)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


def _make_runner() -> MagicMock:
    runner = MagicMock()
    runner.db = MagicMock()
    runner.is_cancelled.return_value = False
    return runner


def test_catalog_cache_build_registered_in_job_handlers() -> None:
    from jobs.handlers import JOB_HANDLERS, handle_catalog_cache_build

    assert JOB_HANDLERS['catalog_cache_build'] is handle_catalog_cache_build


@patch('jobs.handlers.stacks._resolve_library_db_or_fail', return_value='/tmp/library.db')
@patch('jobs.handlers.stacks.list_instagram_dump_keys_needing_clip_embedding', return_value=[])
@patch('jobs.handlers.stacks.list_catalog_keys_needing_clip_embedding', return_value=[])
@patch('jobs.handlers.stacks._handle_catalog_similarity_inner')
@patch('jobs.handlers.stacks._handle_batch_stack_detect_inner')
@patch('jobs.handlers.stacks._handle_batch_embed_image_inner')
@patch('jobs.handlers.stacks._handle_catalog_sync_inner')
def test_chain_runs_stages_in_order(
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
        runner.complete_job(
            jid,
            {'embedded': 0, 'skipped': 0, 'failed': 0, 'total': 0},
        )

    def mark_stack(runner: MagicMock, jid: str, metadata: dict) -> None:
        order.append('stack')
        runner.complete_job(
            jid,
            {
                'stacks_created': 0,
                'images_skipped_no_date': 0,
                'images_skipped_already_stacked': 0,
            },
        )

    def mark_sim(runner: MagicMock, jid: str, metadata: dict) -> None:
        order.append('similarity')
        runner.complete_job(
            jid,
            {
                'groups_created': 0,
                'candidates_created': 0,
                'skipped_non_primary': 0,
                'skipped_no_embedding': 0,
            },
        )

    mock_sync.side_effect = mark_sync
    mock_embed.side_effect = mark_embed
    mock_stack.side_effect = mark_stack
    mock_sim.side_effect = mark_sim

    runner = _make_runner()

    handle_catalog_cache_build(runner, 'job-chain', {})

    assert order == ['sync', 'embed', 'stack', 'similarity']
    runner.complete_job.assert_called_once()
    payload = runner.complete_job.call_args[0][1]
    assert payload['catalog_cache_build'] is True
    assert 'sync' in payload and 'embed' in payload and 'stack' in payload and 'similarity' in payload


@patch('jobs.handlers.stacks._resolve_library_db_or_fail', return_value='/tmp/library.db')
@patch('jobs.handlers.stacks.list_instagram_dump_keys_needing_clip_embedding', return_value=[])
@patch('jobs.handlers.stacks.list_catalog_keys_needing_clip_embedding', return_value=[])
@patch('jobs.handlers.stacks._handle_catalog_similarity_inner')
@patch('jobs.handlers.stacks._handle_batch_stack_detect_inner')
@patch('jobs.handlers.stacks._handle_batch_embed_image_inner')
@patch('jobs.handlers.stacks._handle_catalog_sync_inner', return_value={'added': 0, 'stale': 0})
def test_chain_honors_cancel_between_stages(
    mock_sync: MagicMock,
    mock_embed: MagicMock,
    mock_stack: MagicMock,
    mock_sim: MagicMock,
    _mock_cat_need: MagicMock,
    _mock_ig_need: MagicMock,
    _mock_db: MagicMock,
) -> None:
    from jobs.handlers import handle_catalog_cache_build

    cancel_after_embed = {'hit': False}

    def mark_embed(runner: MagicMock, jid: str, metadata: dict) -> None:
        cancel_after_embed['hit'] = True
        runner.complete_job(
            jid,
            {'embedded': 0, 'skipped': 0, 'failed': 0, 'total': 0},
        )

    mock_embed.side_effect = mark_embed

    runner = _make_runner()

    def is_cancelled(jid: str) -> bool:
        return cancel_after_embed['hit']

    runner.is_cancelled.side_effect = is_cancelled

    handle_catalog_cache_build(runner, 'job-cancel', {})

    mock_stack.assert_not_called()
    mock_sim.assert_not_called()
    runner.finalize_cancelled.assert_called_once_with('job-cancel')
    runner.complete_job.assert_not_called()


@patch('jobs.handlers.stacks._resolve_library_db_or_fail', return_value='/tmp/library.db')
@patch('jobs.handlers.stacks.add_job_log')
@patch('jobs.handlers.stacks.list_instagram_dump_keys_needing_clip_embedding', return_value=[])
@patch('jobs.handlers.stacks.list_catalog_keys_needing_clip_embedding', return_value=[])
@patch('jobs.handlers.stacks._handle_catalog_similarity_inner')
@patch('jobs.handlers.stacks._handle_batch_stack_detect_inner')
@patch('jobs.handlers.stacks._handle_batch_embed_image_inner')
@patch('jobs.handlers.stacks._handle_catalog_sync_inner', return_value={'added': 0, 'stale': 0})
def test_stage_banner_logs_include_similarity_stage(
    mock_sync: MagicMock,
    mock_embed: MagicMock,
    mock_stack: MagicMock,
    mock_sim: MagicMock,
    _mock_cat_need: MagicMock,
    _mock_ig_need: MagicMock,
    mock_log: MagicMock,
    _mock_db: MagicMock,
) -> None:
    from jobs.handlers import handle_catalog_cache_build

    def finish(runner: MagicMock, jid: str, metadata: dict) -> None:
        runner.complete_job(jid, {})

    mock_embed.side_effect = finish
    mock_stack.side_effect = finish
    mock_sim.side_effect = finish

    runner = _make_runner()
    handle_catalog_cache_build(runner, 'job-log', {})

    messages = [call.args[3] for call in mock_log.call_args_list if len(call.args) > 3]
    joined = '\n'.join(messages)
    assert 'stage=similarity' in joined
    assert '[catalog-cache-build]' in joined


def test_catalog_cache_stage_mapped_progress_splits_bar() -> None:
    from jobs.handlers.stacks import _catalog_cache_stage_mapped_progress

    assert _catalog_cache_stage_mapped_progress(0, 5) == 5
    assert _catalog_cache_stage_mapped_progress(3, 100) == 100
    mid = _catalog_cache_stage_mapped_progress(1, 52)
    assert 28 <= mid <= 52
