import logging
import shutil
import sqlite3
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

KeywordAddResult = Literal["added", "already_present", "image_not_found"]
KeywordRemoveResult = Literal["removed", "not_present", "image_not_found"]

CULL_KEYWORD = "lrt-cull"

# One backup per day of activity. See backup_catalog_if_needed.
BACKUP_MIN_INTERVAL_SECONDS = 24 * 60 * 60


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


def backup_catalog_if_needed(
    catalog_path: str,
    *,
    max_backups: int = 2,
    min_interval_seconds: float = BACKUP_MIN_INTERVAL_SECONDS,
) -> str:
    """Copy the catalog aside before writing to it, at most once per interval.

    The per-click copy this function used to do was actively harmful: with
    ``max_backups = 2`` the second write evicts the only snapshot that
    predates every write we made, so backing up more often leaves *less*
    to recover from. A real catalog here is 3 GB, so it also cost ~3 s and
    6 GB of disk per toggle. When a backup younger than
    ``min_interval_seconds`` already exists, that one is reused and nothing
    is copied; its path is returned either way.
    """
    cat = Path(catalog_path)
    parent = cat.parent
    pattern = f"{cat.name}.backup-*"
    if min_interval_seconds > 0:
        existing = sorted(parent.glob(pattern), key=lambda x: x.stat().st_mtime)
        if existing:
            newest = existing[-1]
            age = time.time() - newest.stat().st_mtime
            if age < min_interval_seconds:
                logger.info(
                    "Catalog backup %s is %.0fs old; reusing it.", newest, age
                )
                return str(newest)
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


def add_keyword_by_key(
    conn: sqlite3.Connection, image_key: str, keyword_name: str
) -> KeywordAddResult:
    """Add keyword to image by our key format."""
    image_id = get_image_local_id(conn, image_key)
    if not image_id:
        return "image_not_found"

    keyword_id = get_or_create_keyword(conn, keyword_name)
    if add_keyword_to_image(conn, image_id, keyword_id):
        return "added"
    return "already_present"


def remove_keyword_from_image(
    conn: sqlite3.Connection, image_id: int, keyword_id: int
) -> bool:
    """Remove a keyword link from an image.

    Returns:
        True if a link was removed, False if the image did not have the keyword.
    """
    if not image_has_keyword(conn, image_id, keyword_id):
        return False

    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM AgLibraryKeywordImage WHERE image = ? AND tag = ?",
        (image_id, keyword_id),
    )
    conn.commit()
    return True


def remove_keyword_by_key(
    conn: sqlite3.Connection, image_key: str, keyword_name: str
) -> KeywordRemoveResult:
    """Remove keyword from image by our key format.

    Leaves the keyword row in the catalog when the last image loses it.
    """
    image_id = get_image_local_id(conn, image_key)
    if not image_id:
        return "image_not_found"

    keyword_id = get_keyword_id(conn, keyword_name)
    if not keyword_id:
        return "not_present"

    if remove_keyword_from_image(conn, image_id, keyword_id):
        return "removed"
    return "not_present"


def image_has_keyword_by_key(
    conn: sqlite3.Connection, image_key: str, keyword_name: str
) -> bool:
    """Return whether the catalog image currently carries ``keyword_name``."""
    image_id = get_image_local_id(conn, image_key)
    if not image_id:
        return False
    keyword_id = get_keyword_id(conn, keyword_name)
    if not keyword_id:
        return False
    return image_has_keyword(conn, image_id, keyword_id)


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
                logger.warning("Image not found for keyword batch add: %s", image_key)
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
            logger.warning("Error adding keyword to %s: %s", image_key, e)

    return result


if __name__ == "__main__":
    import sys


    if len(sys.argv) < 3:
        print("Usage: python -m lightroom_tagger.lightroom.writer <catalog_path> <keyword> [image_key]")
        sys.exit(1)

    catalog_path = sys.argv[1]
    keyword = sys.argv[2]
    image_key = sys.argv[3] if len(sys.argv) > 3 else None

    if not Path(catalog_path).exists():
        print(f"Error: Catalog not found: {catalog_path}")
        sys.exit(1)

    conn = connect_catalog(catalog_path)

    if image_key:
        outcome = add_keyword_by_key(conn, image_key, keyword)
        if outcome == "added":
            print(f"Keyword '{keyword}' added for {image_key}")
        elif outcome == "already_present":
            print(f"Keyword '{keyword}' already present for {image_key}")
        else:
            print(f"Image not found for key: {image_key}")
    else:
        keyword_id = get_or_create_keyword(conn, keyword)
        print(f"Keyword '{keyword}' has ID: {keyword_id}")

        exists = keyword_exists(conn, keyword)
        print(f"Keyword exists: {exists}")

    conn.close()
