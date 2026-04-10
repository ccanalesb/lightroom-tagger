from database import add_job_log, create_job, get_active_jobs, get_job, list_jobs, update_job_field, update_job_status
from flask import Blueprint, current_app, jsonify, request

bp = Blueprint('jobs', __name__)

@bp.route('/', methods=['GET'])
def list_all_jobs():
    status = request.args.get('status')
    jobs = list_jobs(current_app.db, status=status)
    return jsonify(jobs)

@bp.route('/', methods=['POST'])
def create_new_job():
    data = request.json

    if not data or 'type' not in data:
        return jsonify({'error': 'type is required'}), 400

    job_type = data['type']
    metadata = data.get('metadata', {})

    job_id = create_job(current_app.db, job_type, metadata)
    job = get_job(current_app.db, job_id)

    return jsonify(job), 201

@bp.route('/<job_id>', methods=['GET'])
def get_job_details(job_id):
    job = get_job(current_app.db, job_id)

    if not job:
        return jsonify({'error': 'Job not found'}), 404

    return jsonify(job)

@bp.route('/<job_id>', methods=['DELETE'])
def cancel_job(job_id):
    from app import get_job_runner, socketio

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

    return jsonify({'error': 'Can only cancel running or pending jobs'}), 400

@bp.route('/<job_id>/retry', methods=['POST'])
def retry_job(job_id):
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


@bp.route('/active', methods=['GET'])
def list_active_jobs():
    jobs = get_active_jobs(current_app.db)
    return jsonify(jobs)
