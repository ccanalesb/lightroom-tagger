from flask import Blueprint, jsonify, current_app
from tinydb import TinyDB
import os
import config

bp = Blueprint('system', __name__)

@bp.route('/status', methods=['GET'])
def get_status():
    return jsonify({'status': 'ok'})

@bp.route('/stats', methods=['GET'])
def get_stats():
    try:
        db_path = config.LIBRARY_DB
        if not os.path.exists(db_path):
            return jsonify({'error': 'Library database not found'}), 404
        
        db = TinyDB(db_path)
        
        images = db.table('images').all()
        instagram_images = db.table('instagram_images').all()
        
        posted_count = sum(1 for img in images if img.get('instagram_posted'))
        matches = db.table('matches').all() if 'matches' in db.tables() else []
        
        stats = {
            'catalog_images': len(images),
            'instagram_images': len(instagram_images),
            'posted_to_instagram': posted_count,
            'matches_found': len(matches),
            'db_path': db_path,
        }
        
        db.close()
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500