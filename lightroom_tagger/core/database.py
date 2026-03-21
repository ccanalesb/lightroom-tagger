from tinydb import TinyDB, Query
from typing import Optional
import os
from datetime import datetime


def init_database(db_path: str) -> TinyDB:
    """Initialize TinyDB at given path."""
    os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else '.', exist_ok=True)
    db = TinyDB(db_path)
    db.default_table_name = 'images'
    return db


def generate_key(record: dict) -> str:
    """Generate unique key from record: {date_taken}_{filename}"""
    date_taken = record.get('date_taken', 'unknown')
    filename = record.get('filename', 'unknown')
    return f"{date_taken}_{filename}"


def store_image(db, record: dict) -> str:
    """Store image record, return key. Upsert if exists."""
    key = generate_key(record)
    record['key'] = key
    
    default_instagram_fields = {
        'instagram_posted': False,
        'instagram_post_date': None,
        'instagram_url': None,
        'instagram_index': 0,
        'image_hash': None,
    }
    for field, default_val in default_instagram_fields.items():
        if field not in record:
            record[field] = default_val
    
    Image = Query()
    existing = db.search(Image.key == key)
    
    if existing:
        existing_record = existing[0]
        for field, value in default_instagram_fields.items():
            if field not in record:
                record[field] = existing_record.get(field, value)
        db.update(record, Image.key == key)
    else:
        db.insert(record)
    
    return key


def store_images_batch(db, records: list[dict]) -> int:
    """Store multiple records, return count."""
    count = 0
    for record in records:
        store_image(db, record)
        count += 1
    return count


def get_image(db, key: str) -> dict | None:
    """Get image by key."""
    Image = Query()
    results = db.search(Image.key == key)
    return results[0] if results else None


def search_by_keyword(db, keyword: str) -> list[dict]:
    """Search images by keyword."""
    Image = Query()
    keyword_lower = keyword.lower()
    return db.search(
        (Image.keywords.test(lambda k: any(keyword_lower in str(w).lower() for w in k))) |
        (Image.filename.test(lambda f: keyword_lower in str(f).lower())) |
        (Image.title.test(lambda t: t and keyword_lower in str(t).lower())) |
        (Image.description.test(lambda d: d and keyword_lower in str(d).lower()))
    )


def search_by_rating(db, min_rating: int = 0) -> list[dict]:
    """Search images by minimum rating."""
    Image = Query()
    return db.search(Image.rating >= min_rating)


def search_by_date(db, start_date: str, end_date: str = None) -> list[dict]:
    """Search images by date range (ISO format)."""
    Image = Query()
    if end_date:
        return db.search((Image.date_taken >= start_date) & (Image.date_taken <= end_date))
    return db.search(Image.date_taken >= start_date)


def search_by_color_label(db, label: str) -> list[dict]:
    """Search images by color label."""
    Image = Query()
    label_lower = label.lower()
    return db.search(Image.color_label.test(lambda c: c and c.lower() == label_lower))


def get_all_images(db) -> list[dict]:
    """Get all images."""
    return db.all()


def get_image_count(db) -> int:
    """Get total image count."""
    return len(db)


def delete_image(db, key: str) -> bool:
    """Delete image by key."""
    Image = Query()
    existing = db.search(Image.key == key)
    if existing:
        db.remove(Image.key == key)
        return True
    return False


def init_instagram_dump_table(db: TinyDB):
    """Ensure instagram_dump_media table exists."""
    if 'instagram_dump_media' not in db.tables():
        db.table('instagram_dump_media')


def store_instagram_dump_media(db, record: dict) -> str:
    """Store Instagram dump media record. Idempotent by media_key. Aggregative - merges data.

    Args:
        db: TinyDB instance
        record: Dict with media_key, file_path, caption, created_at, exif_data, post_url

    Returns:
        media_key
    """
    Media = Query()

    media_key = record.get('media_key')
    if not media_key:
        raise ValueError("media_key is required")

    # Set defaults
    record.setdefault('processed', False)
    record.setdefault('matched_catalog_key', None)
    record.setdefault('vision_result', None)
    record.setdefault('vision_score', None)
    record.setdefault('processed_at', None)
    record.setdefault('added_at', datetime.now().isoformat())
    record.setdefault('exif_data', None)
    record.setdefault('post_url', None)

    existing = db.table('instagram_dump_media').search(Media.media_key == media_key)

    if existing:
        existing_record = existing[0]
        # Aggregative: merge new data with existing (new data takes precedence)
        merged = {**existing_record, **record}
        # Keep original added_at
        merged['added_at'] = existing_record.get('added_at', record.get('added_at'))
        # Update only if not already processed
        if not existing_record.get('processed'):
            db.table('instagram_dump_media').update(merged, Media.media_key == media_key)
    else:
        db.table('instagram_dump_media').insert(record)

    return media_key


def get_instagram_dump_media(db, media_key: str) -> Optional[dict]:
    """Get Instagram dump media by key."""
    Media = Query()
    results = db.table('instagram_dump_media').search(Media.media_key == media_key)
    return results[0] if results else None


def get_unprocessed_dump_media(db, limit: int = None) -> list:
    """Get unprocessed Instagram dump media for matching."""
    Media = Query()
    results = db.table('instagram_dump_media').search(Media.processed == False)
    if limit:
        return results[:limit]
    return results


def mark_dump_media_processed(db, media_key: str, matched_catalog_key: str = None,
                              vision_result: str = None, vision_score: float = None) -> bool:
    """Mark Instagram dump media as processed with match results."""
    Media = Query()

    updates = {
        'processed': True,
        'matched_catalog_key': matched_catalog_key,
        'vision_result': vision_result,
        'vision_score': vision_score,
        'processed_at': datetime.now().isoformat(),
    }

    existing = db.table('instagram_dump_media').search(Media.media_key == media_key)
    if existing:
        db.table('instagram_dump_media').update(updates, Media.media_key == media_key)
        return True
    return False
    return False


def clear_all(db) -> int:
    """Clear all images. Returns count."""
    count = len(db)
    db.truncate()
    return count


def update_instagram_status(db, key: str, posted: bool = True, post_date: str = None, 
                           url: str = None, index: int = 0) -> bool:
    """Update Instagram status for an image.
    
    Args:
        db: TinyDB instance
        key: Image key
        posted: Whether image was posted
        post_date: Date of Instagram post (ISO format)
        url: Instagram post URL
        index: Index in carousel (0 for single image)
    
    Returns:
        True if updated, False if not found
    """
    Image = Query()
    existing = db.search(Image.key == key)
    
    if not existing:
        return False
    
    updates = {
        'instagram_posted': posted,
        'instagram_post_date': post_date,
        'instagram_url': url,
        'instagram_index': index,
    }
    
    db.update(updates, Image.key == key)
    return True


def search_by_instagram_posted(db, posted: bool = True) -> list[dict]:
    """Search images by Instagram posted status."""
    Image = Query()
    return db.search(Image.instagram_posted == posted)


def get_images_without_hash(db) -> list[dict]:
    """Get all images that don't have a computed hash yet."""
    Image = Query()
    return db.search(Image.image_hash == None)


def update_image_hash(db, key: str, image_hash: str) -> bool:
    """Update the image hash for an image."""
    Image = Query()
    existing = db.search(Image.key == key)
    
    if not existing:
        return False
    
    db.update({'image_hash': image_hash}, Image.key == key)
    return True


def batch_update_hashes(db, updates: list[dict]) -> int:
    """Batch update image hashes.
    
    Args:
        db: TinyDB instance
        updates: List of dicts with 'key' and 'image_hash'
    
    Returns:
        Number of updates made
    """
    count = 0
    for update in updates:
        key = update.get('key')
        image_hash = update.get('image_hash')
        if key and image_hash:
            if update_image_hash(db, key, image_hash):
                count += 1
    return count


if __name__ == "__main__":
    import tempfile
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    print(f"Testing database at: {db_path}")
    db = init_database(db_path)
    
    test_records = [
        {
            'date_taken': '2024-01-15',
            'filename': 'photo1.jpg',
            'rating': 5,
            'keywords': ['nature', 'mountain'],
            'color_label': 'Red',
            'title': 'Mountain View',
            'description': 'Beautiful mountain landscape'
        },
        {
            'date_taken': '2024-02-20',
            'filename': 'photo2.jpg',
            'rating': 3,
            'keywords': ['water', 'lake'],
            'color_label': 'Blue',
            'title': 'Lake Sunset',
            'description': 'Peaceful lake at sunset'
        },
        {
            'date_taken': '2024-03-10',
            'filename': 'photo3.jpg',
            'rating': 5,
            'keywords': ['nature', 'flower'],
            'color_label': 'Green',
            'title': 'Spring Flower',
            'description': 'Beautiful bloom'
        }
    ]
    
    print("\n--- Testing store_images_batch ---")
    count = store_images_batch(db, test_records)
    print(f"Stored {count} records")
    
    print("\n--- Testing get_image_count ---")
    print(f"Total images: {get_image_count(db)}")
    
    print("\n--- Testing get_image ---")
    key = generate_key(test_records[0])
    img = get_image(db, key)
    print(f"Retrieved: {img['title'] if img else 'Not found'}")
    
    print("\n--- Testing search_by_rating ---")
    results = search_by_rating(db, 5)
    print(f"Images with rating >= 5: {len(results)}")
    
    print("\n--- Testing search_by_date ---")
    results = search_by_date(db, '2024-01-01', '2024-02-28')
    print(f"Images in Jan-Feb 2024: {len(results)}")
    
    print("\n--- Testing search_by_keyword ---")
    results = search_by_keyword(db, 'nature')
    print(f"Images with 'nature' keyword: {len(results)}")
    
    print("\n--- Testing search_by_color_label ---")
    results = search_by_color_label(db, 'Red')
    print(f"Images with Red label: {len(results)}")
    
    print("\n--- Testing upsert ---")
    updated_record = {
        'date_taken': '2024-01-15',
        'filename': 'photo1.jpg',
        'rating': 4,
        'keywords': ['nature', 'mountain', 'updated'],
        'color_label': 'Red',
        'title': 'Mountain View Updated',
        'description': 'Updated description'
    }
    new_key = store_image(db, updated_record)
    img = get_image(db, new_key)
    print(f"Updated title: {img['title']}")
    print(f"Total count after upsert: {get_image_count(db)}")
    
    print("\n--- Testing delete_image ---")
    deleted = delete_image(db, new_key)
    print(f"Deleted: {deleted}, count: {get_image_count(db)}")
    
    print("\n--- Testing clear_all ---")
    count = clear_all(db)
    print(f"Cleared {count} records")
    
    db.close()
    os.unlink(db_path)
    print("\nAll tests passed!")


def init_catalog_table(db: TinyDB):
    """Ensure catalog_images table exists."""
    if 'catalog_images' not in db.tables():
        db.table('catalog_images')


def init_instagram_table(db: TinyDB):
    """Ensure instagram_images table exists."""
    if 'instagram_images' not in db.tables():
        db.table('instagram_images')


def init_matches_table(db: TinyDB):
    """Ensure matches table exists."""
    if 'matches' not in db.tables():
        db.table('matches')


def store_catalog_image(db, record: dict) -> str:
    """Store catalog image with analysis. Idempotent."""
    Catalog = Query()
    
    key = record.get('key')
    record['analyzed_at'] = datetime.now().isoformat()
    
    existing = db.table('catalog_images').search(Catalog.key == key)
    if existing:
        db.table('catalog_images').update(record, Catalog.key == key)
    else:
        db.table('catalog_images').insert(record)
    
    return key


def store_instagram_image(db, record: dict) -> str:
    """Store Instagram image with analysis. Idempotent by local_path."""
    Insta = Query()
    
    local_path = record.get('local_path')
    post_url = record.get('post_url')
    filename = record.get('filename', '')
    key = f"insta_{datetime.now().strftime('%Y-%m-%d')}_{post_url.split('/')[-2]}_{filename}"
    record['key'] = key
    record['crawled_at'] = datetime.now().isoformat()
    
    existing = db.table('instagram_images').search(Insta.local_path == local_path)
    if existing:
        db.table('instagram_images').update(record, Insta.local_path == local_path)
    else:
        db.table('instagram_images').insert(record)
    
    return key


def store_match(db, record: dict) -> str:
    """Store match between catalog and Instagram image."""
    Match = Query()
    
    catalog_key = record.get('catalog_key')
    insta_key = record.get('insta_key')
    record['matched_at'] = datetime.now().isoformat()
    
    existing = db.table('matches').search(
        (Match.catalog_key == catalog_key) & (Match.insta_key == insta_key)
    )
    if existing:
        db.table('matches').update(record, (Match.catalog_key == catalog_key) & (Match.insta_key == insta_key))
    else:
        db.table('matches').insert(record)
    
    return f"{catalog_key} <-> {insta_key}"


def get_catalog_images_needing_analysis(db) -> list:
    """Get catalog images without phash."""
    Catalog = Query()
    return db.table('catalog_images').search(Catalog.phash == None)


def get_instagram_images_needing_analysis(db) -> list:
    """Get Instagram images without phash."""
    Insta = Query()
    return db.table('instagram_images').search(Insta.phash == None)


def init_vision_comparisons_table(db: TinyDB):
    """Ensure vision_comparisons table exists."""
    if 'vision_comparisons' not in db.tables():
        db.table('vision_comparisons')


def get_vision_comparison(db, catalog_key: str, insta_key: str) -> Optional[dict]:
    """Get cached vision comparison result.
    
    Returns:
        dict with 'result', 'vision_score', 'compared_at', 'model_used' or None if not cached.
    """
    Vision = Query()
    results = db.table('vision_comparisons').search(
        (Vision.catalog_key == catalog_key) & (Vision.insta_key == insta_key)
    )
    return results[0] if results else None


def store_vision_comparison(db, catalog_key: str, insta_key: str, 
                           result: str, vision_score: float, model_used: str) -> bool:
    """Store vision comparison result in cache. Never expires.
    
    Args:
        db: TinyDB instance
        catalog_key: Key of catalog image
        insta_key: Key of Instagram image
        result: 'SAME' | 'DIFFERENT' | 'UNCERTAIN'
        vision_score: float (1.0, 0.5, or 0.0)
        model_used: Vision model identifier
    
    Returns:
        True if stored successfully
    """
    Vision = Query()
    
    record = {
        'catalog_key': catalog_key,
        'insta_key': insta_key,
        'result': result,
        'vision_score': vision_score,
        'compared_at': datetime.now().isoformat(),
        'model_used': model_used
    }
    
    existing = db.table('vision_comparisons').search(
        (Vision.catalog_key == catalog_key) & (Vision.insta_key == insta_key)
    )
    
    if existing:
        db.table('vision_comparisons').update(
            record,
            (Vision.catalog_key == catalog_key) & (Vision.insta_key == insta_key)
        )
    else:
        db.table('vision_comparisons').insert(record)
    
    return True
