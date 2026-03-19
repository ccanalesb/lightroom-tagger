from flask import Blueprint, jsonify

bp = Blueprint('system', __name__)

@bp.route('/status', methods=['GET'])
def get_status():
    return jsonify({'status': 'ok'})