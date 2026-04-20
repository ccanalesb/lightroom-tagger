from __future__ import annotations

import os
import sys
import threading
import time
from typing import TYPE_CHECKING

import config

if TYPE_CHECKING:
    from jobs.runner import JobRunner
from database import (
    add_job_log,
    get_active_jobs,
    get_job,
    get_pending_jobs,
    init_db,
    make_connection_for_path,
    update_job_status,
)
from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

db = None
_JOBS_DB_PATH: str | None = None
socketio = None
job_processor_thread = None
job_processor_running = False
_job_runner: JobRunner | None = None
_running_job_ids: set[str] = set()
_running_job_ids_lock = threading.Lock()


# Processor heartbeat: ``_job_processor`` updates these fields every loop
# iteration so we can distinguish "processor healthy but waiting for work"
# from "processor stuck / crashed / never started". The diagnostic endpoint
# ``/api/jobs/_processor_health`` surfaces these values for the UI and for
# humans poking the backend with curl during an incident.
_processor_health: dict[str, object] = {
    'started_at': None,
    'last_iteration_at': None,
    'iterations_total': 0,
    'current_job_id': None,
    'current_job_started_at': None,
    'last_error': None,
}
_processor_health_lock = threading.Lock()


def get_processor_health_snapshot() -> dict:
    """Return a defensive copy of the processor heartbeat for API exposure."""
    with _processor_health_lock:
        return dict(_processor_health)


def _processor_heartbeat(**changes) -> None:
    """Atomically update one or more heartbeat fields from the processor loop."""
    with _processor_health_lock:
        _processor_health.update(changes)


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
    # Stash the resolved path on the module so the processor thread can grab
    # its own thread-local connection rather than sharing ``db`` across
    # threads. See :func:`database.make_connection_for_path`.
    global _JOBS_DB_PATH
    _JOBS_DB_PATH = db_path
    app.db = db

    from api import (
        analytics,
        descriptions,
        identity,
        images,
        jobs,
        lt_config,
        perspectives,
        providers,
        scores,
        system,
    )
    app.register_blueprint(jobs.bp, url_prefix='/api/jobs')
    app.register_blueprint(images.bp, url_prefix='/api/images')
    app.register_blueprint(analytics.bp, url_prefix='/api/analytics')
    app.register_blueprint(descriptions.bp, url_prefix='/api/descriptions')
    app.register_blueprint(providers.bp, url_prefix='/api/providers')
    app.register_blueprint(system.bp, url_prefix='/api')
    app.register_blueprint(lt_config.bp, url_prefix='/api/config')
    app.register_blueprint(perspectives.bp, url_prefix='/api/perspectives')
    app.register_blueprint(scores.bp, url_prefix='/api/scores')
    app.register_blueprint(identity.bp, url_prefix='/api/identity')

    from websocket.events import register_socket_events
    register_socket_events(socketio)

    if not os.environ.get('WERKZEUG_RUN_MAIN') and config.FLASK_DEBUG:
        return app

    _recover_orphaned_jobs(db)

    job_processor_running = True
    _start_job_processor_thread()

    return app


def _start_job_processor_thread():
    """Start the job processor thread, wrapped in a watchdog that restarts it on crash."""
    def watchdog():
        while job_processor_running:
            t = threading.Thread(target=_job_processor, daemon=True, name="job-processor")
            t.start()
            t.join()  # blocks until the thread exits for any reason
            if job_processor_running:
                print("Job processor thread exited unexpectedly — restarting in 2s")
                time.sleep(2)

    threading.Thread(target=watchdog, daemon=True, name="job-processor-watchdog").start()


def _recover_orphaned_jobs(db):
    """Re-queue running jobs that have a v1 checkpoint; fail the rest (restart recovery)."""
    recovered_ids: list[str] = []
    for job in get_active_jobs(db):
        if job['status'] != 'running':
            continue
        job_id = job['id']
        meta = job.get('metadata') or {}
        ck = meta.get('checkpoint') if isinstance(meta, dict) else None
        if isinstance(ck, dict) and ck.get('checkpoint_version') == 1:
            update_job_status(
                db,
                job_id,
                'pending',
                progress=job.get('progress') or 0,
                current_step='Recovered after restart',
            )
            add_job_log(
                db,
                job_id,
                'info',
                'Recovered after restart; job re-queued with checkpoint.',
            )
            recovered_ids.append(job_id)
            print(f"Recovered orphaned job {job_id}: re-queued pending with checkpoint")
        else:
            update_job_status(db, job_id, 'failed')
            add_job_log(
                db,
                job_id,
                'error',
                'This job was still running when the server restarted. It was marked failed; use Retry if you want to run it again.',
            )
            print(f"Recovered orphaned job {job_id}: marked as failed")

    if recovered_ids and socketio:
        socketio.emit('jobs_recovered', {'job_ids': recovered_ids})


def _job_processor():
    """Background thread that processes pending jobs."""
    global socketio, job_processor_running, _job_runner

    from jobs.handlers import JOB_HANDLERS
    from jobs.runner import JobRunner

    # Own connection, owned by this thread. Sharing the Flask-thread ``db``
    # across the processor + all workers + HTTP handlers was the ultimate
    # cause of the stall on job 50710bf6 — see the comments in
    # ``database.py`` and ``runner.log_from_worker``.
    assert _JOBS_DB_PATH, "Jobs DB path was not set before starting processor"
    processor_db = make_connection_for_path(_JOBS_DB_PATH)

    runner = JobRunner(
        processor_db,
        emit_progress=lambda job_id, progress, step: (
            socketio.emit('job_updated', get_job(processor_db, job_id))
            if socketio else None
        ),
        db_path=_JOBS_DB_PATH,
    )
    _job_runner = runner

    _processor_heartbeat(
        started_at=time.time(),
        last_iteration_at=time.time(),
        iterations_total=0,
        current_job_id=None,
        current_job_started_at=None,
        last_error=None,
    )

    while job_processor_running:
        try:
            _processor_heartbeat(last_iteration_at=time.time())
            pending = get_pending_jobs(processor_db)
            for job in pending:
                job_id = job.get('id', 'unknown')
                job_type = job.get('type', 'unknown')
                metadata = job.get('metadata', {})

                print(f"Processing job {job_id}: type={job_type}, status={job.get('status')}")

                fresh = get_job(processor_db, job_id)
                if not fresh or fresh.get('status') != 'pending':
                    continue

                started = runner.start_job(job_id, job_type, metadata)
                if not started:
                    socketio.emit('job_updated', get_job(processor_db, job_id)) if socketio else None
                    continue
                socketio.emit('job_updated', get_job(processor_db, job_id)) if socketio else None

                # Execute handler — guard against duplicate execution if a stale
                # handler thread from a previous watchdog cycle is still running.
                with _running_job_ids_lock:
                    if job_id in _running_job_ids:
                        print(f"Job {job_id} is already running in another thread — skipping duplicate dispatch")
                        continue
                    _running_job_ids.add(job_id)

                handler = JOB_HANDLERS.get(job_type)
                _processor_heartbeat(
                    current_job_id=job_id,
                    current_job_started_at=time.time(),
                )
                try:
                    if handler:
                        try:
                            handler(runner, job_id, metadata)
                        except Exception as e:
                            print(f"Handler error for job {job_id}: {e}")
                            import traceback
                            traceback.print_exc()
                            row_after = get_job(processor_db, job_id)
                            if row_after and row_after.get('status') == 'running':
                                runner.fail_job(job_id, str(e))
                    else:
                        row_after = get_job(processor_db, job_id)
                        if row_after and row_after.get('status') == 'running':
                            runner.fail_job(job_id, f'Unknown job type: {job_type}')
                finally:
                    with _running_job_ids_lock:
                        _running_job_ids.discard(job_id)
                    _processor_heartbeat(
                        current_job_id=None,
                        current_job_started_at=None,
                    )

                socketio.emit('job_updated', get_job(processor_db, job_id)) if socketio else None

            # Iteration complete (with or without pending jobs) — counts as a
            # healthy tick so ``/_processor_health`` can distinguish
            # "quietly waiting" from "stuck".
            with _processor_health_lock:
                _processor_health['iterations_total'] = int(_processor_health.get('iterations_total') or 0) + 1

        except BaseException as e:
            import traceback
            print(f"Job processor error: {e}")
            print(traceback.format_exc())
            _processor_heartbeat(last_error=f'{type(e).__name__}: {e}')
            if isinstance(e, (SystemExit, KeyboardInterrupt)):
                raise  # let the thread die so the watchdog can restart it

        time.sleep(1)  # Check every second

def _refuse_if_port_in_use(host: str, port: int) -> None:
    """Exit early if another backend is already bound to host:port.

    Running two backends against the same SQLite file produces write-lock
    contention and intermittent 500s on cancel/retry. This guard prevents
    that whole failure mode.

    Skipped inside Werkzeug's reloader child (WERKZEUG_RUN_MAIN=true), which
    re-exec's the app and would otherwise trip the check against itself.
    """
    if os.environ.get('WERKZEUG_RUN_MAIN'):
        return

    import socket
    probe_host = '127.0.0.1' if host in ('0.0.0.0', '') else host
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        try:
            s.connect((probe_host, port))
        except (ConnectionRefusedError, socket.timeout, OSError):
            return

    print(
        f"ERROR: Another process is already listening on {probe_host}:{port}.\n"
        f"       Running two visualizer backends against the same SQLite database\n"
        f"       causes write-lock contention and breaks job cancel/retry.\n"
        f"       Stop the other process first:\n"
        f"         lsof -iTCP:{port} -sTCP:LISTEN -P -n\n"
        f"         kill <pid>",
        file=sys.stderr,
    )
    sys.exit(1)


if __name__ == '__main__':
    _refuse_if_port_in_use(config.FLASK_HOST, config.FLASK_PORT)
    app = create_app()
    socketio.run(app, host=config.FLASK_HOST, port=config.FLASK_PORT, debug=config.FLASK_DEBUG, allow_unsafe_werkzeug=True)
