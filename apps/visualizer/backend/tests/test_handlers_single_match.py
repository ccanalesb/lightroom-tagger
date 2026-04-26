from unittest.mock import MagicMock, patch

from lightroom_tagger.core.database import (
    init_database,
    store_image,
    store_instagram_dump_media,
)


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


@patch('lightroom_tagger.scripts.match_instagram_dump.describe_instagram_image', return_value=False)
@patch('lightroom_tagger.scripts.match_instagram_dump.describe_matched_image', return_value=False)
@patch('lightroom_tagger.scripts.match_instagram_dump.score_candidates_with_vision')
def test_match_dump_media_representative_only_sends_members_to_scoring(
    mock_score, _describe_matched, _describe_insta, tmp_path,
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
