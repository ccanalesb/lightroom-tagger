"""Job type handlers for vision matching and catalog operations."""
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from database import add_job_log, update_job_field

from lightroom_tagger.core.config import load_config
from lightroom_tagger.core.database import init_database
from lightroom_tagger.core.provider_errors import AuthenticationError, InvalidRequestError
from lightroom_tagger.scripts.import_instagram_dump import import_dump
from lightroom_tagger.scripts.match_instagram_dump import match_dump_media

from . import path_setup as _path_setup  # noqa: F401


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

        update_job_field(runner.db, job_id, 'metadata', {
            **metadata,
            'method': 'cascade_matching',
            'date_window_days': 90,
            'threshold': custom_threshold,
            'weights': custom_weights,
            **({"provider_id": provider_id} if provider_id else {}),
            **({"provider_model": provider_model} if provider_model else {}),
        })

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

            stats, matches = match_dump_media(
                db,
                threshold=custom_threshold,
                month=month,
                year=year,
                last_months=last_months,
                progress_callback=progress_callback,
                log_callback=log_callback,
                media_key=media_key,
                force_descriptions=force_descriptions,
                force_reprocess=force_reprocess,
                provider_id=provider_id,
                provider_model=provider_model,
                max_workers=max_workers,
                should_cancel=lambda: runner.is_cancelled(job_id),
            )

            if runner.is_cancelled(job_id):
                runner.finalize_cancelled(job_id)
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

    try:
        db = init_database(db_path)
        init_catalog_table(db)

        catalog_images = get_catalog_images_needing_analysis(db)

        if not catalog_images:
            from lightroom_tagger.core.database import get_all_images
            all_images = get_all_images(db)
            catalog_images = [img for img in all_images if not img.get('analyzed_at')]

        total = len(catalog_images)
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

                if (i + 1) % 10 == 0 or i == total - 1:
                    progress = int(20 + (processed / total) * 70)
                    runner.update_progress(job_id, progress, f'Processed {processed}/{total} images')

            except Exception as e:
                errors += 1
                print(f"Error processing image {i + 1}: {e}")

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
        if db:
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

        def process_single_image(image, db_path):
            """Each thread gets its own DB connection."""
            filepath = image.get('filepath')
            key = image.get('key')
            if not filepath or not key:
                return ('failed', key or 'unknown', 'Missing filepath or key')
            if not os.path.exists(filepath):
                return ('failed', key, f'File not found: {filepath}')

            thread_db = sqlite3.connect(db_path)
            thread_db.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
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

        max_workers = min(4, os.cpu_count() or 2)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_single_image, img, db_path): img for img in images}
            completed = 0
            for _future in as_completed(futures):
                if runner.is_cancelled(job_id):
                    add_job_log(
                        runner.db,
                        job_id,
                        'info',
                        'Prepare catalog cache stopped: cancel requested',
                    )
                    break
                completed += 1
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

                if completed % 10 == 0 or completed == total:
                    progress = int(10 + (completed / total) * 85)
                    runner.update_progress(job_id, progress, f'Processed {completed}/{total} images')

        if runner.is_cancelled(job_id):
            runner.finalize_cancelled(job_id)
            return

        # Get final cache stats from library DB
        cache_stats_after = get_cache_stats(lib_db)
        log_callback('info', f"Complete: {newly_cached} newly cached, {already_cached_count} already cached, {failed_count} failed")
        log_callback('info', f"Total cache size: {cache_stats_after['cache_size_mb']:.1f}MB")

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


def _describe_single_image(lib_db, key: str, itype: str, force: bool, desc_provider_id, desc_provider_model) -> tuple[str, bool, str | None]:
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
            )
        else:
            result = describe_instagram_image(
                lib_db, key, force=force,
                provider_id=desc_provider_id, model=desc_provider_model,
            )
        
        if result:
            return ('described', True, None)
        else:
            return ('skipped', False, 'No description generated (file missing or model error)')
    except Exception as e:
        return ('failed', False, str(e))


def handle_batch_describe(runner, job_id: str, metadata: dict):
    """Generate AI descriptions for catalog and/or Instagram images in bulk."""
    lib_db = None
    old_model_env = os.environ.get('DESCRIPTION_VISION_MODEL')
    try:
        config = load_config()
        db_path = os.getenv('LIBRARY_DB')
        if not db_path:
            db_path = config.db_path or 'library.db'
        lib_db = init_database(db_path)

        image_type = metadata.get('image_type', 'both')  # catalog, instagram, both
        date_filter = metadata.get('date_filter', 'all')  # all, 3months, 6months, 12months
        force = metadata.get('force', False)
        desc_provider_id = metadata.get('provider_id')
        desc_provider_model = metadata.get('provider_model')

        months = {'3months': 3, '6months': 6, '12months': 12}.get(date_filter)
        min_rating_raw = metadata.get('min_rating')
        min_rating = None
        if min_rating_raw is not None:
            try:
                min_rating = int(min_rating_raw)
            except (TypeError, ValueError):
                min_rating = None
        max_workers = int(metadata.get('max_workers', 4))

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

        total = len(images_to_describe)
        runner.update_progress(job_id, 5, f'Found {total} images to describe')

        if total == 0:
            runner.complete_job(job_id, {
                'described': 0, 'skipped': 0, 'failed': 0, 'total': 0,
            })
            return

        described = 0
        skipped = 0
        failed = 0
        consecutive_failures = 0

        # Use parallel processing if max_workers > 1 and batch is large enough
        if max_workers > 1 and total > 3:
            def process_image_worker(key: str, itype: str):
                """Worker function with its own DB connection."""
                worker_db = init_database(db_path)
                try:
                    status, success, error_msg = _describe_single_image(
                        worker_db, key, itype, force, desc_provider_id, desc_provider_model
                    )
                    return (key, status, error_msg)
                finally:
                    worker_db.close()

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(process_image_worker, key, itype): (idx, key)
                    for idx, (key, itype) in enumerate(images_to_describe, 1)
                }
                
                for future in as_completed(futures):
                    if runner.is_cancelled(job_id):
                        add_job_log(
                            runner.db,
                            job_id,
                            'info',
                            'Batch describe cancel noted; finishing already-running tasks',
                        )
                        break
                    idx, key = futures[future]
                    progress = int(5 + (idx / total) * 90)
                    runner.update_progress(job_id, progress, f'Describing {idx}/{total}')
                    
                    try:
                        result_key, status, error_msg = future.result()
                        if status == 'described':
                            described += 1
                            consecutive_failures = 0
                        elif status == 'skipped':
                            skipped += 1
                            consecutive_failures += 1
                            if consecutive_failures <= 3:
                                add_job_log(runner.db, job_id, 'warning', f'{result_key}: {error_msg}')
                        else:  # failed
                            failed += 1
                            consecutive_failures += 1
                            add_job_log(runner.db, job_id, 'warning', f'{result_key}: {error_msg}')
                    except Exception as e:
                        failed += 1
                        consecutive_failures += 1
                        add_job_log(runner.db, job_id, 'warning', f'{key}: {e}')
                    
                    if consecutive_failures >= 10:
                        add_job_log(runner.db, job_id, 'error',
                                    f'Stopping: {consecutive_failures} consecutive failures')
                        break

            if runner.is_cancelled(job_id):
                runner.finalize_cancelled(job_id)
                return
        else:
            # Sequential fallback for single worker or small batches
            for idx, (key, itype) in enumerate(images_to_describe, 1):
                if runner.is_cancelled(job_id):
                    add_job_log(runner.db, job_id, 'info', 'Batch describe stopped: cancel requested')
                    runner.finalize_cancelled(job_id)
                    return
                progress = int(5 + (idx / total) * 90)
                runner.update_progress(job_id, progress, f'Describing {idx}/{total}: {key}')
                
                status, success, error_msg = _describe_single_image(
                    lib_db, key, itype, force, desc_provider_id, desc_provider_model
                )
                
                if status == 'described':
                    described += 1
                    consecutive_failures = 0
                elif status == 'skipped':
                    skipped += 1
                    consecutive_failures += 1
                    if consecutive_failures <= 3:
                        add_job_log(runner.db, job_id, 'warning', f'{key}: {error_msg}')
                else:  # failed
                    failed += 1
                    consecutive_failures += 1
                    add_job_log(runner.db, job_id, 'warning', f'{key}: {error_msg}')
                
                if consecutive_failures >= 10:
                    add_job_log(runner.db, job_id, 'error',
                                f'Stopping: {consecutive_failures} consecutive failures')
                    break

        runner.complete_job(job_id, {
            'described': described,
            'skipped': skipped,
            'failed': failed,
            'total': total,
            'image_type': image_type,
            'date_filter': date_filter,
            'force': force,
        })

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
}
