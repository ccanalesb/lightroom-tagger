from flask import Blueprint, jsonify, request, current_app
from database import create_job, get_job, list_jobs, get_active_jobs, update_job_status

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
    job = get_job(current_app.db, job_id)
    
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    if job['status'] == 'running':
        update_job_status(current_app.db, job_id, 'cancelled')
        return jsonify({'status': 'cancelled'})
    
    return jsonify({'error': 'Can only cancel running jobs'}), 400

@bp.route('/active', methods=['GET'])
def list_active_jobs():
    jobs = get_active_jobs(current_app.db)
    return jsonify(jobs)