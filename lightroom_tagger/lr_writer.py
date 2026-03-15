import sqlite3
from typing import Optional
from pathlib import Path


def connect_catalog(catalog_path: str) -> sqlite3.Connection:
    """Connect to Lightroom catalog."""
    conn = sqlite3.connect(catalog_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_keyword_id(conn: sqlite3.Connection, keyword_name: str) -> Optional[int]:
    """Get keyword ID by name."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id_local FROM AgLibraryKeyword WHERE name = ?",
        (keyword_name,)
    )
    row = cursor.fetchone()
    return row[0] if row else None


def keyword_exists(conn: sqlite3.Connection, keyword_name: str) -> bool:
    """Check if keyword exists in catalog."""
    return get_keyword_id(conn, keyword_name) is not None


def create_keyword(conn: sqlite3.Connection, keyword_name: str) -> int:
    """Create a new keyword in the catalog.
    
    Returns:
        Keyword ID
    """
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO AgLibraryKeyword 
           (id_global, name, lc_name, dateCreated, keywordType) 
           VALUES (?, ?, ?, datetime('now'), 0)""",
        (keyword_name.lower(), keyword_name, keyword_name.lower())
    )
    conn.commit()
    return cursor.lastrowid


def get_or_create_keyword(conn: sqlite3.Connection, keyword_name: str) -> int:
    """Get existing keyword ID or create new one.
    
    Returns:
        Keyword ID
    """
    existing_id = get_keyword_id(conn, keyword_name)
    if existing_id:
        return existing_id
    return create_keyword(conn, keyword_name)


def get_image_local_id(conn: sqlite3.Connection, image_key: str) -> Optional[int]:
    """Get image local ID from our key (date_taken_filename format)."""
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT f.id_local 
        FROM AgLibraryFile f
        JOIN Adobe_images img ON f.id_local = img.rootFile
        WHERE f.id_local = ?
    """, (int(image_key.split('_')[1]) if image_key.split('_')[1].isdigit() else 0,))
    
    row = cursor.fetchone()
    
    if not row:
        date_part = image_key.split('_')[0] if '_' in image_key else ''
        filename = image_key.split('_')[1] if '_' in image_key else image_key
        
        cursor.execute("""
            SELECT f.id_local 
            FROM AgLibraryFile f
            JOIN AgLibraryFolder fl ON f.folder = fl.id_local
            WHERE f.baseName = ?
        """, (filename,))
        row = cursor.fetchone()
    
    return row[0] if row else None


def image_has_keyword(conn: sqlite3.Connection, image_id: int, keyword_id: int) -> bool:
    """Check if image already has this keyword."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) FROM AgLibraryKeywordImage 
        WHERE image = ? AND tag = ?
    """, (image_id, keyword_id))
    return cursor.fetchone()[0] > 0


def add_keyword_to_image(conn: sqlite3.Connection, image_id: int, keyword_id: int) -> bool:
    """Add a keyword to an image.
    
    Returns:
        True if added, False if already existed
    """
    if image_has_keyword(conn, image_id, keyword_id):
        return False
    
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO AgLibraryKeywordImage (image, tag)
        VALUES (?, ?)
    """, (image_id, keyword_id))
    conn.commit()
    return True


def add_keyword_by_key(conn: sqlite3.Connection, image_key: str, keyword_name: str) -> bool:
    """Add keyword to image by our key format.
    
    Returns:
        True if added, False if already existed or error
    """
    image_id = get_image_local_id(conn, image_key)
    if not image_id:
        print(f"  Warning: Could not find image for key: {image_key}")
        return False
    
    keyword_id = get_or_create_keyword(conn, keyword_name)
    return add_keyword_to_image(conn, image_id, keyword_id)


def add_keyword_to_images_batch(conn: sqlite3.Connection, image_keys: list[str], 
                                keyword_name: str, dry_run: bool = False) -> dict:
    """Add keyword to multiple images.
    
    Returns:
        dict with 'added', 'skipped', 'errors' counts
    """
    result = {'added': 0, 'skipped': 0, 'errors': 0}
    
    keyword_id = get_or_create_keyword(conn, keyword_name)
    
    for image_key in image_keys:
        try:
            image_id = get_image_local_id(conn, image_key)
            if not image_id:
                result['errors'] += 1
                print(f"  Error: Image not found: {image_key}")
                continue
            
            if dry_run:
                if image_has_keyword(conn, image_id, keyword_id):
                    result['skipped'] += 1
                else:
                    result['added'] += 1
            else:
                if add_keyword_to_image(conn, image_id, keyword_id):
                    result['added'] += 1
                else:
                    result['skipped'] += 1
        except Exception as e:
            result['errors'] += 1
            print(f"  Error adding keyword to {image_key}: {e}")
    
    return result


if __name__ == "__main__":
    import sys
    from lightroom_tagger.config import load_config
    
    if len(sys.argv) < 3:
        print("Usage: python lr_writer.py <catalog_path> <keyword> [image_key]")
        sys.exit(1)
    
    catalog_path = sys.argv[1]
    keyword = sys.argv[2]
    image_key = sys.argv[3] if len(sys.argv) > 3 else None
    
    if not Path(catalog_path).exists():
        print(f"Error: Catalog not found: {catalog_path}")
        sys.exit(1)
    
    conn = connect_catalog(catalog_path)
    
    if image_key:
        success = add_keyword_by_key(conn, image_key, keyword)
        print(f"Keyword '{keyword}' {'added' if success else 'already exists'} for {image_key}")
    else:
        keyword_id = get_or_create_keyword(conn, keyword)
        print(f"Keyword '{keyword}' has ID: {keyword_id}")
        
        exists = keyword_exists(conn, keyword)
        print(f"Keyword exists: {exists}")
    
    conn.close()
