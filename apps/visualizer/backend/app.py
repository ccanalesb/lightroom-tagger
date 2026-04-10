from __future__ import annotations

import os
import sys
import threading
import time
from typing import TYPE_CHECKING

import config

if TYPE_CHECKING:
    from jobs.runner import JobRunner
from database import add_job_log, get_active_jobs, get_job, get_pending_jobs, init_db, update_job_status
from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

db = None
socketio = None
job_processor_thread = None
job_processor_running = False
_job_runner: JobRunner | None = None


def get_job_runner() -> JobRunner | None:
    """Return the JobRunner used by the background processor thread, if started."""
    return _job_runner


def create_app():
    global db, socketio, job_processor_thread, job_processor_running
    app = Flask(__name__)
    app.name = 'backend'

    # Set up NAS path resolution environment variables from lightroom-tagger config
    try:
        from lightroom_tagger.core.config import load_config as load_lt_config
        from lightroom_tagger.database import init_database
        lt_config = load_lt_config()
        if lt_config.mount_point:
            os.environ['NAS_MOUNT_POINT'] = lt_config.mount_point
            # Auto-detect NAS prefix from library.db
            if not os.environ.get('NAS_PATH_PREFIX'):
                try:
                    library_db_path = os.getenv('LIBRARY_DB') or lt_config.db_path
                    if library_db_path and os.path.exists(library_db_path):
                        temp_db = init_database(library_db_path)
                        unc_sample = temp_db.execute(
                            "SELECT filepath FROM images WHERE filepath LIKE '//%' LIMIT 1"
                        ).fetchone()
                        if unc_sample and unc_sample.get('filepath'):
                            unc_path = unc_sample['filepath']
                            parts = unc_path.lstrip('/').split('/')
                            if len(parts) >= 2:
                                detected_prefix = f'//{parts[0]}/{parts[1]}'
                                os.environ['NAS_PATH_PREFIX'] = detected_prefix
                                print(f"Auto-detected NAS prefix: {detected_prefix} -> {lt_config.mount_point}")
                        temp_db.close()
                except Exception as e:
                    print(f"Could not auto-detect NAS prefix: {e}")
    except Exception as e:
        print(f"Warning: Could not load NAS config from lightroom-tagger: {e}")

    CORS(app, origins=config.FRONTEND_URL.split(','))
    socketio = SocketIO(app, cors_allowed_origins="*")

    db_path = os.path.join(os.path.dirname(__file__), config.DATABASE_PATH)
    db = init_db(db_path)
    app.db = db

    from api import descriptions, images, jobs, lt_config, providers, system
    app.register_blueprint(jobs.bp, url_prefix='/api/jobs')
    app.register_blueprint(images.bp, url_prefix='/api/images')
    app.register_blueprint(descriptions.bp, url_prefix='/api/descriptions')
    app.register_blueprint(providers.bp, url_prefix='/api/providers')
    app.register_blueprint(system.bp, url_prefix='/api')
    app.register_blueprint(lt_config.bp, url_prefix='/api/config')

    from websocket.events import register_socket_events
    register_socket_events(socketio)

    _recover_orphaned_jobs(db)

    job_processor_running = True
    job_processor_thread = threading.Thread(target=_job_processor, daemon=True)
    job_processor_thread.start()

    return app


def _recover_orphaned_jobs(db):
    """Mark any 'running' jobs as failed — they were interrupted by a server restart."""
    for job in get_active_jobs(db):
        if job['status'] == 'running':
            update_job_status(db, job['id'], 'failed')
            add_job_log(db, job['id'], 'error', 'Job interrupted by server restart')
            print(f"Recovered orphaned job {job['id']}: marked as failed")


def _job_processor():
    """Background thread that processes pending jobs."""
    global db, socketio, job_processor_running, _job_runner

    from jobs.handlers import JOB_HANDLERS
    from jobs.runner import JobRunner

    runner = JobRunner(db, emit_progress=lambda job_id, progress, step:
        socketio.emit('job_updated', get_job(db, job_id)) if socketio else None)
    _job_runner = runner

    while job_processor_running:
        try:
            # Get pending jobs
            pending = get_pending_jobs(db)
            for job in pending:
                job_id = job.get('id', 'unknown')
                job_type = job.get('type', 'unknown')
                metadata = job.get('metadata', {})

                print(f"Processing job {job_id}: type={job_type}, status={job.get('status')}")

                fresh = get_job(db, job_id)
                if not fresh or fresh.get('status') != 'pending':
                    continue

                # Mark as running
                started = runner.start_job(job_id, job_type, metadata)
                if not started:
                    socketio.emit('job_updated', get_job(db, job_id)) if socketio else None
                    continue
                socketio.emit('job_updated', get_job(db, job_id)) if socketio else None

                # Execute handler
                handler = JOB_HANDLERS.get(job_type)
                if handler:
                    try:
                        handler(runner, job_id, metadata)
                    except Exception as e:
                        print(f"Handler error for job {job_id}: {e}")
                        import traceback
                        traceback.print_exc()
                        row_after = get_job(db, job_id)
                        if row_after and row_after.get('status') == 'running':
                            runner.fail_job(job_id, str(e))
                else:
                    row_after = get_job(db, job_id)
                    if row_after and row_after.get('status') == 'running':
                        runner.fail_job(job_id, f'Unknown job type: {job_type}')

                # Emit update after handler completes
                socketio.emit('job_updated', get_job(db, job_id)) if socketio else None

        except Exception as e:
            import traceback
            print(f"Job processor error: {e}")
            print(traceback.format_exc())

        time.sleep(1)  # Check every second

if __name__ == '__main__':
    app = create_app()
    socketio.run(app, host=config.FLASK_HOST, port=config.FLASK_PORT, debug=config.FLASK_DEBUG, allow_unsafe_werkzeug=True)
