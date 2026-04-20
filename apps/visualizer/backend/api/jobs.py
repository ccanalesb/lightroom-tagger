import sqlite3

from database import (
    add_job_log,
    count_job_logs,
    count_jobs,
    create_job,
    get_active_jobs,
    get_job,
    list_jobs,
    update_job_field,
    update_job_status,
)
from library_db import JOB_TYPES_REQUIRING_CATALOG, describe_library_db
from utils.responses import success_paginated
from flask import Blueprint, current_app, jsonify, request

bp = Blueprint('jobs', __name__)


_DB_BUSY_MESSAGE = (
    'Database is temporarily busy — another operation is holding a write lock. '
    'Try again in a moment; if it keeps happening, check for duplicate backend processes.'
)


def _db_busy_response():
    """Return a 503 JSON response for transient SQLite lock/busy errors."""
    return jsonify({'error': _DB_BUSY_MESSAGE, 'code': 'db_busy'}), 503

@bp.route('/', methods=['GET'])
def list_all_jobs():
    status = request.args.get('status')
    limit = request.args.get('limit', default=50, type=int)
    offset = request.args.get('offset', default=0, type=int)
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    jobs = list_jobs(current_app.db, status=status, limit=limit, offset=offset)
    total = count_jobs(current_app.db, status=status)
    return success_paginated(jobs, total=total, offset=offset, limit=limit)

@bp.route('/', methods=['POST'])
def create_new_job():
    data = request.json

    if not data or 'type' not in data:
        return jsonify({'error': 'type is required'}), 400

    job_type = data['type']
    metadata = data.get('metadata', {})

    if job_type in JOB_TYPES_REQUIRING_CATALOG:
        status = describe_library_db()
        if not status.exists:
            return jsonify({
                'error': (
                    f"Cannot enqueue {job_type!r}: Lightroom catalog database is unavailable. "
                    f"{status.reason or ''}"
                ).strip(),
                'code': 'catalog_unavailable',
                'library_db': status.to_dict(),
            }), 422

    try:
        job_id = create_job(current_app.db, job_type, metadata)
        job = get_job(current_app.db, job_id)
    except sqlite3.OperationalError as e:
        if 'locked' in str(e).lower() or 'busy' in str(e).lower():
            return _db_busy_response()
        raise

    return jsonify(job), 201

@bp.route('/<job_id>', methods=['GET'])
def get_job_details(job_id):
    # Resolve the tail size **before** loading the job so ``get_job`` only
    # pulls the rows the client actually needs. The frontend's modal view
    # asks for ``logs_limit=200`` to ``1000`` in steady state; anything
    # bigger is a power-user override capped at 10k for safety.
    logs_limit_raw = request.args.get('logs_limit', type=int)
    if logs_limit_raw is None:
        effective_limit: int | None = None  # default tail
        include_all = False
    elif logs_limit_raw == 0:
        effective_limit = None
        include_all = True
    else:
        effective_limit = max(1, min(logs_limit_raw, 10_000))
        include_all = False

    job = get_job(
        current_app.db,
        job_id,
        logs_limit=effective_limit,
        include_all_logs=include_all,
    )
    if not job:
        return jsonify({'error': 'Job not found'}), 404

    # ``logs_total`` must reflect the *full* log count, not the tail length,
    # so the frontend can render "showing N of M" correctly.
    job['logs_total'] = count_job_logs(current_app.db, job_id)
    return jsonify(job)

@bp.route('/<job_id>', methods=['DELETE'])
def cancel_job(job_id):
    from app import get_job_runner, socketio

    try:
        job = get_job(current_app.db, job_id)

        if not job:
            return jsonify({'error': 'Job not found'}), 404

        if job['status'] == 'running':
            update_job_status(current_app.db, job_id, 'cancelled')
            r = get_job_runner()
            if r:
                r.signal_cancel(job_id)
            add_job_log(current_app.db, job_id, 'info', 'Cancel requested via API')
            updated = get_job(current_app.db, job_id)
            if socketio:
                socketio.emit('job_updated', updated)
            return jsonify(updated)

        if job['status'] == 'pending':
            update_job_status(current_app.db, job_id, 'cancelled')
            add_job_log(current_app.db, job_id, 'info', 'Cancel requested via API')
            updated = get_job(current_app.db, job_id)
            if socketio:
                socketio.emit('job_updated', updated)
            return jsonify(updated)

        # Idempotent cancel: a cancel against an already-terminal job returns
        # the current row with a hint instead of an error, so rapid clicks /
        # retries from the UI don't produce misleading 400 toasts. Terminal
        # states are ``cancelled``, ``completed``, and ``failed``.
        if job['status'] in ('cancelled', 'completed', 'failed'):
            r = get_job_runner()
            if job['status'] == 'cancelled' and r:
                # Make sure the worker's cancel flag is set even if we missed
                # it the first time (e.g. DB was flipped directly by another
                # process). Cheap no-op if the job isn't active.
                r.signal_cancel(job_id)
            return jsonify({
                **job,
                'cancel_noop': True,
                'cancel_noop_reason': f"Job is already {job['status']}",
            })

        return jsonify({'error': f"Cannot cancel job in status {job['status']!r}"}), 400
    except sqlite3.OperationalError as e:
        if 'locked' in str(e).lower() or 'busy' in str(e).lower():
            return _db_busy_response()
        raise

@bp.route('/<job_id>/retry', methods=['POST'])
def retry_job(job_id):
    try:
        job = get_job(current_app.db, job_id)

        if not job:
            return jsonify({'error': 'Job not found'}), 404

        if job['status'] not in ('failed', 'cancelled'):
            return jsonify({'error': 'Can only retry failed or cancelled jobs'}), 400

        update_job_status(current_app.db, job_id, 'pending', progress=0, current_step=None)
        update_job_field(current_app.db, job_id, 'error', None)
        current_app.db.execute(
            "UPDATE jobs SET error_severity = NULL WHERE id = ?",
            (job_id,),
        )
        current_app.db.commit()
        update_job_field(current_app.db, job_id, 'result', None)
        add_job_log(current_app.db, job_id, 'info', 'Job queued for retry')

        return jsonify(get_job(current_app.db, job_id))
    except sqlite3.OperationalError as e:
        if 'locked' in str(e).lower() or 'busy' in str(e).lower():
            return _db_busy_response()
        raise


@bp.route('/active', methods=['GET'])
def list_active_jobs():
    jobs = get_active_jobs(current_app.db)
    return jsonify(jobs)


@bp.route('/health', methods=['GET'])
def get_jobs_health():
    """Expose subsystem health so the UI can warn before users enqueue broken jobs.

    Returns library DB resolution info plus the job types that require it.
    Always 200 — ``library_db.exists == false`` is the signal to render a banner.
    """
    status = describe_library_db()
    return jsonify({
        'library_db': status.to_dict(),
        'jobs_requiring_catalog': sorted(JOB_TYPES_REQUIRING_CATALOG),
        'catalog_available': status.exists,
    })


# Staleness threshold for the processor heartbeat. The loop ticks every ~1s,
# so anything older than 15s is very likely a hang. Kept loose enough that a
# slow DB query or a long socket emit doesn't trigger false positives.
_PROCESSOR_STALE_AFTER_SECONDS = 15.0


@bp.route('/_processor_health', methods=['GET'])
def get_processor_health():
    """Diagnose the background job processor — was it started, is it ticking?

    This endpoint was added after an incident where a ``pending`` job sat
    untouched for minutes and there was no way to tell from the outside
    whether the processor thread was alive, stuck, or never started.

    Response shape
    --------------
    - ``running`` (bool): the module-level flag ``job_processor_running``.
    - ``started_at`` / ``last_iteration_at`` (float | null): unix timestamps.
    - ``last_iteration_age_seconds`` (float | null): derived convenience.
    - ``iterations_total`` (int): cheap proof-of-life counter.
    - ``current_job_id`` / ``current_job_started_at``: what the processor
      is actively working on, if anything.
    - ``pending_count`` (int): outstanding jobs in the DB; useful alongside
      ``current_job_id`` to spot "pending but not being picked up".
    - ``stale`` (bool): convenience flag — True if ``last_iteration_age_seconds``
      exceeds :data:`_PROCESSOR_STALE_AFTER_SECONDS`. Clients can treat it
      as the primary signal without reimplementing the threshold.
    - ``last_error`` (str | null): most recent exception string from the
      outer ``try`` in the processor loop.
    """
    import sys
    import time as _time

    # When ``app.py`` is started directly (``python app.py``), the running
    # process has the server registered under ``__main__`` and the blueprint
    # imports a *second* copy as ``app``. The processor thread lives in the
    # ``__main__`` module, so snapshotting via ``from app import ...`` returns
    # the dormant copy and this endpoint misreports the processor as dead.
    # We prefer ``__main__`` when it exposes the heartbeat, and fall back to
    # the ``app`` module (the path used by tests and by ``flask run``).
    candidate_modules = []
    main_mod = sys.modules.get('__main__')
    if main_mod is not None and hasattr(main_mod, 'get_processor_health_snapshot'):
        candidate_modules.append(main_mod)
    app_mod = sys.modules.get('app')
    if app_mod is not None and app_mod is not main_mod:
        candidate_modules.append(app_mod)

    # Choose the module whose processor has actually started. If none have,
    # fall back to the first candidate so we still return a well-formed
    # payload with ``running: false``.
    source_mod = None
    for mod in candidate_modules:
        if getattr(mod, 'job_processor_running', False):
            source_mod = mod
            break
    if source_mod is None and candidate_modules:
        source_mod = candidate_modules[0]

    if source_mod is None:
        # Pathological: neither module is importable. Import explicitly so
        # the error surfaces clearly rather than returning a blank payload.
        from app import get_processor_health_snapshot, job_processor_running
        snapshot = get_processor_health_snapshot()
        job_running = job_processor_running
    else:
        snapshot = source_mod.get_processor_health_snapshot()
        job_running = bool(getattr(source_mod, 'job_processor_running', False))
    last_iter = snapshot.get('last_iteration_at')
    age = None
    if isinstance(last_iter, (int, float)):
        age = max(0.0, _time.time() - float(last_iter))

    pending_count = count_jobs(current_app.db, status='pending')
    running_count = count_jobs(current_app.db, status='running')

    return jsonify({
        'running': job_running,
        'started_at': snapshot.get('started_at'),
        'last_iteration_at': last_iter,
        'last_iteration_age_seconds': age,
        'iterations_total': snapshot.get('iterations_total') or 0,
        'current_job_id': snapshot.get('current_job_id'),
        'current_job_started_at': snapshot.get('current_job_started_at'),
        'pending_count': pending_count,
        'running_count': running_count,
        'stale': (age is not None and age > _PROCESSOR_STALE_AFTER_SECONDS),
        'stale_threshold_seconds': _PROCESSOR_STALE_AFTER_SECONDS,
        'last_error': snapshot.get('last_error'),
    })
