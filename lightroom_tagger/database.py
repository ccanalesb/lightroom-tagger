from tinydb import TinyDB, Query
from typing import Optional
import os


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
    
    Image = Query()
    existing = db.search(Image.key == key)
    
    if existing:
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


def clear_all(db) -> int:
    """Clear all images. Returns count."""
    count = len(db)
    db.truncate()
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
