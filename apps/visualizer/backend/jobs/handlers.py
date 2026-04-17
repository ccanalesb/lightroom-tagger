"""Job type handlers for vision matching and catalog operations."""
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from database import add_job_log, get_job, update_job_field

from lightroom_tagger.core.config import load_config
from lightroom_tagger.core.database import init_database
from lightroom_tagger.core.provider_errors import AuthenticationError, InvalidRequestError
from lightroom_tagger.scripts.import_instagram_dump import import_dump
from lightroom_tagger.scripts.match_instagram_dump import match_dump_media

from . import path_setup as _path_setup  # noqa: F401
from .checkpoint import (
    fingerprint_batch_describe,
    fingerprint_batch_score,
    fingerprint_catalog_keys,
    fingerprint_vision_match,
)

_CHECKPOINT_MAX_ENTRIES = 100_000


def _failure_severity_from_exception(exc: BaseException) -> str:
    if isinstance(exc, (AuthenticationError, InvalidRequestError)):
        return 'warning'
    if isinstance(exc, (PermissionError, OSError)):
        return 'critical'
    if isinstance(exc, RuntimeError) and str(exc) == 'Close Lightroom before writing to catalog.':
        return 'critical'
    return 'error'


def handle_analyze_instagram(runner, job_id: str, metadata: dict):
    """Analyze Instagram images."""
    runner.update_progress(job_id, 50, 'Analyzing images...')
    runner.complete_job(job_id, {'images_processed': 0})


def handle_instagram_import(runner, job_id: str, metadata: dict):
    """Import Instagram export dump media into the library database."""
    add_job_log(runner.db, job_id, 'info', 'Starting Instagram dump import...')
    runner.update_progress(job_id, 10, 'Importing Instagram dump...')

    try:
        config = load_config()
        raw = (
            metadata.get('dump_path')
            or config.instagram_dump_path
            or os.getenv('INSTAGRAM_DUMP_PATH')
            or ''
        )
        stripped = str(raw).strip()
        if not stripped:
            runner.fail_job(
                job_id,
                'Instagram dump path not configured or not a directory',
                severity='warning',
            )
            return
        dump_path = Path(stripped).expanduser()
        if not os.path.isdir(dump_path):
            runner.fail_job(
                job_id,
                'Instagram dump path not configured or not a directory',
                severity='warning',
            )
            return

        db_path = os.getenv('LIBRARY_DB')
        if not db_path:
            db_path = config.db_path or 'library.db'
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Database not found at: {db_path}")

        skip_dedup = bool(metadata.get('skip_dedup', False))
        reimport = bool(metadata.get('reimport', False))

        db = init_database(db_path)
        try:
            imported = import_dump(
                db,
                str(dump_path),
                skip_existing=not reimport,
                skip_dedup=skip_dedup,
            )
        finally:
            db.close()

        runner.update_progress(job_id, 100, 'Complete')
        runner.complete_job(
            job_id,
            {
                'imported': imported,
                'dump_path': str(dump_path),
                'reimport': reimport,
                'skip_dedup': skip_dedup,
            },
        )
    except Exception as e:
        severity = _failure_severity_from_exception(e)
        runner.fail_job(job_id, str(e), severity=severity)


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
        provider_id = metadata.get('provider_id')
        provider_model = metadata.get('provider_model')
        max_workers = int(metadata.get('max_workers', config.matching_workers or 4))

        fp_vm = fingerprint_vision_match(
            threshold=float(custom_threshold),
            weights=dict(custom_weights),
            month=metadata.get('month'),
            year=metadata.get('year'),
            last_months=metadata.get('last_months'),
            media_key=metadata.get('media_key'),
            force_reprocess=bool(metadata.get('force_reprocess', False)),
            force_descriptions=bool(force_descriptions),
            provider_id=provider_id,
            provider_model=provider_model,
            max_workers=max_workers,
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

        resume_media: set[str] = set()
        row_vm = get_job(runner.db, job_id)
        if row_vm:
            meta_vm = row_vm.get('metadata') or {}
            if isinstance(meta_vm, dict):
                chk_vm = meta_vm.get('checkpoint')
                if (
                    isinstance(chk_vm, dict)
                    and chk_vm.get('checkpoint_version') == 1
                    and chk_vm.get('job_type') == 'vision_match'
                ):
                    if chk_vm.get('fingerprint') == fp_vm:
                        resume_media = set(chk_vm.get('processed_media_keys') or [])
                    else:
                        add_job_log(
                            runner.db,
                            job_id,
                            'info',
                            'checkpoint mismatch: vision_match fingerprint changed, starting fresh',
                        )

        done_media: set[str] = set(resume_media)
        # Coordinator thread only: on_media_complete calls runner.persist_checkpoint (not workers).

        def on_media_complete(mk: str) -> None:
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
                {
                    'job_type': 'vision_match',
                    'fingerprint': fp_vm,
                    'processed_media_keys': sorted(done_media),
                },
            )

        # Use LIBRARY_DB env var if set, otherwise fall back to config
        import os
        import time

        start_time = time.time()
        db_path = os.getenv('LIBRARY_DB')
        print(f"[Job {job_id[:8]}] LIBRARY_DB env: {db_path is not None}")

        config = load_config()
        print(f"[Job {job_id[:8]}] Config loaded in {time.time() - start_time:.2f}s")

        if not db_path:
            db_path = config.db_path or 'library.db'
            print(f"[Job {job_id[:8]}] Using DB path: {db_path}")

        # Check if database exists
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Database not found at: {db_path}")

        db = init_database(db_path)
        print(f"[Job {job_id[:8]}] Database opened")

        def progress_callback(current, total, message):
            """Report progress from matching."""
            progress = int(30 + (current / total) * 50)  # Scale to 30-80%
            runner.update_progress(job_id, progress, message)

        def log_callback(level, message):
            """Add detailed log entry to job."""
            from database import add_job_log
            add_job_log(runner.db, job_id, level, message)

        try:
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
                provider_id=provider_id,
                provider_model=provider_model,
                max_workers=max_workers,
                should_cancel=lambda: runner.is_cancelled(job_id),
                resume_processed_keys=resume_media or None,
                on_media_complete=on_media_complete,
                batch_progress_callback=batch_progress_callback,
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
                        lr_stats = update_lightroom_from_matches(catalog_path, matches)
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
                'lightroom_updated': lr_stats['success'],
                'lightroom_failed': lr_stats['failed'],
                'method': 'cascade_matching',
                'date_window_days': 90,
                'threshold': custom_threshold,
                'weights': custom_weights,
                **({"provider_id": provider_id} if provider_id else {}),
                **({"provider_model": provider_model} if provider_model else {}),
            }
            if matches:
                best_score = max(float(m.get('total_score') or 0) for m in matches)
                result_payload['best_score'] = best_score
            runner.clear_checkpoint(job_id)
            runner.complete_job(job_id, result_payload)

        finally:
            db.close()

    except Exception as e:
        if runner.is_cancelled(job_id):
            runner.finalize_cancelled(job_id)
            return
        severity = _failure_severity_from_exception(e)
        runner.fail_job(job_id, str(e), severity=severity)


def handle_enrich_catalog(runner, job_id: str, metadata: dict):
    """Enrich catalog with metadata."""
    import os

    from lightroom_tagger.core.analyzer import analyze_image
    from lightroom_tagger.core.config import load_config
    from lightroom_tagger.core.database import (
        get_catalog_images_needing_analysis,
        init_catalog_table,
        init_database,
    )
    from lightroom_tagger.core.vision_cache import get_or_create_cached_image

    runner.update_progress(job_id, 10, 'Initializing enrichment...')

    config = load_config()
    db_path = os.getenv('LIBRARY_DB')
    if not db_path:
        db_path = config.db_path or 'library.db'

    if not os.path.exists(db_path):
        runner.fail_job(job_id, f"Library database not found at: {db_path}")
        return

    db = None
    try:
        db = init_database(db_path)
        init_catalog_table(db)

        catalog_images = get_catalog_images_needing_analysis(db)

        if not catalog_images:
            from lightroom_tagger.core.database import get_all_images
            all_images = get_all_images(db)
            catalog_images = [img for img in all_images if not img.get('analyzed_at')]

        total = len(catalog_images)
        catalog_keys = sorted(k for k in (r.get('key') for r in catalog_images) if k)
        fp_en = fingerprint_catalog_keys(total=total, keys=catalog_keys)
        processed_ck: set[str] = set()
        row_en = get_job(runner.db, job_id)
        if row_en:
            meta_en = row_en.get('metadata') or {}
            if isinstance(meta_en, dict):
                chk_en = meta_en.get('checkpoint')
                if (
                    isinstance(chk_en, dict)
                    and chk_en.get('checkpoint_version') == 1
                    and chk_en.get('job_type') == 'enrich_catalog'
                ):
                    if chk_en.get('fingerprint') == fp_en:
                        processed_ck = set(chk_en.get('processed_image_keys') or [])
                    else:
                        add_job_log(
                            runner.db,
                            job_id,
                            'info',
                            'checkpoint mismatch: enrich_catalog fingerprint changed, starting fresh',
                        )

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

                analysis = analyze_image(filepath)

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
                    {
                        'job_type': 'enrich_catalog',
                        'fingerprint': fp_en,
                        'processed_image_keys': sorted(processed_ck),
                    },
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
    finally:
        if db is not None:
            db.close()


def handle_prepare_catalog(runner, job_id: str, metadata: dict):
    """Pre-compress and cache all catalog images for vision matching.

    This job compresses catalog images once and stores them in the vision cache,
    eliminating redundant compression during vision matching runs.
    """
    from lightroom_tagger.core.database import (
        get_all_catalog_images,
        get_cache_stats,
        init_database,
    )
    from lightroom_tagger.core.vision_cache import get_or_create_cached_image

    runner.update_progress(job_id, 5, 'Initializing cache preparation...')

    # Use LIBRARY_DB for cache operations, not runner.db
    db_path = os.getenv('LIBRARY_DB')
    if not db_path:
        config = load_config()
        db_path = config.db_path or 'library.db'

    if not os.path.exists(db_path):
        runner.fail_job(job_id, f"Library database not found at: {db_path}")
        return

    lib_db = None
    try:
        lib_db = init_database(db_path)

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
        processed_prep: set[str] = set()
        row_pr = get_job(runner.db, job_id)
        if row_pr:
            meta_pr = row_pr.get('metadata') or {}
            if isinstance(meta_pr, dict):
                chk_pr = meta_pr.get('checkpoint')
                if (
                    isinstance(chk_pr, dict)
                    and chk_pr.get('checkpoint_version') == 1
                    and chk_pr.get('job_type') == 'prepare_catalog'
                ):
                    if chk_pr.get('fingerprint') == fp_pr:
                        processed_prep = set(chk_pr.get('processed_image_keys') or [])
                    else:
                        add_job_log(
                            runner.db,
                            job_id,
                            'info',
                            'checkpoint mismatch: prepare_catalog fingerprint changed, starting fresh',
                        )

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
            thread_db.execute("PRAGMA busy_timeout=5000")
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
                            {
                                'job_type': 'prepare_catalog',
                                'fingerprint': fp_pr,
                                'processed_image_keys': sorted(processed_prep),
                            },
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
    finally:
        if lib_db:
            lib_db.close()


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
            if not os.path.exists(resolved):
                return f'File not found: {resolved}'
            return 'Model returned empty or invalid response'
        else:
            if not force and get_image_description(lib_db, key):
                return 'Already described (use force to regenerate)'
            ig = get_instagram_dump_media(lib_db, key)
            if not ig:
                return 'Instagram media key not found'
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
    lib_db = None
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
        db_path = os.getenv('LIBRARY_DB')
        if not db_path:
            db_path = config.db_path or 'library.db'
        if not os.path.exists(db_path):
            runner.fail_job(job_id, f"Library database not found at: {db_path}")
            return
        lib_db = init_database(db_path)

        raw_ps = metadata.get('perspective_slugs')
        if isinstance(raw_ps, list) and len(raw_ps) > 0:
            perspective_slugs = [str(x) for x in raw_ps]
        else:
            perspective_slugs = None

        runner.update_progress(job_id, 10, f'Describing {image_type} image…')

        status, success, error_msg = _describe_single_image(
            lib_db, image_key, image_type, force, provider_id, provider_model,
            perspective_slugs,
        )

        if success:
            runner.complete_job(job_id, {
                'image_key': image_key,
                'image_type': image_type,
                'status': status,
            })
        else:
            runner.fail_job(job_id, error_msg or 'Description generation failed')

    except Exception as e:
        severity = _failure_severity_from_exception(e)
        runner.fail_job(job_id, str(e), severity=severity)
    finally:
        if lib_db:
            lib_db.close()


def handle_single_score(runner, job_id: str, metadata: dict):
    """Score a single image for one or more perspectives.

    Fails the job if **any** requested perspective returns hard ``failed`` (skips are OK).
    """
    lib_db = None
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
        db_path = os.getenv('LIBRARY_DB')
        if not db_path:
            db_path = config.db_path or 'library.db'
        if not os.path.exists(db_path):
            runner.fail_job(job_id, f"Library database not found at: {db_path}")
            return
        lib_db = init_database(db_path)

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
        })
    except Exception as e:
        severity = _failure_severity_from_exception(e)
        runner.fail_job(job_id, str(e), severity=severity)
    finally:
        if lib_db:
            lib_db.close()


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
    processed_pairs: set[str] = set()
    if nested_analyze_checkpoint:
        nested_chk = _analyze_load_checkpoint(runner, job_id)
        describe_obj = nested_chk.get('describe') if isinstance(nested_chk, dict) else None
        if isinstance(describe_obj, dict):
            if describe_obj.get('fingerprint') == fp_bd:
                processed_pairs = set(describe_obj.get('processed_pairs') or [])
            elif describe_obj.get('fingerprint'):
                add_job_log(
                    runner.db,
                    job_id,
                    'info',
                    'checkpoint mismatch: batch_analyze describe fingerprint changed, starting describe fresh',
                )
    else:
        row_bd = get_job(runner.db, job_id)
        if row_bd:
            meta_bd = row_bd.get('metadata') or {}
            if isinstance(meta_bd, dict):
                chk_bd = meta_bd.get('checkpoint')
                if (
                    isinstance(chk_bd, dict)
                    and chk_bd.get('checkpoint_version') == 1
                    and chk_bd.get('job_type') == 'batch_describe'
                ):
                    if chk_bd.get('fingerprint') == fp_bd:
                        processed_pairs = set(chk_bd.get('processed_pairs') or [])
                    else:
                        add_job_log(
                            runner.db,
                            job_id,
                            'info',
                            f'{log_prefix}checkpoint mismatch: batch_describe fingerprint changed, starting fresh'
                            if log_prefix else
                            'checkpoint mismatch: batch_describe fingerprint changed, starting fresh',
                        )

    def pair_label(key: str, itype: str) -> str:
        return f'{key}|{itype}'

    images_to_describe = [
        (k, t) for k, t in images_to_describe if pair_label(k, t) not in processed_pairs
    ]

    if not force and images_to_describe:
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
        empty = {'described': 0, 'skipped': 0, 'failed': 0, 'total': 0}
        if finalize:
            runner.clear_checkpoint(job_id)
            runner.complete_job(job_id, empty)
            return None
        return empty

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
                {'job_type': 'batch_describe', **describe_payload},
            )
        return True

    described = 0
    skipped = 0
    failed = 0
    consecutive_failures = 0

    if max_workers > 1 and total > 3:
        def process_image_worker(key: str, itype: str):
            """Worker function with its own DB connection."""
            worker_db = init_database(db_path)
            try:
                status, success, error_msg = _describe_single_image(
                    worker_db, key, itype, force, desc_provider_id, desc_provider_model,
                    perspective_slugs,
                )
                return (key, status, error_msg)
            finally:
                worker_db.close()

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
                lib_db, key, itype, force, desc_provider_id, desc_provider_model,
                perspective_slugs,
            )

            if status == 'described':
                described += 1
                consecutive_failures = 0
                if not record_done(key, itype):
                    break
            elif status == 'skipped':
                skipped += 1
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

    result_summary = {
        'described': described,
        'skipped': skipped,
        'failed': failed,
        'total': total_at_start,
        'image_type': image_type,
        'date_filter': date_filter,
        'force': force,
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
    lib_db = None
    old_model_env = os.environ.get('DESCRIPTION_VISION_MODEL')
    try:
        config = load_config()
        db_path = os.getenv('LIBRARY_DB')
        if not db_path:
            db_path = config.db_path or 'library.db'
        if not os.path.exists(db_path):
            runner.fail_job(job_id, f"Library database not found at: {db_path}")
            return
        lib_db = init_database(db_path)

        image_type = metadata.get('image_type', 'both')  # catalog, instagram, both
        date_filter = metadata.get('date_filter', 'all')  # all, 3months, 6months, 12months
        force = metadata.get('force', False)

        months = {'3months': 3, '6months': 6, '12months': 12}.get(date_filter)
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

        images_to_describe: list[tuple[str, str]] = []  # (key, type)

        if image_type in ('catalog', 'both'):
            if force:
                sql = "SELECT key FROM images"
                conditions: list[str] = []
                sql_params: list = []
                if months:
                    conditions.append("date_taken >= date('now', ?)")
                    sql_params.append(f'-{months} months')
                if min_rating is not None:
                    conditions.append("rating >= ?")
                    sql_params.append(min_rating)
                if conditions:
                    sql += " WHERE " + " AND ".join(conditions)
                rows = lib_db.execute(sql, tuple(sql_params)).fetchall()
                images_to_describe += [(r['key'], 'catalog') for r in rows]
            else:
                images_to_describe += [
                    (img['key'], 'catalog')
                    for img in get_undescribed_catalog_images(
                        lib_db, months=months, min_rating=min_rating
                    )
                ]

        if image_type in ('instagram', 'both'):
            if force:
                rows = lib_db.execute("SELECT media_key FROM instagram_dump_media").fetchall()
                if months:
                    rows = lib_db.execute(
                        "SELECT media_key FROM instagram_dump_media WHERE created_at >= date('now', ?)",
                        (f'-{months} months',),
                    ).fetchall()
                images_to_describe += [(r['media_key'], 'instagram') for r in rows]
            else:
                images_to_describe += [
                    (img['media_key'], 'instagram')
                    for img in get_undescribed_instagram_images(lib_db, months=months)
                ]

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
        if lib_db:
            lib_db.close()


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
    processed_triplets: set[str] = set()
    if nested_analyze_checkpoint:
        nested_chk = _analyze_load_checkpoint(runner, job_id)
        score_obj = nested_chk.get('score') if isinstance(nested_chk, dict) else None
        if isinstance(score_obj, dict):
            if score_obj.get('fingerprint') == fp_bs:
                processed_triplets = set(score_obj.get('processed_triplets') or [])
            elif score_obj.get('fingerprint'):
                add_job_log(
                    runner.db,
                    job_id,
                    'info',
                    'checkpoint mismatch: batch_analyze score fingerprint changed, starting score fresh',
                )
    else:
        row_bs = get_job(runner.db, job_id)
        if row_bs:
            meta_bs = row_bs.get('metadata') or {}
            if isinstance(meta_bs, dict):
                chk_bs = meta_bs.get('checkpoint')
                if (
                    isinstance(chk_bs, dict)
                    and chk_bs.get('checkpoint_version') == 1
                    and chk_bs.get('job_type') == 'batch_score'
                ):
                    if chk_bs.get('fingerprint') == fp_bs:
                        processed_triplets = set(chk_bs.get('processed_triplets') or [])
                    else:
                        add_job_log(
                            runner.db,
                            job_id,
                            'info',
                            f'{log_prefix}checkpoint mismatch: batch_score fingerprint changed, starting fresh'
                            if log_prefix else
                            'checkpoint mismatch: batch_score fingerprint changed, starting fresh',
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
        empty = {'scored': 0, 'skipped': 0, 'failed': 0, 'total': 0}
        if finalize:
            runner.clear_checkpoint(job_id)
            runner.complete_job(job_id, empty)
            return None
        return empty

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
                {'job_type': 'batch_score', **score_payload},
            )
        return True

    scored = 0
    skipped = 0
    failed = 0
    consecutive_failures = 0

    if max_workers > 1 and total > 3:
        def process_score_worker(key: str, itype: str, slug: str):
            worker_db = init_database(db_path)
            try:
                return _score_single_image(
                    worker_db, key, itype, slug, force,
                    score_provider_id, score_provider_model, None,
                )
            finally:
                worker_db.close()

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
    lib_db = None
    try:
        config = load_config()
        db_path = os.getenv('LIBRARY_DB')
        if not db_path:
            db_path = config.db_path or 'library.db'
        if not os.path.exists(db_path):
            runner.fail_job(job_id, f"Library database not found at: {db_path}")
            return
        lib_db = init_database(db_path)

        image_type = metadata.get('image_type', 'both')
        date_filter = metadata.get('date_filter', 'all')

        months = {'3months': 3, '6months': 6, '12months': 12}.get(date_filter)
        min_rating_raw = metadata.get('min_rating')
        min_rating = None
        if min_rating_raw is not None:
            try:
                min_rating = int(min_rating_raw)
            except (TypeError, ValueError):
                min_rating = None
        force = metadata.get('force', False)

        images_for_scores: list[tuple[str, str]] = []

        if image_type in ('catalog', 'both'):
            if force:
                sql = "SELECT key FROM images"
                conditions: list[str] = []
                sql_params: list = []
                if months:
                    conditions.append("date_taken >= date('now', ?)")
                    sql_params.append(f'-{months} months')
                if min_rating is not None:
                    conditions.append("rating >= ?")
                    sql_params.append(min_rating)
                if conditions:
                    sql += " WHERE " + " AND ".join(conditions)
                rows = lib_db.execute(sql, tuple(sql_params)).fetchall()
                images_for_scores += [(r['key'], 'catalog') for r in rows]
            else:
                sql = "SELECT key FROM images"
                conditions = []
                sql_params = []
                if months:
                    conditions.append("date_taken >= date('now', ?)")
                    sql_params.append(f'-{months} months')
                if min_rating is not None:
                    conditions.append("rating >= ?")
                    sql_params.append(min_rating)
                if conditions:
                    sql += " WHERE " + " AND ".join(conditions)
                rows = lib_db.execute(sql, tuple(sql_params)).fetchall()
                images_for_scores += [(r['key'], 'catalog') for r in rows]

        if image_type in ('instagram', 'both'):
            if force:
                rows = lib_db.execute("SELECT media_key FROM instagram_dump_media").fetchall()
                if months:
                    rows = lib_db.execute(
                        "SELECT media_key FROM instagram_dump_media WHERE created_at >= date('now', ?)",
                        (f'-{months} months',),
                    ).fetchall()
                images_for_scores += [(r['media_key'], 'instagram') for r in rows]
            else:
                rows = lib_db.execute("SELECT media_key FROM instagram_dump_media").fetchall()
                if months:
                    rows = lib_db.execute(
                        "SELECT media_key FROM instagram_dump_media WHERE created_at >= date('now', ?)",
                        (f'-{months} months',),
                    ).fetchall()
                images_for_scores += [(r['media_key'], 'instagram') for r in rows]

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
    finally:
        if lib_db:
            lib_db.close()


def handle_batch_analyze(runner, job_id: str, metadata: dict):
    """Unified analyze: run describe then score over a single shared (key, itype) selection.

    Drives one job through two stages with split progress (``0..50`` describe, ``50..100`` score),
    ``current_step`` updates (``'Describing'`` / ``'Scoring'``), nested ``batch_analyze``
    checkpoints, and a combined ``complete_job`` payload (D-06 keys). ``force_describe`` /
    ``force_score`` in ``metadata`` are normalized into per-stage ``force`` via shallow-merge
    before hitting the helpers' fingerprint + pre-filter logic (D-11).
    """
    lib_db = None
    old_model_env = os.environ.get('DESCRIPTION_VISION_MODEL')
    try:
        config = load_config()
        db_path = os.getenv('LIBRARY_DB')
        if not db_path:
            db_path = config.db_path or 'library.db'
        if not os.path.exists(db_path):
            runner.fail_job(job_id, f"Library database not found at: {db_path}")
            return
        lib_db = init_database(db_path)

        image_type = metadata.get('image_type', 'both')
        date_filter = metadata.get('date_filter', 'all')
        force = bool(metadata.get('force_describe', False))

        months = {'3months': 3, '6months': 6, '12months': 12}.get(date_filter)
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

        shared_selection: list[tuple[str, str]] = []

        if image_type in ('catalog', 'both'):
            if force:
                sql = "SELECT key FROM images"
                conditions: list[str] = []
                sql_params: list = []
                if months:
                    conditions.append("date_taken >= date('now', ?)")
                    sql_params.append(f'-{months} months')
                if min_rating is not None:
                    conditions.append("rating >= ?")
                    sql_params.append(min_rating)
                if conditions:
                    sql += " WHERE " + " AND ".join(conditions)
                rows = lib_db.execute(sql, tuple(sql_params)).fetchall()
                shared_selection += [(r['key'], 'catalog') for r in rows]
            else:
                shared_selection += [
                    (img['key'], 'catalog')
                    for img in get_undescribed_catalog_images(
                        lib_db, months=months, min_rating=min_rating
                    )
                ]

        if image_type in ('instagram', 'both'):
            if force:
                rows = lib_db.execute("SELECT media_key FROM instagram_dump_media").fetchall()
                if months:
                    rows = lib_db.execute(
                        "SELECT media_key FROM instagram_dump_media WHERE created_at >= date('now', ?)",
                        (f'-{months} months',),
                    ).fetchall()
                shared_selection += [(r['media_key'], 'instagram') for r in rows]
            else:
                shared_selection += [
                    (img['media_key'], 'instagram')
                    for img in get_undescribed_instagram_images(lib_db, months=months)
                ]

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
        if lib_db:
            lib_db.close()


JOB_HANDLERS = {
    'analyze_instagram': handle_analyze_instagram,
    'instagram_import': handle_instagram_import,
    'vision_match': handle_vision_match,
    'enrich_catalog': handle_enrich_catalog,
    'prepare_catalog': handle_prepare_catalog,
    'batch_describe': handle_batch_describe,
    'single_describe': handle_single_describe,
    'single_score': handle_single_score,
    'batch_score': handle_batch_score,
    'batch_analyze': handle_batch_analyze,
}
