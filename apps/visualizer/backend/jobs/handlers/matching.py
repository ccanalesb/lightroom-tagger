"""Vision matching and catalog enrichment / prepare_catalog job handlers."""

import os
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from unittest.mock import MagicMock

from database import add_job_log, get_job, update_job_field
from library_db import require_library_db

from lightroom_tagger.core.config import load_config
from lightroom_tagger.core.database import init_database
from lightroom_tagger.scripts.match_instagram_dump import match_dump_media

from .db_lifecycle import make_managed_library_db
from ..checkpoint import fingerprint_catalog_keys, fingerprint_vision_match, job_type_entry, load_resume_state
from .common import (
    _CHECKPOINT_MAX_ENTRIES,
    _failure_severity_from_exception,
    _resolve_library_db_or_fail,
)
from .path_diagnostics import PathSkipDiagnostics, make_path_classify_fn

managed_library_db = make_managed_library_db(lambda p: init_database(p))

_VISION_MATCH_PREFILTER_SUMMARY_EVERY = 40


def _vision_match_media_keys(db, metadata: dict) -> list[str]:
    """Return Instagram dump media keys that ``match_dump_media`` would process."""
    from datetime import datetime

    from lightroom_tagger.core.database import (
        get_instagram_by_date_filter,
        get_unprocessed_dump_media,
    )

    media_key = metadata.get('media_key')
    month = metadata.get('month')
    year = metadata.get('year')
    last_months = metadata.get('last_months')
    force_reprocess = bool(metadata.get('force_reprocess', False))
    run_start = datetime.now().isoformat()

    if media_key:
        row = db.execute(
            "SELECT media_key FROM instagram_dump_media WHERE media_key = ?",
            (media_key,),
        ).fetchone()
        return [str(row['media_key'])] if row else []

    if month or year or last_months:
        rows = get_instagram_by_date_filter(
            db,
            month=month,
            year=year,
            last_months=last_months,
            run_start=run_start,
            include_processed=force_reprocess,
        )
    else:
        rows = get_unprocessed_dump_media(
            db,
            limit=None,
            run_start=run_start,
            include_processed=force_reprocess,
        )
    return [str(r['media_key']) for r in rows if r.get('media_key')]


def _expand_matches_for_lightroom_writes(matches: list) -> list:
    """One match row may imply multiple catalog keys after stack-wide apply."""
    out = []
    for m in matches:
        keys = m.get('_lightroom_catalog_keys')
        if keys:
            for ck in keys:
                entry = {**m, 'catalog_key': ck}
                entry.pop('_lightroom_catalog_keys', None)
                out.append(entry)
        elif m.get('catalog_key'):
            out.append(dict(m))
    return out


def handle_vision_match(runner, job_id: str, metadata: dict):
    """Run vision matching with cascade filtering."""
    runner.update_progress(job_id, 10, 'Initializing...')

    try:
        config = load_config()

        custom_threshold = metadata.get('threshold', config.match_threshold or 0.7)
        custom_weights = metadata.get('weights', {
            'phash': config.phash_weight or 0.4,
            'description': config.desc_weight or 0.3,
            'vision': config.vision_weight or 0.3
        })
        force_descriptions = metadata.get('force_descriptions', False)
        skip_undescribed = bool(metadata.get('skip_undescribed', True))
        provider_id = metadata.get('provider_id')
        provider_model = metadata.get('provider_model')
        max_workers = int(metadata.get('max_workers', config.matching_workers or 4))

        raw_clip = metadata.get('clip_top_k', 50)
        try:
            raw_clip_int = int(float(raw_clip))
        except (TypeError, ValueError):
            add_job_log(
                runner.db,
                job_id,
                'warning',
                f'[vision-match] clip_top_k coercion: raw={raw_clip!r} -> default=50',
            )
            raw_clip_int = 50
        clip_top_k = max(1, min(raw_clip_int, 500))

        fp_vm = fingerprint_vision_match(
            threshold=float(custom_threshold),
            weights=dict(custom_weights),
            month=metadata.get('month'),
            year=metadata.get('year'),
            last_months=metadata.get('last_months'),
            media_key=metadata.get('media_key'),
            force_reprocess=bool(metadata.get('force_reprocess', False)),
            force_descriptions=bool(force_descriptions),
            skip_undescribed=skip_undescribed,
            provider_id=provider_id,
            provider_model=provider_model,
            max_workers=max_workers,
            clip_top_k=clip_top_k,
        )

        update_job_field(runner.db, job_id, 'metadata', {
            **metadata,
            'method': 'cascade_matching',
            'date_window_days': 90,
            'threshold': custom_threshold,
            'weights': custom_weights,
            **({"provider_id": provider_id} if provider_id else {}),
            **({"provider_model": provider_model} if provider_model else {}),
        })

        row_vm = get_job(runner.db, job_id)
        resume_media = load_resume_state(
            'vision_match',
            (row_vm.get('metadata') or {}) if row_vm and isinstance(row_vm.get('metadata'), dict) else {},
            fp_vm,
            lambda msg: add_job_log(runner.db, job_id, 'info', msg),
        )

        done_media: set[str] = set(resume_media)
        media_since_prefilter_summary = 0
        jt_vision_match = job_type_entry('vision_match')
        # Coordinator thread only: on_media_complete calls runner.persist_checkpoint (not workers).

        # judgments= log field / vision_judgments_total count shortlisted catalog candidates through score_candidates_with_vision, not LLM HTTP requests — keep names for parsers.
        def _emit_prefilter_summary(stats_snap: dict) -> None:
            add_job_log(
                runner.db,
                job_id,
                'info',
                (
                    'vision-match-prefilter-summary '
                    f"date_window_in={int(stats_snap.get('clip_prefilter_candidates_in', 0))} "
                    f"clip_shortlist_out={int(stats_snap.get('clip_prefilter_shortlist_total', 0))} "
                    f"judgments={int(stats_snap.get('vision_judgments_total', 0))}"
                ),
            )

        def on_media_complete(mk: str, stats_snap: dict | None = None) -> None:
            nonlocal media_since_prefilter_summary
            done_media.add(mk)
            if len(done_media) > _CHECKPOINT_MAX_ENTRIES:
                add_job_log(
                    runner.db,
                    job_id,
                    'error',
                    'checkpoint too large: exceeds maximum entry limit',
                )
                runner.fail_job(
                    job_id,
                    'checkpoint too large: exceeds 100000 entries',
                    severity='error',
                )
                runner.signal_cancel(job_id)
                return
            runner.persist_checkpoint(
                job_id,
                jt_vision_match.build_checkpoint_body(
                    fingerprint=fp_vm,
                    processed=done_media,
                ),
            )
            if stats_snap is not None:
                media_since_prefilter_summary += 1
                if media_since_prefilter_summary >= _VISION_MATCH_PREFILTER_SUMMARY_EVERY:
                    _emit_prefilter_summary(stats_snap)
                    media_since_prefilter_summary = 0

        start_time = time.time()
        db_path = require_library_db()
        print(f"[Job {job_id[:8]}] Using DB path: {db_path}")

        config = load_config()
        print(f"[Job {job_id[:8]}] Config loaded in {time.time() - start_time:.2f}s")

        with managed_library_db(db_path) as db:
            print(f"[Job {job_id[:8]}] Database opened")

            chain_mode = bool(metadata.get('_catalog_cache_chain'))
            path_diag = PathSkipDiagnostics(
                runner,
                job_id,
                db,
                job_label='vision_match',
                chain_mode=chain_mode,
                log_action='vision match',
            )
            media_keys = _vision_match_media_keys(db, metadata)
            if media_keys and not isinstance(db, MagicMock) and not path_diag.run_preflight(media_keys):
                return

            def progress_callback(current, total, message):
                """Report progress from matching."""
                progress = int(30 + (current / total) * 50)  # Scale to 30-80%
                runner.update_progress(job_id, progress, message)

            def log_callback(level, message):
                """Add detailed log entry to job."""
                from database import add_job_log
                add_job_log(runner.db, job_id, level, message)

            # Get date filters and custom options from metadata
            month = metadata.get('month')
            year = metadata.get('year')
            last_months = metadata.get('last_months')
            media_key = metadata.get('media_key')
            force_reprocess = metadata.get('force_reprocess', False)

            log_callback('info', f"Configuration: threshold={custom_threshold}, provider={provider_id or 'default'}, model={provider_model or 'auto'}")
            log_callback('info', f"Weights: phash={custom_weights['phash']:.2f}, desc={custom_weights['description']:.2f}, vision={custom_weights['vision']:.2f}")
            if force_descriptions:
                log_callback('info', 'Force regenerate descriptions: ON')

            def batch_progress_callback(item_idx, item_total, chunk, num_chunks):
                # Progress: 30-80% range, combining item position and intra-item batch position
                item_frac = (item_idx - 1 + chunk / num_chunks) / max(item_total, 1)
                progress = int(30 + item_frac * 50)
                step = f'Matching {item_idx}/{item_total} (batch {chunk}/{num_chunks})'
                runner.update_progress(job_id, progress, step)

            stats, matches = match_dump_media(
                db,
                threshold=custom_threshold,
                month=month,
                year=year,
                last_months=last_months,
                progress_callback=progress_callback,
                log_callback=log_callback,
                weights=custom_weights,
                media_key=media_key,
                force_descriptions=force_descriptions,
                force_reprocess=force_reprocess,
                skip_undescribed=skip_undescribed,
                provider_id=provider_id,
                provider_model=provider_model,
                max_workers=max_workers,
                clip_top_k=clip_top_k,
                should_cancel=lambda: runner.is_cancelled(job_id),
                resume_processed_keys=resume_media or None,
                on_media_complete=on_media_complete,
                batch_progress_callback=batch_progress_callback,
                source_job_id=job_id,
                path_classify_fn=make_path_classify_fn(db),
                skip_reason_counts=path_diag.skip_reason_counts,
            )

            if media_since_prefilter_summary > 0:
                _emit_prefilter_summary(stats)

            log_callback(
                'info',
                'Matching summary: non-representative catalog candidates filtered (cumulative) = '
                f"{stats.get('non_representative_candidates_filtered', 0)}",
            )
            log_callback(
                'info',
                'Stack-wide apply: members_applied='
                f"{stats.get('stack_members_applied', 0)}, skipped_conflicts="
                f"{stats.get('stack_members_skipped_conflicts', 0)}, skipped_other="
                f"{stats.get('stack_members_skipped_other', 0)}",
            )

            if runner.is_cancelled(job_id):
                runner.finalize_cancelled(job_id)
                return

            row_vm_done = get_job(runner.db, job_id)
            if row_vm_done and row_vm_done.get('status') == 'failed':
                return

            # Update Lightroom with "Posted" keyword for matched images
            lr_stats = {'success': 0, 'failed': 0}
            if runner.is_cancelled(job_id):
                runner.finalize_cancelled(job_id)
                return
            if matches:
                from lightroom_tagger.lightroom.writer import update_lightroom_from_matches
                catalog_path = config.catalog_path or config.small_catalog_path
                if catalog_path and Path(catalog_path).exists():
                    try:
                        lr_matches = _expand_matches_for_lightroom_writes(matches)
                        lr_stats = update_lightroom_from_matches(catalog_path, lr_matches)
                    except RuntimeError as e:
                        if str(e) == "Close Lightroom before writing to catalog.":
                            log_callback('error', str(e))
                            runner.fail_job(job_id, str(e), severity='critical')
                            return
                        raise
                else:
                    log_callback('warning', f'Lightroom catalog path not configured — {len(matches)} match(es) found but NOT written to catalog. Set CATALOG_PATH in .env to enable.')

            runner.update_progress(job_id, 100, 'Complete')
            result_payload = {
                'processed': stats['processed'],
                'matched': stats['matched'],
                'skipped': stats['skipped'],
                'descriptions_generated': stats.get('descriptions_generated', 0),
                'clip_prefilter_candidates_in': stats.get('clip_prefilter_candidates_in', 0),
                'clip_prefilter_shortlist_total': stats.get('clip_prefilter_shortlist_total', 0),
                'vision_judgments_total': stats.get('vision_judgments_total', 0),  # vision-scored candidates, not HTTP calls
                'stack_apply_applied': stats.get('stack_members_applied', 0),
                'stack_apply_skipped_conflicts': stats.get(
                    'stack_members_skipped_conflicts', 0
                ),
                'stack_apply_skipped_other': stats.get('stack_members_skipped_other', 0),
                'lightroom_updated': lr_stats['success'],
                'lightroom_failed': lr_stats['failed'],
                'method': 'cascade_matching',
                'date_window_days': 90,
                'threshold': custom_threshold,
                'weights': custom_weights,
                'skip_reason_counts': path_diag.skip_reason_counts,
                **({"provider_id": provider_id} if provider_id else {}),
                **({"provider_model": provider_model} if provider_model else {}),
            }
            if matches:
                best_score = max(float(m.get('total_score') or 0) for m in matches)
                result_payload['best_score'] = best_score
            runner.clear_checkpoint(job_id)
            runner.complete_job(job_id, result_payload)

    except Exception as e:
        if runner.is_cancelled(job_id):
            runner.finalize_cancelled(job_id)
            return
        severity = _failure_severity_from_exception(e)
        runner.fail_job(job_id, str(e), severity=severity)


def handle_enrich_catalog(runner, job_id: str, metadata: dict):
    """Enrich catalog with metadata."""
    import os

    from lightroom_tagger.core.analyzer import compute_phash, describe_image, extract_exif
    from lightroom_tagger.core.config import load_config
    from lightroom_tagger.core.database import (
        get_catalog_images_needing_analysis,
        init_catalog_table,
    )
    from lightroom_tagger.core.vision_cache import get_or_create_cached_image

    runner.update_progress(job_id, 10, 'Initializing enrichment...')

    config = load_config()
    db_path = _resolve_library_db_or_fail(runner, job_id)
    if db_path is None:
        return

    try:
        with managed_library_db(db_path) as db:
            init_catalog_table(db)

            catalog_images = get_catalog_images_needing_analysis(db)

            if not catalog_images:
                from lightroom_tagger.core.database import get_all_images
                all_images = get_all_images(db)
                catalog_images = [img for img in all_images if not img.get('analyzed_at')]

            total = len(catalog_images)
            catalog_keys = sorted(k for k in (r.get('key') for r in catalog_images) if k)
            fp_en = fingerprint_catalog_keys(total=total, keys=catalog_keys)
            row_en = get_job(runner.db, job_id)
            processed_ck = load_resume_state(
                'enrich_catalog',
                (row_en.get('metadata') or {}) if row_en and isinstance(row_en.get('metadata'), dict) else {},
                fp_en,
                lambda msg: add_job_log(runner.db, job_id, 'info', msg),
            )
            jt_enrich_catalog = job_type_entry('enrich_catalog')

            processed = 0
            skipped = 0
            errors = 0

            runner.update_progress(job_id, 20, f'Found {total} images to enrich')

            for i, record in enumerate(catalog_images):
                if runner.is_cancelled(job_id):
                    runner.finalize_cancelled(job_id)
                    return
                try:
                    key = record.get('key')
                    filepath = record.get('filepath')

                    if not key or not filepath:
                        skipped += 1
                        continue

                    if key in processed_ck:
                        continue

                    phash = compute_phash(filepath)
                    exif = extract_exif(filepath)
                    structured = describe_image(filepath)
                    analysis = {
                        'phash': phash,
                        'exif': exif,
                        'description': structured.get('summary', ''),
                        'structured_description': structured,
                    }

                    enriched_record = {
                        'key': key,
                        'filepath': filepath,
                        'analyzed_at': analysis.get('analyzed_at', 'unknown'),
                        'phash': analysis.get('phash'),
                        'exif': analysis.get('exif', {}),
                        'catalog_path': record.get('catalog_path', ''),
                        'date_taken': record.get('date_taken', ''),
                        'filename': record.get('filename', ''),
                        'rating': record.get('rating', 0),
                        'keywords': record.get('keywords', []),
                        'color_label': record.get('color_label', ''),
                        'title': record.get('title', ''),
                        'description': analysis.get('description', record.get('description', '')),
                    }

                    from lightroom_tagger.core.database import store_catalog_image
                    store_catalog_image(db, enriched_record)

                    if config.vision_cache_enabled:
                        get_or_create_cached_image(db, key, filepath)

                    processed += 1
                    processed_ck.add(key)
                    if len(processed_ck) > _CHECKPOINT_MAX_ENTRIES:
                        runner.fail_job(
                            job_id,
                            'checkpoint too large: exceeds 100000 entries',
                            severity='error',
                        )
                        return
                    # Single-threaded handler: safe to call runner.persist_checkpoint each iteration.
                    runner.persist_checkpoint(
                        job_id,
                        jt_enrich_catalog.build_checkpoint_body(
                            fingerprint=fp_en,
                            processed=processed_ck,
                        ),
                    )

                    if (i + 1) % 10 == 0 or i == total - 1:
                        progress = int(20 + (processed / total) * 70)
                        runner.update_progress(job_id, progress, f'Processed {processed}/{total} images')

                except Exception as e:
                    errors += 1
                    print(f"Error processing image {i + 1}: {e}")

            runner.clear_checkpoint(job_id)
            runner.complete_job(job_id, {
                'processed': processed,
                'skipped': skipped,
                'errors': errors,
                'method': 'enrich_catalog',
                'limit': metadata.get('limit')
            })

    except Exception as e:
        severity = _failure_severity_from_exception(e)
        runner.fail_job(job_id, str(e), severity=severity)


def handle_prepare_catalog(runner, job_id: str, metadata: dict):
    """Pre-compress and cache all catalog images for vision matching.

    This job compresses catalog images once and stores them in the vision cache,
    eliminating redundant compression during vision matching runs.
    """
    from lightroom_tagger.core.database import (
        get_all_catalog_images,
        get_cache_stats,
    )
    from lightroom_tagger.core.vision_cache import get_or_create_cached_image

    runner.update_progress(job_id, 5, 'Initializing cache preparation...')

    db_path = _resolve_library_db_or_fail(runner, job_id)
    if db_path is None:
        return

    try:
        with managed_library_db(db_path) as lib_db:

            # Update metadata with configuration
            config = load_config()
            cache_dir = config.vision_cache_dir

            update_job_field(runner.db, job_id, 'metadata', {
                **metadata,
                'cache_dir': cache_dir,
                'method': 'prepare_catalog_cache',
            })

            def log_callback(level, message):
                from database import add_job_log
                add_job_log(runner.db, job_id, level, message)

            # Get cache stats from library DB
            cache_stats_before = get_cache_stats(lib_db)
            total_images = cache_stats_before['total']
            already_cached = cache_stats_before['cached']

            log_callback('info', f"Cache directory: {cache_dir}")
            log_callback('info', f"Using library DB: {db_path}")
            log_callback('info', f"Cache status: {already_cached}/{total_images} images cached ({cache_stats_before['cache_size_mb']:.1f}MB)")

            if total_images == 0:
                runner.clear_checkpoint(job_id)
                runner.complete_job(job_id, {
                    'cached': 0,
                    'already_cached': 0,
                    'failed': 0,
                    'total': 0,
                    'cache_size_mb': 0,
                    'message': 'No catalog images found'
                })
                return

            # Get all catalog images from library DB
            images = get_all_catalog_images(lib_db)
            catalog_keys_pr = sorted(k for k in (img.get('key') for img in images) if k)
            fp_pr = fingerprint_catalog_keys(total=len(images), keys=catalog_keys_pr)
            row_pr = get_job(runner.db, job_id)
            processed_prep = load_resume_state(
                'prepare_catalog',
                (row_pr.get('metadata') or {}) if row_pr and isinstance(row_pr.get('metadata'), dict) else {},
                fp_pr,
                lambda msg: add_job_log(runner.db, job_id, 'info', msg),
            )
            jt_prepare_catalog = job_type_entry('prepare_catalog')

            def _prepare_image_pending(img: dict) -> bool:
                k = img.get('key')
                if not k:
                    return True
                return k not in processed_prep

            pending_images = [img for img in images if _prepare_image_pending(img)]

            def process_single_image(image, db_path):
                """Each thread gets its own DB connection."""
                filepath = image.get('filepath')
                key = image.get('key')
                if not filepath or not key:
                    return ('failed', key or 'unknown', 'Missing filepath or key')
                if not os.path.exists(filepath):
                    return ('failed', key, f'File not found: {filepath}')

                thread_db = sqlite3.connect(db_path)
                thread_db.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r, strict=False))
                thread_db.execute("PRAGMA journal_mode=WAL")
                # Match ``init_database`` — 30s busy_timeout + synchronous=NORMAL
                # to survive parallel-writer contention on the library DB.
                thread_db.execute("PRAGMA busy_timeout=30000")
                thread_db.execute("PRAGMA synchronous=NORMAL")
                try:
                    from lightroom_tagger.core.database import is_vision_cache_valid

                    if is_vision_cache_valid(thread_db, key, filepath):
                        return ('already_cached', key)
                    compressed_path = get_or_create_cached_image(thread_db, key, filepath)
                    if compressed_path:
                        size_kb = os.path.getsize(compressed_path) / 1024
                        return ('newly_cached', key, size_kb)
                    return ('failed', key, 'Compression returned None')
                except Exception as e:
                    return ('failed', key, str(e))
                finally:
                    thread_db.close()

            newly_cached = 0
            already_cached_count = 0
            failed_count = 0
            total = len(images)
            total_run = len(pending_images)

            max_workers = min(4, os.cpu_count() or 2)
            if pending_images:
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {
                        executor.submit(process_single_image, img, db_path): img
                        for img in pending_images
                    }
                    for completed, _future in enumerate(as_completed(futures), start=1):
                        if runner.is_cancelled(job_id):
                            add_job_log(
                                runner.db,
                                job_id,
                                'info',
                                'Prepare catalog cache stopped: cancel requested',
                            )
                            break
                        result = _future.result()
                        kind = result[0]
                        if kind == 'already_cached':
                            already_cached_count += 1
                        elif kind == 'newly_cached':
                            newly_cached += 1
                        elif kind == 'failed':
                            failed_count += 1
                            err_key = result[1]
                            err_msg = result[2] if len(result) > 2 else 'unknown'
                            log_callback('error', f"Failed to cache {err_key}: {err_msg}")

                        res_key = result[1] if len(result) > 1 else None
                        if kind in ('already_cached', 'newly_cached') and res_key and res_key != 'unknown':
                            processed_prep.add(res_key)
                            if len(processed_prep) > _CHECKPOINT_MAX_ENTRIES:
                                add_job_log(
                                    runner.db,
                                    job_id,
                                    'error',
                                    'checkpoint too large: exceeds maximum entry limit',
                                )
                                runner.fail_job(
                                    job_id,
                                    'checkpoint too large: exceeds 100000 entries',
                                    severity='error',
                                )
                                runner.signal_cancel(job_id)
                                break
                            # Coordinator thread (as_completed): runner.persist_checkpoint only here.
                            runner.persist_checkpoint(
                                job_id,
                                jt_prepare_catalog.build_checkpoint_body(
                                    fingerprint=fp_pr,
                                    processed=processed_prep,
                                ),
                            )

                        if completed % 10 == 0 or completed == total_run:
                            progress = int(10 + (completed / total_run) * 85)
                            runner.update_progress(
                                job_id, progress, f'Processed {completed}/{total_run} images'
                            )

            if runner.is_cancelled(job_id):
                runner.finalize_cancelled(job_id)
                return

            row_prep_done = get_job(runner.db, job_id)
            if row_prep_done and row_prep_done.get('status') == 'failed':
                return

            # Get final cache stats from library DB
            cache_stats_after = get_cache_stats(lib_db)
            log_callback('info', f"Complete: {newly_cached} newly cached, {already_cached_count} already cached, {failed_count} failed")
            log_callback('info', f"Total cache size: {cache_stats_after['cache_size_mb']:.1f}MB")

            runner.clear_checkpoint(job_id)
            runner.complete_job(job_id, {
                'cached': newly_cached,
                'already_cached': already_cached_count,
                'failed': failed_count,
                'total': total,
                'cache_size_mb': cache_stats_after['cache_size_mb'],
                'parallel_workers': max_workers,
                'cache_dir': cache_dir
            })

    except Exception as e:
        severity = _failure_severity_from_exception(e)
        runner.fail_job(job_id, str(e), severity=severity)
