import logging
import os
import sys

import config
from flask import Blueprint, current_app, has_app_context, jsonify
from lightroom_tagger.core.database import init_database

logger = logging.getLogger(__name__)

# Add project root for lightroom_tagger imports
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, _PROJECT_ROOT)

bp = Blueprint('system', __name__)

@bp.route('/status', methods=['GET'])
def get_status():
    return jsonify({'status': 'ok'})

@bp.route('/vision-models', methods=['GET'])
def get_vision_models():
    """Get available vision models from all providers (registry + optional user DB rows)."""
    try:
        from lightroom_tagger.core.provider_registry import ProviderRegistry

        registry = ProviderRegistry()
        defaults = registry.defaults
        default_comparison = defaults.get("vision_comparison", {})
        default_provider = default_comparison.get("provider", "ollama")
        default_model = default_comparison.get("model")

        all_models = []
        for provider in registry.list_providers():
            if not provider["available"]:
                continue
            try:
                models = registry.list_models(provider["id"])
            except Exception:
                logger.exception("Failed to list models for provider %s", provider["id"])
                continue
            for model in models:
                if not model.get("vision"):
                    continue
                model_name = model["id"]
                is_default = (
                    provider["id"] == default_provider
                    and (default_model is None or default_model == model_name)
                    and not any(entry.get("default") for entry in all_models)
                )
                all_models.append({
                    "name": model_name,
                    "provider_id": provider["id"],
                    "default": is_default,
                })

        if has_app_context():
            db = getattr(current_app, "db", None)
            if db is not None:
                from database import get_user_models

                seen = {(entry["provider_id"], entry["name"]) for entry in all_models}
                for user_model in get_user_models(db):
                    if not user_model.get("vision"):
                        continue
                    key = (user_model["provider_id"], user_model["model_id"])
                    if key in seen:
                        continue
                    all_models.append({
                        "name": user_model["model_id"],
                        "provider_id": user_model["provider_id"],
                        "default": False,
                    })
                    seen.add(key)

        if not all_models:
            return jsonify({
                "models": [{"name": "gemma3:27b", "default": True}],
                "fallback": True,
            })

        if not any(entry["default"] for entry in all_models):
            all_models[0]["default"] = True

        return jsonify({"models": all_models, "fallback": False})
    except Exception:
        logger.exception("Failed to load vision models from registry")
        return jsonify({
            "models": [{"name": "gemma3:27b", "default": True}],
            "fallback": True,
        })

@bp.route('/stats', methods=['GET'])
def get_stats():
    try:
        db_path = config.LIBRARY_DB
        if not os.path.exists(db_path):
            return jsonify({'error': 'Library database not found'}), 404

        db = init_database(db_path)

        images = db.execute("SELECT * FROM images").fetchall()
        instagram_images = db.execute("SELECT * FROM instagram_dump_media").fetchall()

        posted_row = db.execute(
            "SELECT COUNT(*) AS cnt FROM images WHERE instagram_posted = 1"
        ).fetchone()
        posted_count = int(posted_row["cnt"])
        matches = db.execute("SELECT * FROM matches").fetchall()

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


@bp.route('/catalog/status', methods=['GET'])
def get_catalog_status():
    """Return whether the catalog vision cache has any prepared entries."""
    try:
        from lightroom_tagger.core.database import get_cache_stats

        db_path = config.LIBRARY_DB
        if not os.path.exists(db_path):
            return jsonify({'cached': False})

        db = init_database(db_path)
        try:
            stats = get_cache_stats(db)
        finally:
            db.close()
        return jsonify({'cached': stats['cached'] > 0})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/cache/status', methods=['GET'])
def get_cache_status():
    """Get vision cache status."""
    try:
        from lightroom_tagger.core.config import load_config as load_lt_config
        from lightroom_tagger.core.database import get_cache_stats

        db_path = config.LIBRARY_DB
        if not os.path.exists(db_path):
            return jsonify({'error': 'Library database not found'}), 404

        db = init_database(db_path)

        cache_stats = get_cache_stats(db)

        # Use lightroom_tagger config for cache_dir
        lt_config = load_lt_config()
        cache_dir = lt_config.vision_cache_dir

        db.close()
        return jsonify({
            'total_images': cache_stats['total'],
            'cached_images': cache_stats['cached'],
            'missing': cache_stats['missing'],
            'cache_size_mb': round(cache_stats['cache_size_mb'], 2),
            'cache_dir': cache_dir,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
