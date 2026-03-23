# Consolidate Instagram Import Scripts Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Merge `import_instagram_dump_enhanced.py` into `import_instagram_dump.py`, keeping visual deduplication but adding clearer step-by-step output style.

**Architecture:** Remove the redundant "enhanced" script and update the main script with better output formatting ("Step 1/2/3/4/5" style) while preserving all functionality (visual deduplication, skip-existing logic, image_hash storage, CLI flags).

**Tech Stack:** Python, argparse, TinyDB

---

## Background

We currently have two similar Instagram import scripts:
- `import_instagram_dump.py` (197 lines) - Has visual deduplication, skip-existing logic, image_hash storage
- `import_instagram_dump_enhanced.py` (146 lines) - Has clearer step-by-step output but NO visual deduplication

**The Problem:** We accidentally used the enhanced version which doesn't deduplicate, causing duplicates in the UI.

**The Solution:** Keep the main script (with all features) but improve its output style to match the enhanced version's clarity.

---

## Task 1: Update import_instagram_dump.py Output Style

**Files:**
- Modify: `lightroom_tagger/scripts/import_instagram_dump.py:74-164`

**Step 1: Update import_dump function signature and docstring**

Lines 56-70 currently:
```python
def import_dump(db, dump_path: str, skip_existing: bool = True, skip_dedup: bool = False) -> int:
    """Import all media files from Instagram dump into database with enhanced metadata.

    Prioritizes posts over archived_posts - if same media exists in both, use posts version
    but merge archived metadata (which has better EXIF data).

    Args:
        db: TinyDB instance
        dump_path: Path to instagram-dump directory
        skip_existing: If True, skip files already in database
        skip_dedup: If True, skip visual duplicate detection

    Returns:
        Number of new media files imported
    """
```

**Step 2: Update Step 1 output (Discover media files)**

Change lines 74-76 from:
```python
    # Discover all media files from filesystem
    media_files = discover_media_files(dump_path)
    print(f"Found {len(media_files)} media files in dump")
```

To:
```python
    # Step 1: Discover all media files from filesystem
    print("Step 1: Discovering media files...")
    media_files = discover_media_files(dump_path)
    print(f"  Found {len(media_files)} media files")
```

**Step 3: Update Step 2 output (Visual deduplication)**

Change lines 78-93 from:
```python
    # Visual deduplication: compute hashes and merge duplicates
    if skip_dedup:
        print("\nSkipping visual deduplication (--skip-dedup)")
        deduplicated_media = media_files
    else:
        print("\nComputing image hashes for visual duplicate detection...")
        media_with_hashes = compute_image_hashes(media_files)
        hash_groups = group_by_hash(media_with_hashes)
        print(f"Found {len(hash_groups)} unique visual hashes")

        # Select best versions and merge EXIF data
        print("Selecting best versions and merging EXIF data...")
        deduplicated_media = select_best_versions(hash_groups)
        duplicates_removed = len(media_files) - len(deduplicated_media)
        print(f"After visual deduplication: {len(deduplicated_media)} unique images")
        print(f" (Removed {duplicates_removed} visual duplicates)")
```

To:
```python
    # Step 2: Visual deduplication
    print("\nStep 2: Computing image hashes for visual duplicate detection...")
    if skip_dedup:
        print("  Skipping (--skip-dedup flag set)")
        deduplicated_media = media_files
    else:
        media_with_hashes = compute_image_hashes(media_files)
        hash_groups = group_by_hash(media_with_hashes)
        print(f"  Found {len(hash_groups)} unique visual hashes")
        
        print("  Selecting best versions and merging EXIF data...")
        deduplicated_media = select_best_versions(hash_groups)
        duplicates_removed = len(media_files) - len(deduplicated_media)
        print(f"  After deduplication: {len(deduplicated_media)} unique images")
        print(f"  (Removed {duplicates_removed} visual duplicates)")
```

**Step 4: Update Step 3 output (Parse JSON metadata)**

Change lines 95-108 from:
```python
    # Parse metadata from all JSON sources
    print("Parsing JSON metadata...")
    posts_metadata = parse_posts_metadata(dump_path)
    print(f" posts_1.json: {len(posts_metadata)} items")

    archived_metadata = parse_archived_posts_metadata(dump_path)
    print(f" archived_posts.json: {len(archived_metadata)} items")

    other_metadata = parse_other_content_metadata(dump_path)
    print(f" other_content.json: {len(other_metadata)} items")

    # Combine metadata (aggregative)
    combined_metadata = combine_metadata(posts_metadata, archived_metadata, other_metadata)
    print(f"Combined unique metadata: {len(combined_metadata)} items")
```

To:
```python
    # Step 3: Parse JSON metadata
    print("\nStep 3: Parsing JSON metadata...")
    posts_metadata = parse_posts_metadata(dump_path)
    print(f"  posts_1.json: {len(posts_metadata)} items")

    archived_metadata = parse_archived_posts_metadata(dump_path)
    print(f"  archived_posts.json: {len(archived_metadata)} items")

    other_metadata = parse_other_content_metadata(dump_path)
    print(f"  other_content.json: {len(other_metadata)} items")

    # Combine metadata (aggregative)
    combined_metadata = combine_metadata(posts_metadata, archived_metadata, other_metadata)
    print(f"  Combined unique metadata: {len(combined_metadata)} items")
```

**Step 5: Update Step 4 output (Extract URLs)**

Change lines 110-113 from:
```python
    # Extract URLs from saved/reposted content
    print("Extracting Instagram URLs...")
    url_lookup = parse_saved_and_reposted_urls(dump_path)
    print(f" Found {len(url_lookup)} URLs")
```

To:
```python
    # Step 4: Extract URLs from saved/reposted content
    print("\nStep 4: Extracting Instagram URLs...")
    url_lookup = parse_saved_and_reposted_urls(dump_path)
    print(f"  Found {len(url_lookup)} URLs")
```

**Step 6: Update Step 5 output (Import media)**

Change lines 115-158 from:
```python
    imported = 0
    skipped = 0
    with_exif = 0
    with_urls = 0

    for media in deduplicated_media:
        media_key = media['media_key']

        # Check if already exists
        if skip_existing:
            existing = get_instagram_dump_media(db, media_key)
            if existing:
                skipped += 1
                continue

        # Build base record from filesystem
        record = {
            'media_key': media_key,
            'file_path': media['file_path'],
            'filename': media['filename'],
            'date_folder': media['date_folder'],
            'image_hash': media.get('image_hash'),  # Store the visual hash
        }

        # Add metadata from JSON if available
        meta = combined_metadata.get(media_key, {})
        if meta:
            record.update(meta)
            if meta.get('exif_data'):
                with_exif += 1

        # Match URL by timestamp
        creation_ts = record.get('creation_timestamp')
        if creation_ts and creation_ts in url_lookup:
            record['post_url'] = url_lookup[creation_ts]
            with_urls += 1

        # Store
        store_instagram_dump_media(db, record)
        imported += 1

        if imported % 500 == 0:
            print(f" Imported {imported}...")

    print(f"\n✓ Import complete:")
    print(f" Imported: {imported} new media files")
    print(f" Skipped: {skipped} existing files")
    print(f" With EXIF data: {with_exif}")
    print(f" With URLs: {with_urls}")

    return imported
```

To:
```python
    # Step 5: Import media
    print("\nStep 5: Importing media...")
    imported = 0
    skipped = 0
    with_exif = 0
    with_urls = 0

    for media in deduplicated_media:
        media_key = media['media_key']

        # Check if already exists
        if skip_existing:
            existing = get_instagram_dump_media(db, media_key)
            if existing:
                skipped += 1
                continue

        # Build base record from filesystem
        record = {
            'media_key': media_key,
            'file_path': media['file_path'],
            'filename': media['filename'],
            'date_folder': media['date_folder'],
            'image_hash': media.get('image_hash'),  # Store the visual hash
        }

        # Add metadata from JSON if available
        meta = combined_metadata.get(media_key, {})
        if meta:
            record.update(meta)
            if meta.get('exif_data'):
                with_exif += 1

        # Match URL by timestamp
        creation_ts = record.get('creation_timestamp')
        if creation_ts and creation_ts in url_lookup:
            record['post_url'] = url_lookup[creation_ts]
            with_urls += 1

        # Store
        store_instagram_dump_media(db, record)
        imported += 1

        if imported % 500 == 0:
            print(f"  Imported {imported}...")

    print(f"\n✓ Import complete!")
    print(f"  Imported: {imported} new media files")
    print(f"  Skipped: {skipped} existing files")
    print(f"  With EXIF data: {with_exif}")
    print(f"  With URLs: {with_urls}")

    return imported
```

**Step 7: Test the updated script**

Run:
```bash
cd /home/cristian/lightroom_tagger
python3 -m lightroom_tagger.scripts.import_instagram_dump --dump-path /home/cristian/instagram-dump --db test_import.db --reimport 2>&1 | head -30
```

Expected output:
```
Step 1: Discovering media files...
  Found 492 media files

Step 2: Computing image hashes for visual duplicate detection...
  Found 455 unique visual hashes
  Selecting best versions and merging EXIF data...
  After deduplication: 455 unique images
  (Removed 37 visual duplicates)

Step 3: Parsing JSON metadata...
  posts_1.json: 215 items
  ...
```

**Step 8: Commit**

```bash
git add lightroom_tagger/scripts/import_instagram_dump.py
git commit -m "style: clearer step-by-step output for Instagram import"
```

---

## Task 2: Delete Redundant Enhanced Script

**Files:**
- Delete: `lightroom_tagger/scripts/import_instagram_dump_enhanced.py`

**Step 1: Remove the file**

```bash
rm /home/cristian/lightroom_tagger/lightroom_tagger/scripts/import_instagram_dump_enhanced.py
```

**Step 2: Verify it's gone**

```bash
ls /home/cristian/lightroom_tagger/lightroom_tagger/scripts/import_instagram_dump*.py
```

Expected: Only `import_instagram_dump.py` remains

**Step 3: Commit**

```bash
git add -A
git commit -m "chore: remove redundant import_instagram_dump_enhanced.py"
```

---

## Task 3: Check and Update Documentation

**Files:**
- Check: `README.md`
- Check: `docs/plans/2026-03-21-visual-deduplication.md`
- Check: `docs/plans/2026-03-21-visualizer-migration-to-dump.md`

**Step 1: Search for references to enhanced script**

```bash
grep -r "import_instagram_dump_enhanced" /home/cristian/lightroom_tagger --include="*.md" --include="*.py" --include="*.txt" 2>/dev/null
```

**Step 2: If any references found, update them**

Replace `import_instagram_dump_enhanced` with `import_instagram_dump`

**Step 3: Verify no broken references**

```bash
grep -r "import_instagram_dump_enhanced" /home/cristian/lightroom_tagger --include="*.md" --include="*.py" 2>/dev/null || echo "No references found - good!"
```

**Step 4: Commit if changes made**

```bash
git add -A
git commit -m "docs: remove references to deleted enhanced import script"
```

---

## Task 4: Re-import with Correct Script (Fix Duplicates)

**Files:**
- Modify: Database `library.db` (clear and reimport)

**Step 1: Clear existing Instagram data**

```python
from tinydb import TinyDB
db = TinyDB('/home/cristian/lightroom_tagger/library.db')
if 'instagram_dump_media' in db.tables():
    db.drop_table('instagram_dump_media')
print("Cleared instagram_dump_media table")
db.close()
```

**Step 2: Re-import with correct script**

```bash
cd /home/cristian/lightroom_tagger
python3 -m lightroom_tagger.scripts.import_instagram_dump \
    --dump-path /home/cristian/instagram-dump \
    --db library.db
```

Expected output:
```
Step 1: Discovering media files...
  Found 492 media files

Step 2: Computing image hashes for visual duplicate detection...
  Found 455 unique visual hashes
  Selecting best versions and merging EXIF data...
  After deduplication: 455 unique images
  (Removed 37 visual duplicates)

Step 3: Parsing JSON metadata...
  posts_1.json: 215 items
  archived_posts.json: 112 items
  other_content.json: 20 items
  Combined unique metadata: 347 items

Step 4: Extracting Instagram URLs...
  Found 142 URLs

Step 5: Importing media...
  Imported: 455 new media files
  Skipped: 0 existing files
  With EXIF data: 112
  With URLs: 0

✓ Import complete!
```

**Step 3: Verify database state**

```python
from tinydb import TinyDB
db = TinyDB('library.db')
print("Tables:", db.tables())
instagram = db.table('instagram_dump_media').all()
print(f"Instagram images: {len(instagram)}")
print(f"Images with image_hash: {len([i for i in instagram if i.get('image_hash')])}")
db.close()
```

Expected:
- Instagram images: 455 (not 492)
- Images with image_hash: 455

**Step 4: Verify no duplicates in UI**

Check that images like `202308/...989` and `202308/...0162` don't appear as duplicates.

---

## Summary

**Changes Made:**
1. ✅ Updated `import_instagram_dump.py` with clearer step-by-step output
2. ✅ Deleted redundant `import_instagram_dump_enhanced.py`
3. ✅ Updated documentation references
4. ✅ Re-imported data with visual deduplication (455 unique images, 37 duplicates removed)

**Files Modified:**
- `lightroom_tagger/scripts/import_instagram_dump.py` - Better output formatting
- `lightroom_tagger/scripts/import_instagram_dump_enhanced.py` - Deleted
- Documentation - Updated references

**Result:**
- Single import script with all features
- Clear step-by-step output
- No visual duplicates in database
- 455 unique Instagram images (down from 492)

---

**Plan complete and saved to:** `docs/plans/2026-03-23-consolidate-import-scripts.md`

**Two execution options:**

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
