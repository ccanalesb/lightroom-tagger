from flask import Blueprint, jsonify, request, send_file
from tinydb import Query
import os
from utils.db import with_db
from utils.responses import error_not_found, error_server_error, success_paginated

bp = Blueprint('images', __name__)


def _enrich_instagram_media(media_items):
    """Transform database media items to API response format."""
    enriched = []
    for media in media_items:
        file_path = media.get('file_path', '')
        source_folder = _extract_source_folder(file_path)

        enriched.append({
            'key': media['media_key'],
            'local_path': file_path,
            'filename': media.get('filename', ''),
            'instagram_folder': media.get('date_folder', ''),
            'source_folder': source_folder,
            'image_hash': media.get('image_hash'),
            'description': media.get('caption', ''),
            'crawled_at': media.get('added_at', ''),
            'image_index': 1,
            'total_in_post': 1,
            'post_url': media.get('post_url'),
            'exif_data': media.get('exif_data'),
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
        media_items = db.table('instagram_dump_media').all()
        enriched_images = _enrich_instagram_media(media_items)

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
        response = success_paginated(paginated, total, offset, limit)
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


@bp.route('/instagram/<path:image_key>/thumbnail', methods=['GET'])
@with_db
def get_instagram_thumbnail(db, image_key):
    """Get thumbnail for Instagram image."""
    try:
        Media = Query()
        media_items = db.table('instagram_dump_media').search(Media.media_key == image_key)

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
    """Get thumbnail for catalog image."""
    try:
        Image = Query()
        images = db.table('images').search(Image.key == image_key)

        if not images:
            return error_not_found('image')

        image = images[0]
        filepath = image.get('filepath')

        if not filepath or not os.path.exists(filepath):
            return error_not_found('file')

        return send_file(filepath, mimetype='image/jpeg')
    except Exception as e:
        return error_server_error(str(e))


@bp.route('/catalog', methods=['GET'])
@with_db
def list_catalog_images(db):
    """List catalog images with optional filtering."""
    try:
        images = db.table('images').all()

        posted = request.args.get('posted')
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)

        if posted == 'true':
            images = [img for img in images if img.get('instagram_posted')]
        elif posted == 'false':
            images = [img for img in images if not img.get('instagram_posted')]

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

        table = db.table('instagram_dump_media')
        Media = Query()

        if processed == 'true':
            media = table.search(Media.processed == True)
        elif processed == 'false':
            media = table.search(Media.processed == False)
        elif matched == 'true':
            media = table.search(Media.matched_catalog_key != None)
        elif matched == 'false':
            media = table.search(Media.matched_catalog_key == None)
        else:
            media = table.all()

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
    """List matches between Instagram and catalog images."""
    try:
        if 'matches' not in db.tables():
            return jsonify({'total': 0, 'matches': []})

        matches = db.table('matches').all()

        # Build lookup tables for images (avoid N+1 queries)
        instagram_lookup = {}
        if 'instagram_images' in db.tables():
            for img in db.table('instagram_images').all():
                instagram_lookup[img.get('key')] = img

        catalog_lookup = {}
        for img in db.table('images').all():
            catalog_lookup[img.get('key')] = img

        # Enrich matches with image data
        enriched_matches = []
        for match in matches:
            enriched = {**match}

            # Add Instagram image details
            insta_key = match.get('insta_key')
            if insta_key and insta_key in instagram_lookup:
                enriched['instagram_image'] = instagram_lookup[insta_key]

            # Add Catalog image details
            catalog_key = match.get('catalog_key')
            if catalog_key and catalog_key in catalog_lookup:
                enriched['catalog_image'] = catalog_lookup[catalog_key]

            enriched_matches.append(enriched)

        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)

        paginated = enriched_matches[offset:offset+limit]

        return jsonify({
            'total': len(enriched_matches),
            'matches': paginated,
        })
    except Exception as e:
        return error_server_error(str(e))
