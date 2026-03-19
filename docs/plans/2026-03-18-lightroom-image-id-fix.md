# Lightroom Image ID Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix `get_image_local_id()` to return Adobe_images.id_local instead of AgLibraryFile.id_local, enabling Lightroom to see keyword-photo links.

**Architecture:** The current implementation queries `AgLibraryFile` directly, returning file IDs. Lightroom's `AgLibraryKeywordImage.image` column references `Adobe_images.id_local`, not file IDs. We must join `AgLibraryFile` → `Adobe_images` via `rootFile` to get the correct image ID.

**Tech Stack:** Python, SQLite, pytest

---

## Background: The Bug

**Evidence from actual catalog:**

```sql
-- Current links (WRONG):
AgLibraryKeywordImage.image = 5648  (file ID)
-- Lightroom can't find image with id_local=5648 in Adobe_images

-- Correct links should be:
AgLibraryKeywordImage.image = 3733   (image ID)
-- Via: Adobe_images.id_local = 3733, rootFile = 5648
```

**Table relationships:**
```
AgLibraryFile.id_local = 5648 (file "R0000034")
          ↓
Adobe_images.rootFile = 5648
Adobe_images.id_local = 3733 (the ACTUAL image ID)
          ↓
AgLibraryKeywordImage.image = 3733 (should reference this)
AgLibraryKeywordImage.tag = 262 (keyword ID)
```

---

## Tasks

### Task 1: Add Test for Correct Image ID Resolution

**Files:**
- Modify: `lightroom/test_writer.py`

**Step 1: Write the failing test**

```python
# Add to lightroom/test_writer.py

def test_get_image_local_id_returns_adobe_image_id(tmp_path):
    """Should return Adobe_images.id_local, NOT AgLibraryFile.id_local."""
    import sqlite3
    from lightroom_tagger.lightroom.writer import get_image_local_id
    
    catalog = tmp_path / "test.lrcat"
    conn = sqlite3.connect(str(catalog))
    
    # Create schema matching actual Lightroom
    conn.execute("""
        CREATE TABLE AgLibraryFile (
            id_local INTEGER PRIMARY KEY,
            baseName TEXT,
            extension TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE Adobe_images (
            id_local INTEGER PRIMARY KEY,
            rootFile INTEGER
        )
    """)
    
    # Insert test data
    # File ID 5648, image ID 3733 (like real data)
    conn.execute("INSERT INTO AgLibraryFile (id_local, baseName, extension) VALUES (5648, 'R0000034', 'JPG')")
    conn.execute("INSERT INTO Adobe_images (id_local, rootFile) VALUES (3733, 5648)")
    conn.commit()
    
    # Test: should return IMAGE id (3733), not FILE id (5648)
    result = get_image_local_id(conn, "2026-01-15_R0000034.JPG")
    
    assert result == 3733, f"Expected Adobe_images.id_local (3733), got {result}"
    
    conn.close()


def test_get_image_local_id_with_dng(tmp_path):
    """Should correctly resolve DNG files to Adobe_images."""
    import sqlite3
    from lightroom_tagger.lightroom.writer import get_image_local_id
    
    catalog = tmp_path / "test.lrcat"
    conn = sqlite3.connect(str(catalog))
    
    conn.execute("""
        CREATE TABLE AgLibraryFile (
            id_local INTEGER PRIMARY KEY,
            baseName TEXT,
            extension TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE Adobe_images (
            id_local INTEGER PRIMARY KEY,
            rootFile INTEGER
        )
    """)
    
    # File ID 303, image ID 265
    conn.execute("INSERT INTO AgLibraryFile (id_local, baseName, extension) VALUES (303, 'L1007324', 'DNG')")
    conn.execute("INSERT INTO Adobe_images (id_local, rootFile) VALUES (265, 303)")
    conn.commit()
    
    result = get_image_local_id(conn, "L1007324.DNG")
    
    assert result == 265, f"Expected Adobe_images.id_local (265), got {result}"
    
    conn.close()


def test_get_image_local_id_not_found_returns_none(tmp_path):
    """Should return None if image not found."""
    import sqlite3
    from lightroom_tagger.lightroom.writer import get_image_local_id
    
    catalog = tmp_path / "test.lrcat"
    conn = sqlite3.connect(str(catalog))
    
    conn.execute("""
        CREATE TABLE AgLibraryFile (
            id_local INTEGER PRIMARY KEY,
            baseName TEXT,
            extension TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE Adobe_images (
            id_local INTEGER PRIMARY KEY,
            rootFile INTEGER
        )
    """)
    conn.commit()
    
    result = get_image_local_id(conn, "NonExistent.DNG")
    
    assert result is None
    
    conn.close()
```

**Step 2: Run test to verify it fails**

```bash
cd /home/cristian/lightroom_tagger
python3 -m pytest lightroom/test_writer.py::test_get_image_local_id_returns_adobe_image_id -v
```

Expected: FAIL - returns file ID (5648) instead of image ID (3733)

**Step 3: Write minimal implementation**

```python
# Modify lightroom/writer.py get_image_local_id function

def get_image_local_id(conn: sqlite3.Connection, image_key: str) -> Optional[int]:
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
```

**Step 4: Run test to verify it passes**

```bash
cd /home/cristian/lightroom_tagger
python3 -m pytest lightroom/test_writer.py::test_get_image_local_id_returns_adobe_image_id lightroom/test_writer.py::test_get_image_local_id_with_dng lightroom/test_writer.py::test_get_image_local_id_not_found_returns_none -v
```

Expected: All PASS

**Step 5: Commit**

```bash
cd /home/cristian/lightroom_tagger
git add lightroom/writer.py lightroom/test_writer.py
git commit -m "fix: get_image_local_id returns Adobe_images.id_local instead of file ID"
```

---

### Task 2: Check and Fix Duplicate Files

**Files:**
- Check: `lightroom_tagger/lightroom/writer.py` (the nested copy)
- Check: `lr_writer.py` (if exists)

**Step 1: Check for duplicate files**

```bash
cd /home/cristian/lightroom_tagger
find . -name "writer.py" -path "*/lightroom/*"
find . -name "lr_writer.py"
```

**Step 2: Apply same fix to any duplicates**

If duplicates exist, apply the same fix to all of them.

---

### Task 3: Create Cleanup Script for Existing Wrong Links

**Files:**
- Create: `lightroom/cleanup_wrong_links.py`

**Step 1: Create cleanup script**

```python
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
```

**Step 2: Test dry run**

```bash
cd /home/cristian
PYTHONPATH=/home/cristian python3 -c "
from lightroom_tagger.lightroom.cleanup_wrong_links import cleanup_wrong_keyword_links
cleanup_wrong_keyword_links('/mnt/c/Users/cristian/Pictures/Lightroom/Lightroom Catalog.lrcat', dry_run=True)
"
```

---

### Task 4: Run Full Test Suite

**Step 1: Run all tests**

```bash
cd /home/cristian/lightroom_tagger
python3 -m pytest --tb=short -q
```

Expected: All PASS

**Step 2: Commit cleanup script**

```bash
git add lightroom/cleanup_wrong_links.py
git commit -m "feat: add cleanup script for wrong keyword links"
```

---

## Summary

After this plan:

1. **Correct ID resolution** - `get_image_local_id()` returns Adobe_images.id_local
2. **New tests** - Verify image ID resolution works for JPG/DNG/not-found
3. **Cleanup script** - Fix existing wrong links in catalog