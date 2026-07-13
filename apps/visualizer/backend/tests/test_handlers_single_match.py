import re
from unittest.mock import MagicMock, patch

from jobs.checkpoint import fingerprint_vision_match
from lightroom_tagger.core.vision_op import VisionOpOutcome

_SKIPPED = VisionOpOutcome(status='skipped')
from lightroom_tagger.core.database import (
    init_database,
    store_image,
    store_instagram_dump_media,
    store_match,
)


def test_fingerprint_vision_match_includes_clip_top_k():
    kwargs = dict(
        threshold=0.7,
        weights={'phash': 0.4, 'description': 0.3, 'vision': 0.3},
        month=None,
        year=None,
        last_months=None,
        media_key=None,
        force_reprocess=False,
        force_descriptions=False,
        skip_undescribed=True,
        provider_id=None,
        provider_model=None,
        max_workers=4,
    )
    assert fingerprint_vision_match(**kwargs, clip_top_k=50) != fingerprint_vision_match(
        **kwargs,
        clip_top_k=200,
    )


# log_callback imports add_job_log; real add_job_log + MagicMock runner.db breaks json.dumps(logs).
@patch('jobs.handlers.matching.add_job_log')
@patch('jobs.handlers.matching.match_dump_media')
@patch('jobs.handlers.matching.init_database')
@patch('jobs.handlers.matching.load_config')
@patch('jobs.handlers.matching.update_job_field')
@patch('jobs.handlers.matching.require_library_db', return_value='/tmp/library.db')
@patch('jobs.handlers.matching.os.getenv', return_value='/tmp/library.db')
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


@patch('jobs.handlers.matching.add_job_log')
@patch('jobs.handlers.matching.match_dump_media')
@patch('jobs.handlers.matching.init_database')
@patch('jobs.handlers.matching.load_config')
@patch('jobs.handlers.matching.update_job_field')
@patch('jobs.handlers.matching.require_library_db', return_value='/tmp/library.db')
@patch('jobs.handlers.matching.os.getenv', return_value='/tmp/library.db')
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


@patch('jobs.handlers.matching.add_job_log')
@patch('jobs.handlers.matching.match_dump_media')
@patch('jobs.handlers.matching.init_database')
@patch('jobs.handlers.matching.load_config')
@patch('jobs.handlers.matching.update_job_field')
@patch('jobs.handlers.matching.require_library_db', return_value='/tmp/library.db')
@patch('jobs.handlers.matching.os.getenv', return_value='/tmp/library.db')
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


@patch('jobs.handlers.matching.add_job_log')
@patch('jobs.handlers.matching.match_dump_media')
@patch('jobs.handlers.matching.init_database')
@patch('jobs.handlers.matching.load_config')
@patch('jobs.handlers.matching.update_job_field')
@patch('jobs.handlers.matching.require_library_db', return_value='/tmp/library.db')
@patch('jobs.handlers.matching.os.getenv', return_value='/tmp/library.db')
def test_handle_vision_match_warns_on_invalid_clip_top_k(
    mock_getenv,
    mock_exists,
    mock_update_field,
    mock_config,
    mock_init_db,
    mock_match,
    mock_add_log,
):
    from jobs.handlers import handle_vision_match

    mock_config.return_value = MagicMock(
        vision_model='gemma3:27b',
        match_threshold=0.7,
        phash_weight=0.4,
        desc_weight=0.3,
        vision_weight=0.3,
        ollama_host='http://localhost:11434',
    )
    mock_match.return_value = ({'processed': 1, 'matched': 0, 'skipped': 0}, [])
    mock_init_db.return_value = MagicMock()

    runner = MagicMock()
    runner.db = MagicMock()

    handle_vision_match(runner, 'test-job-id', {'clip_top_k': 'not-a-number'})

    mock_add_log.assert_any_call(
        runner.db,
        'test-job-id',
        'warning',
        "[vision-match] clip_top_k coercion: raw='not-a-number' -> default=50",
    )
    assert mock_match.call_args.kwargs.get('clip_top_k') == 50


def _shortlist_passthrough(_db, _mk, cand_keys, top_k):
    """Preserve pre–Phase-8 test behavior when IG has no CLIP row in the DB."""
    return cand_keys[:top_k]


@patch('lightroom_tagger.scripts.match_instagram_dump.describe_instagram_image', return_value=_SKIPPED)
@patch('lightroom_tagger.scripts.match_instagram_dump.describe_matched_image', return_value=_SKIPPED)
@patch('lightroom_tagger.scripts.match_instagram_dump.score_candidates_with_vision')
@patch('lightroom_tagger.scripts.match_instagram_dump.shortlist_catalog_candidates_by_clip')
def test_shortlist_gates_score_candidates_with_vision(
    mock_shortlist, mock_score, _describe_matched, _describe_insta, tmp_path,
):
    """D-03: scorer never receives more than clip_top_k representative candidates."""
    from lightroom_tagger.scripts.match_instagram_dump import match_dump_media

    db_path = tmp_path / 'lib.db'
    db = init_database(str(db_path))

    for i in range(8):
        p = tmp_path / f'cap{i}.jpg'
        p.write_bytes(b'')
        store_image(
            db,
            {
                'filename': f'cap{i}.jpg',
                'filepath': str(p),
                'date_taken': f'2026-03-{i + 1:02d}T12:00:00',
                'instagram_posted': False,
            },
        )

    ig_path = tmp_path / 'ig_gate.jpg'
    ig_path.write_bytes(b'')
    store_instagram_dump_media(
        db,
        {
            'media_key': 'ig_gate',
            'file_path': str(ig_path),
            'filename': 'ig_gate.jpg',
            'date_folder': '202603',
            'caption': '',
            'created_at': '2026-03-15T12:00:00',
        },
    )

    shortlisted: list[str] = []

    def _shortlist_gate(_db, _mk, cand_keys, top_k):
        out = cand_keys[: min(3, len(cand_keys))]
        shortlisted.clear()
        shortlisted.extend(out)
        return out

    mock_shortlist.side_effect = _shortlist_gate
    mock_score.return_value = []

    match_dump_media(
        db,
        threshold=0.5,
        media_key='ig_gate',
        skip_undescribed=True,
        clip_top_k=3,
    )

    mock_shortlist.assert_called()
    assert mock_shortlist.call_args[0][3] == 3
    assert len(mock_shortlist.call_args[0][2]) >= 8

    mock_score.assert_called()
    for call in mock_score.call_args_list:
        vision_candidates = call[0][2]
        assert len(vision_candidates) <= 3
        assert len(vision_candidates) > 0
        for c in vision_candidates:
            assert c.get('key') in shortlisted
    db.close()


def _score_template_row(rep_key: str, insta_key: str) -> dict:
    return {
        'catalog_key': rep_key,
        'insta_key': insta_key,
        'phash_distance': 0,
        'phash_score': 0.9,
        'desc_similarity': 0.9,
        'vision_result': 'match',
        'vision_score': 0.9,
        'total_score': 0.95,
        'model_used': 'test',
        'vision_reasoning': None,
    }


@patch('lightroom_tagger.scripts.match_instagram_dump.describe_instagram_image', return_value=_SKIPPED)
@patch('lightroom_tagger.scripts.match_instagram_dump.describe_matched_image', return_value=_SKIPPED)
@patch(
    'lightroom_tagger.scripts.match_instagram_dump.shortlist_catalog_candidates_by_clip',
    side_effect=_shortlist_passthrough,
)
@patch('lightroom_tagger.scripts.match_instagram_dump.score_candidates_with_vision')
def test_match_dump_media_representative_only_sends_members_to_scoring(
    mock_score, _mock_shortlist, _describe_matched, _describe_insta, tmp_path,
):
    """Stack members must not appear in the vision/scoring candidate list."""
    from lightroom_tagger.scripts.match_instagram_dump import match_dump_media

    db_path = tmp_path / 'lib.db'
    db = init_database(str(db_path))
    rep_key = store_image(
        db,
        {
            'filename': 'a.jpg',
            'filepath': str(tmp_path / 'a.jpg'),
            'date_taken': '2026-03-10T12:00:00',
            'instagram_posted': False,
        },
    )
    member_key = store_image(
        db,
        {
            'filename': 'b.jpg',
            'filepath': str(tmp_path / 'b.jpg'),
            'date_taken': '2026-03-11T12:00:00',
            'instagram_posted': False,
        },
    )
    (tmp_path / 'a.jpg').write_bytes(b'')
    (tmp_path / 'b.jpg').write_bytes(b'')

    db.execute(
        'INSERT INTO image_stacks (representative_key, stack_size, user_modified) '
        'VALUES (?, ?, 0)',
        (rep_key, 2),
    )
    sid_row = db.execute('SELECT last_insert_rowid() AS id').fetchone()
    sid = int(sid_row['id'])
    db.execute(
        'INSERT INTO image_stack_members (stack_id, image_key) VALUES (?, ?)',
        (sid, rep_key),
    )
    db.execute(
        'INSERT INTO image_stack_members (stack_id, image_key) VALUES (?, ?)',
        (sid, member_key),
    )
    db.commit()

    ig_path = tmp_path / 'ig.jpg'
    ig_path.write_bytes(b'')
    store_instagram_dump_media(
        db,
        {
            'media_key': 'igk1',
            'file_path': str(ig_path),
            'filename': 'ig.jpg',
            'date_folder': '202603',
            'caption': '',
            'created_at': '2026-03-15T12:00:00',
        },
    )

    captured: dict = {}

    def _score(db_conn, dump_image, vision_candidates, **kwargs):
        captured['catalog_keys'] = [c['key'] for c in vision_candidates]
        return [_score_template_row(rep_key, dump_image['key'])]

    mock_score.side_effect = _score

    stats, matches = match_dump_media(
        db,
        threshold=0.5,
        media_key='igk1',
        skip_undescribed=True,
    )

    assert captured.get('catalog_keys') == [rep_key]
    assert member_key not in captured.get('catalog_keys', [])
    assert stats['non_representative_candidates_filtered'] >= 1
    assert len(matches) == 1
    db.close()


@patch('lightroom_tagger.scripts.match_instagram_dump.describe_instagram_image', return_value=_SKIPPED)
@patch('lightroom_tagger.scripts.match_instagram_dump.describe_matched_image', return_value=_SKIPPED)
@patch(
    'lightroom_tagger.scripts.match_instagram_dump.shortlist_catalog_candidates_by_clip',
    side_effect=_shortlist_passthrough,
)
@patch('lightroom_tagger.scripts.match_instagram_dump.score_candidates_with_vision')
def test_match_dump_media_stack_apply_skips_conflicting_member(
    mock_score, _mock_shortlist, _describe_matched, _describe_insta, tmp_path,
):
    """Stack-wide apply must not overwrite a member already matched to another IG key."""
    from lightroom_tagger.scripts.match_instagram_dump import match_dump_media

    db_path = tmp_path / 'lib.db'
    db = init_database(str(db_path))

    def _img(name: str, dt: str) -> str:
        p = tmp_path / name
        p.write_bytes(b'')
        return store_image(
            db,
            {
                'filename': name,
                'filepath': str(p),
                'date_taken': dt,
                'instagram_posted': False,
            },
        )

    rep_key = _img('a.jpg', '2026-03-10T12:00:00')
    member_ok = _img('b.jpg', '2026-03-11T12:00:00')
    member_conflict = _img('c.jpg', '2026-03-12T12:00:00')

    db.execute(
        'INSERT INTO image_stacks (representative_key, stack_size, user_modified) '
        'VALUES (?, ?, 0)',
        (rep_key, 3),
    )
    sid_row = db.execute('SELECT last_insert_rowid() AS id').fetchone()
    sid = int(sid_row['id'])
    for k in (rep_key, member_ok, member_conflict):
        db.execute(
            'INSERT INTO image_stack_members (stack_id, image_key) VALUES (?, ?)',
            (sid, k),
        )
    db.commit()

    store_match(
        db,
        {
            'catalog_key': member_conflict,
            'insta_key': 'other_ig',
            'phash_distance': 1,
            'phash_score': 0.5,
            'desc_similarity': 0.5,
            'vision_result': 'x',
            'vision_score': 0.5,
            'total_score': 0.5,
            'model_used': 'legacy',
            'rank': 1,
        },
        commit=True,
    )

    ig_path = tmp_path / 'ig_new.jpg'
    ig_path.write_bytes(b'')
    store_instagram_dump_media(
        db,
        {
            'media_key': 'ig_new',
            'file_path': str(ig_path),
            'filename': 'ig_new.jpg',
            'date_folder': '202603',
            'caption': '',
            'created_at': '2026-03-15T12:00:00',
        },
    )

    mock_score.side_effect = lambda _db, dump_image, _vc, **kw: [
        _score_template_row(rep_key, dump_image['key']),
    ]

    stats, matches = match_dump_media(
        db,
        threshold=0.5,
        media_key='ig_new',
        skip_undescribed=True,
    )

    assert stats['stack_members_applied'] == 1
    assert stats['stack_members_skipped_conflicts'] == 1
    assert len(matches) == 1
    lr_keys = matches[0].get('_lightroom_catalog_keys') or []
    assert rep_key in lr_keys and member_ok in lr_keys
    assert member_conflict not in lr_keys

    row_other = db.execute(
        'SELECT 1 FROM matches WHERE catalog_key = ? AND insta_key = ?',
        (member_conflict, 'other_ig'),
    ).fetchone()
    assert row_other is not None
    row_bad = db.execute(
        'SELECT 1 FROM matches WHERE catalog_key = ? AND insta_key = ?',
        (member_conflict, 'ig_new'),
    ).fetchone()
    assert row_bad is None

    row_ok = db.execute(
        'SELECT 1 FROM matches WHERE catalog_key = ? AND insta_key = ?',
        (member_ok, 'ig_new'),
    ).fetchone()
    assert row_ok is not None
    db.close()


@patch('lightroom_tagger.scripts.match_instagram_dump.describe_instagram_image', return_value=_SKIPPED)
@patch('lightroom_tagger.scripts.match_instagram_dump.describe_matched_image', return_value=_SKIPPED)
@patch(
    'lightroom_tagger.scripts.match_instagram_dump.shortlist_catalog_candidates_by_clip',
    side_effect=_shortlist_passthrough,
)
@patch('lightroom_tagger.scripts.match_instagram_dump.score_candidates_with_vision')
def test_match_dump_media_stack_apply_reaches_all_non_conflict_members(
    mock_score, _mock_shortlist, _describe_matched, _describe_insta, tmp_path,
):
    """When no member conflicts, stack-wide apply persists one row per non-rep member."""
    from lightroom_tagger.scripts.match_instagram_dump import match_dump_media

    db_path = tmp_path / 'lib.db'
    db = init_database(str(db_path))

    def _img(name: str, dt: str) -> str:
        p = tmp_path / name
        p.write_bytes(b'')
        return store_image(
            db,
            {
                'filename': name,
                'filepath': str(p),
                'date_taken': dt,
                'instagram_posted': False,
            },
        )

    rep_key = _img('a.jpg', '2026-03-10T12:00:00')
    m1 = _img('b.jpg', '2026-03-11T12:00:00')
    m2 = _img('c.jpg', '2026-03-12T12:00:00')

    db.execute(
        'INSERT INTO image_stacks (representative_key, stack_size, user_modified) '
        'VALUES (?, ?, 0)',
        (rep_key, 3),
    )
    sid_row = db.execute('SELECT last_insert_rowid() AS id').fetchone()
    sid = int(sid_row['id'])
    for k in (rep_key, m1, m2):
        db.execute(
            'INSERT INTO image_stack_members (stack_id, image_key) VALUES (?, ?)',
            (sid, k),
        )
    db.commit()

    ig_path = tmp_path / 'ig_stack.jpg'
    ig_path.write_bytes(b'')
    store_instagram_dump_media(
        db,
        {
            'media_key': 'ig_stack',
            'file_path': str(ig_path),
            'filename': 'ig_stack.jpg',
            'date_folder': '202603',
            'caption': '',
            'created_at': '2026-03-15T12:00:00',
        },
    )

    mock_score.side_effect = lambda _db, dump_image, _vc, **kw: [
        _score_template_row(rep_key, dump_image['key']),
    ]

    stats, matches = match_dump_media(
        db,
        threshold=0.5,
        media_key='ig_stack',
        skip_undescribed=True,
    )

    assert stats['stack_members_applied'] == 2
    assert stats['stack_members_skipped_conflicts'] == 0
    lr_keys = matches[0].get('_lightroom_catalog_keys') or []
    assert set(lr_keys) == {rep_key, m1, m2}

    for ck in (m1, m2):
        assert db.execute(
            'SELECT 1 FROM matches WHERE catalog_key = ? AND insta_key = ?',
            (ck, 'ig_stack'),
        ).fetchone()
    db.close()


@patch('jobs.handlers.matching.add_job_log')
@patch('jobs.handlers.matching.match_dump_media')
@patch('jobs.handlers.matching.init_database')
@patch('jobs.handlers.matching.load_config')
@patch('jobs.handlers.matching.update_job_field')
@patch('jobs.handlers.matching.require_library_db', return_value='/tmp/library.db')
@patch('jobs.handlers.matching.os.getenv', return_value='/tmp/library.db')
def test_handle_vision_match_result_payload_includes_stack_apply_counts(
    mock_getenv,
    mock_require,
    mock_update_field,
    mock_config,
    mock_init_db,
    mock_match,
    _mock_add_log,
):
    from jobs.handlers import handle_vision_match

    mock_config.return_value = MagicMock(
        vision_model='gemma3:27b',
        match_threshold=0.7,
        phash_weight=0.4,
        desc_weight=0.3,
        vision_weight=0.3,
        ollama_host='http://localhost:11434',
        catalog_path=None,
        small_catalog_path=None,
    )
    mock_match.return_value = (
        {
            'processed': 1,
            'matched': 1,
            'skipped': 0,
            'descriptions_generated': 0,
            'non_representative_candidates_filtered': 0,
            'stack_members_applied': 2,
            'stack_members_skipped_conflicts': 1,
            'stack_members_skipped_other': 0,
        },
        [],
    )
    mock_init_db.return_value = MagicMock()

    runner = MagicMock()
    runner.db = MagicMock()
    runner.is_cancelled.return_value = False

    handle_vision_match(runner, 'job-stack', {})

    runner.complete_job.assert_called()
    _jid, payload = runner.complete_job.call_args[0]
    assert payload['stack_apply_applied'] == 2
    assert payload['stack_apply_skipped_conflicts'] == 1
    assert payload['stack_apply_skipped_other'] == 0
    assert payload.get('clip_prefilter_candidates_in') == 0
    assert payload.get('clip_prefilter_shortlist_total') == 0
    assert payload.get('vision_judgments_total') == 0


@patch('jobs.handlers.matching.add_job_log')
@patch('jobs.handlers.matching.match_dump_media')
@patch('jobs.handlers.matching.init_database')
@patch('jobs.handlers.matching.load_config')
@patch('jobs.handlers.matching.update_job_field')
@patch('jobs.handlers.matching.require_library_db', return_value='/tmp/library.db')
@patch('jobs.handlers.matching.os.getenv', return_value='/tmp/library.db')
def test_handle_vision_match_clip_top_k_bounds(
    mock_getenv,
    mock_require,
    mock_update_field,
    mock_config,
    mock_init_db,
    mock_match,
    _mock_add_log,
):
    from jobs.handlers import handle_vision_match

    mock_config.return_value = MagicMock(
        vision_model='gemma3:27b',
        match_threshold=0.7,
        phash_weight=0.4,
        desc_weight=0.3,
        vision_weight=0.3,
        ollama_host='http://localhost:11434',
        matching_workers=4,
        catalog_path=None,
        small_catalog_path=None,
    )
    mock_match.return_value = (
        {
            'processed': 1,
            'matched': 0,
            'skipped': 0,
            'clip_prefilter_candidates_in': 0,
            'clip_prefilter_shortlist_total': 0,
            'vision_judgments_total': 0,
        },
        [],
    )
    mock_init_db.return_value = MagicMock()

    runner = MagicMock()
    runner.db = MagicMock()
    runner.is_cancelled.return_value = False

    handle_vision_match(runner, 'job-k', {'clip_top_k': 0})
    assert mock_match.call_args.kwargs['clip_top_k'] == 1

    handle_vision_match(runner, 'job-k', {'clip_top_k': 9999})
    assert mock_match.call_args.kwargs['clip_top_k'] == 500


@patch('jobs.handlers.matching.add_job_log')
@patch('jobs.handlers.matching.match_dump_media')
@patch('jobs.handlers.matching.init_database')
@patch('jobs.handlers.matching.load_config')
@patch('jobs.handlers.matching.update_job_field')
@patch('jobs.handlers.matching.require_library_db', return_value='/tmp/library.db')
@patch('jobs.handlers.matching.os.getenv', return_value='/tmp/library.db')
def test_handle_vision_match_prefilter_summary_log_regex(
    mock_getenv,
    mock_require,
    mock_update_field,
    mock_config,
    mock_init_db,
    mock_match,
    mock_add_log,
):
    from jobs.handlers import handle_vision_match

    stats_out = {
        'processed': 1,
        'matched': 0,
        'skipped': 0,
        'clip_prefilter_candidates_in': 12,
        'clip_prefilter_shortlist_total': 5,
        'vision_judgments_total': 5,
    }

    def _side_effect(*_a, **_kwargs):
        cb = _kwargs.get('on_media_complete')
        if cb:
            cb('mk1', stats_out)
        return stats_out, []

    mock_match.side_effect = _side_effect
    mock_config.return_value = MagicMock(
        vision_model='gemma3:27b',
        match_threshold=0.7,
        phash_weight=0.4,
        desc_weight=0.3,
        vision_weight=0.3,
        ollama_host='http://localhost:11434',
        matching_workers=4,
        catalog_path=None,
        small_catalog_path=None,
    )
    mock_init_db.return_value = MagicMock()

    runner = MagicMock()
    runner.db = MagicMock()
    runner.is_cancelled.return_value = False

    handle_vision_match(runner, 'job-log', {})

    pat = re.compile(
        r'^vision-match-prefilter-summary date_window_in=\d+ '
        r'clip_shortlist_out=\d+ judgments=\d+$'
    )
    msgs = [c[0][3] for c in mock_add_log.call_args_list if len(c[0]) > 3]
    assert any(pat.match(m) for m in msgs), msgs
