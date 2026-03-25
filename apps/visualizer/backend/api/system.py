from flask import Blueprint, jsonify, current_app
from tinydb import TinyDB
import os
import config
import subprocess

bp = Blueprint('system', __name__)

@bp.route('/status', methods=['GET'])
def get_status():
    return jsonify({'status': 'ok'})

@bp.route('/vision-models', methods=['GET'])
def get_vision_models():
    """Get available vision models from Ollama."""
    try:
        # Get list of vision-capable models from Ollama
        result = subprocess.run(
            ['ollama', 'list'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            # Fallback to common vision models
            return jsonify({
                'models': [
                    {'name': 'gemma3:27b', 'default': True},
                    {'name': 'gemma3:4b', 'default': False},
                ],
                'fallback': True
            })

        models = []
        default_model = config.vision_model if hasattr(config, 'vision_model') else 'gemma3:27b'
        for line in result.stdout.strip().split('\n'):
            if line and not line.startswith('NAME'):
                model_name = line.split()[0]
                models.append({
                    'name': model_name,
                    'default': model_name == default_model
                })

        return jsonify({
            'models': models,
            'fallback': False
        })

    except Exception as e:
        return jsonify({
            'models': [
                {'name': 'gemma3:27b', 'default': True},
            ],
            'fallback': True
        })

@bp.route('/stats', methods=['GET'])
def get_stats():
    try:
        db_path = config.LIBRARY_DB
        if not os.path.exists(db_path):
            return jsonify({'error': 'Library database not found'}), 404

        db = TinyDB(db_path)

        images = db.table('images').all()
        instagram_images = db.table('instagram_dump_media').all()

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
