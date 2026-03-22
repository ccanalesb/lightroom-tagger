# Visual Duplicate Detection and Deduplication Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement visual duplicate detection for Instagram dump import to merge archived posts into posts, keeping only unique images based on perceptual hash.

**Architecture:** Compute pHash for all images during import, group by hash, prioritize posts over archived, merge EXIF data from archived into posts, and store only unique images.

**Tech Stack:** Python, PIL, imagehash, TinyDB

---

## Background

The Instagram dump contains visually identical photos in both `posts/` and `archived_posts/` folders. For example:
- `posts/202307/17889019142800763.jpg` (hash: bc363e6cc2c1c3c9)
- `archived_posts/202307/17854200000003279.jpg` (hash: bc363e6cc2c1c3c9)
- `archived_posts/202307/17992177534951530.jpg` (hash: bc363e6cc2c1c3c9)

These 3 files are visually identical but currently imported as 3 separate records.

**Deduplication Rules:**
1. When same photo exists in posts and archived → keep posts, skip archived
2. When same photo exists only in archived (multiple copies) → keep ONE best EXIF, skip others
3. When photo only in archived (single) → keep it
4. Merge EXIF data from archived into posts version

---

## Task 1: Add Image Hash Storage to Database

**Files:**
- Modify: `lightroom_tagger/core/database.py`

**Step 1: Update store_instagram_dump_media to support image_hash**

Add `image_hash` field to the record defaults in `store_instagram_dump_media` function around line 180.

**Step 2: Add function to find duplicates by hash**

Create new function `get_media_by_hash(db, image_hash)` that queries instagram_dump_media table by image_hash.

**Step 3: Write test**

Create test in `lightroom_tagger/core/test_database.py`:
- Test storing media with image_hash
- Test retrieving by hash

**Step 4: Run test**

```bash
python3 -m pytest lightroom_tagger/core/test_database.py::TestInstagramDumpMedia -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add lightroom_tagger/core/database.py lightroom_tagger/core/test_database.py
git commit -m "feat: add image_hash field to instagram_dump_media"
```

---

## Task 2: Add Visual Duplicate Detection to Import Script

**Files:**
- Modify: `lightroom_tagger/scripts/import_instagram_dump.py`
- Create: `lightroom_tagger/instagram/deduplicator.py`

**Step 1: Create deduplicator module**

Create `lightroom_tagger/instagram/deduplicator.py` with functions:
- `compute_image_hashes(media_files)` - computes pHash for each file
- `group_by_hash(media_files_with_hashes)` - groups files by hash value
- `select_best_version(hash_group)` - selects posts over archived
- `merge_exif_data(best_version, duplicates)` - merges EXIF from all duplicates

**Step 2: Write tests for deduplicator**

Create `lightroom_tagger/instagram/test_deduplicator.py`:
- Test hash computation
- Test grouping by hash
- Test selection logic (posts > archived)
- Test EXIF merging

**Step 3: Run tests**

```bash
python3 -m pytest lightroom_tagger/instagram/test_deduplicator.py -v
```
Expected: PASS

**Step 4: Commit**

```bash
git add lightroom_tagger/instagram/deduplicator.py lightroom_tagger/instagram/test_deduplicator.py
git commit -m "feat: add visual duplicate detection module"
```

---

## Task 3: Integrate Deduplication into Import Script

**Files:**
- Modify: `lightroom_tagger/scripts/import_instagram_dump.py`

**Step 1: Import deduplicator module**

Add import at top of file:
```python
from lightroom_tagger.instagram.deduplicator import (
    compute_image_hashes,
    group_by_hash,
    select_best_versions,
    merge_exif_data
)
```

**Step 2: Add deduplication step before import**

After `discover_media_files()`, add:
```python
# Compute hashes and deduplicate
print("Computing image hashes for duplicate detection...")
media_with_hashes = compute_image_hashes(media_files)
hash_groups = group_by_hash(media_with_hashes)
print(f"Found {len(hash_groups)} unique images from {len(media_files)} files")

# Select best versions and merge EXIF
print("Deduplicating...")
deduplicated_media = select_best_versions(hash_groups)
print(f"After deduplication: {len(deduplicated_media)} unique images")
```

**Step 3: Update import loop to use deduplicated list**

Change `for media in media_files:` to `for media in deduplicated_media:`

**Step 4: Store image_hash in database**

Add `image_hash` to the record being stored.

**Step 5: Run integration test**

```bash
rm -f test_dedup.db
python3 -m lightroom_tagger.scripts.import_instagram_dump --dump-path /home/cristian/instagram-dump --db test_dedup.db
```

Expected output:
```
Found 660 media files in dump
Computing image hashes for duplicate detection...
Found 500 unique images from 660 files
Deduplication...
After deduplication: 500 unique images
```

**Step 6: Commit**

```bash
git add lightroom_tagger/scripts/import_instagram_dump.py
git commit -m "feat: integrate visual deduplication into import"
```

---

## Task 4: Add CLI Option to Skip Deduplication (Optional)

**Files:**
- Modify: `lightroom_tagger/scripts/import_instagram_dump.py`

**Step 1: Add --skip-dedup argument**

Add to argparse:
```python
parser.add_argument('--skip-dedup', action='store_true',
                   help='Skip visual duplicate detection')
```

**Step 2: Conditionally run deduplication**

```python
if not args.skip_dedup:
    # Run deduplication
else:
    deduplicated_media = media_files
```

**Step 3: Commit**

```bash
git add lightroom_tagger/scripts/import_instagram_dump.py
git commit -m "feat: add --skip-dedup flag for import"
```

---

## Task 5: Rebuild Library Database with Deduplication

**Step 1: Backup old database**

```bash
cp library.db library.db.backup.pre-dedup
```

**Step 2: Reset database**

```bash
rm library.db
python3 -c "
from lightroom_tagger.core.database import init_database, init_instagram_dump_table
db = init_database('library.db')
init_instagram_dump_table(db)
db.close()
print('Database recreated')
"
```

**Step 3: Re-import with deduplication**

```bash
python3 -m lightroom_tagger.scripts.import_instagram_dump --dump-path /home/cristian/instagram-dump --db library.db
```

Expected:
- Before: 660 files
- After: ~500 unique images (160 duplicates removed)

**Step 4: Verify results**

```bash
python3 -c "
from tinydb import TinyDB
db = TinyDB('library.db')
media = db.table('instagram_dump_media').all()
print(f'Total media: {len(media)}')

# Count with hashes
with_hash = [m for m in media if m.get('image_hash')]
print(f'With image_hash: {len(with_hash)}')

# Check 202307
print('\\n202307 files:')
for m in media:
    if '202307' in m['media_key']:
        print(f\"  {m['media_key']} - {m['file_path']}\")
db.close()
"
```

Expected: Only 1 file for 202307 (the posts version)

**Step 5: Restart servers**

```bash
tmux send-keys -t visualizer:backend C-c
tmux send-keys -t visualizer:backend "cd apps/visualizer/backend && python3 app.py" Enter
```

**Step 6: Verify in browser**

Visit: http://localhost:5173/instagram

Expected: 202307 shows only 1 image, not 7

**Step 7: Commit changes**

```bash
git add -A
git commit -m "feat: rebuild library with visual deduplication"
```

---

## Task 6: Update API to Return image_hash (Optional)

**Files:**
- Modify: `apps/visualizer/backend/api/images.py`

**Step 1: Add image_hash to response**

In `list_instagram_images()`, add to enriched_images:
```python
'image_hash': media.get('image_hash'),
```

**Step 2: Update TypeScript types**

In `apps/visualizer/frontend/src/services/api.ts`, add to InstagramImage interface:
```typescript
image_hash?: string
```

**Step 3: Test API**

```bash
curl -s "http://localhost:5000/api/images/instagram?limit=1" | python3 -m json.tool
```

Should show `image_hash` field

**Step 4: Commit**

```bash
git add apps/visualizer/backend/api/images.py apps/visualizer/frontend/src/services/api.ts
git commit -m "feat: expose image_hash in API"
```

---

## Summary

**Files Modified:**
1. `lightroom_tagger/core/database.py` - Add image_hash field
2. `lightroom_tagger/core/test_database.py` - Tests for image_hash
3. `lightroom_tagger/instagram/deduplicator.py` - NEW: Visual duplicate detection
4. `lightroom_tagger/instagram/test_deduplicator.py` - NEW: Tests for deduplication
5. `lightroom_tagger/scripts/import_instagram_dump.py` - Integrate deduplication
6. `apps/visualizer/backend/api/images.py` - Expose image_hash (optional)
7. `apps/visualizer/frontend/src/services/api.ts` - TypeScript types (optional)

**Expected Results:**
- Before: 660 files (with duplicates)
- After: ~500 files (unique images only)
- EXIF data: Merged from archived into posts
- 202307: Reduced from 7 files to 1 file

**Testing:**
- All existing tests pass
- New tests for deduplication pass
- Visual verification in browser

---

**Plan complete and saved to:** `docs/plans/2026-03-21-visual-deduplication.md`

**Two execution options:**

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
