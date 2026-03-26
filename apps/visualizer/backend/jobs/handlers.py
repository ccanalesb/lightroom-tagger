"""Job type handlers for vision matching and catalog operations."""
import os
from pathlib import Path

from tinydb import Query

from lightroom_tagger.core.config import load_config
from lightroom_tagger.core.database import init_database
from lightroom_tagger.scripts.match_instagram_dump import match_dump_media

from . import path_setup as _path_setup  # noqa: F401


def handle_analyze_instagram(runner, job_id: str, metadata: dict):
    """Analyze Instagram images."""
    runner.update_progress(job_id, 50, 'Analyzing images...')
    runner.complete_job(job_id, {'images_processed': 0})


def handle_vision_match(runner, job_id: str, metadata: dict):
    """Run vision matching with cascade filtering."""
    runner.update_progress(job_id, 10, 'Initializing...')

    try:
        # Store config in metadata so it shows during job run
        config = load_config()

        # Use custom values from metadata if provided, otherwise config defaults
        custom_model = metadata.get('vision_model', config.vision_model or 'gemma3:27b')
        custom_threshold = metadata.get('threshold', config.match_threshold or 0.7)
        custom_weights = metadata.get('weights', {
            'phash': config.phash_weight or 0.4,
            'description': config.desc_weight or 0.3,
            'vision': config.vision_weight or 0.3
        })

        runner.db.table('jobs').update({
            'metadata': {
                **metadata,
                'method': 'cascade_matching',
                'date_window_days': 90,
                'threshold': custom_threshold,
                'vision_model': custom_model,
                'weights': custom_weights
            }
        }, Query().id == job_id)

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

            # Set environment variable for vision model if custom
            if custom_model and custom_model != config.vision_model:
                os.environ['VISION_MODEL'] = custom_model
                print(f"[Job {job_id[:8]}] Using custom vision model: {custom_model}")

            # Log custom configuration
            log_callback('info', f"Configuration: threshold={custom_threshold}, model={custom_model}")
            log_callback('info', f"Weights: phash={custom_weights['phash']:.2f}, desc={custom_weights['description']:.2f}, vision={custom_weights['vision']:.2f}")

            # Run cascade matching with progress callback
            stats, matches = match_dump_media(
                db,
                threshold=custom_threshold,
                month=month,
                year=year,
                last_months=last_months,
                progress_callback=progress_callback,
                log_callback=log_callback
            )

            # Update Lightroom with "Posted" keyword for matched images
            lr_stats = {'success': 0, 'failed': 0}
            if matches:
                from lightroom_tagger.lightroom.writer import update_lightroom_from_matches
                catalog_path = config.catalog_path or config.small_catalog_path
                if catalog_path and Path(catalog_path).exists():
                    lr_stats = update_lightroom_from_matches(catalog_path, matches)

            runner.update_progress(job_id, 100, 'Complete')
            runner.complete_job(job_id, {
                'processed': stats['processed'],
                'matched': stats['matched'],
                'skipped': stats['skipped'],
                'lightroom_updated': lr_stats['success'],
                'lightroom_failed': lr_stats['failed'],
                'method': 'cascade_matching',
                'date_window_days': 90,
                'vision_model': custom_model,
                'threshold': custom_threshold,
                'weights': custom_weights
            })

        finally:
            db.close()

    except Exception as e:
        runner.fail_job(job_id, str(e))


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
        runner.fail_job(job_id, str(e))
    finally:
        if db:
            db.close()


def handle_prepare_catalog(runner, job_id: str, metadata: dict):
    """Pre-compress and cache all catalog images for vision matching.

    This job compresses catalog images once and stores them in the vision cache,
    eliminating redundant compression during vision matching runs.
    """
    import time
    from concurrent.futures import ThreadPoolExecutor, as_completed

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

        runner.db.table('jobs').update({
            'metadata': {
                **metadata,
                'cache_dir': cache_dir,
                'method': 'prepare_catalog_cache',
            }
        }, Query().id == job_id)

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

        # Determine parallelism (I/O bound, so threads are fine)
        max_workers = min(4, os.cpu_count() or 2)
        log_callback('info', f"Using {max_workers} parallel threads for compression")

        newly_cached = 0
        already_cached_count = 0
        failed_count = 0
        total = len(images)

        def process_single_image(image):
            """Process one image with retry logic."""
            filepath = image.get('filepath')
            key = image.get('key')
            import os as _os

            if not filepath or not key:
                return ('failed', key or 'unknown', 'Missing filepath or key')

            if not _os.path.exists(filepath):
                return ('failed', key, f'File not found: {filepath}')

            retries = 2
            for attempt in range(retries):
                try:
                    # Check if already cached and valid
                    from lightroom_tagger.core.database import is_vision_cache_valid
                    if is_vision_cache_valid(lib_db, key, filepath):
                        return ('already_cached', key)

                    # Create cache
                    compressed_path = get_or_create_cached_image(lib_db, key, filepath)
                    if compressed_path:
                        size_kb = _os.path.getsize(compressed_path) / 1024
                        return ('newly_cached', key, size_kb)
                    return ('failed', key, 'Compression returned None')
                except Exception as e:
                    if attempt < retries - 1:
                        time.sleep(0.5 * (attempt + 1))
                        continue
                    return ('failed', key, str(e))

        # Process images in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_single_image, img): img for img in images}

            for idx, future in enumerate(as_completed(futures), 1):
                result = future.result()
                if result[0] == 'already_cached':
                    already_cached_count += 1
                elif result[0] == 'newly_cached':
                    newly_cached += 1
                else:
                    failed_count += 1
                    log_callback('error', f"Failed to cache {result[1]}: {result[2]}")

                # Update progress every 10 images or at end
                if idx % 10 == 0 or idx == total:
                    progress = int(10 + (idx / total) * 85) # Scale to 10-95%
                    runner.update_progress(job_id, progress, f'Processed {idx}/{total} images')

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
        runner.fail_job(job_id, str(e))
    finally:
        if lib_db:
            lib_db.close()


JOB_HANDLERS = {
    'analyze_instagram': handle_analyze_instagram,
    'vision_match': handle_vision_match,
    'enrich_catalog': handle_enrich_catalog,
    'prepare_catalog': handle_prepare_catalog,
}
