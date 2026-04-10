import logging
import shutil
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def _catalog_lock_candidates(catalog_path: str) -> list[Path]:
    p = Path(catalog_path)
    return [
        p.parent / f"{p.stem}.lrcat-lock",
        p.parent / f"{p.name}.lock",
    ]


def raise_if_catalog_locked(catalog_path: str) -> None:
    for path in _catalog_lock_candidates(catalog_path):
        if path.exists() and (path.is_file() or path.is_dir()):
            raise RuntimeError("Close Lightroom before writing to catalog.")
    return None


# Backups run once per write call (update_lightroom_from_matches runs once per job invocation).
def backup_catalog_if_needed(catalog_path: str, *, max_backups: int = 2) -> str:
    cat = Path(catalog_path)
    parent = cat.parent
    pattern = f"{cat.name}.backup-*"
    while True:
        existing = sorted(parent.glob(pattern), key=lambda x: x.stat().st_mtime)
        if len(existing) < max_backups:
            break
        existing[0].unlink(missing_ok=True)
    ts = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    dest = parent / f"{cat.name}.backup-{ts}"
    shutil.copy2(catalog_path, dest)
    logger.info("Catalog backup created: %s", dest)
    return str(dest)


def connect_catalog(catalog_path: str) -> sqlite3.Connection:
    """Connect to Lightroom catalog."""
    conn = sqlite3.connect(catalog_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_keyword_id(conn: sqlite3.Connection, keyword_name: str) -> int | None:
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
    # Generate a proper UUID for id_global
    new_uuid = uuid.uuid4().hex.upper()  # 32-char hex without dashes, matches Lightroom format
    cursor.execute(
        """INSERT INTO AgLibraryKeyword
           (id_global, name, lc_name, dateCreated, keywordType)
           VALUES (?, ?, ?, datetime('now'), 0)""",
        (new_uuid, keyword_name, keyword_name.lower())
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


def get_image_local_id(conn: sqlite3.Connection, image_key: str) -> int | None:
    """Get Adobe_images.id_local from our key (date_taken_filename format).

    NOTE: AgLibraryKeywordImage.image references Adobe_images.id_local,
    NOT AgLibraryFile.id_local. We must join to get the correct ID.

    Args:
        conn: Database connection
        image_key: Key in format "YYYY-MM-DD_filename.ext" or just "filename.ext"

    Returns:
        Adobe_images.id_local or None if not found
    """
    cursor = conn.cursor()

    # Extract filename - handle formats like "2026-01-15_L1007168.JPG" or "L1007168.DNG"
    filename = image_key
    if '_' in image_key:
        filename = image_key.split('_', 1)[1]
    # Remove extension to get baseName
    if '.' in filename:
        filename = filename.rsplit('.', 1)[0]

    # CRITICAL FIX: Join AgLibraryFile -> Adobe_images to get correct ID
    # AgLibraryKeywordImage.image references Adobe_images.id_local, not file ID
    cursor.execute("""
        SELECT ai.id_local
        FROM AgLibraryFile f
        JOIN Adobe_images ai ON ai.rootFile = f.id_local
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
                print(f" Error: Image not found: {image_key}")
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
            print(f" Error adding keyword to {image_key}: {e}")

    return result


def update_lightroom_from_matches(catalog_path: str, matches: list) -> dict:
    """Add 'Posted' keyword to matched catalog images.

    Args:
        catalog_path: Path to Lightroom catalog
        matches: List of match dicts with 'catalog_key' field

    Returns:
        dict with 'success', 'failed' counts
    """
    stats = {'success': 0, 'failed': 0}

    if not matches:
        return stats

    conn = connect_catalog(catalog_path)
    keyword_id = get_or_create_keyword(conn, "Posted")

    for match in matches:
        catalog_key = match.get('catalog_key')
        if not catalog_key:
            continue

        image_id = get_image_local_id(conn, catalog_key)
        if image_id and add_keyword_to_image(conn, image_id, keyword_id):
            stats['success'] += 1
        else:
            stats['failed'] += 1

    conn.commit()
    conn.close()
    return stats


if __name__ == "__main__":
    import sys


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
