from flask import Blueprint, jsonify

bp = Blueprint('jobs', __name__)

@bp.route('/', methods=['GET'])
def list_jobs():
    return jsonify([])

@bp.route('/', methods=['POST'])
def create_job():
    return jsonify({'id': 'test', 'status': 'pending'}), 201