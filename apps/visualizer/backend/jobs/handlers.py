"""Job type handlers for vision matching and catalog operations."""
import sys
import os
from pathlib import Path

# Add project root to Python path
# Project root is where library.db and lightroom_tagger/ package are located
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.insert(0, _PROJECT_ROOT)

from tinydb import Query
from lightroom_tagger.core.database import init_database
from lightroom_tagger.core.config import load_config
from lightroom_tagger.scripts.match_instagram_dump import match_dump_media


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
    runner.update_progress(job_id, 50, 'Enriching catalog...')
    runner.complete_job(job_id, {'enriched': 0})


JOB_HANDLERS = {
    'analyze_instagram': handle_analyze_instagram,
    'vision_match': handle_vision_match,
    'enrich_catalog': handle_enrich_catalog,
}
