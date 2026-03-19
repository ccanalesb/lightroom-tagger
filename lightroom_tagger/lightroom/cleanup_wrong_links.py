# lightroom/cleanup_wrong_links.py
"""
One-time script to fix existing keyword-image links that used wrong IDs.

Run this ONCE after deploying the fix.
"""

import sqlite3
from pathlib import Path
import shutil
from datetime import datetime


def cleanup_wrong_keyword_links(catalog_path: str, dry_run: bool = True):
    """Fix keyword links that used AgLibraryFile.id_local instead of Adobe_images.id_local.
    
    Args:
        catalog_path: Path to .lrcat file
        dry_run: If True, just report what would be fixed
    """
    catalog = Path(catalog_path)
    if not catalog.exists():
        raise FileNotFoundError(f"Catalog not found: {catalog_path}")
    
    # Backup first
    if not dry_run:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = catalog.parent / f"{catalog.name}.backup-{timestamp}"
        shutil.copy2(catalog_path, backup_path)
        print(f"Backed up to: {backup_path}")
    
    conn = sqlite3.connect(catalog_path)
    conn.row_factory = sqlite3.Row
    
    cursor = conn.cursor()
    
    # Find wrong links: where AgLibraryKeywordImage.image matches AgLibraryFile.id_local
    # but NOT Adobe_images.id_local
    cursor.execute("""
        SELECT ki.id_local, ki.image as wrong_id, ki.tag,
               f.baseName, ai.id_local as correct_id
        FROM AgLibraryKeywordImage ki
        JOIN AgLibraryFile f ON ki.image = f.id_local
        JOIN Adobe_images ai ON ai.rootFile = f.id_local
    """)
    
    wrong_links = cursor.fetchall()
    print(f"Found {len(wrong_links)} links to check")
    
    if dry_run:
        for row in wrong_links[:10]:
            print(f"  Would fix: id={row['id_local']}, wrong_id={row['wrong_id']} -> correct_id={row['correct_id']} for {row['baseName']}")
        if len(wrong_links) > 10:
            print(f"  ... and {len(wrong_links) - 10} more")
        conn.close()
        return
    
    # Fix each link
    fixed = 0
    for row in wrong_links:
        cursor.execute(
            "UPDATE AgLibraryKeywordImage SET image = ? WHERE id_local = ?",
            (row['correct_id'], row['id_local'])
        )
        fixed += 1
    
    conn.commit()
    conn.close()
    
    print(f"Fixed {fixed} keyword-image links")
    print("NOTE: You must restart Lightroom to see the changes")


if __name__ == "__main__":
    import sys
    
    catalog = "/mnt/c/Users/cristian/Pictures/Lightroom/Lightroom Catalog.lrcat"
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--fix":
            dry_run = False
        else:
            catalog = sys.argv[1]
    
    print("=== Checking for wrong keyword links ===")
    print(f"Catalog: {catalog}")
    print()
    
    if "--fix" in sys.argv:
        print("=== APPLYING FIX ===")
        cleanup_wrong_keyword_links(catalog, dry_run=False)
    else:
        print("=== DRY RUN ===")
        cleanup_wrong_keyword_links(catalog, dry_run=True)
        print()
        print("Run with --fix to apply changes")