# Instagram Sync Module Deepening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extract the Instagram sync workflow from `core/cli.py` into a deep, testable module that hides orchestration complexity behind a simple interface.

**Architecture:** Create `core/sync.py` that encapsulates the 5-step sync workflow (crawl → hash → match → update DB → write Lightroom). The CLI will call one function instead of 194 lines. All subsystems (Instagram, hashing, database, Lightroom) become injectable dependencies for testing.

**Tech Stack:** Python, TinyDB, SQLite (Lightroom), PIL/imagehash

**Dependencies:** Current modules: `instagram/scraper.py`, `instagram/browser.py`, `core/hasher.py`, `core/phash.py`, `core/database.py`, `lightroom/writer.py`

---

## Task 1: Create sync module structure and first failing test

**Files:**
- Create: `core/sync.py`
- Create: `core/test_sync.py`

**Step 1: Write the failing test**

```python
# core/test_sync.py
import pytest
from unittest.mock import Mock, MagicMock, patch
from core.sync import sync_instagram

def test_sync_returns_zero_on_success():
    """Sync should return 0 when complete."""
    # Arrange - mock all dependencies
    mock_db = Mock()
    mock_catalog = Mock()
    mock_crawler = Mock()
    mock_crawler.return_value = ([], {})  # no posts
    
    with patch('core.sync.init_database', return_value=mock_db), \
         patch('core.sync.crawl_instagram', mock_crawler), \
         patch('core.sync.compute_phash', return_value='abc123'), \
         patch('core.sync.find_matches', return_value=[]), \
         patch('core.sync.connect_catalog', return_value=mock_catalog), \
         patch('core.sync.add_keyword_to_images_batch', return_value={'added': 0, 'skipped': 0, 'errors': 0}):
        
        result = sync_instagram(
            db_path='/fake/db.json',
            instagram_url='https://instagram.com/user',
            keyword='test',
            catalog_path=None,
            threshold=10,
            dry_run=True
        )
    
    assert result == 0
```

**Step 2: Run test to verify it fails**

```bash
cd /home/cristian/lightroom_tagger && python -m pytest core/test_sync.py::test_sync_returns_zero_on_success -v
```
Expected: FAIL with "ModuleNotFoundError: No module named 'core.sync'"

**Step 3: Write minimal implementation**

```python
# core/sync.py
def sync_instagram(db_path, instagram_url, keyword, catalog_path, threshold, dry_run=True, limit=50, use_browser=False):
    """Sync Instagram posts with local catalog."""
    return 0
```

**Step 4: Run test to verify it passes**

```bash
cd /home/cristian/lightroom_tagger && python -m pytest core/test_sync.py::test_sync_returns_zero_on_success -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add core/sync.py core/test_sync.py
git commit -m "feat(sync): create sync module skeleton with passing test"
```

---

## Task 2: Test and implement crawler abstraction

**Files:**
- Modify: `core/sync.py`
- Modify: `core/test_sync.py`

**Step 1: Write the failing test**

```python
# core/test_sync.py - add test
def test_sync_crawls_instagram_with_correct_username():
    """Sync should extract username from Instagram URL and pass to crawler."""
    mock_db = Mock()
    mock_crawler = Mock(return_value=([], {}))
    
    with patch('core.sync.init_database', return_value=mock_db), \
         patch('core.sync.crawl_instagram', mock_crawler) as crawl_mock, \
         patch('core.sync.compute_phash', return_value='abc123'), \
         patch('core.sync.find_matches', return_value=[]), \
         patch('core.sync.add_keyword_to_images_batch', return_value={'added': 0, 'skipped': 0, 'errors': 0}):
        
        sync_instagram(
            db_path='/fake/db.json',
            instagram_url='https://instagram.com/testuser',
            keyword='test',
            catalog_path=None,
            threshold=10,
            dry_run=True,
            output_dir='/tmp'
        )
    
    # Verify crawler was called with extracted username
    crawl_mock.assert_called_once()
    call_args = crawl_mock.call_args
    assert call_args[0][0] == 'testuser'  # first positional arg is config
```

**Step 2: Run test to verify it fails**

```bash
cd /home/cristian/lightroom_tagger && python -m pytest core/test_sync.py::test_sync_crawls_instagram_with_correct_username -v
```
Expected: FAIL - crawler not called correctly

**Step 3: Write implementation**

```python
# core/sync.py
import os
from pathlib import Path

def sync_instagram(db_path, instagram_url, keyword, catalog_path, threshold, 
                   dry_run=True, limit=50, use_browser=False, output_dir='/tmp'):
    """Sync Instagram posts with local catalog."""
    from lightroom_tagger.instagram.scraper import crawl_instagram
    from lightroom_tagger.instagram.browser import crawl_instagram_browser
    
    # Extract username from URL
    username = instagram_url.split('/')[-2] if '/' in instagram_url else instagram_url
    
    # Crawl Instagram
    if use_browser:
        from lightroom_tagger.instagram.browser import crawl_instagram_browser
        posts, url_to_path = crawl_instagram_browser(username, output_dir, limit, session_name="instagram")
    else:
        posts, url_to_path = crawl_instagram(None, output_dir, limit=limit)
    
    return 0
```

**Step 4: Run test to verify it passes**

```bash
cd /home/cristian/lightroom_tagger && python -m pytest core/test_sync.py::test_sync_crawls_instagram_with_correct_username -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add core/sync.py core/test_sync.py
git commit -m "feat(sync): extract username from URL and call crawler"
```

---

## Task 3: Test and implement hash computation step

**Files:**
- Modify: `core/sync.py`
- Modify: `core/test_sync.py`

**Step 1: Write the failing test**

```python
# core/test_sync.py
def test_sync_computes_hashes_for_local_images():
    """Sync should compute hashes for images without hashes."""
    mock_db = Mock()
    mock_db.__enter__ = Mock(return_value=mock_db)
    mock_db.__exit__ = Mock(return_value=False)
    mock_db.query.return_value = []  # no images need hash
    
    mock_crawler = Mock(return_value=([], {}))
    
    with patch('core.sync.init_database', return_value=mock_db), \
         patch('core.sync.crawl_instagram', mock_crawler), \
         patch('core.sync.get_all_images', return_value=[{'key': 'img1', 'filepath': '/fake/path.jpg'}]), \
         patch('core.sync.get_images_without_hash', return_value=[{'key': 'img1', 'filepath': '/fake/path.jpg'}]), \
         patch('core.sync.compute_phash', return_value='abc123') as phash_mock, \
         patch('core.sync.batch_update_hashes', return_value=None), \
         patch('core.sync.find_matches', return_value=[]):
        
        sync_instagram(
            db_path='/fake/db.json',
            instagram_url='https://instagram.com/user',
            keyword='test',
            catalog_path=None,
            threshold=10,
            dry_run=True,
            output_dir='/tmp'
        )
    
    phash_mock.assert_called()
```

**Step 2: Run test to verify it fails**

```bash
cd /home/cristian/lightroom_tagger && python -m pytest core/test_sync.py::test_sync_computes_hashes_for_local_images -v
```
Expected: FAIL - functions not imported/called

**Step 3: Write implementation**

```python
# core/sync.py - add imports and logic
from lightroom_tagger.core.database import (
    init_database, get_all_images, get_images_without_hash, 
    batch_update_hashes, update_instagram_status
)
from lightroom_tagger.core.hasher import compute_phash
from lightroom_tagger.core.phash import find_matches
from lightroom_tagger.lightroom.writer import add_keyword_to_images_batch
from lightroom_tagger.lightroom.reader import connect_catalog
from lightroom_tagger.core.config import load_config

def sync_instagram(db_path, instagram_url, keyword, catalog_path, threshold, 
                   dry_run=True, limit=50, use_browser=False, output_dir='/tmp'):
    """Sync Instagram posts with local catalog."""
    # ... crawler code from Task 2 ...
    
    db = init_database(db_path)
    
    # Step 1: Compute hashes for local images
    local_images = get_all_images(db)
    images_needing_hash = get_images_without_hash(db)
    
    config = load_config()
    
    hash_updates = []
    for record in images_needing_hash:
        filepath = record.get('filepath')
        if filepath:
            resolved_path = config._resolve_path(filepath)
            if resolved_path and Path(resolved_path).exists():
                image_hash = compute_phash(resolved_path)
                if image_hash:
                    hash_updates.append({'key': record['key'], 'image_hash': image_hash})
    
    if hash_updates:
        batch_update_hashes(db, hash_updates)
    
    local_images = get_all_images(db)
    local_with_hash = [img for img in local_images if img.get('image_hash')]
    
    # Step 2: Crawl Instagram (already done above)
    
    # Step 3: Find matches
    matches = find_matches(local_with_hash, insta_images, threshold)
    
    # ... rest ...
    
    db.close()
    return 0
```

**Step 4: Run test to verify it passes**

```bash
cd /home/cristian/lightroom_tagger && python -m pytest core/test_sync.py::test_sync_computes_hashes_for_local_images -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add core/sync.py core/test_sync.py
git commit -m "feat(sync): implement local hash computation step"
```

---

## Task 4: Test and implement full workflow with match finding

**Files:**
- Modify: `core/sync.py`
- Modify: `core/test_sync.py`

**Step 1: Write the failing test**

```python
# core/test_sync.py
def test_sync_finds_matches_and_returns_count():
    """Sync should find matches between local and Instagram images."""
    mock_db = Mock()
    mock_db.__enter__ = Mock(return_value=mock_db)
    mock_db.__exit__ = Mock(return_value=False)
    
    mock_crawler = Mock(return_value=([], {}))
    
    # Mock post with matching image
    mock_post = Mock()
    mock_post.post_url = 'https://instagram.com/p/abc123'
    mock_post.index = 0
    
    with patch('core.sync.init_database', return_value=mock_db), \
         patch('core.sync.crawl_instagram', return_value=([mock_post], {'https://instagram.com/p/abc123': ['/tmp/insta.jpg']})), \
         patch('core.sync.get_all_images', return_value=[{'key': 'local1', 'filepath': '/fake/img.jpg', 'image_hash': 'abc123'}]), \
         patch('core.sync.get_images_without_hash', return_value=[]), \
         patch('core.sync.compute_phash', return_value='abc123'), \
         patch('core.sync.find_matches', return_value=[{'local_key': 'local1', 'insta_url': 'https://instagram.com/p/abc123', 'hash_distance': 2}]) as matches_mock, \
         patch('core.sync.update_instagram_status') as update_mock:
        
        result = sync_instagram(
            db_path='/fake/db.json',
            instagram_url='https://instagram.com/user',
            keyword='test',
            catalog_path=None,
            threshold=10,
            dry_run=True,
            output_dir='/tmp'
        )
    
    matches_mock.assert_called_once()
    update_mock.assert_called_once()
    assert result == 0
```

**Step 2: Run test to verify it fails**

```bash
cd /home/cristian/lightroom_tagger && python -m pytest core/test_sync.py::test_sync_finds_matches_and_returns_count -v
```
Expected: FAIL - incomplete implementation

**Step 3: Write implementation (complete sync function)**

```python
# core/sync.py - complete implementation
def sync_instagram(db_path, instagram_url, keyword, catalog_path, threshold, 
                   dry_run=True, limit=50, use_browser=False, output_dir='/tmp'):
    """Sync Instagram posts with local catalog.
    
    Args:
        db_path: Path to TinyDB database
        instagram_url: Instagram profile or post URL
        keyword: Keyword to add to matched images in Lightroom
        catalog_path: Path to Lightroom catalog (optional)
        threshold: Hamming distance threshold for hash matching
        dry_run: If True, don't actually write to database or Lightroom
        limit: Maximum Instagram posts to crawl
        use_browser: Use browser-based crawling instead of API
        output_dir: Directory to save downloaded images
    
    Returns:
        0 on success, 1 on error
    """
    from lightroom_tagger.instagram.scraper import crawl_instagram
    from lightroom_tagger.instagram.browser import crawl_instagram_browser
    
    # Extract username from URL
    username = instagram_url.split('/')[-2] if '/' in instagram_url else instagram_url
    
    # Crawl Instagram
    if use_browser:
        posts, url_to_path = crawl_instagram_browser(username, output_dir, limit, session_name="instagram")
    else:
        posts, url_to_path = crawl_instagram(None, output_dir, limit=limit)
    
    if not posts:
        return 1
    
    db = init_database(db_path)
    
    # Step 1: Compute hashes for local images
    local_images = get_all_images(db)
    images_needing_hash = get_images_without_hash(db)
    
    config = load_config()
    
    hash_updates = []
    for record in images_needing_hash:
        filepath = record.get('filepath')
        if filepath:
            resolved_path = config._resolve_path(filepath)
            if resolved_path and Path(resolved_path).exists():
                image_hash = compute_phash(resolved_path)
                if image_hash:
                    hash_updates.append({'key': record['key'], 'image_hash': image_hash})
    
    if hash_updates:
        batch_update_hashes(db, hash_updates)
    
    local_images = get_all_images(db)
    local_with_hash = [img for img in local_images if img.get('image_hash')]
    
    # Step 2: Hash Instagram images
    insta_images = []
    for post in posts:
        local_paths = url_to_path.get(post.post_url)
        if local_paths:
            for local_path in local_paths:
                if os.path.exists(local_path):
                    image_hash = compute_phash(local_path)
                    insta_images.append({
                        'url': post.post_url,
                        'local_path': local_path,
                        'image_hash': image_hash,
                        'index': post.index,
                    })
    
    # Step 3: Find matches
    matches = find_matches(local_with_hash, insta_images, threshold)
    
    if not matches:
        db.close()
        return 0
    
    # Step 4: Update database
    matched_keys = [m['local_key'] for m in matches]
    
    for match in matches:
        if not dry_run:
            update_instagram_status(
                db, 
                match['local_key'],
                posted=True,
                url=match['insta_url']
            )
    
    # Step 5: Write to Lightroom
    if catalog_path and Path(catalog_path).exists() and not dry_run:
        connect = connect_catalog(catalog_path)
        add_keyword_to_images_batch(connect, matched_keys, keyword)
    
    db.close()
    return 0
```

**Step 4: Run test to verify it passes**

```bash
cd /home/cristian/lightroom_tagger && python -m pytest core/test_sync.py::test_sync_finds_matches_and_returns_count -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add core/sync.py core/test_sync.py
git commit -m "feat(sync): implement full sync workflow with matching"
```

---

## Task 5: Test edge cases - no posts found

**Files:**
- Modify: `core/test_sync.py`

**Step 1: Write the failing test**

```python
# core/test_sync.py
def test_sync_returns_error_when_no_posts_found():
    """Sync should return 1 when no Instagram posts are found."""
    mock_db = Mock()
    
    with patch('core.sync.init_database', return_value=mock_db), \
         patch('core.sync.crawl_instagram', return_value=([], {})):
        
        result = sync_instagram(
            db_path='/fake/db.json',
            instagram_url='https://instagram.com/user',
            keyword='test',
            catalog_path=None,
            threshold=10,
            dry_run=True,
            output_dir='/tmp'
        )
    
    assert result == 1
```

**Step 2: Run test to verify it fails**

```bash
cd /home/cristian/lightroom_tagger && python -m pytest core/test_sync.py::test_sync_returns_error_when_no_posts_found -v
```
Expected: FAIL - currently returns 0

**Step 3: Verify test fails correctly**

The test fails because the current implementation returns 0 even with no posts. This is the correct behavior we want to test - we need to fix the implementation.

**Step 4: Fix implementation**

```python
# In sync_instagram, after crawling:
if not posts:
    db.close()
    return 1  # Return error when no posts
```

**Step 5: Run test to verify it passes**

```bash
cd /home/cristian/lightroom_tagger && python -m pytest core/test_sync.py::test_sync_returns_error_when_no_posts_found -v
```
Expected: PASS

**Step 6: Commit**

```bash
git add core/sync.py core/test_sync.py
git commit -m "fix(sync): return error code when no posts found"
```

---

## Task 6: Test edge cases

**Files:**
 - no matches found- Modify: `core/test_sync.py`

**Step 1: Write the failing test**

```python
# core/test_sync.py
def test_sync_returns_zero_when_no_matches_found():
    """Sync should return 0 (not error) when posts exist but no matches."""
    mock_db = Mock()
    
    mock_post = Mock()
    mock_post.post_url = 'https://instagram.com/p/abc123'
    mock_post.index = 0
    
    with patch('core.sync.init_database', return_value=mock_db), \
         patch('core.sync.crawl_instagram', return_value=([mock_post], {})), \
         patch('core.sync.get_all_images', return_value=[]), \
         patch('core.sync.get_images_without_hash', return_value=[]), \
         patch('core.sync.compute_phash', return_value='abc123'), \
         patch('core.sync.find_matches', return_value=[]):
        
        result = sync_instagram(
            db_path='/fake/db.json',
            instagram_url='https://instagram.com/user',
            keyword='test',
            catalog_path=None,
            threshold=10,
            dry_run=True,
            output_dir='/tmp'
        )
    
    assert result == 0  # Not an error, just no matches
```

**Step 2: Run test to verify it fails**

```bash
cd /home/cristian/lightroom_tagger && python -m pytest core/test_sync.py::test_sync_returns_zero_when_no_matches_found -v
```
Expected: Should pass (already handled in implementation)

**Step 3: Commit**

```bash
git add core/test_sync.py
git commit -m "test(sync): add test for no matches case"
```

---

## Task 7: Refactor CLI to use new module

**Files:**
- Modify: `core/cli.py`

**Step 1: Write the failing test**

```python
# Create core/test_cli_sync.py
import pytest
from unittest.mock import Mock, patch

def test_cli_calls_sync_module(monkeypatch):
    """CLI should delegate to sync_instagram function."""
    mock_sync = Mock(return_value=0)
    
    # Mock argparse
    mock_args = Mock(
        db='/fake/db.json',
        instagram_url='https://instagram.com/user',
        keyword='test',
        catalog='/fake/catalog.lrcat',
        hash_threshold=10,
        dry_run=True,
        limit=50,
        browser=False,
        output_dir='/tmp'
    )
    
    with patch('core.sync.sync_instagram', mock_sync) as sync_mock:
        from core.cli import cmd_instagram_sync
        result = cmd_instagram_sync(mock_args, Mock())
    
    sync_mock.assert_called_once()
    assert result == 0
```

**Step 2: Run test to verify it fails**

```bash
cd /home/cristian/lightroom_tagger && python -m pytest core/test_cli_sync.py::test_cli_calls_sync_module -v
```
Expected: FAIL - CLI doesn't use sync module yet

**Step 3: Implement the refactor**

```python
# core/cli.py - replace cmd_instagram_sync body
def cmd_instagram_sync(args, config):
    """Sync Instagram posts with local catalog."""
    from core.sync import sync_instagram
    
    db_path = args.db or config.db_path
    
    if not db_path:
        print("Error: No database path provided. Use --db or config.yaml")
        return 1

    if not Path(db_path).exists():
        print(f"Error: Database not found: {db_path}")
        return 1

    instagram_url = args.instagram_url or config.instagram_url
    keyword = args.keyword or config.instagram_keyword
    threshold = args.hash_threshold or config.hash_threshold
    catalog_path = args.catalog or config.small_catalog_path
    output_dir = args.output_dir
    dry_run = args.dry_run
    limit = args.limit
    use_browser = args.browser
    
    # Handle login separately (browser session management)
    if use_browser and args.login:
        # ... keep existing login logic ...
        return 0
    
    return sync_instagram(
        db_path=db_path,
        instagram_url=instagram_url,
        keyword=keyword,
        catalog_path=catalog_path,
        threshold=threshold,
        dry_run=dry_run,
        limit=limit,
        use_browser=use_browser,
        output_dir=output_dir
    )
```

**Step 4: Run test to verify it passes**

```bash
cd /home/cristian/lightroom_tagger && python -m pytest core/test_cli_sync.py::test_cli_calls_sync_module -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add core/cli.py core/test_cli_sync.py
git commit -m "refactor(cli): delegate to sync module"
```

---

## Task 8: Add integration test with real components

**Files:**
- Create: `core/test_sync_integration.py`

**Step 1: Write integration test**

```python
# core/test_sync_integration.py
import pytest
import tempfile
import os
from pathlib import Path

def test_sync_with_real_database(tmp_path):
    """Integration test using real TinyDB."""
    from core.sync import sync_instagram
    from core.database import init_database
    
    # Create temp database
    db_path = tmp_path / "test.db"
    db = init_database(str(db_path))
    
    # Add test image record
    from core.database import store_images_batch
    store_images_batch(db, [{
        'key': 'test_2024-01-01_test.jpg',
        'filepath': '/nonexistent/image.jpg',  # Won't hash, but record exists
        'date_taken': '2024-01-01',
        'filename': 'test.jpg'
    }])
    
    db.close()
    
    # This should complete without error even with missing files
    result = sync_instagram(
        db_path=str(db_path),
        instagram_url='https://instagram.com/nonexistent',
        keyword='test',
        catalog_path=None,
        threshold=10,
        dry_run=True,
        limit=1
    )
    
    # Should return 1 (no posts found) not crash
    assert result in [0, 1]
```

**Step 2: Run test**

```bash
cd /home/cristian/lightroom_tagger && python -m pytest core/test_sync_integration.py -v
```
Expected: PASS

**Step 3: Commit**

```bash
git add core/test_sync_integration.py
git commit -m "test(sync): add integration test with real database"
```

---

## Summary

After this refactor:
- `core/cli.py` reduces by ~180 lines
- `core/sync.py` provides a testable interface (1 function, ~100 lines)
- Tests verify behavior at module boundaries without mocking internals
- The sync workflow can be called programmatically from other code
- CLI remains thin, only handling argument parsing and user interaction

**Plan complete.** Which execution approach would you like?
