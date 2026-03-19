from flask import Blueprint, jsonify

bp = Blueprint('images', __name__)

@bp.route('/', methods=['GET'])
def list_images():
    return jsonify([])