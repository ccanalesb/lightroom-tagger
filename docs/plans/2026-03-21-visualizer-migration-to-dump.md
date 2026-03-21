# Visualizer Migration to Instagram Dump Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Update the visualizer to use `instagram_dump_media` table instead of the old `instagram_images` table, fixing thumbnails, stats, dashboard, and image cards.

**Architecture:** Replace all references to `instagram_images` with `instagram_dump_media`, adapting field names and handling missing fields (like `post_url`) gracefully.

**Tech Stack:** Flask, TinyDB, Python, React, TypeScript

---

## Background

The visualizer was built for the old web scraper which stored data in `instagram_images` table. We've now imported the Instagram data dump into `instagram_dump_media` table (1,768 records). The visualizer needs migration.

**Field Mapping:**
- `instagram_images.key` → `instagram_dump_media.media_key`
- `instagram_images.local_path` → `instagram_dump_media.file_path`
- `instagram_images.filename` → `instagram_dump_media.filename`
- `instagram_images.description` → `instagram_dump_media.caption`
- `instagram_images.instagram_folder` → `instagram_dump_media.date_folder`
- `instagram_images.post_url` → **MISSING** - Need to extract from posts_1.json (each post has `cross_post_source.source_app` but no direct URL. May need to construct from media ID or skip)

---

## Phase 1: Fix Backend - Thumbnail Endpoint

### Task 1: Update get_instagram_thumbnail to use dump_media

**Files:**
- Modify: `apps/visualizer/backend/api/images.py:56-74`

**Step 1: Write failing test**

Create: `apps/visualizer/backend/api/test_images.py`

```python
def test_instagram_thumbnail_from_dump():
    """Test thumbnail endpoint uses dump_media table."""
    import tempfile
    import os
    from tinydb import TinyDB
    from PIL import Image
    
    from api.images import bp
    from flask import Flask
    
    app = Flask(__name__)
    app.register_blueprint(bp, url_prefix='/api/images')
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test image
        img_path = os.path.join(tmpdir, 'test.jpg')
        img = Image.new('RGB', (100, 100), color='red')
        img.save(img_path)
        
        # Create test database
        db_path = os.path.join(tmpdir, 'test.db')
        db = TinyDB(db_path)
        db.table('instagram_dump_media').insert({
            'media_key': '202203/test123',
            'file_path': img_path,
            'filename': 'test.jpg',
        })
        db.close()
        
        # Test endpoint (would need config override)
        # This is a conceptual test
```

**Step 2: Modify endpoint**

In `apps/visualizer/backend/api/images.py`, change lines 56-74:

```python
@bp.route('/instagram/<path:image_key>/thumbnail', methods=['GET'])
def get_instagram_thumbnail(image_key):
    try:
        db_path = config.LIBRARY_DB
        if not os.path.exists(db_path):
            return jsonify({'error': 'Library database not found'}), 404

        db = TinyDB(db_path)
        Media = Query()
        # Use instagram_dump_media instead of instagram_images
        media_items = db.table('instagram_dump_media').search(Media.media_key == image_key)
        db.close()

        if not media_items:
            return jsonify({'error': 'Image not found'}), 404

        media = media_items[0]
        file_path = media.get('file_path')

        if not file_path or not os.path.exists(file_path):
            return jsonify({'error': 'Image file not found'}), 404

        return send_file(file_path, mimetype='image/jpeg')
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

**Step 3: Test**

```bash
curl "http://localhost:5001/api/images/instagram/202203/17885081414569849/thumbnail" --output test.jpg
```

Expected: Image downloads successfully

**Step 4: Commit**

```bash
git add apps/visualizer/backend/api/images.py
git commit -m "fix: update instagram thumbnail endpoint to use dump_media table"
```

---

## Phase 2: Fix Backend - Stats Endpoint

### Task 2: Update get_stats to count from dump_media

**Files:**
- Modify: `apps/visualizer/backend/api/system.py:22"

**Step 1: Modify the query**

Change line 22 from:
```python
instagram_images = db.table('instagram_images').all()
```

To:
```python
instagram_images = db.table('instagram_dump_media').all()
```

**Step 2: Test**

```bash
curl "http://localhost:5001/api/stats"
```

Expected: `{"catalog_images": 0, "instagram_images": 1768, ...}`

**Step 3: Commit**

```bash
git add apps/visualizer/backend/api/system.py
git commit -m "fix: update stats endpoint to count from instagram_dump_media"
```

---

## Phase 3: Fix Backend - Matching Endpoint

### Task 3: Update list_matches to join with dump_media

**Files:**
- Modify: `apps/visualizer/backend/api/images.py:186-193"

**Step 1: Modify the instagram_lookup**

Change lines 186-193 from:
```python
instagram_lookup = {}
if 'instagram_images' in db.tables():
    for img in db.table('instagram_images').all():
        instagram_lookup[img.get('key')] = img
```

To:
```python
instagram_lookup = {}
if 'instagram_dump_media' in db.tables():
    for media in db.table('instagram_dump_media').all():
        instagram_lookup[media.get('media_key')] = media
```

**Step 2: Update enrichment section**

Also update line 207 to use `insta_key` lookup in the dump_media:
```python
# Add Instagram image details
insta_key = match.get('insta_key')
if insta_key and insta_key in instagram_lookup:
    enriched['instagram_image'] = instagram_lookup[insta_key]
```

**Step 3: Test**

```bash
curl "http://localhost:5001/api/images/matches"
```

**Step 4: Commit**

```bash
git add apps/visualizer/backend/api/images.py
git commit -m "fix: update matches endpoint to join with instagram_dump_media"
```

---

## Phase 4: Fix Frontend - Instagram Image Card

### Task 4: Handle missing post_url in InstagramImageCard

**Files:**
- Modify: `apps/visualizer/frontend/src/pages/InstagramPage.tsx:83-136`

**Step 1: Update the interface/type**

In `apps/visualizer/frontend/src/services/api.ts`, update InstagramImage interface:

```typescript
export interface InstagramImage {
  key: string
  local_path: string
  filename: string
  instagram_folder: string
  phash?: string
  description?: string
  crawled_at: string
  image_index: number
  total_in_post: number
  post_url?: string  // Make optional since dump doesn't have it
}
```

**Step 2: Update InstagramImageCard component**

In `InstagramPage.tsx`, modify lines 121-128 to handle missing post_url:

```typescript
{image.post_url ? (
  <a
    href={`${image.post_url}?img_index=${image.image_index - 1}`}
    target="_blank"
    rel="noopener noreferrer"
    className="text-xs text-blue-600 hover:underline flex-shrink-0"
  >
    View
  </a>
) : (
  <span className="text-xs text-gray-400 flex-shrink-0">No link</span>
)}
```

Or better, show "Open File" that opens the local file:

```typescript
<a
  href={`file://${image.local_path}`}
  target="_blank"
  rel="noopener noreferrer"
  className="text-xs text-blue-600 hover:underline flex-shrink-0"
>
  View
</a>
```

**Step 3: Test in browser**

Open http://localhost:5175/instagram and verify:
- Images load without "View" link errors
- Thumbnails display correctly
- Card layout is clean

**Step 4: Commit**

```bash
git add apps/visualizer/frontend/src/pages/InstagramPage.tsx apps/visualizer/frontend/src/services/api.ts
git commit -m "fix: handle missing post_url in instagram image cards"
```

---

## Phase 5: Fix Frontend - Dashboard Stats

### Task 5: Ensure dashboard displays correct stats

**Files:**
- Already fixed in Phase 2

**Step 1: Verify dashboard loads**

Open http://localhost:5175/

Expected: Dashboard shows:
- Catalog Images: 0 (or actual count if exists)
- Instagram Images: 1768
- Posted: 0
- Matches: 0

**Step 2: Test**

Dashboard should load without errors and show 1768 Instagram images.

**Step 3: Commit**

If any fixes needed:
```bash
git add -A
git commit -m "fix: dashboard shows correct instagram dump stats"
```

---

## Phase 6: Verification

### Task 6: Full visualizer test

**Step 1: Restart backend**

```bash
pkill -f "python3 app.py"
cd apps/visualizer/backend
python3 app.py
```

**Step 2: Test all endpoints**

```bash
curl "http://localhost:5001/api/status"
curl "http://localhost:5001/api/stats"
curl "http://localhost:5001/api/images/instagram?limit=2"
curl "http://localhost:5001/api/images/dump-media?limit=2"
```

**Step 3: Verify in browser**

- Dashboard shows 1768 Instagram images
- Instagram page loads with thumbnails
- No console errors
- "View" links work (or show gracefully)

**Step 4: Commit**

```bash
git add -A
git commit -m "test: verify visualizer migration complete"
```

---

## Summary

**Files Modified:**
- `apps/visualizer/backend/api/images.py` - Thumbnail, list_instagram, matches endpoints
- `apps/visualizer/backend/api/system.py` - Stats endpoint
- `apps/visualizer/frontend/src/pages/InstagramPage.tsx` - Handle missing post_url
- `apps/visualizer/frontend/src/services/api.ts` - Make post_url optional

**Testing:**
- All endpoints return data from `instagram_dump_media`
- Dashboard shows 1768 Instagram images
- Thumbnails load
- Image cards display without errors

**Usage:**
```bash
# Start backend
cd apps/visualizer/backend
python3 app.py

# Access visualizer
http://localhost:5175
```

---

**Plan complete and saved to:** `.opencode/plans/2026-03-21-visualizer-migration-to-dump.md`

**Two execution options:**

**1. Subagent-Driven (this session)** - Dispatch fresh subagent per task, review between tasks

**2. Parallel Session (separate)** - Open new session with executing-plans

**Which approach?**

---

## Appendix: Extracting post_url from Dump

The `posts_1.json` doesn't contain direct Instagram post URLs, but we can:

1. **Option A:** Extract `cross_post_source` (shows FB as source, not URL)
2. **Option B:** Construct URL from media ID if we know the shortcode mapping
3. **Option C:** Skip post_url for dump media and show local file link instead

**Current data in posts_1.json:**
```json
{
  "media": [{
    "uri": "media/posts/202603/17940060624158613.jpg",
    "creation_timestamp": 1773179890,
    "cross_post_source": {"source_app": "FB"}
  }],
  "title": "Caption text",
  "creation_timestamp": 1773179891
}
```

**Note:** Instagram URLs use a shortcode (e.g., `https://instagram.com/p/ABC123/`) which is not directly available in the dump. Would require reverse engineering or additional metadata.

---

## Phase 7: Enhanced Data Extraction (EXIF & URLs)

### Background
Analysis of JSON files reveals valuable matching data:

**EXIF Data Coverage:**
- `archived_posts.json`: 100% have EXIF + GPS (112 items) - BEST DATA
- `posts_1.json`: 69% have GPS (215 items, 148 with EXIF, 145 with GPS)
- `other_content.json`: 0% have EXIF (20 items)

**No Duplicates:** 0 overlaps between JSON files (506 unique media total)

**Instagram URLs:** Only available in `saved_posts.json` and `reposts.json`

### Task 7: Parse All Media JSON Files

**Files:**
- Modify: `lightroom_tagger/instagram/dump_reader.py`

**Step 1: Parse archived_posts.json**

Add new function:
```python
def parse_archived_posts_metadata(dump_path: str) -> Dict[str, Dict]:
    """Parse archived_posts.json to extract EXIF-rich metadata."""
    # Extract: media_key, caption, creation_timestamp, EXIF data
    # EXIF fields: date_time_original, latitude, longitude, device_id, 
    #              lens_model, iso, aperture, shutter_speed, etc.
```

**Step 2: Parse other_content.json**

Add new function:
```python
def parse_other_content_metadata(dump_path: str) -> Dict[str, Dict]:
    """Parse other_content.json (minimal metadata)."""
    # Extract: media_key, caption, creation_timestamp
    # No EXIF in this file
```

**Step 3: Parse saved_posts.json and reposts.json for URLs**

Add new function:
```python
def parse_saved_posts_for_urls(dump_path: str) -> Dict[int, str]:
    """Extract URLs from saved_posts.json and reposts.json.
    
    Returns: Dict mapping creation_timestamp -> Instagram URL
    """
    # Match by timestamp to link URLs to dump media
```

**Step 4: Combine all parsers in import script**

Update `import_instagram_dump.py`:
```python
def import_dump(db, dump_path: str) -> int:
    # 1. Discover all files from filesystem
    media_files = discover_media_files(dump_path)
    
    # 2. Parse all JSON metadata
    posts_metadata = parse_posts_metadata(dump_path)
    archived_metadata = parse_archived_posts_metadata(dump_path)
    other_metadata = parse_other_content_metadata(dump_path)
    url_lookup = parse_saved_posts_for_urls(dump_path)
    
    # 3. Combine into single lookup (aggregative - merge by media_key)
    combined = {}
    for key, data in posts_metadata.items():
        combined[key] = data
    for key, data in archived_metadata.items():
        if key in combined:
            # Merge: keep EXIF from archived, caption from posts
            combined[key].update(data)
        else:
            combined[key] = data
    for key, data in other_metadata.items():
        if key in combined:
            combined[key].update(data)
        else:
            combined[key] = data
    
    # 4. Add URLs by timestamp matching
    for key, data in combined.items():
        ts = data.get('creation_timestamp')
        if ts and ts in url_lookup:
            data['post_url'] = url_lookup[ts]
    
    # 5. Store all media (with or without JSON metadata)
    for media_file in media_files:
        key = media_file['media_key']
        record = {
            'media_key': key,
            'file_path': media_file['file_path'],
            'filename': media_file['filename'],
            'date_folder': media_file['date_folder'],
            **combined.get(key, {})  # Add metadata if exists
        }
        store_instagram_dump_media(db, record)
```

### Task 8: Update Database Schema

**Files:**
- Modify: `lightroom_tagger/core/database.py`

**Step 1: Update store_instagram_dump_media**

Change to support aggregative updates:
```python
def store_instagram_dump_media(db, record: dict) -> str:
    """Store Instagram dump media record. Aggregative - merges data."""
    # If record exists, merge new data with existing
    # Keep original added_at
    # Update only if not processed
```

**Step 2: Add EXIF fields to defaults**

```python
record.setdefault('exif_data', None)  # Store full EXIF as JSON
defaults for specific fields:
record.setdefault('exif_date_time_original', None)
record.setdefault('exif_latitude', None)
record.setdefault('exif_longitude', None)
record.setdefault('exif_device_id', None)
record.setdefault('exif_lens_model', None)
record.setdefault('post_url', None)
```

**Step 3: Test EXIF extraction**

```bash
cd /home/cristian/lightroom_tagger/.worktrees/instagram-dump
python3 -c "
from tinydb import TinyDB
from lightroom_tagger.core.database import init_database, init_instagram_dump_table

db = init_database('test_exif.db')
init_instagram_dump_table(db)

# Verify EXIF fields exist
media = db.table('instagram_dump_media').all()
print(f'Media count: {len(media)}')
if media:
    print(f'Sample keys: {list(media[0].keys())}')
db.close()
"
```

**Step 4: Commit**

```bash
git add lightroom_tagger/instagram/dump_reader.py
git add lightroom_tagger/core/database.py
git commit -m "feat: extract EXIF data and URLs from all media JSON files"
```

### Task 9: Re-import with Enhanced Data

**Step 1: Clear and re-import**

```bash
cd /home/cristian/lightroom_tagger/.worktrees/instagram-dump
rm library.db
python3 -m lightroom_tagger.scripts.import_instagram_dump --dump-path /home/cristian/instagram-dump --db library.db
```

**Step 2: Verify EXIF data**

```python
from tinydb import TinyDB
db = TinyDB('library.db')
media = db.table('instagram_dump_media').all()

# Count with EXIF
with_exif = [m for m in media if m.get('exif_data')]
with_gps = [m for m in media if m.get('exif_latitude')]
with_urls = [m for m in media if m.get('post_url')]

print(f'Total: {len(media)}')
print(f'With EXIF: {len(with_exif)}')
print(f'With GPS: {len(with_gps)}')
print(f'With URLs: {len(with_urls)}')
db.close()
```

Expected:
- Total: ~1,768
- With EXIF: ~260 (112 archived + 148 posts with EXIF)
- With GPS: ~257 (109 archived + 145 posts with GPS)
- With URLs: ~200 (from saved_posts + reposts)

---

## Updated Summary

**Files Modified:**
- `lightroom_tagger/instagram/dump_reader.py` - Parse all JSON files
- `lightroom_tagger/core/database.py` - Support aggregative updates + EXIF fields
- `lightroom_tagger/scripts/import_instagram_dump.py` - Combine all parsers
- `apps/visualizer/backend/api/images.py` - Use dump_media table
- `apps/visualizer/backend/api/system.py` - Count from dump_media
- `apps/visualizer/frontend/src/pages/InstagramPage.tsx` - Show URLs where available

**New Data Available:**
- EXIF: date_time_original, GPS, camera info
- URLs: From saved/reposted content
- Coverage: 506 media with JSON metadata, 1,262 with filesystem only

**Usage After Update:**
```bash
cd /home/cristian/lightroom_tagger/.worktrees/instagram-dump
python3 -m lightroom_tagger.scripts.import_instagram_dump --dump-path /home/cristian/instagram-dump
```
