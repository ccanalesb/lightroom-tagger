"""Describe, score, and unified batch-analyze job handlers."""

import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import MagicMock

from database import add_job_log, get_job, update_job_field

from lightroom_tagger.core import cancel_scope
from lightroom_tagger.core.config import load_config
from lightroom_tagger.core.database import init_database

from .db_lifecycle import make_managed_library_db
from ..checkpoint import fingerprint_batch_describe, fingerprint_batch_score, job_type_entry, load_resume_state

managed_library_db = make_managed_library_db(globals())

from .common import (
    _CHECKPOINT_MAX_ENTRIES,
    _CATALOG_NOT_VIDEO_SQL,
    _failure_severity_from_exception,
    _resolve_date_window,
    _resolve_library_db_or_fail,
    _select_catalog_keys,
    _select_instagram_keys,
)
from .path_diagnostics import PathSkipDiagnostics, empty_skip_reason_counts

def _merge_skip_reason_counts(*parts) -> dict[str, int]:
    merged = empty_skip_reason_counts()
    for part in parts:
        if not isinstance(part, dict):
            continue
        for key in merged:
            raw = part.get(key, 0)
            try:
                merged[key] += int(raw)
            except (TypeError, ValueError):
                pass
    return merged


def _record_path_skip_from_status(
    path_diag: PathSkipDiagnostics | None,
    lib_db,
    key: str,
    itype: str,
    status: str,
    *,
    log_prefix: str = '',
) -> None:
    """When an item was skipped, classify path accessibility for grouped counts."""
    if path_diag is None or status != 'skipped':
        return
    _, skip_reason, skip_detail = path_diag.classify(key)
    if skip_reason:
        path_diag.record_skip(skip_reason, key, detail=skip_detail, log_prefix=log_prefix)


def _select_catalog_keys_missing_visual_tags(
    lib_db,
    *,
    months: int | None,
    year: str | None,
    min_rating: int | None,
) -> list[tuple[str, str]]:
    """Catalog images that already have a description row with ``dominant_colors IS NULL``.

    Used for user-initiated backfill of visual tags (D-18). Respects the same
    date and rating window as :func:`_select_catalog_keys`.
    """
    params: list = []
    sql = (
        "SELECT i.key AS key FROM images i "
        "WHERE EXISTS ("
        "  SELECT 1 FROM image_descriptions d "
        "  WHERE d.image_key = i.key AND d.image_type = 'catalog' AND d.dominant_colors IS NULL"
        ")"
    )
    date_col = "i.date_taken"
    rating_col = "i.rating"
    conditions: list[str] = [_CATALOG_NOT_VIDEO_SQL]
    if months:
        conditions.append(f"{date_col} >= date('now', ?)")
        params.append(f'-{months} months')
    if year is not None:
        conditions.append(f"strftime('%Y', {date_col}) = ?")
        params.append(year)
    if min_rating is not None:
        conditions.append(f"{rating_col} >= ?")
        params.append(min_rating)
    if conditions:
        sql += " AND " + " AND ".join(conditions)
    rows = lib_db.execute(sql, tuple(params)).fetchall()
    return [(r['key'], 'catalog') for r in rows]


def _score_single_image(
    lib_db,
    key: str,
    itype: str,
    perspective_slug: str,
    force: bool,
    provider_id,
    provider_model,
    log_callback,
) -> tuple[str, bool, str | None]:
    """Score one image for one perspective. Returns ``(status, success, error)``."""
    from lightroom_tagger.core.scoring_service import score_image_for_perspective

    try:
        return score_image_for_perspective(
            lib_db,
            image_key=key,
            image_type=itype,
            perspective_slug=perspective_slug,
            force=force,
            provider_id=provider_id,
            model=provider_model,
            log_callback=log_callback,
        )
    except Exception as e:
        return ('failed', False, str(e))


def _diagnose_describe_skip(lib_db, key: str, itype: str, force: bool) -> str:
    """Return a specific reason why describe_*_image returned False."""
    try:
        from lightroom_tagger.core.analyzer import VIDEO_EXTENSIONS
        from lightroom_tagger.core.database import (
            get_image,
            get_image_description,
            get_instagram_dump_media,
        )

        if itype == 'catalog':
            if not force and get_image_description(lib_db, key):
                return 'Already described (use force to regenerate)'
            image = get_image(lib_db, key)
            if not image:
                return 'Image key not found in catalog'
            filepath = image.get('filepath', '')
            if not filepath:
                return 'No filepath in catalog record'
            from lightroom_tagger.core.description_service import resolve_filepath
            resolved = resolve_filepath(filepath)
            ext = os.path.splitext(resolved)[1].lower()
            if ext in VIDEO_EXTENSIONS:
                return f'Video file not describable: {os.path.basename(resolved)}'
            if not os.path.exists(resolved):
                return f'File not found: {resolved}'
            return 'Model returned empty or invalid response'
        else:
            if not force and get_image_description(lib_db, key):
                return 'Already described (use force to regenerate)'
            ig = get_instagram_dump_media(lib_db, key)
            if not ig:
                return 'Instagram media key not found'
            filepath = ig.get('file_path') or ''
            ext = os.path.splitext(filepath)[1].lower()
            if ext in VIDEO_EXTENSIONS:
                return f'Video file not describable: {os.path.basename(filepath)}'
            return 'Model returned empty or invalid response'
    except Exception as exc:
        return f'No description generated ({exc})'


def _describe_single_image(
    lib_db,
    key: str,
    itype: str,
    force: bool,
    desc_provider_id,
    desc_provider_model,
    perspective_slugs: list[str] | None = None,
    telemetry: dict | None = None,
) -> tuple[str, bool, str | None]:
    """
    Describe a single image (DRY helper).

    Returns:
        (status, success, error_message) where status is 'described'|'skipped'|'failed'
    """
    from lightroom_tagger.core.description_service import (
        describe_instagram_image,
        describe_matched_image,
    )

    try:
        if itype == 'catalog':
            result = describe_matched_image(
                lib_db, key, force=force,
                provider_id=desc_provider_id, model=desc_provider_model,
                perspective_slugs=perspective_slugs,
                telemetry=telemetry,
            )
        else:
            result = describe_instagram_image(
                lib_db, key, force=force,
                provider_id=desc_provider_id, model=desc_provider_model,
                perspective_slugs=perspective_slugs,
            )

        if result:
            return ('described', True, None)
        else:
            reason = _diagnose_describe_skip(lib_db, key, itype, force)
            return ('skipped', False, reason)
    except Exception as e:
        return ('failed', False, str(e))


def handle_single_describe(runner, job_id: str, metadata: dict):
    """Generate an AI description for a single image, run as an async job."""
    try:
        image_key = metadata.get('image_key')
        image_type = metadata.get('image_type', 'catalog')
        force = metadata.get('force', False)
        provider_id = metadata.get('provider_id')
        provider_model = metadata.get('provider_model')

        if not image_key:
            runner.fail_job(job_id, 'image_key is required in metadata')
            return

        config = load_config()
        db_path = _resolve_library_db_or_fail(runner, job_id)
        if db_path is None:
            return
        with managed_library_db(db_path) as lib_db:
            raw_ps = metadata.get('perspective_slugs')
            if isinstance(raw_ps, list) and len(raw_ps) > 0:
                perspective_slugs = [str(x) for x in raw_ps]
            else:
                perspective_slugs = None

            runner.update_progress(job_id, 10, f'Describing {image_type} image…')

            path_diag = PathSkipDiagnostics(
                runner,
                job_id,
                lib_db,
                job_label='single_describe',
            )
            if not path_diag.run_preflight([image_key]):
                return

            status, success, error_msg = _describe_single_image(
                lib_db, image_key, image_type, force, provider_id, provider_model,
                perspective_slugs,
            )

            if success:
                runner.complete_job(job_id, {
                    'image_key': image_key,
                    'image_type': image_type,
                    'status': status,
                    'skip_reason_counts': path_diag.skip_reason_counts,
                })
            else:
                _record_path_skip_from_status(path_diag, lib_db, image_key, image_type, status)
                runner.fail_job(job_id, error_msg or 'Description generation failed')

    except Exception as e:
        severity = _failure_severity_from_exception(e)
        runner.fail_job(job_id, str(e), severity=severity)


def handle_single_score(runner, job_id: str, metadata: dict):
    """Score a single image for one or more perspectives.

    Fails the job if **any** requested perspective returns hard ``failed`` (skips are OK).
    """
    try:
        image_key = metadata.get('image_key')
        image_type = metadata.get('image_type', 'catalog')
        force = metadata.get('force', False)
        provider_id = metadata.get('provider_id')
        provider_model = metadata.get('provider_model')

        if not image_key:
            runner.fail_job(job_id, 'image_key is required in metadata')
            return
        if image_type not in ('catalog', 'instagram'):
            runner.fail_job(job_id, 'image_type must be catalog or instagram')
            return

        config = load_config()
        db_path = _resolve_library_db_or_fail(runner, job_id)
        if db_path is None:
            return
        with managed_library_db(db_path) as lib_db:

            raw_ps = metadata.get('perspective_slugs')
            if isinstance(raw_ps, list) and len(raw_ps) > 0:
                slugs = [str(x) for x in raw_ps]
            else:
                from lightroom_tagger.core.database import list_perspectives
                slugs = [r['slug'] for r in list_perspectives(lib_db, active_only=True)]

            if not slugs:
                runner.fail_job(job_id, 'No perspectives to score (provide perspective_slugs or activate perspectives)')
                return

            def log_callback(level, message):
                add_job_log(runner.db, job_id, level, message)

            scored = 0
            skipped = 0
            failed = 0

            runner.update_progress(job_id, 10, f'Scoring {image_type} image…')

            path_diag = PathSkipDiagnostics(
                runner,
                job_id,
                lib_db,
                job_label='single_score',
            )
            if not path_diag.run_preflight([image_key]):
                return

            for slug in slugs:
                status, _success, err = _score_single_image(
                    lib_db, image_key, image_type, slug, force,
                    provider_id, provider_model, log_callback,
                )
                if status == 'scored':
                    scored += 1
                elif status == 'skipped':
                    skipped += 1
                else:
                    failed += 1
                    runner.fail_job(
                        job_id,
                        err or f'Scoring failed for perspective {slug!r}',
                    )
                    return

            runner.complete_job(job_id, {
                'image_key': image_key,
                'image_type': image_type,
                'scored': scored,
                'skipped': skipped,
                'failed': failed,
                'skip_reason_counts': path_diag.skip_reason_counts,
            })
    except Exception as e:
        severity = _failure_severity_from_exception(e)
        runner.fail_job(job_id, str(e), severity=severity)


def _map_job_progress(progress_range: tuple[float, float], pct: int) -> int:
    lo, hi = progress_range
    return int(lo + (hi - lo) * pct / 100)


def _analyze_load_checkpoint(runner, job_id: str) -> dict:
    """Load the nested ``batch_analyze`` checkpoint body (without ``checkpoint_version``) or ``{}``."""
    row = get_job(runner.db, job_id)
    if not row:
        return {}
    meta = row.get('metadata') or {}
    if not isinstance(meta, dict):
        return {}
    chk = meta.get('checkpoint')
    if not isinstance(chk, dict):
        return {}
    if chk.get('checkpoint_version') != 1 or chk.get('job_type') != 'batch_analyze':
        return {}
    return {k: v for k, v in chk.items() if k != 'checkpoint_version'}


def _analyze_merge_persist(
    runner,
    job_id: str,
    *,
    stage: str,
    describe: dict,
    score: dict,
) -> None:
    """Persist the nested batch_analyze checkpoint body for ``stage`` with both sub-objects."""
    checkpoint_body = {
        'job_type': 'batch_analyze',
        'stage': stage,
        'describe': describe,
        'score': score,
    }
    runner.persist_checkpoint(job_id, checkpoint_body)


def _run_describe_pass(
    runner,
    job_id: str,
    metadata: dict,
    lib_db,
    selection: list[tuple[str, str]],
    *,
    db_path: str,
    progress_range: tuple[float, float],
    log_prefix: str = "",
    finalize: bool = True,
    nested_analyze_checkpoint: bool = False,
) -> dict | None:
    """Shared describe pipeline used by handle_batch_describe and batch_analyze.

    Moves the post-selection processing body of ``handle_batch_describe`` here; every internal
    ``update_progress`` call is remapped through ``_map_job_progress(progress_range, ...)`` and
    every log message is prefixed with ``log_prefix`` when non-empty.

    When ``nested_analyze_checkpoint=False`` (default) the helper reads and writes the flat
    ``{'job_type': 'batch_describe', ...}`` checkpoint (Plan 01 contract). When ``True`` the
    helper instead loads the ``describe`` sub-object from a ``batch_analyze`` checkpoint and
    persists via :func:`_analyze_merge_persist` with ``stage='describe'``.

    When ``finalize=True`` (default) the helper calls ``runner.clear_checkpoint`` +
    ``runner.complete_job`` on the success path exactly as before. When ``False`` it returns the
    result-summary dict instead (caller owns terminal completion). ``fail_job`` /
    ``finalize_cancelled`` / early zero-work ``complete_job`` paths always run regardless of
    ``finalize``; callers check the ``None`` return to detect those short-circuit paths.
    """
    image_type = metadata.get('image_type', 'both')
    date_filter = metadata.get('date_filter', 'all')
    force = metadata.get('force', False)
    backfill_visual_tags = bool(metadata.get('backfill_visual_tags', False))
    describe_force = bool(force) or backfill_visual_tags
    desc_provider_id = metadata.get('provider_id')
    desc_provider_model = metadata.get('provider_model')
    max_workers = int(metadata.get('max_workers', 4))

    raw_ps = metadata.get('perspective_slugs')
    if isinstance(raw_ps, list) and len(raw_ps) > 0:
        perspective_slugs = [str(x) for x in raw_ps]
    else:
        perspective_slugs = None

    images_to_describe: list[tuple[str, str]] = list(selection)
    total_at_start = len(images_to_describe)
    fp_bd = fingerprint_batch_describe(metadata, images_to_describe)
    jt_batch_describe = job_type_entry('batch_describe')

    def _log_describe_mismatch(msg: str) -> None:
        add_job_log(
            runner.db,
            job_id,
            'info',
            f'{log_prefix}{msg}' if log_prefix else msg,
        )

    if nested_analyze_checkpoint:
        row_nested = get_job(runner.db, job_id)
        meta_nested = (row_nested.get('metadata') or {}) if row_nested and isinstance(row_nested.get('metadata'), dict) else {}
        processed_pairs = load_resume_state(
            'batch_describe',
            meta_nested,
            fp_bd,
            _log_describe_mismatch,
            nested_sub_key='describe',
            nested_root_job_type='batch_analyze',
            mismatch_message='checkpoint mismatch: batch_analyze describe fingerprint changed, starting describe fresh',
        )
    else:
        row_bd = get_job(runner.db, job_id)
        meta_bd = (row_bd.get('metadata') or {}) if row_bd and isinstance(row_bd.get('metadata'), dict) else {}
        processed_pairs = load_resume_state(
            'batch_describe',
            meta_bd,
            fp_bd,
            _log_describe_mismatch,
        )

    def pair_label(key: str, itype: str) -> str:
        return f'{key}|{itype}'

    images_to_describe = [
        (k, t) for k, t in images_to_describe if pair_label(k, t) not in processed_pairs
    ]

    if not backfill_visual_tags and not force and images_to_describe:
        already_described: set[str] = set()
        rows_desc = lib_db.execute(
            "SELECT image_key FROM image_descriptions"
        ).fetchall()
        for r in rows_desc:
            already_described.add(r['image_key'])
        before_desc = len(images_to_describe)
        images_to_describe = [
            (k, t) for k, t in images_to_describe
            if k not in already_described
        ]
        skipped_by_db = before_desc - len(images_to_describe)
        if skipped_by_db:
            add_job_log(
                runner.db, job_id, 'info',
                f'{log_prefix}Skipped {skipped_by_db} already-described images (DB pre-filter)'
                if log_prefix else
                f'Skipped {skipped_by_db} already-described images (DB pre-filter)',
            )

    total = len(images_to_describe)
    already_done = total_at_start - total
    runner.update_progress(
        job_id,
        _map_job_progress(progress_range, int(5 + (already_done / max(total_at_start, 1)) * 90)),
        f'{log_prefix}Found {total_at_start} images to describe ({total} remaining)'
        if log_prefix else
        f'Found {total_at_start} images to describe ({total} remaining)',
    )

    if total_at_start == 0:
        empty = {
            'described': 0,
            'skipped': 0,
            'failed': 0,
            'total': 0,
            'skip_reason_counts': empty_skip_reason_counts(),
        }
        if finalize:
            runner.clear_checkpoint(job_id)
            runner.complete_job(job_id, empty)
            return None
        return empty

    path_diag = PathSkipDiagnostics(
        runner,
        job_id,
        lib_db,
        job_label='batch_describe',
        chain_mode=bool(metadata.get('_catalog_cache_chain')),
        log_action='describe',
    )
    preflight_keys = [k for k, _t in images_to_describe]
    if not isinstance(lib_db, MagicMock) and not path_diag.run_preflight(preflight_keys):
        return None

    def record_done(desc_key: str, itype: str) -> bool:
        processed_pairs.add(pair_label(desc_key, itype))
        if len(processed_pairs) > _CHECKPOINT_MAX_ENTRIES:
            runner.fail_job(
                job_id,
                'checkpoint too large: exceeds 100000 entries',
                severity='error',
            )
            return False
        describe_payload = {
            'fingerprint': fp_bd,
            'processed_pairs': sorted(processed_pairs),
            'total_at_start': total_at_start,
        }
        if nested_analyze_checkpoint:
            existing = _analyze_load_checkpoint(runner, job_id)
            score_sibling = existing.get('score') if isinstance(existing, dict) else None
            if not isinstance(score_sibling, dict):
                score_sibling = {}
            _analyze_merge_persist(
                runner,
                job_id,
                stage='describe',
                describe=describe_payload,
                score=score_sibling,
            )
        else:
            runner.persist_checkpoint(
                job_id,
                jt_batch_describe.build_checkpoint_body(
                    fingerprint=fp_bd,
                    processed=processed_pairs,
                    total_at_start=total_at_start,
                ),
            )
        return True

    described = 0
    skipped = 0
    failed = 0
    consecutive_failures = 0

    telemetry = None
    if nested_analyze_checkpoint:
        telemetry = {'silent_compression_skips': 0, '_lock': threading.Lock()}

    if max_workers > 1 and total > 3:
        def process_image_worker(key: str, itype: str):
            """Worker function with its own DB connection.

            Installs a thread-local cancel scope so retry/backoff sleeps and
            the fallback cascade inside ``_describe_single_image`` observe
            ``runner.is_cancelled(job_id)``. Without this, a worker thread
            caught inside a 32s retry sleep wouldn't notice a cancel until
            the sleep finished.
            """
            with managed_library_db(db_path) as worker_db:
                with cancel_scope.install(lambda: runner.is_cancelled(job_id)):
                    status, success, error_msg = _describe_single_image(
                        worker_db, key, itype, describe_force, desc_provider_id, desc_provider_model,
                        perspective_slugs,
                        telemetry,
                    )
                return (key, status, error_msg)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(process_image_worker, key, itype): (key, itype)
                for key, itype in images_to_describe
            }
            for completed_parallel, future in enumerate(as_completed(futures), start=1):
                if runner.is_cancelled(job_id):
                    add_job_log(
                        runner.db,
                        job_id,
                        'info',
                        f'{log_prefix}Batch describe cancel noted; finishing already-running tasks'
                        if log_prefix else
                        'Batch describe cancel noted; finishing already-running tasks',
                    )
                    break
                coord_key, coord_itype = futures[future]
                pct = int(5 + ((already_done + completed_parallel) / max(total_at_start, 1)) * 90)
                runner.update_progress(
                    job_id,
                    _map_job_progress(progress_range, pct),
                    f'{log_prefix}Describing {already_done + completed_parallel}/{total_at_start}'
                    if log_prefix else
                    f'Describing {already_done + completed_parallel}/{total_at_start}',
                )

                try:
                    result_key, status, error_msg = future.result()
                    if status == 'described':
                        described += 1
                        consecutive_failures = 0
                        if not record_done(result_key, coord_itype):
                            break
                    elif status == 'skipped':
                        skipped += 1
                        _record_path_skip_from_status(
                            path_diag, lib_db, result_key, coord_itype, status,
                            log_prefix=log_prefix,
                        )
                        add_job_log(runner.db, job_id, 'warning', f'{log_prefix}{result_key}: {error_msg}' if log_prefix else f'{result_key}: {error_msg}')
                        if not record_done(result_key, coord_itype):
                            break
                    else:  # failed
                        failed += 1
                        consecutive_failures += 1
                        add_job_log(runner.db, job_id, 'warning', f'{log_prefix}{result_key}: {error_msg}' if log_prefix else f'{result_key}: {error_msg}')
                except Exception as e:
                    failed += 1
                    consecutive_failures += 1
                    add_job_log(runner.db, job_id, 'warning', f'{log_prefix}{coord_key}: {e}' if log_prefix else f'{coord_key}: {e}')

                if consecutive_failures >= 10:
                    add_job_log(runner.db, job_id, 'error',
                                f'{log_prefix}Stopping: {consecutive_failures} consecutive failures'
                                if log_prefix else
                                f'Stopping: {consecutive_failures} consecutive failures')
                    break

        if runner.is_cancelled(job_id):
            runner.finalize_cancelled(job_id)
            return
    else:
        # Cancel scope is installed around the entire handler (see
        # batch_describe / batch_analyze wrappers) so the per-iteration
        # ``is_cancelled`` check here still guards entry into each new
        # item, AND any retry/fallback backoff sleeps below abort early.
        for idx, (key, itype) in enumerate(images_to_describe, 1):
            if runner.is_cancelled(job_id):
                add_job_log(runner.db, job_id, 'info', f'{log_prefix}Batch describe stopped: cancel requested' if log_prefix else 'Batch describe stopped: cancel requested')
                runner.finalize_cancelled(job_id)
                return
            pct = int(5 + ((already_done + idx) / max(total_at_start, 1)) * 90)
            runner.update_progress(
                job_id,
                _map_job_progress(progress_range, pct),
                f'{log_prefix}Describing {already_done + idx}/{total_at_start}: {key}'
                if log_prefix else
                f'Describing {already_done + idx}/{total_at_start}: {key}',
            )

            status, success, error_msg = _describe_single_image(
                lib_db, key, itype, describe_force, desc_provider_id, desc_provider_model,
                perspective_slugs,
                telemetry,
            )

            if status == 'described':
                described += 1
                consecutive_failures = 0
                if not record_done(key, itype):
                    break
            elif status == 'skipped':
                skipped += 1
                _record_path_skip_from_status(
                    path_diag, lib_db, key, itype, status, log_prefix=log_prefix,
                )
                add_job_log(runner.db, job_id, 'warning', f'{log_prefix}{key}: {error_msg}' if log_prefix else f'{key}: {error_msg}')
                if not record_done(key, itype):
                    break
            else:  # failed
                failed += 1
                consecutive_failures += 1
                add_job_log(runner.db, job_id, 'warning', f'{log_prefix}{key}: {error_msg}' if log_prefix else f'{key}: {error_msg}')

            if consecutive_failures >= 10:
                add_job_log(runner.db, job_id, 'error',
                            f'{log_prefix}Stopping: {consecutive_failures} consecutive failures'
                            if log_prefix else
                            f'Stopping: {consecutive_failures} consecutive failures')
                break

    row_status = get_job(runner.db, job_id)
    if row_status and row_status.get('status') == 'failed':
        return None

    if (
        nested_analyze_checkpoint
        and telemetry is not None
        and telemetry['silent_compression_skips'] > 0
    ):
        add_job_log(
            runner.db,
            job_id,
            'info',
            f"{telemetry['silent_compression_skips']} images already compressed, skipped.",
        )

    result_summary = {
        'described': described,
        'skipped': skipped,
        'failed': failed,
        'total': total_at_start,
        'image_type': image_type,
        'date_filter': date_filter,
        'force': force,
        'skip_reason_counts': path_diag.skip_reason_counts,
    }

    if described == 0 and consecutive_failures >= 10:
        runner.fail_job(
            job_id,
            f'Aborted after {consecutive_failures} consecutive failures'
            ' with 0 successful descriptions'
            ' — check file paths and provider connectivity',
            severity='error',
        )
        return None

    if finalize:
        runner.clear_checkpoint(job_id)
        runner.complete_job(job_id, result_summary)
        return None
    return result_summary


def handle_batch_describe(runner, job_id: str, metadata: dict):
    """Generate AI descriptions for catalog and/or Instagram images in bulk."""
    # Install the cancel scope for the main handler thread so retry/fallback
    # sleeps inside the sequential describe path observe cancel requests
    # without any explicit plumbing. The parallel path installs its own
    # scope per worker thread (see ``process_image_worker`` in
    # ``_run_describe_pass``) because ThreadPool workers don't inherit
    # thread-local state from the submitter.
    with cancel_scope.install(lambda: runner.is_cancelled(job_id)):
        _handle_batch_describe_inner(runner, job_id, metadata)


def _handle_batch_describe_inner(runner, job_id: str, metadata: dict):
    old_model_env = os.environ.get('DESCRIPTION_VISION_MODEL')
    try:
        config = load_config()
        db_path = _resolve_library_db_or_fail(runner, job_id)
        if db_path is None:
            return
        with managed_library_db(db_path) as lib_db:

            image_type = metadata.get('image_type', 'both')  # catalog, instagram, both
            force = metadata.get('force', False)

            # ``last_months`` (int) and ``year`` ('YYYY') now win over the legacy
            # ``date_filter`` string; see ``_resolve_date_window`` for details.
            months, year = _resolve_date_window(metadata)
            min_rating_raw = metadata.get('min_rating')
            min_rating = None
            if min_rating_raw is not None:
                try:
                    min_rating = int(min_rating_raw)
                except (TypeError, ValueError):
                    min_rating = None

            from lightroom_tagger.core.database import (
                get_undescribed_catalog_images,
                get_undescribed_instagram_images,
            )

            backfill_visual_tags = bool(metadata.get('backfill_visual_tags', False))

            images_to_describe: list[tuple[str, str]] = []  # (key, type)

            if image_type in ('catalog', 'both'):
                if backfill_visual_tags:
                    # Catalog only for this mode (D-18); re-describe rows missing visual tags.
                    images_to_describe += _select_catalog_keys_missing_visual_tags(
                        lib_db,
                        months=months,
                        year=year,
                        min_rating=min_rating,
                    )
                elif force or year is not None:
                    # ``year`` is a new window that the undescribed-only helper
                    # doesn't know about yet, so we run the raw SQL path for both
                    # ``force`` and ``year`` (joining in the description filter
                    # manually when ``force`` is off).
                    images_to_describe += _select_catalog_keys(
                        lib_db,
                        months=months,
                        year=year,
                        min_rating=min_rating,
                        undescribed_only=not force,
                    )
                else:
                    images_to_describe += [
                        (img['key'], 'catalog')
                        for img in get_undescribed_catalog_images(
                            lib_db, months=months, min_rating=min_rating
                        )
                    ]

            if image_type in ('instagram', 'both'):
                # Always route through _select_instagram_keys so the COALESCE/date_folder
                # fallback applies consistently regardless of force/year flags.
                images_to_describe += _select_instagram_keys(
                    lib_db,
                    months=months,
                    year=year,
                    undescribed_only=not force,
                )

            if backfill_visual_tags and not images_to_describe:
                add_job_log(
                    runner.db,
                    job_id,
                    'info',
                    'Backfill visual tags: no images matched the current scope '
                    '(no catalog rows with missing color/mood data in the date/rating window, or no work selected).',
                )

            _run_describe_pass(
                runner,
                job_id,
                metadata,
                lib_db,
                images_to_describe,
                db_path=db_path,
                progress_range=(0, 100),
                log_prefix="",
            )
    except Exception as e:
        severity = _failure_severity_from_exception(e)
        runner.fail_job(job_id, str(e), severity=severity)
    finally:
        if old_model_env is not None:
            os.environ['DESCRIPTION_VISION_MODEL'] = old_model_env
        else:
            os.environ.pop('DESCRIPTION_VISION_MODEL', None)


def _run_score_pass(
    runner,
    job_id: str,
    metadata: dict,
    lib_db,
    selection: list[tuple[str, str]],
    *,
    db_path: str,
    progress_range: tuple[float, float],
    log_prefix: str = "",
    finalize: bool = True,
    nested_analyze_checkpoint: bool = False,
) -> dict | None:
    """Shared score pipeline used by handle_batch_score and batch_analyze.

    Moves the post-selection processing body of ``handle_batch_score`` here; every internal
    ``update_progress`` call is remapped through ``_map_job_progress(progress_range, ...)`` and
    every log message is prefixed with ``log_prefix`` when non-empty.

    When ``nested_analyze_checkpoint=False`` (default) the helper reads and writes the flat
    ``{'job_type': 'batch_score', ...}`` checkpoint (Plan 01 contract). When ``True`` the helper
    instead loads the ``score`` sub-object from a ``batch_analyze`` checkpoint and persists via
    :func:`_analyze_merge_persist` with ``stage='score'``.

    When ``finalize=True`` (default) the helper calls ``runner.clear_checkpoint`` +
    ``runner.complete_job`` on the success path exactly as before. When ``False`` it returns
    the result-summary dict instead (caller owns terminal completion).
    """
    image_type = metadata.get('image_type', 'both')
    date_filter = metadata.get('date_filter', 'all')
    force = metadata.get('force', False)
    score_provider_id = metadata.get('provider_id')
    score_provider_model = metadata.get('provider_model')
    max_workers = int(metadata.get('max_workers', 4))

    raw_ps = metadata.get('perspective_slugs')
    if isinstance(raw_ps, list) and len(raw_ps) > 0:
        perspective_slugs = [str(x) for x in raw_ps]
    else:
        perspective_slugs = None

    from lightroom_tagger.core.database import list_perspectives

    images_for_scores: list[tuple[str, str]] = list(selection)

    slugs = perspective_slugs
    if not slugs:
        slugs = [r['slug'] for r in list_perspectives(lib_db, active_only=True)]

    work_triples: list[tuple[str, str, str]] = [
        (k, t, s) for k, t in images_for_scores for s in slugs
    ]
    total_at_start = len(work_triples)
    fp_bs = fingerprint_batch_score(metadata, work_triples)
    jt_batch_score = job_type_entry('batch_score')

    def _log_score_mismatch(msg: str) -> None:
        add_job_log(
            runner.db,
            job_id,
            'info',
            f'{log_prefix}{msg}' if log_prefix else msg,
        )

    if nested_analyze_checkpoint:
        row_nested = get_job(runner.db, job_id)
        meta_nested = (row_nested.get('metadata') or {}) if row_nested and isinstance(row_nested.get('metadata'), dict) else {}
        processed_triplets = load_resume_state(
            'batch_score',
            meta_nested,
            fp_bs,
            _log_score_mismatch,
            nested_sub_key='score',
            nested_root_job_type='batch_analyze',
            mismatch_message='checkpoint mismatch: batch_analyze score fingerprint changed, starting score fresh',
        )
    else:
        row_bs = get_job(runner.db, job_id)
        meta_bs = (row_bs.get('metadata') or {}) if row_bs and isinstance(row_bs.get('metadata'), dict) else {}
        processed_triplets = load_resume_state(
            'batch_score',
            meta_bs,
            fp_bs,
            _log_score_mismatch,
        )

    def triplet_label(key: str, itype: str, slug: str) -> str:
        return f'{key}|{itype}|{slug}'

    work_triples = [
        (k, t, s) for k, t, s in work_triples
        if triplet_label(k, t, s) not in processed_triplets
    ]

    if not force and work_triples:
        from lightroom_tagger.core.scoring_service import compute_prompt_version
        from lightroom_tagger.core.database import get_perspective_by_slug
        slug_versions = {}
        for s in slugs:
            prow = get_perspective_by_slug(lib_db, s)
            if prow:
                slug_versions[s] = compute_prompt_version(prow)
        if slug_versions:
            already_scored: set[str] = set()
            for slug, pv in slug_versions.items():
                rows = lib_db.execute(
                    "SELECT image_key, image_type FROM image_scores "
                    "WHERE perspective_slug = ? AND prompt_version = ? AND is_current = 1",
                    (slug, pv),
                ).fetchall()
                for r in rows:
                    already_scored.add(triplet_label(r['image_key'], r['image_type'], slug))
            before = len(work_triples)
            work_triples = [
                (k, t, s) for k, t, s in work_triples
                if triplet_label(k, t, s) not in already_scored
            ]
            skipped_by_db = before - len(work_triples)
            if skipped_by_db:
                add_job_log(
                    runner.db, job_id, 'info',
                    f'{log_prefix}Skipped {skipped_by_db} already-scored triplets (DB pre-filter)'
                    if log_prefix else
                    f'Skipped {skipped_by_db} already-scored triplets (DB pre-filter)',
                )

    total = len(work_triples)
    already_done = total_at_start - total
    runner.update_progress(
        job_id,
        _map_job_progress(progress_range, int(5 + (already_done / max(total_at_start, 1)) * 90)),
        f'{log_prefix}Found {total_at_start} scoring units ({total} remaining)'
        if log_prefix else
        f'Found {total_at_start} scoring units ({total} remaining)',
    )

    if total_at_start == 0:
        empty = {
            'scored': 0,
            'skipped': 0,
            'failed': 0,
            'total': 0,
            'skip_reason_counts': empty_skip_reason_counts(),
        }
        if finalize:
            runner.clear_checkpoint(job_id)
            runner.complete_job(job_id, empty)
            return None
        return empty

    path_diag = PathSkipDiagnostics(
        runner,
        job_id,
        lib_db,
        job_label='batch_score',
        chain_mode=bool(metadata.get('_catalog_cache_chain')),
        log_action='score',
    )
    preflight_keys = list(dict.fromkeys(k for k, _t, _s in work_triples))
    if not isinstance(lib_db, MagicMock) and not path_diag.run_preflight(preflight_keys):
        return None

    def record_done(score_key: str, itype: str, slug: str) -> bool:
        processed_triplets.add(triplet_label(score_key, itype, slug))
        if len(processed_triplets) > _CHECKPOINT_MAX_ENTRIES:
            runner.fail_job(
                job_id,
                'checkpoint too large: exceeds 100000 entries',
                severity='error',
            )
            return False
        score_payload = {
            'fingerprint': fp_bs,
            'processed_triplets': sorted(processed_triplets),
            'total_at_start': total_at_start,
        }
        if nested_analyze_checkpoint:
            existing = _analyze_load_checkpoint(runner, job_id)
            describe_sibling = existing.get('describe') if isinstance(existing, dict) else None
            if not isinstance(describe_sibling, dict):
                describe_sibling = {}
            _analyze_merge_persist(
                runner,
                job_id,
                stage='score',
                describe=describe_sibling,
                score=score_payload,
            )
        else:
            runner.persist_checkpoint(
                job_id,
                jt_batch_score.build_checkpoint_body(
                    fingerprint=fp_bs,
                    processed=processed_triplets,
                    total_at_start=total_at_start,
                ),
            )
        return True

    scored = 0
    skipped = 0
    failed = 0
    consecutive_failures = 0

    if max_workers > 1 and total > 3:
        def _worker_log_callback(level: str, msg: str) -> None:
            # Worker-thread diagnostics (retry notices, repair logs) go
            # through ``log_from_worker`` so every thread writes via its own
            # sqlite3 connection. Sharing ``runner.db`` across all workers
            # was the root cause of the 3h stall on job 50710bf6 — Python's
            # sqlite3 connection mutex serialized every INSERT, which in
            # turn starved the main-thread ``as_completed`` coordinator.
            runner.log_from_worker(
                job_id, level, f"{log_prefix}{msg}" if log_prefix else msg
            )

        def process_score_worker(key: str, itype: str, slug: str):
            # Install the cancel scope per worker thread so retry/backoff
            # sleeps and fallback cascades observe ``runner.is_cancelled``.
            # See ``process_image_worker`` in ``_run_describe_pass`` for
            # the matching pattern.
            with managed_library_db(db_path) as worker_db:
                with cancel_scope.install(lambda: runner.is_cancelled(job_id)):
                    return _score_single_image(
                        worker_db, key, itype, slug, force,
                        score_provider_id, score_provider_model,
                        _worker_log_callback,
                    )

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(process_score_worker, key, itype, slug): (key, itype, slug)
                for key, itype, slug in work_triples
            }
            for completed_parallel, future in enumerate(as_completed(futures), start=1):
                if runner.is_cancelled(job_id):
                    add_job_log(
                        runner.db,
                        job_id,
                        'info',
                        f'{log_prefix}Batch score cancel noted; finishing already-running tasks'
                        if log_prefix else
                        'Batch score cancel noted; finishing already-running tasks',
                    )
                    break
                coord_key, coord_itype, coord_slug = futures[future]
                pct = int(5 + ((already_done + completed_parallel) / max(total_at_start, 1)) * 90)
                runner.update_progress(
                    job_id,
                    _map_job_progress(progress_range, pct),
                    f'{log_prefix}Scoring {already_done + completed_parallel}/{total_at_start}'
                    if log_prefix else
                    f'Scoring {already_done + completed_parallel}/{total_at_start}',
                )
                try:
                    status, _success, error_msg = future.result()
                    if status == 'scored':
                        scored += 1
                        consecutive_failures = 0
                        if not record_done(coord_key, coord_itype, coord_slug):
                            break
                    elif status == 'skipped':
                        skipped += 1
                        _record_path_skip_from_status(
                            path_diag, lib_db, coord_key, coord_itype, status,
                            log_prefix=log_prefix,
                        )
                        add_job_log(
                            runner.db, job_id, 'warning',
                            f'{log_prefix}{coord_key}|{coord_slug}: {error_msg}'
                            if log_prefix else
                            f'{coord_key}|{coord_slug}: {error_msg}',
                        )
                        if not record_done(coord_key, coord_itype, coord_slug):
                            break
                    else:
                        failed += 1
                        consecutive_failures += 1
                        add_job_log(
                            runner.db, job_id, 'warning',
                            f'{log_prefix}{coord_key}|{coord_slug}: {error_msg}'
                            if log_prefix else
                            f'{coord_key}|{coord_slug}: {error_msg}',
                        )
                except Exception as e:
                    failed += 1
                    consecutive_failures += 1
                    add_job_log(runner.db, job_id, 'warning', f'{log_prefix}{coord_key}: {e}' if log_prefix else f'{coord_key}: {e}')

                if consecutive_failures >= 10:
                    add_job_log(
                        runner.db, job_id, 'error',
                        f'{log_prefix}Stopping: {consecutive_failures} consecutive failures'
                        if log_prefix else
                        f'Stopping: {consecutive_failures} consecutive failures',
                    )
                    break

        if runner.is_cancelled(job_id):
            runner.finalize_cancelled(job_id)
            return
    else:
        for idx, (key, itype, slug) in enumerate(work_triples, 1):
            if runner.is_cancelled(job_id):
                add_job_log(runner.db, job_id, 'info', f'{log_prefix}Batch score stopped: cancel requested' if log_prefix else 'Batch score stopped: cancel requested')
                runner.finalize_cancelled(job_id)
                return
            pct = int(5 + ((already_done + idx) / max(total_at_start, 1)) * 90)
            runner.update_progress(
                job_id,
                _map_job_progress(progress_range, pct),
                f'{log_prefix}Scoring {already_done + idx}/{total_at_start}: {key}|{slug}'
                if log_prefix else
                f'Scoring {already_done + idx}/{total_at_start}: {key}|{slug}',
            )

            def log_callback(level, message):
                add_job_log(runner.db, job_id, level, f'{log_prefix}{message}' if log_prefix else message)

            status, _success, error_msg = _score_single_image(
                lib_db, key, itype, slug, force,
                score_provider_id, score_provider_model, log_callback,
            )

            if status == 'scored':
                scored += 1
                consecutive_failures = 0
                if not record_done(key, itype, slug):
                    break
            elif status == 'skipped':
                skipped += 1
                _record_path_skip_from_status(
                    path_diag, lib_db, key, itype, status, log_prefix=log_prefix,
                )
                add_job_log(runner.db, job_id, 'warning', f'{log_prefix}{key}|{slug}: {error_msg}' if log_prefix else f'{key}|{slug}: {error_msg}')
                if not record_done(key, itype, slug):
                    break
            else:
                failed += 1
                consecutive_failures += 1
                add_job_log(runner.db, job_id, 'warning', f'{log_prefix}{key}|{slug}: {error_msg}' if log_prefix else f'{key}|{slug}: {error_msg}')

            if consecutive_failures >= 10:
                add_job_log(
                    runner.db, job_id, 'error',
                    f'{log_prefix}Stopping: {consecutive_failures} consecutive failures'
                    if log_prefix else
                    f'Stopping: {consecutive_failures} consecutive failures',
                )
                break

    row_score = get_job(runner.db, job_id)
    if row_score and row_score.get('status') == 'failed':
        return None

    score_result = {
        'scored': scored,
        'skipped': skipped,
        'failed': failed,
        'total': total_at_start,
        'image_type': image_type,
        'date_filter': date_filter,
        'force': force,
        'skip_reason_counts': path_diag.skip_reason_counts,
    }

    if scored == 0 and consecutive_failures >= 10:
        runner.fail_job(
            job_id,
            f'Aborted after {consecutive_failures} consecutive failures'
            ' with 0 successful scores'
            ' — check file paths and provider connectivity',
            severity='error',
        )
        return None

    if finalize:
        runner.clear_checkpoint(job_id)
        runner.complete_job(job_id, score_result)
        return None
    return score_result


def handle_batch_score(runner, job_id: str, metadata: dict):
    """Score catalog and/or Instagram images in bulk (one vision call per image × perspective).

    Checkpoint resume uses ``processed_triplets`` (``key|itype|slug``). Any hard failure increments
    ``failed``; skipped rows (already current, missing file) still advance the checkpoint like
    batch describe.
    """
    # See ``handle_batch_describe`` for cancel-scope rationale.
    with cancel_scope.install(lambda: runner.is_cancelled(job_id)):
        _handle_batch_score_inner(runner, job_id, metadata)


def _handle_batch_score_inner(runner, job_id: str, metadata: dict):
    try:
        config = load_config()
        db_path = _resolve_library_db_or_fail(runner, job_id)
        if db_path is None:
            return
        with managed_library_db(db_path) as lib_db:

            image_type = metadata.get('image_type', 'both')

            months, year = _resolve_date_window(metadata)
            min_rating_raw = metadata.get('min_rating')
            min_rating = None
            if min_rating_raw is not None:
                try:
                    min_rating = int(min_rating_raw)
                except (TypeError, ValueError):
                    min_rating = None
            # ``handle_batch_score`` always rescans the full candidate set
            # (scoring isn't gated on missing descriptions the same way describe
            # is), so ``undescribed_only=False`` matches the previous SQL exactly —
            # both the ``force`` and non-``force`` arms had identical selection.

            images_for_scores: list[tuple[str, str]] = []

            if image_type in ('catalog', 'both'):
                images_for_scores += _select_catalog_keys(
                    lib_db,
                    months=months,
                    year=year,
                    min_rating=min_rating,
                    undescribed_only=False,
                )

            if image_type in ('instagram', 'both'):
                images_for_scores += _select_instagram_keys(
                    lib_db,
                    months=months,
                    year=year,
                    undescribed_only=False,
                )

            _run_score_pass(
                runner,
                job_id,
                metadata,
                lib_db,
                images_for_scores,
                db_path=db_path,
                progress_range=(0, 100),
                log_prefix="",
            )

    except Exception as e:
        severity = _failure_severity_from_exception(e)
        runner.fail_job(job_id, str(e), severity=severity)


def handle_batch_analyze(runner, job_id: str, metadata: dict):
    """Unified analyze: run describe then score over a single shared (key, itype) selection.

    Drives one job through two stages with split progress (``0..50`` describe, ``50..100`` score),
    ``current_step`` updates (``'Describing'`` / ``'Scoring'``), nested ``batch_analyze``
    checkpoints, and a combined ``complete_job`` payload (D-06 keys). ``force_describe`` /
    ``force_score`` in ``metadata`` are normalized into per-stage ``force`` via shallow-merge
    before hitting the helpers' fingerprint + pre-filter logic (D-11).
    """
    # See ``handle_batch_describe`` for cancel-scope rationale.
    with cancel_scope.install(lambda: runner.is_cancelled(job_id)):
        _handle_batch_analyze_inner(runner, job_id, metadata)


def _handle_batch_analyze_inner(runner, job_id: str, metadata: dict):
    old_model_env = os.environ.get('DESCRIPTION_VISION_MODEL')
    try:
        config = load_config()
        db_path = _resolve_library_db_or_fail(runner, job_id)
        if db_path is None:
            return
        with managed_library_db(db_path) as lib_db:

            image_type = metadata.get('image_type', 'both')
            force = bool(metadata.get('force_describe', False))

            months, year = _resolve_date_window(metadata)
            min_rating_raw = metadata.get('min_rating')
            min_rating = None
            if min_rating_raw is not None:
                try:
                    min_rating = int(min_rating_raw)
                except (TypeError, ValueError):
                    min_rating = None

            from lightroom_tagger.core.database import (
                get_undescribed_catalog_images,
                get_undescribed_instagram_images,
            )

            backfill_visual_tags = bool(metadata.get('backfill_visual_tags', False))

            shared_selection: list[tuple[str, str]] = []

            if image_type in ('catalog', 'both'):
                if backfill_visual_tags:
                    shared_selection += _select_catalog_keys_missing_visual_tags(
                        lib_db,
                        months=months,
                        year=year,
                        min_rating=min_rating,
                    )
                elif force or year is not None:
                    shared_selection += _select_catalog_keys(
                        lib_db,
                        months=months,
                        year=year,
                        min_rating=min_rating,
                        undescribed_only=not force,
                    )
                else:
                    shared_selection += [
                        (img['key'], 'catalog')
                        for img in get_undescribed_catalog_images(
                            lib_db, months=months, min_rating=min_rating
                        )
                    ]

            if image_type in ('instagram', 'both'):
                if force or year is not None:
                    shared_selection += _select_instagram_keys(
                        lib_db,
                        months=months,
                        year=year,
                        undescribed_only=not force,
                    )
                else:
                    shared_selection += [
                        (img['media_key'], 'instagram')
                        for img in get_undescribed_instagram_images(lib_db, months=months)
                    ]

            if backfill_visual_tags and not shared_selection:
                add_job_log(
                    runner.db,
                    job_id,
                    'info',
                    'Backfill visual tags: no images matched the current scope '
                    '(no catalog rows with missing color/mood data in the date/rating window, or no work selected).',
                )

            metadata_for_describe = {**metadata, 'force': bool(metadata.get('force_describe', False))}
            metadata_for_score = {**metadata, 'force': bool(metadata.get('force_score', False))}

            describe_fp = fingerprint_batch_describe(metadata_for_describe, shared_selection)
            loaded_chk = _analyze_load_checkpoint(runner, job_id)
            skip_describe = False
            if loaded_chk.get('stage') == 'score':
                describe_sub = loaded_chk.get('describe') or {}
                if isinstance(describe_sub, dict) and describe_sub.get('fingerprint') == describe_fp:
                    skip_describe = True

            describe_summary: dict | None = None
            if skip_describe:
                describe_summary = {
                    'described': 0,
                    'skipped': 0,
                    'failed': 0,
                    'total': int((loaded_chk.get('describe') or {}).get('total_at_start') or 0),
                }
            else:
                update_job_field(runner.db, job_id, 'current_step', 'Describing')
                describe_summary = _run_describe_pass(
                    runner,
                    job_id,
                    metadata_for_describe,
                    lib_db,
                    shared_selection,
                    db_path=db_path,
                    progress_range=(0, 50),
                    log_prefix='[describe] ',
                    finalize=False,
                    nested_analyze_checkpoint=True,
                )
                if describe_summary is None:
                    return

            update_job_field(runner.db, job_id, 'current_step', 'Scoring')
            score_summary = _run_score_pass(
                runner,
                job_id,
                metadata_for_score,
                lib_db,
                shared_selection,
                db_path=db_path,
                progress_range=(50, 100),
                log_prefix='[score] ',
                finalize=False,
                nested_analyze_checkpoint=True,
            )
            if score_summary is None:
                return

            combined = {
                'describe_total': int(describe_summary.get('total', 0)),
                'describe_succeeded': int(describe_summary.get('described', 0)),
                'describe_failed': int(describe_summary.get('failed', 0)),
                'score_total': int(score_summary.get('total', 0)),
                'score_succeeded': int(score_summary.get('scored', 0)),
                'score_failed': int(score_summary.get('failed', 0)),
                'skip_reason_counts': _merge_skip_reason_counts(
                    describe_summary.get('skip_reason_counts'),
                    score_summary.get('skip_reason_counts'),
                ),
            }
            runner.clear_checkpoint(job_id)
            runner.complete_job(job_id, combined)

    except Exception as e:
        severity = _failure_severity_from_exception(e)
        runner.fail_job(job_id, str(e), severity=severity)
    finally:
        if old_model_env is not None:
            os.environ['DESCRIPTION_VISION_MODEL'] = old_model_env
        else:
            os.environ.pop('DESCRIPTION_VISION_MODEL', None)
