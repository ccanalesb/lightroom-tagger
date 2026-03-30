import json
import os

from flask import Blueprint, jsonify, request
from lightroom_tagger.core.database import (
    get_all_images_with_descriptions,
    get_image_description,
)
from lightroom_tagger.core.description_service import (
    describe_instagram_image,
    describe_matched_image,
)
from utils.db import with_db
from utils.responses import error_server_error

bp = Blueprint('descriptions', __name__)

_JSON_COLS = ('composition', 'perspectives', 'technical', 'subjects')


@bp.route('/', methods=['GET'])
@with_db
def list_descriptions(db):
    """List images with their AI descriptions."""
    try:
        image_type = request.args.get('image_type')  # catalog, instagram, or None for both
        described_only = request.args.get('described_only', 'false') == 'true'
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)

        items, total = get_all_images_with_descriptions(
            db, image_type=image_type, described_only=described_only,
            limit=limit, offset=offset,
        )

        return jsonify({
            'total': total,
            'items': items,
            'pagination': {
                'offset': offset,
                'limit': limit,
                'current_page': (offset // limit) + 1,
                'total_pages': (total + limit - 1) // limit if total else 0,
                'has_more': (offset + limit) < total,
            },
        })
    except Exception as e:
        return error_server_error(str(e))


@bp.route('/<path:image_key>', methods=['GET'])
@with_db
def get_description(db, image_key):
    """Get full description for a single image."""
    try:
        desc = get_image_description(db, image_key)
        if not desc:
            return jsonify({'description': None})
        return jsonify({'description': _deserialize(desc)})
    except Exception as e:
        return error_server_error(str(e))


@bp.route('/<path:image_key>/generate', methods=['POST'])
@with_db
def generate_description(db, image_key):
    """Generate AI description for a single image."""
    from lightroom_tagger.core.provider_errors import (
        AuthenticationError,
        ConnectionError,
        ModelUnavailableError,
        RateLimitError,
    )

    old_model_env = os.environ.get('DESCRIPTION_VISION_MODEL')
    provider_id = None
    try:
        data = request.json or {}
        image_type = data.get('image_type', 'catalog')
        force = data.get('force', False)
        model = data.get('model')
        provider_id = data.get('provider_id')
        provider_model = data.get('provider_model')

        if model and not provider_id:
            os.environ['DESCRIPTION_VISION_MODEL'] = model

        try:
            if image_type == 'catalog':
                generated = describe_matched_image(
                    db, image_key, force=force,
                    provider_id=provider_id, model=provider_model,
                )
            elif image_type == 'instagram':
                generated = describe_instagram_image(
                    db, image_key, force=force,
                    provider_id=provider_id, model=provider_model,
                )
            else:
                return jsonify({'error': f'Invalid image_type: {image_type}'}), 400
        except KeyError:
            if not provider_id:
                raise
            return jsonify({
                'error': 'invalid_provider',
                'message': f'Unknown provider: {provider_id}',
            }), 400

        if not generated:
            existing = get_image_description(db, image_key)
            if existing:
                return jsonify({'generated': False, 'description': _deserialize(existing)})
            return jsonify({'generated': False, 'description': None})

        desc = get_image_description(db, image_key)
        return jsonify({'generated': True, 'description': _deserialize(desc) if desc else None})
    except RateLimitError as e:
        return jsonify({
            'error': 'rate_limit',
            'message': str(e),
            'provider': getattr(e, 'provider', None) or provider_id,
        }), 429
    except AuthenticationError as e:
        return jsonify({
            'error': 'auth_error',
            'message': str(e),
            'provider': getattr(e, 'provider', None) or provider_id,
        }), 401
    except (ModelUnavailableError, ConnectionError) as e:
        return jsonify({
            'error': 'provider_unavailable',
            'message': str(e),
            'provider': getattr(e, 'provider', None) or provider_id,
        }), 503
    except Exception as e:
        return error_server_error(str(e))
    finally:
        if old_model_env is not None:
            os.environ['DESCRIPTION_VISION_MODEL'] = old_model_env
        else:
            os.environ.pop('DESCRIPTION_VISION_MODEL', None)


def _deserialize(row: dict) -> dict:
    out = dict(row)
    for col in _JSON_COLS:
        val = out.get(col)
        if isinstance(val, str):
            try:
                out[col] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                pass
    return out
