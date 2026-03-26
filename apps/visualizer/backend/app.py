import os
import sys
import threading
import time

import config
from database import get_job, get_pending_jobs, init_db
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

def create_app():
    global db, socketio, job_processor_thread, job_processor_running
    app = Flask(__name__)
    app.name = 'backend'

    CORS(app, origins=config.FRONTEND_URL.split(','))
    socketio = SocketIO(app, cors_allowed_origins="*")

    db_path = os.path.join(os.path.dirname(__file__), config.DATABASE_PATH)
    db = init_db(db_path)
    app.db = db

    from api import images, jobs, system
    app.register_blueprint(jobs.bp, url_prefix='/api/jobs')
    app.register_blueprint(images.bp, url_prefix='/api/images')
    app.register_blueprint(system.bp, url_prefix='/api')

    from websocket.events import register_socket_events
    register_socket_events(socketio)

    # Start job processor thread
    job_processor_running = True
    job_processor_thread = threading.Thread(target=_job_processor, daemon=True)
    job_processor_thread.start()

    return app


def _job_processor():
    """Background thread that processes pending jobs."""
    global db, socketio, job_processor_running

    from jobs.handlers import JOB_HANDLERS
    from jobs.runner import JobRunner

    runner = JobRunner(db, emit_progress=lambda job_id, progress, step:
        socketio.emit('job_updated', get_job(db, job_id)) if socketio else None)

    while job_processor_running:
        try:
            # Get pending jobs
            pending = get_pending_jobs(db)
            for job in pending:
                job_id = job.get('id', 'unknown')
                job_type = job.get('type', 'unknown')
                metadata = job.get('metadata', {})

                print(f"Processing job {job_id}: type={job_type}, status={job.get('status')}")

                # Mark as running
                runner.start_job(job_id, job_type, metadata)
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
                        runner.fail_job(job_id, str(e))
                else:
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
