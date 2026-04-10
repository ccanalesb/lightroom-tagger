import json
import os
import sqlite3
from collections import OrderedDict

from flask import Blueprint, jsonify, request, send_file
from lightroom_tagger.core.database import (
    reject_match,
    unvalidate_match,
    validate_match,
)
from utils.db import with_db
from utils.responses import error_not_found, error_server_error, success_paginated

bp = Blueprint('images', __name__)

_DESC_JSON_COLS = ('composition', 'perspectives', 'technical', 'subjects')


def _deserialize_description(row: dict) -> dict:
    """Deserialize JSON columns in an image_descriptions row."""
    out = dict(row)
    for col in _DESC_JSON_COLS:
        val = out.get(col)
        if isinstance(val, str):
            try:
                out[col] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                pass
    return out


def _enrich_instagram_media(media_items, model_lookup=None, desc_lookup=None):
    """Transform database media items to API response format."""
    model_lookup = model_lookup or {}
    desc_lookup = desc_lookup or {}
    enriched = []
    for media in media_items:
        file_path = media.get('file_path', '')
        source_folder = _extract_source_folder(file_path)

        exif_data = media.get('exif_data')
        if isinstance(exif_data, str):
            try:
                exif_data = json.loads(exif_data)
            except (json.JSONDecodeError, TypeError):
                pass

        media_key = media['media_key']
        ai_desc = desc_lookup.get((media_key, 'instagram'))

        enriched.append({
            'key': media_key,
            'local_path': file_path,
            'filename': media.get('filename', ''),
            'instagram_folder': media.get('date_folder', ''),
            'date_folder': media.get('date_folder', ''),  # Add explicit date_folder for frontend
            'created_at': media.get('created_at'),  # Add created_at timestamp
            'source_folder': source_folder,
            'image_hash': media.get('image_hash'),
            'description': ai_desc.get('summary', '') if ai_desc else '',  # AI description
            'caption': media.get('caption', ''),  # Instagram caption
            'crawled_at': media.get('added_at', ''),
            'image_index': 1,
            'total_in_post': 1,
            'post_url': media.get('post_url'),
            'exif_data': exif_data,
            'processed': bool(media.get('processed')),
            'matched_catalog_key': media.get('matched_catalog_key'),
            'matched_model': model_lookup.get(media_key),
        })
    return enriched


def _extract_source_folder(file_path):
    """Extract source folder (posts, archived_posts) from file path."""
    if '/media/' in file_path:
        parts = file_path.split('/media/')
        if len(parts) > 1:
            subpath = parts[1].split('/')
            if len(subpath) > 0:
                return subpath[0]
    return 'unknown'


def _filter_by_date(images, date_folder, date_from, date_to):
    """Filter images by date parameters."""
    if date_folder:
        return [img for img in images if img['instagram_folder'] == date_folder]

    if date_from:
        images = [img for img in images if img['instagram_folder'] and img['instagram_folder'] >= date_from]
    if date_to:
        images = [img for img in images if img['instagram_folder'] and img['instagram_folder'] <= date_to]

    return images


@bp.route('/instagram', methods=['GET'])
@with_db
def list_instagram_images(db):
    """List Instagram images with filtering and pagination."""
    try:
        media_items = db.execute("SELECT * FROM instagram_dump_media").fetchall()

        model_lookup = {}
        try:
            for row in db.execute("SELECT insta_key, model_used FROM matches").fetchall():
                model_lookup[row['insta_key']] = row['model_used']
        except sqlite3.OperationalError:
            pass

        desc_lookup = {}
        try:
            for desc in db.execute("SELECT * FROM image_descriptions WHERE image_type = 'instagram'").fetchall():
                key = (desc.get('image_key'), desc.get('image_type'))
                desc_lookup[key] = _deserialize_description(desc)
        except sqlite3.OperationalError:
            pass

        enriched_images = _enrich_instagram_media(media_items, model_lookup, desc_lookup)

        # Get filter parameters
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        date_folder = request.args.get('date_folder', '')

        # Apply filters
        enriched_images = _filter_by_date(enriched_images, date_folder, date_from, date_to)

        # Sort by date folder descending
        enriched_images.sort(key=lambda x: x['instagram_folder'] or '', reverse=True)

        # Pagination
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        total = len(enriched_images)

        paginated = enriched_images[offset:offset+limit]

        # Build custom response with 'images' key for backward compatibility
        success_paginated(paginated, total, offset, limit)
        # success_paginated returns (response, status) tuple, need to modify the response
        # Let's construct manually for compatibility
        return jsonify({
            'total': total,
            'images': paginated,
            'pagination': {
                'offset': offset,
                'limit': limit,
                'current_page': (offset // limit) + 1,
                'total_pages': (total + limit - 1) // limit,
                'has_more': (offset + limit) < total,
            }
        })
    except Exception as e:
        return error_server_error(str(e))


@bp.route('/instagram/months', methods=['GET'])
@with_db
def get_instagram_months(db):
    """Get unique months available in Instagram images."""
    try:
        media_items = db.execute("SELECT * FROM instagram_dump_media").fetchall()
        months = set()
        for media in media_items:
            date_folder = media.get('date_folder', '')
            if date_folder:
                months.add(date_folder)
        return jsonify({'months': sorted(months, reverse=True)})
    except Exception as e:
        return error_server_error(str(e))


@bp.route('/instagram/<path:image_key>/thumbnail', methods=['GET'])
@with_db
def get_instagram_thumbnail(db, image_key):
    """Get thumbnail for Instagram image."""
    try:
        media_items = db.execute(
            "SELECT * FROM instagram_dump_media WHERE media_key = ?",
            (image_key,),
        ).fetchall()

        if not media_items:
            return error_not_found('image')

        media = media_items[0]
        local_path = media.get('file_path')

        if not local_path or not os.path.exists(local_path):
            return error_not_found('file')

        return send_file(local_path, mimetype='image/jpeg')
    except Exception as e:
        return error_server_error(str(e))


@bp.route('/catalog/<path:image_key>/thumbnail', methods=['GET'])
@with_db
def get_catalog_thumbnail(db, image_key):
    """Get thumbnail for catalog image, creating cache if needed."""
    try:
        images = db.execute(
            "SELECT * FROM images WHERE key = ?",
            (image_key,),
        ).fetchall()

        if not images:
            return error_not_found('image')

        image = images[0]

        # Check vision cache first
        cached = db.execute(
            "SELECT compressed_path FROM vision_cache WHERE key = ?",
            (image_key,),
        ).fetchone()
        if cached and cached.get('compressed_path') and os.path.exists(cached['compressed_path']):
            return send_file(cached['compressed_path'], mimetype='image/jpeg')

        # Resolve original path
        from lightroom_tagger.core.path_utils import resolve_catalog_path
        filepath = resolve_catalog_path(image.get('filepath', ''))

        if not filepath or not os.path.exists(filepath):
            return error_not_found('file')

        # Generate cache on-the-fly for missing thumbnails
        try:
            from lightroom_tagger.core.vision_cache import get_or_create_cached_image
            cached_path = get_or_create_cached_image(db, image_key, filepath)
            if cached_path and os.path.exists(cached_path):
                return send_file(cached_path, mimetype='image/jpeg')
        except Exception as cache_err:
            # If cache generation fails, log but don't break the request
            print(f"Cache generation failed for {image_key}: {cache_err}")

        # Last resort: send original (may not be browser-compatible)
        return send_file(filepath, mimetype='image/jpeg')
    except Exception as e:
        return error_server_error(str(e))


@bp.route('/catalog/months', methods=['GET'])
@with_db
def get_catalog_months(db):
    """Get available year-months from catalog images based on date_taken."""
    try:
        rows = db.execute("""
            SELECT DISTINCT strftime('%Y%m', date_taken) as month
            FROM images
            WHERE date_taken IS NOT NULL
            ORDER BY month DESC
        """).fetchall()
        months = [row['month'] for row in rows if row['month']]
        return jsonify({'months': months})
    except Exception as e:
        return error_server_error(str(e))


@bp.route('/catalog', methods=['GET'])
@with_db
def list_catalog_images(db):
    """List catalog images with optional filtering by posted status and date_taken month."""
    try:
        images = db.execute("SELECT * FROM images").fetchall()

        posted = request.args.get('posted')
        month = request.args.get('month')  # YYYYMM format
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)

        if posted == 'true':
            images = [img for img in images if img.get('instagram_posted')]
        elif posted == 'false':
            images = [img for img in images if not img.get('instagram_posted')]

        if month and len(month) == 6:  # YYYYMM format
            year = month[:4]
            mon = month[4:6]
            images = [
                img for img in images
                if img.get('date_taken') and 
                   img['date_taken'].startswith(f"{year}-{mon}")
            ]

        paginated = images[offset:offset+limit]

        return jsonify({
            'total': len(images),
            'images': paginated,
        })
    except Exception as e:
        return error_server_error(str(e))


@bp.route('/dump-media', methods=['GET'])
@with_db
def list_dump_media(db):
    """List dump media with optional filtering."""
    try:
        processed = request.args.get('processed')
        matched = request.args.get('matched')
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)

        if processed == 'true':
            media = db.execute(
                "SELECT * FROM instagram_dump_media WHERE processed = 1"
            ).fetchall()
        elif processed == 'false':
            media = db.execute(
                "SELECT * FROM instagram_dump_media WHERE processed = 0"
            ).fetchall()
        elif matched == 'true':
            media = db.execute(
                "SELECT * FROM instagram_dump_media WHERE matched_catalog_key IS NOT NULL"
            ).fetchall()
        elif matched == 'false':
            media = db.execute(
                "SELECT * FROM instagram_dump_media WHERE matched_catalog_key IS NULL"
            ).fetchall()
        else:
            media = db.execute("SELECT * FROM instagram_dump_media").fetchall()

        total = len(media)
        paginated = media[offset:offset+limit]

        return jsonify({
            'total': total,
            'media': paginated,
        })
    except Exception as e:
        return error_server_error(str(e))


@bp.route('/matches', methods=['GET'])
@with_db
def list_matches(db):
    """List matches grouped by Instagram image."""
    try:
        matches = db.execute(
            "SELECT * FROM matches ORDER BY insta_key, COALESCE(rank, 1), total_score DESC"
        ).fetchall()

        # Build lookup tables for images (avoid N+1 queries)
        instagram_lookup = {}
        for img in db.execute("SELECT * FROM instagram_images").fetchall():
            instagram_lookup[img.get('key')] = img

        catalog_lookup = {}
        for img in db.execute("SELECT * FROM images").fetchall():
            catalog_lookup[img.get('key')] = img

        desc_lookup = {}
        try:
            for desc in db.execute("SELECT * FROM image_descriptions").fetchall():
                key = (desc.get('image_key'), desc.get('image_type'))
                desc_lookup[key] = _deserialize_description(desc)
        except sqlite3.OperationalError:
            pass

        groups = OrderedDict()
        all_enriched = []

        for match in matches:
            insta_key = match.get('insta_key')
            catalog_key = match.get('catalog_key')

            enriched = {
                **match,
                'instagram_key': insta_key,
                'score': match.get('total_score', 0),
            }

            if insta_key and insta_key in instagram_lookup:
                enriched['instagram_image'] = instagram_lookup[insta_key]
            if catalog_key and catalog_key in catalog_lookup:
                enriched['catalog_image'] = catalog_lookup[catalog_key]

            enriched['catalog_description'] = desc_lookup.get((catalog_key, 'catalog')) if catalog_key else None
            enriched['insta_description'] = desc_lookup.get((insta_key, 'instagram')) if insta_key else None

            groups.setdefault(insta_key, []).append(enriched)
            all_enriched.append(enriched)

        match_groups = []
        for insta_key, candidates in groups.items():
            best = max((c.get('score') or 0) for c in candidates) if candidates else 0
            match_groups.append({
                'instagram_key': insta_key,
                'instagram_image': instagram_lookup.get(insta_key),
                'candidates': candidates,
                'best_score': best,
                'candidate_count': len(candidates),
                'has_validated': any(c.get('validated_at') for c in candidates),
            })

        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        paginated_groups = match_groups[offset:offset+limit]
        paginated_matches = []
        for grp in paginated_groups:
            paginated_matches.extend(grp['candidates'])

        total_groups = len(match_groups)
        total_matches = len(all_enriched)

        return jsonify({
            'total': total_groups,
            'total_groups': total_groups,
            'total_matches': total_matches,
            'match_groups': paginated_groups,
            'matches': paginated_matches,
        })
    except Exception as e:
        return error_server_error(str(e))


@bp.route('/matches/<path:catalog_key>/<path:insta_key>/validate', methods=['PATCH'])
@with_db
def toggle_match_validation(db, catalog_key, insta_key):
    """Toggle human validation on a match."""
    try:
        match_row = db.execute(
            "SELECT validated_at FROM matches WHERE catalog_key = ? AND insta_key = ?",
            (catalog_key, insta_key),
        ).fetchone()
        if not match_row:
            return error_not_found('match')

        if match_row['validated_at']:
            unvalidate_match(db, catalog_key, insta_key)
            return jsonify({'validated': False})
        else:
            validate_match(db, catalog_key, insta_key)
            return jsonify({'validated': True})
    except Exception as e:
        return error_server_error(str(e))


@bp.route('/matches/<path:catalog_key>/<path:insta_key>/reject', methods=['PATCH'])
@with_db
def reject_match_endpoint(db, catalog_key, insta_key):
    """Reject a match: delete it and blocklist the pair."""
    try:
        match_row = db.execute(
            "SELECT validated_at FROM matches WHERE catalog_key = ? AND insta_key = ?",
            (catalog_key, insta_key),
        ).fetchone()
        if not match_row:
            return error_not_found('match')
        if match_row['validated_at']:
            return jsonify({
                'error': 'Match has been validated; un-validate it before rejecting.',
                'rejected': False,
            }), 409

        reject_match(db, catalog_key, insta_key)
        return jsonify({'rejected': True})
    except Exception as e:
        return error_server_error(str(e))
