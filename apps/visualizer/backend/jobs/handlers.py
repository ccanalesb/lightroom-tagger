"""Job type handlers - implemented in later tasks."""
from runner import JobRunner

def handle_analyze_instagram(runner: JobRunner, job_id: str, metadata: dict):
    """Analyze Instagram images."""
    runner.update_progress(job_id, 50, 'Analyzing images...')
    runner.complete_job(job_id, {'images_processed': 0})

def handle_vision_match(runner: JobRunner, job_id: str, metadata: dict):
    """Run vision matching."""
    runner.update_progress(job_id, 50, 'Running vision matching...')
    runner.complete_job(job_id, {'matches': []})

def handle_enrich_catalog(runner: JobRunner, job_id: str, metadata: dict):
    """Enrich catalog with metadata."""
    runner.update_progress(job_id, 50, 'Enriching catalog...')
    runner.complete_job(job_id, {'enriched': 0})

JOB_HANDLERS = {
    'analyze_instagram': handle_analyze_instagram,
    'vision_match': handle_vision_match,
    'enrich_catalog': handle_enrich_catalog,
}