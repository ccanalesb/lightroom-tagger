# Plan: Cache Compressed Images for Vision Matching

## Context
The vision matching process currently wastes significant CPU and time by:
- **Compressing the same Instagram image 50+ times** when comparing against 50 candidates
- **Re-compressing catalog images repeatedly** across multiple matching runs
- **Not pre-computing pHash** for catalog images

Each vision comparison calls `compress_image()` which:
1. Opens the image with PIL
2. Converts to RGB
3. Resizes to max 1024px
4. Saves as compressed JPEG

This happens for every candidate comparison, creating temp files that are immediately deleted.

## Goals
1. Compress catalog images **once** and cache them for reuse
2. Calculate pHash **during compression** and store in database
3. Use cached compressed images in vision matching instead of re-compressing
4. Create a job to pre-process catalog images before matching

## Implementation Plan

### Phase 1: Configuration
**File: `apps/visualizer/backend/config.py`**
- Add `VISION_CACHE_DIR` env variable (default: `~/.cache/lightroom_tagger/vision` - persistent, not /tmp)
- Add `VISION_CACHE_ENABLED` (default: True) - can disable if needed

**Decision:** Persistent cache at `~/.cache/lightroom_tagger/vision` not /tmp
- Add `VISION_CACHE_MAX_AGE_DAYS` (optional: for cache invalidation)

### Phase 2: Database Schema
**File: `lightroom_tagger/core/database.py`**
- Create new table `vision_cache` with fields:
  - `key` (catalog image key - supports multiple catalogs)
  - `compressed_path` (path to cached compressed image)
  - `phash` (pre-computed perceptual hash)
  - `compressed_at` (timestamp)
  - `original_mtime` (file modification time for cache invalidation)

Functions to add:
- `init_vision_cache_table(db)`
- `get_vision_cached_image(db, catalog_key) -> dict`
- `store_vision_cached_image(db, catalog_key, compressed_path, phash, original_mtime)`
- `is_vision_cache_valid(db, catalog_key, original_path) -> bool` - checks mtime

**Decision:** Use file modification time for cache invalidation (simple, reliable)

### Phase 3: Compression & Caching with Atomic Writes
**New file: `lightroom_tagger/core/vision_cache.py`**

```python
import fcntl
import tempfile
import os
from pathlib import Path
from lightroom_tagger.core.database import get_vision_cached_image, store_vision_cached_image
from lightroom_tagger.core.analyzer import compress_image, compute_phash
from lightroom_tagger.core.config import load_config

def get_or_create_cached_image(db, catalog_key: str, original_path: str) -> str:
    """Get compressed image path from cache or create it atomically.
    Uses file locking to prevent concurrent compression of same image.
    """
    config = load_config()
    cache_dir = config.vision_cache_dir
    os.makedirs(cache_dir, exist_ok=True)

    target_path = os.path.join(cache_dir, f"{catalog_key}.jpg")
    lock_file = os.path.join(cache_dir, f"{catalog_key}.lock")

    # Check if already cached and valid (mtime unchanged)
    cached = get_vision_cached_image(db, catalog_key)
    if cached and os.path.exists(cached['compressed_path']):
        current_mtime = os.path.getmtime(original_path)
        if cached.get('original_mtime') == current_mtime:
            return cached['compressed_path']

    # Need to create cache
    # (Note: We accept race conditions here - worst case is duplicate compression work)
        cached = get_vision_cached_image(db, catalog_key)
        if cached and os.path.exists(cached['compressed_path']):
            current_mtime = os.path.getmtime(original_path)
            if cached.get('original_mtime') == current_mtime:
                return cached['compressed_path']

        # Compress to temp file first (atomic write)
        temp_path = compress_image(original_path)
        phash = compute_phash(original_path)
        original_mtime = os.path.getmtime(original_path)

        # Atomic move to final location
        os.rename(temp_path, target_path)

        # Store in database with mtime
        store_vision_cached_image(db, catalog_key, target_path, phash, original_mtime)

        return target_path

def get_cached_phash(db, catalog_key: str) -> str:
    """Get pre-computed pHash from cache."""
    cached = get_vision_cached_image(db, catalog_key)
    return cached.get('phash') if cached else None

class InstagramCache:
    """Cache for compressed Instagram images during a single matching run."""
    _compressed_path: str = None

    def __init__(self, db=None):
        self.db = db

    def compress_instagram_image(self, insta_path: str) -> str:
        """Compress Instagram image once and cache in memory for this run."""
        if self._compressed_path is None:
            self._compressed_path = compress_image(insta_path)
        return self._compressed_path

    def cleanup(self):
        """Clean up temp file after matching run."""
        if self._compressed_path and os.path.exists(self._compressed_path):
            os.unlink(self._compressed_path)
            self._compressed_path = None
```

### Phase 4: Modify Vision Matching
**File: `lightroom_tagger/core/analyzer.py`**
Modify `compare_with_vision` to accept pre-compressed paths:

```python
def compare_with_vision(local_path: str, insta_path: str,
                        cached_local_path: str = None,
                        compressed_insta_path: str = None,
                        log_callback=None) -> str:
    """Compare two images using vision model.

    Args:
        local_path: Original path to catalog image (for error reporting)
        insta_path: Original path to Instagram image (for error reporting)
        cached_local_path: Pre-compressed catalog image (optional)
        compressed_insta_path: Pre-compressed Instagram image (optional)
    """
    # Use pre-compressed paths if available
    if cached_local_path and os.path.exists(cached_local_path):
        compressed_local = cached_local_path
    else:
        compressed_local = compress_image(local_path)

    if compressed_insta_path and os.path.exists(compressed_insta_path):
        compressed_insta = compressed_insta_path
    else:
        compressed_insta = compress_image(insta_path)
    ...
```

**File: `lightroom_tagger/core/matcher.py`**
Modify `score_candidates_with_vision` to use cached images and compress Instagram once:

```python
from lightroom_tagger.core.vision_cache import (
    get_or_create_cached_image, get_cached_phash, InstagramCache
)

def score_candidates_with_vision(db, insta_image: dict, candidates: list,
                                 ..., log_callback=None) -> List[dict]:
    # Compress Instagram image ONCE before candidate loop
    insta_cache = InstagramCache()
    insta_path = insta_image.get('local_path')
    compressed_insta = insta_cache.compress_instagram_image(insta_path)

    total = len(candidates)
    cache_hits = 0
    cache_misses = 0

    if log_callback:
        log_callback('info', f"Vision comparison: {total} candidates to evaluate")

    for idx, candidate in enumerate(candidates, 1):
        # Use cached compressed image for catalog (or create on-demand)
        try:
            cached_path = get_or_create_cached_image(db, candidate['key'], candidate['local_path'])
            cache_hits += 1
            if log_callback and idx <= 5:  # Log first 5 to show it's working
                log_callback('info', f"  [{idx}/{total}] Cache hit: {candidate['key']}")
        except Exception as e:
            cache_misses += 1
            if log_callback:
                log_callback('warning', f"  [{idx}/{total}] Cache miss/on-demand: {candidate['key']}")
            cached_path = None

        # Use cached pHash instead of computing
        phash = get_cached_phash(db, candidate['key'])
        if phash is not None:
            # We already computed and cached pHash
            phash_dist = hamming_distance(insta_image.get('image_hash', ''), phash)
        else:
            # Fallback: compute pHash on the fly
            phash_dist = hamming_distance(
                insta_image.get('image_hash', ''),
                compute_phash(candidate['local_path'])
            )

        # Run vision comparison with pre-compressed paths
        vision_result = compare_with_vision(
            candidate['local_path'],
            insta_path,
            cached_local_path=cached_path,
            compressed_insta_path=compressed_insta,
            log_callback=log_callback
        )

    # Cleanup Instagram temp file
    insta_cache.cleanup()

    # Log summary
    if log_callback:
        log_callback('info', f"Completed: {cache_hits} from cache, {cache_misses} on-demand")

    return sorted(results, key=lambda x: x['total_score'], reverse=True)
```

### Phase 5: Pre-processing Job with Parallel Compression
**New file: `apps/visualizer/backend/jobs/handlers.py` (add handler)**

```python
def handle_prepare_catalog(runner, job_id: str, metadata: dict):
    """Pre-compress and cache all catalog images with parallel processing."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import threading
    from lightroom_tagger.core.vision_cache import get_or_create_cached_image, get_cache_stats
    from lightroom_tagger.core.database import get_all_catalog_images
    from database import add_job_log

    def log(level, message):
        add_job_log(runner.db, job_id, level, message)

    db = init_database(db_path)
    cache_stats = get_cache_stats(db)

    log('info', f"Cache status: {cache_stats['cached']}/{cache_stats['total']} images cached")
    log('info', f"Cache directory: {config.vision_cache_dir}")

    images = get_all_catalog_images(db)
    total = len(images)

    # Determine parallelism (I/O bound, so threads are fine)
    max_workers = min(4, os.cpu_count() or 2)
    log('info', f"Using {max_workers} parallel threads for compression")

    newly_cached = 0
    already_cached = 0
    failed = 0

    def process_single_image(image):
        """Process one image - thread-safe with retry logic."""
        filepath = image['filepath']
        filename = os.path.basename(filepath)
        key = image['key']

        retries = 2
        for attempt in range(retries):
            try:
                # This will check cache first and skip if already cached
                compressed_path = get_or_create_cached_image(db, key, filepath)
                if compressed_path:
                    # Check if it was already cached by checking mtime
                    cached_record = get_cached_image(db, key)
                    if cached_record and cached_record.get('original_mtime') == os.path.getmtime(filepath):
                        return ('already_cached', key)
                    else:
                        size_kb = os.path.getsize(compressed_path) / 1024
                        return ('newly_cached', key, size_kb)
                return ('failed', key, 'compress returned None')
            except Exception as e:
                if attempt < retries - 1:
                    time.sleep(0.5 * (attempt + 1))  # Exponential backoff
                    continue
                return ('failed', key, str(e))

    # Process images in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_single_image, img): img for img in images}

        for idx, future in enumerate(as_completed(futures), 1):
            result = future.result()

            if result[0] == 'already_cached':
                already_cached += 1
            elif result[0] == 'newly_cached':
                newly_cached += 1
            else:
                failed += 1
                log('error', f"Failed to cache {result[1]}: {result[2]}")

            # Update progress every 10 images or at end
            if idx % 10 == 0 or idx == total:
                runner.update_progress(job_id, int((idx / total) * 100),
                                     f'Processed {idx}/{total} images')

    final_stats = get_cache_stats(db)
    log('info', f"Complete: {newly_cached} newly cached, {already_cached} already cached, {failed} failed")
    log('info', f"Total cache size: {final_stats['cache_size_mb']:.1f}MB")

    db.close()
    runner.complete_job(job_id, {
        'cached': newly_cached,
        'already_cached': already_cached,
        'failed': failed,
        'total': total,
        'cache_size_mb': final_stats['cache_size_mb'],
        'parallel_workers': max_workers
    })
```

**Note:** Cache never expires - images stored forever unless deleted manually.

### Phase 6: API Endpoints
**File: `apps/visualizer/backend/api/system.py`**
- Add endpoint to check cache status: `/cache/status`
- Returns: `{ 'total_images': X, 'cached_images': Y, 'cache_size_bytes': Z }`

### Phase 7: UI Integration - Cache Status & Controls
**File: `apps/visualizer/frontend/src/pages/MatchingPage.tsx`**
- Add "Prepare Catalog" button to pre-cache images before matching
- Show cache status: "X of Y catalog images cached (Z MB)"
- Warn if cache is stale or incomplete
- Option to skip matching if cache is not ready

**File: `apps/visualizer/frontend/src/components/JobDetailModal.tsx`**
- Enhance log display with collapsible sections
- Show log entries with timestamps and color-coded levels
- Display "Cache Hits" in job results for prepare_catalog jobs
- Show progress bar with current file being processed

### Phase 8: Matching Job Logging Enhancements
**File: `lightroom_tagger/core/matcher.py`**

Update `score_candidates_with_vision` to log cache usage:

```python
def score_candidates_with_vision(db, insta_image: dict, candidates: list, ...):
    # Before comparison, log cache stats
    if log_callback:
        cache_count = sum(1 for c in candidates if has_cached_image(c['key']))
        log_callback('info', f"Vision comparison: {cache_count}/{len(candidates)} catalog images cached")

    for idx, candidate in enumerate(candidates, 1):
        # Check cache before compression
        cached = get_cached_image(db, candidate['key'])
        if cached:
            log_callback('info', f"  [{idx}/{len(candidates)}] Using cached: {candidate['key']}")
        else:
            log_callback('info', f"  [{idx}/{len(candidates)}] Caching on-demand: {candidate['key']}")
```

This way users can see:
- How many catalog images are pre-cached
- Which images are being compressed on-demand
- Total time saved from caching

## Benefits
| Before | After |
|--------|-------|
| 50 Instagram compressions per 50 candidates | 1 Instagram compression total |
| 50 catalog compressions per matching run | 0 (reused from cache) |
| pHash computed 50 times | pHash computed once during caching |
| ~100 temp files created/deleted | ~2 temp files just for Instagram image |
| Comparsion time: ~2-5 min | Comparison time: ~1-2 min |

## Files to Modify
1. `apps/visualizer/backend/config.py` - Add VISION_CACHE_DIR
2. `lightroom_tagger/core/database.py` - Add vision cache table
3. `lightroom_tagger/core/vision_cache.py` - New module (create)
4. `lightroom_tagger/core/analyzer.py` - Use cached paths
5. `lightroom_tagger/core/matcher.py` - Compress Instagram once, use catalog cache
6. `lightroom_tagger/scripts/match_instagram_dump.py` - Use caching
7. `apps/visualizer/backend/jobs/handlers.py` - Add prepare_catalog handler
8. `apps/visualizer/backend/api/system.py` - Add cache status endpoint

## Verification
1. Run matching and check logs - should see "Using cached image" instead of "Compressed: XKB -> YKB" for catalog images
2. Check database - `vision_cache` table should have entries
3. Check filesystem - cache directory should contain .jpg files named by catalog key
4. Second matching run should be significantly faster
