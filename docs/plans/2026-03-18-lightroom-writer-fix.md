# Lightroom Writer Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix critical bugs in the Lightroom writer module to enable reliable keyword writing with proper safety checks.

**Architecture:** Add safety checks (WAL detection, backup), fix keyword lookup to handle NULL lc_name, fix keyword creation to set required fields, and remove invalid id_global from keyword-image link table.

**Tech Stack:** Python, SQLite, TinyDB, pytest

---

## Background: Schema Analysis

Analyzed actual Lightroom catalog at: `/mnt/c/Users/Cristian/Pictures/Lightroom/Lightroom Catalog.lrcat`

| Table | Actual Schema |
|-------|--------------|
| **AgLibraryKeyword** | Has `id_global`, but can be UUID or simple string. `lc_name` can be **NULL** (bug in existing keywords). `includeOnExport` defaults to 1. |
| **AgLibraryKeywordImage** | Only has: `id_local`, `image`, `tag`. **NO id_global column!** |
| **Image lookup** | `Adobe_images.rootFile → AgLibraryFile.id_local`, query by `baseName` works correctly. |

**Key finding:** The guide's suggestion to add `id_global` to `AgLibraryKeywordImage` is WRONG for this LR version - the column doesn't exist!

---

## Tasks

### Task 1: Add Safety Checks (WAL + Backup)

**Files:**
- Modify: `lightroom_tagger/lightroom/writer.py:1-20`

**Step 1: Write the failing test**

```python
# lightroom_tagger/lightroom/test_writer.py
import pytest
import sqlite3
from pathlib import Path

def test_writer_aborts_if_wal_exists(tmp_path):
    """Should raise error if Lightroom has catalog open (WAL exists)."""
    catalog = tmp_path / "test.lrcat"
    
    # Create minimal SQLite db with required table
    conn = sqlite3.connect(str(catalog))
    conn.execute("CREATE TABLE IF NOT EXISTS AgLibraryKeyword (id_local INTEGER PRIMARY KEY)")
    conn.close()
    
    # Create WAL file (simulating Lightroom open)
    wal = tmp_path / "test.lrcat-wal"
    wal.touch()
    
    # Import the function to test
    from lightroom_tagger.lightroom.writer import is_lightroom_open
    
    # Should detect WAL
    assert is_lightroom_open(str(catalog)) == True

def test_writer_allows_clean_catalog(tmp_path):
    """Should allow operation when no WAL file exists."""
    catalog = tmp_path / "test.lrcat"
    conn = sqlite3.connect(str(catalog))
    conn.execute("CREATE TABLE IF NOT EXISTS AgLibraryKeyword (id_local INTEGER PRIMARY KEY)")
    conn.close()
    
    from lightroom_tagger.lightroom.writer import is_lightroom_open
    
    assert is_lightroom_open(str(catalog)) == False
```

**Step 2: Run test to verify it fails**

```bash
cd /home/cristian/lightroom_tagger
python -m pytest lightroom_tagger/lightroom/test_writer.py::test_writer_aborts_if_wal_exists -v
```

Expected: FAIL with "AttributeError: module 'lightroom_tagger.lightroom.writer' has no attribute 'is_lightroom_open'"

**Step 3: Write minimal implementation**

```python
# Add to lightroom_tagger/lightroom/writer.py (top of file, after imports)
def is_lightroom_open(catalog_path: str) -> bool:
    """Check if Lightroom has the catalog open (WAL or SHM file exists).
    
    Lightroom uses Write-Ahead Logging. If these files exist, an active
    session is in progress and we should not write.
    """
    p = Path(catalog_path)
    wal_path = str(p) + "-wal"
    shm_path = str(p) + "-shm"
    return Path(wal_path).exists() or Path(shm_path).exists()


def check_catalog_safe(catalog_path: str) -> None:
    """Verify catalog is safe to write to.
    
    Raises:
        RuntimeError: If Lightroom is open (WAL exists)
    """
    if is_lightroom_open(catalog_path):
        raise RuntimeError(
            f"Lightroom appears to be open for '{catalog_path}'. "
            "Close Lightroom before writing to the catalog."
        )
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest lightroom_tagger/lightroom/test_writer.py::test_writer_aborts_if_wal_exists -v
```

Expected: PASS

**Step 5: Add backup test**

```python
def test_backup_created(tmp_path, monkeypatch):
    """Should create timestamped backup before writing."""
    catalog = tmp_path / "test.lrcat"
    conn = sqlite3.connect(str(catalog))
    conn.execute("CREATE TABLE AgLibraryKeyword (id_local INTEGER PRIMARY KEY)")
    conn.close()
    
    from lightroom_tagger.lightroom.writer import backup_catalog
    import time
    
    backup = backup_catalog(str(catalog))
    
    assert backup.exists()
    assert backup.name.startswith("test.lrcat.backup-")
```

**Step 6: Run test to verify it fails**

Expected: FAIL - function doesn't exist

**Step 7: Write backup implementation**

```python
def backup_catalog(catalog_path: str) -> Path:
    """Create timestamped backup of catalog before writing.
    
    Returns:
        Path to the backup file
    """
    from datetime import datetime
    import shutil
    
    p = Path(catalog_path)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = Path(str(p) + f".backup-{timestamp}")
    shutil.copy2(catalog_path, backup_path)
    return backup_path
```

**Step 8: Run tests to verify they pass**

```bash
python -m pytest lightroom_tagger/lightroom/test_writer.py::test_writer_aborts_if_wal_exists lightroom_tagger/lightroom/test_writer.py::test_backup_created -v
```

Expected: PASS

**Step 9: Commit**

```bash
git add lightroom_tagger/lightroom/writer.py lightroom_tagger/lightroom/test_writer.py
git commit -m "fix: add WAL check and backup safety to writer"
```

---

### Task 2: Fix Keyword Lookup (handle NULL lc_name)

**Files:**
- Modify: `lightroom_tagger/lightroom/writer.py:13-27`

**Step 1: Write the failing test**

```python
def test_keyword_lookup_handles_null_lc_name(tmp_path):
    """Should find keyword even if lc_name is NULL (existing buggy data)."""
    catalog = tmp_path / "test.lrcat"
    conn = sqlite3.connect(str(catalog))
    conn.execute("""
        CREATE TABLE AgLibraryKeyword (
            id_local INTEGER PRIMARY KEY,
            lc_name TEXT,
            name TEXT
        )
    """)
    # Insert keyword with NULL lc_name (like existing buggy data)
    conn.execute("INSERT INTO AgLibraryKeyword (lc_name, name) VALUES (NULL, 'MyKeyword')")
    conn.commit()
    
    from lightroom_tagger.lightroom.writer import get_keyword_id
    
    # Should find by name fallback
    assert get_keyword_id(conn, "MyKeyword") == 1
    assert get_keyword_id(conn, "mykeyword") == 1  # case insensitive
```

**Step 2: Run test to verify it fails**

Expected: FAIL - function may not handle NULL lc_name

**Step 3: Fix get_keyword_id implementation**

```python
def get_keyword_id(conn: sqlite3.Connection, keyword_name: str) -> Optional[int]:
    """Get keyword ID by name. Handles NULL lc_name by falling back to name.
    
    Args:
        conn: Database connection
        keyword_name: Keyword name (case-insensitive)
    
    Returns:
        Keyword ID or None if not found
    """
    cursor = conn.cursor()
    kw_lower = keyword_name.lower()
    
    # Try lc_name first (preferred)
    cursor.execute(
        "SELECT id_local FROM AgLibraryKeyword WHERE lc_name = ?",
        (kw_lower,)
    )
    row = cursor.fetchone()
    if row:
        return row[0]
    
    # Fallback: try name column if lc_name is NULL
    cursor.execute(
        "SELECT id_local FROM AgLibraryKeyword WHERE LOWER(name) = ?",
        (kw_lower,)
    )
    row = cursor.fetchone()
    return row[0] if row else None
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest lightroom_tagger/lightroom/test_writer.py::test_keyword_lookup_handles_null_lc_name -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add lightroom_tagger/lightroom/writer.py
git commit -m "fix: keyword lookup handles NULL lc_name fallback"
```

---

### Task 3: Fix Keyword Creation (set required fields)

**Files:**
- Modify: `lightroom_tagger/lightroom/writer.py:29-55`

**Step 1: Write the failing test**

```python
def test_create_keyword_sets_all_required_fields(tmp_path):
    """Keyword creation should set lc_name, id_global, includeOnExport."""
    catalog = tmp_path / "test.lrcat"
    conn = sqlite3.connect(str(catalog))
    conn.execute("""
        CREATE TABLE AgLibraryKeyword (
            id_local INTEGER PRIMARY KEY,
            id_global TEXT,
            lc_name TEXT,
            name TEXT,
            includeOnExport INTEGER,
            genealogy TEXT,
            hasChildren INTEGER,
            dateCreated TEXT,
            keywordType INTEGER
        )
    """)
    
    from lightroom_tagger.lightroom.writer import create_keyword
    
    kw_id = create_keyword(conn, "TestKeyword")
    
    # Verify all fields
    conn.execute("SELECT * FROM AgLibraryKeyword WHERE id_local = ?", (kw_id,))
    row = conn.fetchone()
    
    assert row['lc_name'] == 'testkeyword', f"lc_name should be lowercase, got {row['lc_name']}"
    assert row['name'] == 'TestKeyword'
    assert row['id_global'] == 'testkeyword', f"id_global should be keyword string, got {row['id_global']}"
    assert row['includeOnExport'] == 1
    assert row['hasChildren'] == 0
```

**Step 2: Run test to verify it fails**

Expected: FAIL - current implementation doesn't set all fields

**Step 3: Fix create_keyword implementation**

```python
def create_keyword(conn: sqlite3.Connection, keyword_name: str) -> int:
    """Create a new keyword in the catalog.
    
    Args:
        conn: Database connection
        keyword_name: Display name for the keyword
    
    Returns:
        Keyword ID
    
    Note:
        Lightroom stores lc_name (lowercase) separately from name (display).
        id_global can be a simple string (like "instagram", "posted") or UUID.
    """
    cursor = conn.cursor()
    kw_lower = keyword_name.lower()
    
    cursor.execute("""
        INSERT INTO AgLibraryKeyword 
        (id_global, lc_name, name, includeOnExport, genealogy, hasChildren, dateCreated, keywordType) 
        VALUES (?, ?, ?, 1, '', 0, datetime('now'), 0)""",
        (kw_lower, kw_lower, keyword_name)
    )
    conn.commit()
    return cursor.lastrowid
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest lightroom_tagger/lightroom/test_writer.py::test_create_keyword_sets_all_required_fields -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add lightroom_tagger/lightroom/writer.py
git commit -m "fix: keyword creation sets all required fields"
```

---

### Task 4: Fix Keyword Link (REMOVE id_global)

**Files:**
- Modify: `lightroom_tagger/lightroom/writer.py:102-117`

**Step 1: Write the failing test**

```python
def test_keyword_link_no_id_global_column(tmp_path):
    """AgLibraryKeywordImage has NO id_global column in this LR version."""
    catalog = tmp_path / "test.lrcat"
    conn = sqlite3.connect(str(catalog))
    
    # Create tables matching actual LR schema
    conn.execute("""
        CREATE TABLE AgLibraryKeyword (
            id_local INTEGER PRIMARY KEY,
            lc_name TEXT,
            name TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE AgLibraryKeywordImage (
            id_local INTEGER PRIMARY KEY,
            image INTEGER,
            tag INTEGER
        )
    """)
    conn.execute("INSERT INTO AgLibraryKeyword (lc_name, name) VALUES ('posted', 'Posted')")
    conn.commit()
    
    from lightroom_tagger.lightroom.writer import add_keyword_to_image
    
    # This should work without id_global
    result = add_keyword_to_image(conn, image_id=1, keyword_id=1)
    
    assert result == True
    
    # Verify it was added
    conn.execute("SELECT * FROM AgLibraryKeywordImage WHERE image = 1")
    row = conn.fetchone()
    assert row is not None
    assert row['image'] == 1
    assert row['tag'] == 1
```

**Step 2: Run test to verify it fails**

Expected: FAIL - current code tries to insert id_global

**Step 3: Fix add_keyword_to_image implementation**

```python
def add_keyword_to_image(conn: sqlite3.Connection, image_id: int, keyword_id: int) -> bool:
    """Add a keyword to an image.
    
    Args:
        conn: Database connection
        image_id: Adobe_images.id_local
        keyword_id: AgLibraryKeyword.id_local
    
    Returns:
        True if added, False if already existed
    """
    if image_has_keyword(conn, image_id, keyword_id):
        return False
    
    cursor = conn.cursor()
    # Note: AgLibraryKeywordImage does NOT have id_global in this LR version
    cursor.execute("""
        INSERT INTO AgLibraryKeywordImage (image, tag)
        VALUES (?, ?)
    """, (image_id, keyword_id))
    conn.commit()
    return True
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest lightroom_tagger/lightroom/test_writer.py::test_keyword_link_no_id_global_column -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add lightroom_tagger/lightroom/writer.py
git commit -m "fix: remove id_global from keyword link (column doesn't exist)"
```

---

### Task 5: Integrate Safety Checks into Batch Function

**Files:**
- Modify: `lightroom_tagger/lightroom/writer.py:135-169`

**Step 1: Write the failing test**

```python
def test_batch_write_calls_safety_check(tmp_path, monkeypatch):
    """Should check WAL and create backup before batch write."""
    catalog = tmp_path / "test.lrcat"
    
    # Create minimal db
    conn = sqlite3.connect(str(catalog))
    conn.execute("""
        CREATE TABLE AgLibraryKeyword (
            id_local INTEGER PRIMARY KEY,
            lc_name TEXT,
            name TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE AgLibraryFile (
            id_local INTEGER PRIMARY KEY,
            baseName TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE Adobe_images (
            id_local INTEGER PRIMARY KEY,
            rootFile INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE AgLibraryKeywordImage (
            id_local INTEGER PRIMARY KEY,
            image INTEGER,
            tag INTEGER
        )
    """)
    conn.execute("INSERT INTO AgLibraryFile (id_local, baseName) VALUES (1, 'L1007324')")
    conn.execute("INSERT INTO Adobe_images (id_local, rootFile) VALUES (100, 1)")
    conn.commit()
    conn.close()
    
    safety_called = []
    backup_called = []
    
    def mock_check_safe(path):
        safety_called.append(path)
    
    def mock_backup(path):
        backup_called.append(path)
        return Path(path + ".backup")
    
    monkeypatch.setattr("lightroom_tagger.lightroom.writer.check_catalog_safe", mock_check_safe)
    monkeypatch.setattr("lightroom_tagger.lightroom.writer.backup_catalog", mock_backup)
    
    from lightroom_tagger.lightroom.writer import add_keyword_to_images_batch
    
    add_keyword_to_images_batch(str(catalog), ["2026-01-01_L1007324"], "newkeyword", dry_run=False)
    
    assert len(safety_called) == 1, "Should call safety check"
    assert len(backup_called) == 1, "Should create backup"
```

**Step 2: Run test to verify it fails**

Expected: FAIL - safety checks not integrated

**Step 3: Update add_keyword_to_images_batch**

```python
def add_keyword_to_images_batch(conn: sqlite3.Connection, image_keys: list[str], 
                                keyword_name: str, dry_run: bool = False,
                                catalog_path: str = None) -> dict:
    """Add keyword to multiple images.
    
    Args:
        conn: TinyDB connection
        image_keys: List of image keys (date_taken_filename format)
        keyword_name: Keyword to apply
        dry_run: If True, just simulate without writing
        catalog_path: Path to .lrcat file (required for safety checks)
    
    Returns:
        dict with 'added', 'skipped', 'errors' counts
    """
    # Safety checks
    if catalog_path:
        check_catalog_safe(catalog_path)
        if not dry_run:
            backup_catalog(catalog_path)
    
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
```

**Step 4: Update CLI to pass catalog_path**

```python
# In core/cli.py around line 700
result = add_keyword_to_images_batch(
    db, 
    matched_keys, 
    keyword, 
    dry_run=dry_run,
    catalog_path=catalog_path  # NEW: pass for safety checks
)
```

**Step 5: Run test to verify it passes**

```bash
python -m pytest lightroom_tagger/lightroom/test_writer.py::test_batch_write_calls_safety_check -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add lightroom_tagger/lightroom/writer.py core/cli.py
git commit -m "fix: integrate safety checks into batch keyword write"
```

---

### Task 6: Run Full Test Suite

**Step 1: Run all writer tests**

```bash
python -m pytest lightroom_tagger/lightroom/test_writer.py -v
```

Expected: All PASS

**Step 2: Run full test suite**

```bash
python -m pytest -v --tb=short 2>&1 | head -100
```

Expected: No regressions

**Step 3: Commit**

```bash
git add -A
git commit -m "test: all writer tests passing"
```

---

## Summary

After this plan, the writer will:

1. **Check for open Lightroom** - Abort if WAL file exists
2. **Backup catalog** - Create timestamped backup before any write
3. **Find keywords correctly** - Handle NULL lc_name with fallback to name
4. **Create keywords properly** - Set lc_name, id_global, includeOnExport
5. **Link keywords without id_global** - Matches actual LR schema

---

## Plan Complete

**Plan saved to:** `docs/plans/2026-03-18-lightroom-writer-fix.md`

**Two execution options:**

1. **Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

2. **Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?
