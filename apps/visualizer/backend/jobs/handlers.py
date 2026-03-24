"""Job type handlers for vision matching and catalog operations."""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from runner import JobRunner
from lightroom_tagger.core.database import init_database
from lightroom_tagger.core.config import load_config
from lightroom_tagger.scripts.match_instagram_dump import match_dump_media


def handle_analyze_instagram(runner: JobRunner, job_id: str, metadata: dict):
    """Analyze Instagram images."""
    runner.update_progress(job_id, 50, 'Analyzing images...')
    runner.complete_job(job_id, {'images_processed': 0})


def handle_vision_match(runner: JobRunner, job_id: str, metadata: dict):
    """Run vision matching with cascade filtering."""
    runner.update_progress(job_id, 10, 'Initializing...')

    try:
        config = load_config()
        db = init_database(config.get('db_path', 'library.db'))

        try:
            runner.update_progress(job_id, 30, 'Matching...')

            # Get date filters from metadata
            month = metadata.get('month')
            year = metadata.get('year')
            last_months = metadata.get('last_months')

            # Run cascade matching
            stats, matches = match_dump_media(
                db,
                threshold=config.get('match_threshold', 0.7),
                month=month,
                year=year,
                last_months=last_months
            )

            runner.update_progress(job_id, 80, 'Updating Lightroom...')

            # Update Lightroom with "Posted" keyword for matched images
            lr_stats = {'success': 0, 'failed': 0}
            if matches:
                from lightroom_tagger.lightroom.writer import update_lightroom_from_matches
                catalog_path = config.get('catalog_path') or config.get('small_catalog_path')
                if catalog_path and Path(catalog_path).exists():
                    lr_stats = update_lightroom_from_matches(catalog_path, matches)

            runner.update_progress(job_id, 100, 'Complete')
            runner.complete_job(job_id, {
                'processed': stats['processed'],
                'matched': stats['matched'],
                'skipped': stats['skipped'],
                'lightroom_updated': lr_stats['success'],
                'lightroom_failed': lr_stats['failed']
            })

        finally:
            db.close()

    except Exception as e:
        runner.fail_job(job_id, str(e))


def handle_enrich_catalog(runner: JobRunner, job_id: str, metadata: dict):
    """Enrich catalog with metadata."""
    runner.update_progress(job_id, 50, 'Enriching catalog...')
    runner.complete_job(job_id, {'enriched': 0})


JOB_HANDLERS = {
    'analyze_instagram': handle_analyze_instagram,
    'vision_match': handle_vision_match,
    'enrich_catalog': handle_enrich_catalog,
}
