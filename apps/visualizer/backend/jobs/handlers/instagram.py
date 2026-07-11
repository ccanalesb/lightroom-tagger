"""Instagram analysis/import job handlers."""

import os
from pathlib import Path

from database import add_job_log
from library_db import require_library_db

from lightroom_tagger.core.config import load_config
from lightroom_tagger.core.database import init_database
from lightroom_tagger.scripts.import_instagram_dump import import_dump

from .db_lifecycle import make_managed_library_db
from .common import _failure_severity_from_exception

managed_library_db = make_managed_library_db(lambda p: init_database(p))


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

        db_path = require_library_db()

        skip_dedup = bool(metadata.get('skip_dedup', False))
        reimport = bool(metadata.get('reimport', False))

        with managed_library_db(db_path) as db:
            imported = import_dump(
                db,
                str(dump_path),
                skip_existing=not reimport,
                skip_dedup=skip_dedup,
            )

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
