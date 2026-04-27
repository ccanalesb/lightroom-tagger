"""Integration: vision_match handler + real match_dump_media stack paths (SQLite)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from lightroom_tagger.core.database import (
    init_database,
    store_image,
    store_instagram_dump_media,
    store_match,
)

from database import create_job, get_job, init_db


def _shortlist_passthrough(_db, _mk, cand_keys, top_k):
    return cand_keys[:top_k]


def _score_row(rep_key: str, insta_key: str) -> dict:
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


def _make_stack(db, tmp_path, rep_name: str, member_names: list[str]) -> tuple[str, list[str]]:
    """Return (representative_key, all_member_keys)."""
    rep_key = store_image(
        db,
        {
            'filename': rep_name,
            'filepath': str(tmp_path / rep_name),
            'date_taken': '2026-03-10T12:00:00',
            'instagram_posted': False,
        },
    )
    (tmp_path / rep_name).write_bytes(b'')
    member_keys = []
    for i, name in enumerate(member_names):
        (tmp_path / name).write_bytes(b'')
        k = store_image(
            db,
            {
                'filename': name,
                'filepath': str(tmp_path / name),
                'date_taken': f'2026-03-1{i + 1}T12:00:00',
                'instagram_posted': False,
            },
        )
        member_keys.append(k)
    db.execute(
        'INSERT INTO image_stacks (representative_key, stack_size, user_modified) '
        'VALUES (?, ?, 0)',
        (rep_key, 1 + len(member_keys)),
    )
    sid_row = db.execute('SELECT last_insert_rowid() AS id').fetchone()
    sid = int(sid_row['id'])
    for k in [rep_key, *member_keys]:
        db.execute(
            'INSERT INTO image_stack_members (stack_id, image_key) VALUES (?, ?)',
            (sid, k),
        )
    db.commit()
    return rep_key, [rep_key, *member_keys]


@patch('lightroom_tagger.scripts.match_instagram_dump.describe_instagram_image', return_value=False)
@patch('lightroom_tagger.scripts.match_instagram_dump.describe_matched_image', return_value=False)
@patch(
    'lightroom_tagger.scripts.match_instagram_dump.shortlist_catalog_candidates_by_clip',
    side_effect=_shortlist_passthrough,
)
@patch('lightroom_tagger.scripts.match_instagram_dump.score_candidates_with_vision')
@patch('jobs.handlers.load_config')
def test_integration_vision_match_representative_only_candidates(
    mock_load_config, mock_score, _mock_shortlist, _dm, _di, tmp_path, monkeypatch
):
    """Vision scoring receives representative keys only; job result reflects stack apply."""
    from jobs.handlers import handle_vision_match

    lib_path = tmp_path / 'library.db'
    jobs_path = tmp_path / 'jobs.db'
    db = init_database(str(lib_path))
    rep_key, all_keys = _make_stack(db, tmp_path, 'a.jpg', ['b.jpg', 'c.jpg'])
    ig_path = tmp_path / 'ig.jpg'
    ig_path.write_bytes(b'')
    store_instagram_dump_media(
        db,
        {
            'media_key': 'ig_stack',
            'file_path': str(ig_path),
            'filename': 'ig.jpg',
            'date_folder': '202603',
            'caption': '',
            'created_at': '2026-03-15T12:00:00',
        },
    )
    db.close()

    captured: dict = {}

    def _score(_db_conn, dump_image, vision_candidates, **kwargs):
        captured['catalog_keys'] = [c['key'] for c in vision_candidates]
        return [_score_row(rep_key, dump_image['key'])]

    mock_score.side_effect = _score

    monkeypatch.setenv('LIBRARY_DB', str(lib_path))
    mock_load_config.return_value = MagicMock(
        vision_model='test',
        match_threshold=0.7,
        phash_weight=0.4,
        desc_weight=0.3,
        vision_weight=0.3,
        ollama_host='http://localhost:11434',
        catalog_path=None,
        small_catalog_path=None,
        matching_workers=2,
    )

    jdb = init_db(str(jobs_path))
    job_id = create_job(
        jdb,
        'vision_match',
        {'media_key': 'ig_stack', 'threshold': 0.5, 'max_workers': 2},
    )

    from jobs.runner import JobRunner

    runner = JobRunner(jdb, db_path=str(jobs_path))
    handle_vision_match(runner, job_id, {'media_key': 'ig_stack', 'threshold': 0.5, 'max_workers': 2})

    assert captured.get('catalog_keys') == [rep_key]
    for k in all_keys:
        if k != rep_key:
            assert k not in captured.get('catalog_keys', [])

    row = get_job(jdb, job_id, include_all_logs=True)
    assert row and row.get('status') == 'completed'
    result = row.get('result') or {}
    assert result.get('stack_apply_applied') == 2
    assert result.get('stack_apply_skipped_conflicts') == 0
    assert result.get('matched', 0) >= 1
    log_text = ' '.join(str(e.get('message', '')) for e in (row.get('logs') or []))
    assert 'Stack-wide apply: members_applied=2' in log_text

    jdb.close()


@patch('lightroom_tagger.scripts.match_instagram_dump.describe_instagram_image', return_value=False)
@patch('lightroom_tagger.scripts.match_instagram_dump.describe_matched_image', return_value=False)
@patch(
    'lightroom_tagger.scripts.match_instagram_dump.shortlist_catalog_candidates_by_clip',
    side_effect=_shortlist_passthrough,
)
@patch('lightroom_tagger.scripts.match_instagram_dump.score_candidates_with_vision')
@patch('jobs.handlers.load_config')
def test_integration_vision_match_stack_apply_skips_conflict_and_surfaces_counts(
    mock_load_config, mock_score, _mock_shortlist, _dm, _di, tmp_path, monkeypatch
):
    """Partial stack apply: conflicting member skipped; payload and logs report skips."""
    from jobs.handlers import handle_vision_match

    lib_path = tmp_path / 'library.db'
    jobs_path = tmp_path / 'jobs.db'
    db = init_database(str(lib_path))
    rep_key, all_keys = _make_stack(db, tmp_path, 'a.jpg', ['b.jpg', 'c.jpg'])
    member_ok = all_keys[1]
    member_conflict = all_keys[2]

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
    db.close()

    mock_score.side_effect = lambda _db, dump_image, _vc, **kw: [
        _score_row(rep_key, dump_image['key']),
    ]

    monkeypatch.setenv('LIBRARY_DB', str(lib_path))
    mock_load_config.return_value = MagicMock(
        vision_model='test',
        match_threshold=0.7,
        phash_weight=0.4,
        desc_weight=0.3,
        vision_weight=0.3,
        ollama_host='http://localhost:11434',
        catalog_path=None,
        small_catalog_path=None,
        matching_workers=2,
    )

    jdb = init_db(str(jobs_path))
    job_id = create_job(
        jdb,
        'vision_match',
        {'media_key': 'ig_new', 'threshold': 0.5, 'max_workers': 2},
    )

    from jobs.runner import JobRunner

    runner = JobRunner(jdb, db_path=str(jobs_path))
    handle_vision_match(runner, job_id, {'media_key': 'ig_new', 'threshold': 0.5, 'max_workers': 2})

    row = get_job(jdb, job_id, include_all_logs=True)
    assert row and row.get('status') == 'completed'
    result = row.get('result') or {}
    assert result.get('stack_apply_applied') == 1
    assert result.get('stack_apply_skipped_conflicts') == 1

    logs = row.get('logs') or []
    joined = ' '.join(str(e.get('message', '')) for e in logs)
    assert 'non-representative catalog candidates filtered' in joined
    assert 'skipped_conflicts=1' in joined

    jdb.close()
