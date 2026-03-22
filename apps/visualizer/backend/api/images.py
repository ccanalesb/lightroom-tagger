from flask import Blueprint, jsonify, request, send_file
from tinydb import TinyDB, Query
import os
import config

bp = Blueprint('images', __name__)

@bp.route('/instagram', methods=['GET'])
def list_instagram_images():
    try:
        db_path = config.LIBRARY_DB
        if not os.path.exists(db_path):
            return jsonify({'error': 'Library database not found'}), 404

        db = TinyDB(db_path)
        media_items = db.table('instagram_dump_media').all()
        db.close()

        # Transform dump media to Instagram image format
        enriched_images = []
        for media in media_items:
            # Extract source folder from file path (e.g., posts, archived_posts)
            file_path = media.get('file_path', '')
            source_folder = 'unknown'
            if '/media/' in file_path:
                parts = file_path.split('/media/')
                if len(parts) > 1:
                    subpath = parts[1].split('/')
                    if len(subpath) > 0:
                        source_folder = subpath[0]

            enriched_images.append({
                'key': media['media_key'],
                'local_path': file_path,
                'filename': media.get('filename', ''),
                'instagram_folder': media.get('date_folder', ''),
                'source_folder': source_folder,
                'image_hash': media.get('image_hash'),  # Visual hash for duplicate detection
                'description': media.get('caption', ''),
                'crawled_at': media.get('added_at', ''),
                'image_index': 1,
                'total_in_post': 1,
                'post_url': media.get('post_url'),  # Optional - may be null
            })

        # Get filter parameters
        date_from = request.args.get('date_from', '')  # Format: YYYYMM
        date_to = request.args.get('date_to', '')      # Format: YYYYMM
        date_folder = request.args.get('date_folder', '')  # Specific month: YYYYMM
        
        # Filter by date range if specified
        if date_folder:
            # Filter to specific month
            enriched_images = [img for img in enriched_images if img['instagram_folder'] == date_folder]
        elif date_from or date_to:
            # Filter by date range, handling None values
            if date_from:
                enriched_images = [img for img in enriched_images if img['instagram_folder'] and img['instagram_folder'] >= date_from]
            if date_to:
                enriched_images = [img for img in enriched_images if img['instagram_folder'] and img['instagram_folder'] <= date_to]
        
        # Sort by date folder descending (newest first), handling None values
        enriched_images.sort(key=lambda x: x['instagram_folder'] or '', reverse=True)
        
        # Pagination
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        total = len(enriched_images)
        
        paginated = enriched_images[offset:offset+limit]
        
        # Calculate pagination metadata
        has_more = (offset + limit) < total
        current_page = (offset // limit) + 1
        total_pages = (total + limit - 1) // limit

        return jsonify({
            'total': total,
            'images': paginated,
            'pagination': {
                'offset': offset,
                'limit': limit,
                'current_page': current_page,
                'total_pages': total_pages,
                'has_more': has_more,
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/instagram/<path:image_key>/thumbnail', methods=['GET'])
def get_instagram_thumbnail(image_key):
    try:
        db_path = config.LIBRARY_DB
        if not os.path.exists(db_path):
            return jsonify({'error': 'Library database not found'}), 404

        db = TinyDB(db_path)
        Media = Query()
        media_items = db.table('instagram_dump_media').search(Media.media_key == image_key)
        db.close()

        if not media_items:
            return jsonify({'error': 'Image not found'}), 404

        media = media_items[0]
        local_path = media.get('file_path')

        if not local_path or not os.path.exists(local_path):
            return jsonify({'error': 'Image file not found'}), 404

        return send_file(local_path, mimetype='image/jpeg')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/catalog/<path:image_key>/thumbnail', methods=['GET'])
def get_catalog_thumbnail(image_key):
    try:
        db_path = config.LIBRARY_DB
        if not os.path.exists(db_path):
            return jsonify({'error': 'Library database not found'}), 404
        
        db = TinyDB(db_path)
        Image = Query()
        images = db.table('images').search(Image.key == image_key)
        db.close()
        
        if not images:
            return jsonify({'error': 'Image not found'}), 404
        
        image = images[0]
        filepath = image.get('filepath')
        
        if not filepath or not os.path.exists(filepath):
            return jsonify({'error': 'Image file not found'}), 404
        
        return send_file(filepath, mimetype='image/jpeg')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/catalog', methods=['GET'])
def list_catalog_images():
    try:
        db_path = config.LIBRARY_DB
        if not os.path.exists(db_path):
            return jsonify({'error': 'Library database not found'}), 404
        
        db = TinyDB(db_path)
        images = db.table('images').all()
        db.close()
        
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
        return jsonify({'error': str(e)}), 500

@bp.route('/dump-media', methods=['GET'])
def list_dump_media():
    try:
        db_path = config.LIBRARY_DB
        if not os.path.exists(db_path):
            return jsonify({'error': 'Database not found'}), 404
        
        db = TinyDB(db_path)
        
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
        
        db.close()
        
        total = len(media)
        paginated = media[offset:offset+limit]
        
        return jsonify({
            'total': total,
            'media': paginated,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/matches', methods=['GET'])
def list_matches():
    try:
        db_path = config.LIBRARY_DB
        if not os.path.exists(db_path):
            return jsonify({'error': 'Library database not found'}), 404
        
        db = TinyDB(db_path)
        
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
        
        db.close()
        
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        paginated = enriched_matches[offset:offset+limit]
        
        return jsonify({
            'total': len(enriched_matches),
            'matches': paginated,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500