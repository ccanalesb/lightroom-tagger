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
        images = db.table('instagram_images').all()
        db.close()
        
        # Group by post to calculate totals
        from collections import defaultdict
        post_totals = defaultdict(int)
        for img in images:
            post_totals[img['instagram_folder']] += 1
        
        # Enrich images with index and total
        post_counts = defaultdict(int)
        enriched_images = []
        for img in images:
            folder = img['instagram_folder']
            # Extract image index from filename (img_0.jpg -> 0)
            filename = img['filename']
            try:
                idx = int(filename.replace('img_', '').replace('.jpg', ''))
            except:
                idx = post_counts[folder]
            
            enriched_images.append({
                **img,
                'image_index': idx + 1,  # 1-indexed for display
                'total_in_post': post_totals[folder],
            })
            post_counts[folder] += 1
        
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        paginated = enriched_images[offset:offset+limit]
        
        return jsonify({
            'total': len(enriched_images),
            'images': paginated,
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
        Image = Query()
        images = db.table('instagram_images').search(Image.key == image_key)
        db.close()
        
        if not images:
            return jsonify({'error': 'Image not found'}), 404
        
        image = images[0]
        local_path = image.get('local_path')
        
        if not local_path or not os.path.exists(local_path):
            return jsonify({'error': 'Image file not found'}), 404
        
        return send_file(local_path, mimetype='image/jpeg')
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
        db.close()
        
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        paginated = matches[offset:offset+limit]
        
        return jsonify({
            'total': len(matches),
            'matches': paginated,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500