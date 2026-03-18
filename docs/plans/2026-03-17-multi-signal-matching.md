# Multi-Signal Matching Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement multi-signal image matching combining phash, EXIF, and agent-generated descriptions. All stored in TinyDB for on-demand matching.

**Architecture:** Create analyzer module → extend database with new tables → create matcher → add CLI commands. Each module independent, testable at boundaries.

**Tech Stack:** Python, TinyDB, PIL, imagehash, (local/external vision model)

---

## Task 1: Image Analyzer Module

**Files:**
- Create: `core/analyzer.py`
- Create: `core/test_analyzer.py`

**Step 1: Write the failing test**

```python
# core/test_analyzer.py
import pytest
from unittest.mock import Mock, patch, MagicMock
from core.analyzer import analyze_image

def test_analyze_image_returns_all_signals():
    """Analyzer should return phash, exif, and description."""
    with patch('core.analyzer.compute_phash', return_value='a1b2c3d4e5f6g7h8'), \
         patch('core.analyzer.extract_exif', return_value={'camera': 'Canon EOS R5'}), \
         patch('core.analyzer.describe_image', return_value='A sunset photo'):
        
        result = analyze_image('/fake/path.jpg')
    
    assert result['phash'] == 'a1b2c3d4e5f6g7h8'
    assert result['exif']['camera'] == 'Canon EOS R5'
    assert result['description'] == 'A sunset photo'
```

**Step 2: Run test to verify it fails**

```bash
cd /home/cristian/lightroom_tagger && python -m pytest core/test_analyzer.py::test_analyze_image_returns_all_signals -v
```
Expected: FAIL - ModuleNotFoundError: No module named 'core.analyzer'

**Step 3: Write minimal implementation**

```python
# core/analyzer.py
from typing import Dict, Any, Optional

def analyze_image(path: str) -> Dict[str, Any]:
    """Analyze image and return all matching signals.
    
    Returns:
        {phash, exif: {camera, lens, date_taken, gps, ...}, description}
    """
    phash = compute_phash(path)
    exif = extract_exif(path)
    description = describe_image(path)
    
    return {
        'phash': phash,
        'exif': exif,
        'description': description
    }

def compute_phash(path: str) -> Optional[str]:
    """Placeholder - delegate to existing hasher."""
    from lightroom_tagger.core.hasher import compute_phash as _compute
    try:
        return _compute(path)
    except Exception:
        return None

def extract_exif(path: str) -> Dict[str, Any]:
    """Extract EXIF metadata from image."""
    from PIL import Image
    from PIL.ExifTags import TAGS
    import os
    
    result = {}
    try:
        with Image.open(path) as img:
            exif = img._getexif()
            if exif:
                for tag_id, value in exif.items():
                    tag = TAGS.get(tag_id, tag_id)
                    if tag in ['Make', 'Model', 'DateTime', 'LensModel', 'ISOSpeedRatings', 
                              'FNumber', 'ExposureTime', 'GPSInfo']:
                        result[tag.lower()] = str(value)
    except Exception:
        pass
    return result

def describe_image(path: str) -> str:
    """Generate description using configured agent."""
    # Placeholder - will implement with config-based agent
    return ""
```

**Step 4: Run test to verify it passes**

```bash
cd /home/cristian/lightroom_tagger && python -m pytest core/test_analyzer.py::test_analyze_image_returns_all_signals -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add core/analyzer.py core/test_analyzer.py
git commit -m "feat(analyzer): create image analyzer module"
```

---

## Task 2: Agent Description Integration

**Files:**
- Modify: `core/analyzer.py`
- Modify: `core/test_analyzer.py`
- Modify: `core/config.py`

**Step 1: Write the failing test**

```python
# core/test_analyzer.py - add test
def test_describe_image_uses_configured_agent():
    """Should use local or external agent based on config."""
    from core.config import Config
    
    with patch('core.analyzer.run_local_agent', return_value='local desc') as local_mock, \
         patch('core.analyzer.run_external_agent', return_value='external desc') as ext_mock:
        
        # Test local agent
        describe_image('/fake/path.jpg', agent_type='local')
        local_mock.assert_called_once()
        
        # Test external agent
        describe_image('/fake/path.jpg', agent_type='external')
        ext_mock.assert_called_once()
```

**Step 2: Run test to verify it fails**

```bash
cd /home/cristian/lightroom_tagger && python -m pytest core/test_analyzer.py::test_describe_image_uses_configured_agent -v
```
Expected: FAIL - functions don't exist

**Step 3: Implement agent functions**

```python
# core/analyzer.py - add to file
import subprocess
import os
from core.config import load_config

def describe_image(path: str, agent_type: str = None) -> str:
    """Generate image description using configured agent."""
    if agent_type is None:
        config = load_config()
        agent_type = getattr(config, 'agent_type', 'local')
    
    if agent_type == 'local':
        return run_local_agent(path)
    elif agent_type == 'external':
        return run_external_agent(path)
    return ""

def run_local_agent(path: str) -> str:
    """Run local vision model (e.g., LLaVA)."""
    # TODO: Implement local model call
    # Example: subprocess.run(['llava', 'describe', path], capture_output=True)
    return ""

def run_external_agent(path: str) -> str:
    """Run external API (e.g., Claude, GPT-4V)."""
    # TODO: Implement external API call
    # Example: call Claude Vision API
    return ""
```

**Step 4: Run test to verify it passes**

```bash
cd /home/cristian/lightroom_tagger && python -m pytest core/test_analyzer.py::test_describe_image_uses_configured_agent -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add core/analyzer.py core/test_analyzer.py
git commit -m "feat(analyzer): add agent description integration"
```

---

## Task 3: Database Extension for New Tables

**Files:**
- Modify: `core/database.py`
- Modify: `core/test_database.py`

**Step 1: Write the failing test**

```python
# core/test_database.py - add tests
def test_store_catalog_image():
    """Store catalog image with analysis data."""
    db = init_database(':memory:')
    
    key = store_catalog_image(db, {
        'key': '2024-01-15_sunset.jpg',
        'filepath': '/mnt/nas/photos/sunset.jpg',
        'phash': 'a1b2c3d4e5f6g7h8',
        'exif': {'camera': 'Canon EOS R5', 'lens': 'RF 24-70mm'},
        'description': 'Golden hour sunset'
    })
    
    assert key == '2024-01-15_sunset.jpg'
    Image = Query()
    result = db.search(Image.key == key)
    assert len(result) == 1
    assert result[0]['phash'] == 'a1b2c3d4e5f6g7h8'

def test_store_instagram_image():
    """Store Instagram image with analysis data."""
    db = init_database(':memory:')
    
    key = store_instagram_image(db, {
        'post_url': 'https://instagram.com/p/abc123',
        'local_path': '/tmp/insta.jpg',
        'phash': 'a1b2c3d4e5f6g7h8',
        'exif': {'camera': 'Canon EOS R5'},
        'description': 'Beautiful sunset'
    })
    
    assert key.startswith('insta_')
    Image = Query()
    result = db.search(Image.key == key)
    assert len(result) == 1

def test_store_match():
    """Store match between catalog and Instagram image."""
    db = init_database(':memory:')
    
    store_match(db, {
        'catalog_key': '2024-01-15_sunset.jpg',
        'insta_key': 'insta_2024-01-16_post123',
        'phash_distance': 2,
        'phash_score': 0.875,
        'desc_similarity': 0.82,
        'exif_camera_match': True,
        'exif_lens_match': True,
        'total_score': 0.85
    })
    
    Match = Query()
    result = db.search(Match.catalog_key == '2024-01-15_sunset.jpg')
    assert len(result) == 1
    assert result[0]['total_score'] == 0.85
```

**Step 2: Run test to verify it fails**

```bash
cd /home/cristian/lightroom_tagger && python -m pytest core/test_database.py::test_store_catalog_image core/test_database.py::test_store_instagram_image core/test_database.py::test_store_match -v
```
Expected: FAIL - functions don't exist

**Step 3: Implement database functions**

```python
# core/database.py - add functions
from datetime import datetime

def init_catalog_table(db: TinyDB):
    """Ensure catalog_images table exists."""
    if 'catalog_images' not in db.tables:
        db.table('catalog_images')

def init_instagram_table(db: TinyDB):
    """Ensure instagram_images table exists."""
    if 'instagram_images' not in db.tables:
        db.table('instagram_images')

def init_matches_table(db: TinyDB):
    """Ensure matches table exists."""
    if 'matches' not in db.tables:
        db.table('matches')

def store_catalog_image(db, record: dict) -> str:
    """Store catalog image with analysis. Idempotent."""
    from tinydb import Query
    Catalog = Query()
    
    key = record.get('key')
    record['analyzed_at'] = datetime.now().isoformat()
    
    existing = db.table('catalog_images').search(Catalog.key == key)
    if existing:
        db.table('catalog_images').update(record, Catalog.key == key)
    else:
        db.table('catalog_images').insert(record)
    
    return key

def store_instagram_image(db, record: dict) -> str:
    """Store Instagram image with analysis. Idempotent by post_url."""
    from tinydb import Query
    Insta = Query()
    
    post_url = record.get('post_url')
    key = f"insta_{datetime.now().strftime('%Y-%m-%d')}_{post_url.split('/')[-2]}"
    record['key'] = key
    record['crawled_at'] = datetime.now().isoformat()
    
    existing = db.table('instagram_images').search(Insta.post_url == post_url)
    if existing:
        db.table('instagram_images').update(record, Insta.post_url == post_url)
    else:
        db.table('instagram_images').insert(record)
    
    return key

def store_match(db, record: dict) -> str:
    """Store match between catalog and Instagram image."""
    from tinydb import Query
    Match = Query()
    
    catalog_key = record.get('catalog_key')
    insta_key = record.get('insta_key')
    record['matched_at'] = datetime.now().isoformat()
    
    existing = db.table('matches').search(
        (Match.catalog_key == catalog_key) & (Match.insta_key == insta_key)
    )
    if existing:
        db.table('matches').update(record, (Match.catalog_key == catalog_key) & (Match.insta_key == insta_key))
    else:
        db.table('matches').insert(record)
    
    return f"{catalog_key} <-> {insta_key}"

def get_catalog_images_needing_analysis(db) -> list:
    """Get catalog images without phash."""
    from tinydb import Query
    Catalog = Query()
    return db.table('catalog_images').search(Catalog.phash == None)

def get_instagram_images_needing_analysis(db) -> list:
    """Get Instagram images without phash."""
    from tinydb import Query
    Insta = Query()
    return db.table('instagram_images').search(Insta.phash == None)
```

**Step 4: Run test to verify it passes**

```bash
cd /home/cristian/lightroom_tagger && python -m pytest core/test_database.py::test_store_catalog_image core/test_database.py::test_store_instagram_image core/test_database.py::test_store_match -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add core/database.py core/test_database.py
git commit -m "feat(database): add catalog_images, instagram_images, matches tables"
```

---

## Task 4: Catalog Enricher

**Files:**
- Create: `lightroom/enricher.py`
- Create: `lightroom/test_enricher.py`

**Step 1: Write the failing test**

```python
# lightroom/test_enricher.py
import pytest
from unittest.mock import Mock, patch
from lightroom.enricher import enrich_catalog_images

def test_enrich_skips_already_analyzed():
    """Should skip images that already have phash."""
    mock_db = Mock()
    mock_db.table.return_value.search.return_value = []  # No images needing analysis
    
    with patch('lightroom.enricher.get_catalog_images_needing_analysis', return_value=[]):
        result = enrich_catalog_images(mock_db, limit=10)
    
    assert result['processed'] == 0
    assert result['skipped'] == 0

def test_enrich_processes_images():
    """Should analyze images without phash."""
    mock_db = Mock()
    mock_db.table.return_value.search.return_value = [
        {'key': '2024-01-15_sunset.jpg', 'filepath': '/tmp/test.jpg'}
    ]
    
    with patch('lightroom.enricher.get_catalog_images_needing_analysis', return_value=[
        {'key': '2024-01-15_sunset.jpg', 'filepath': '/tmp/test.jpg'}
    ]), \
    patch('lightroom.enricher.analyze_image', return_value={
        'phash': 'a1b2c3d4e5f6g7h8',
        'exif': {'camera': 'Canon'},
        'description': 'Sunset'
    }) as analyze_mock, \
    patch('lightroom.enricher.store_catalog_image') as store_mock:
        
        result = enrich_catalog_images(mock_db)
    
    analyze_mock.assert_called_once()
    store_mock.assert_called_once()
    assert result['processed'] == 1
```

**Step 2: Run test to verify it fails**

```bash
cd /home/cristian/lightroom_tagger && python -m pytest lightroom/test_enricher.py::test_enrich_processes_images -v
```
Expected: FAIL - ModuleNotFoundError

**Step 3: Write minimal implementation**

```python
# lightroom/enricher.py
from typing import Optional
from core.analyzer import analyze_image
from core.database import store_catalog_image, get_catalog_images_needing_analysis

def enrich_catalog_images(db, catalog_path: str = None, limit: int = None) -> dict:
    """Analyze and store metadata for catalog images.
    
    Returns:
        {processed: N, skipped: N, errors: N}
    """
    images_needing_analysis = get_catalog_images_needing_analysis(db)
    
    if limit:
        images_needing_analysis = images_needing_analysis[:limit]
    
    processed = 0
    errors = 0
    
    for record in images_needing_analysis:
        filepath = record.get('filepath')
        if not filepath:
            continue
        
        try:
            analysis = analyze_image(filepath)
            record.update(analysis)
            store_catalog_image(db, record)
            processed += 1
        except Exception as e:
            errors += 1
    
    return {
        'processed': processed,
        'skipped': len(images_needing_analysis) - processed,
        'errors': errors
    }
```

**Step 4: Run test to verify it passes**

```bash
cd /home/cristian/lightroom_tagger && python -m pytest lightroom/test_enricher.py::test_enrich_processes_images -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add lightroom/enricher.py lightroom/test_enricher.py
git commit -m "feat(enricher): create catalog enricher module"
```

---

## Task 5: Instagram Crawler with Analysis

**Files:**
- Create: `instagram/crawler.py`
- Create: `instagram/test_crawler.py`

**Step 1: Write the failing test**

```python
# instagram/test_crawler.py
import pytest
from unittest.mock import Mock, patch, MagicMock
from instagram.crawler import crawl_and_analyze

def test_crawl_analyzes_fetched_images():
    """Should analyze each fetched Instagram image."""
    mock_db = Mock()
    
    mock_post = Mock()
    mock_post.post_url = 'https://instagram.com/p/abc123'
    mock_post.index = 0
    
    with patch('instagram.crawler.crawl_instagram', return_value=([mock_post], {'https://instagram.com/p/abc123': ['/tmp/insta1.jpg']})), \
         patch('instagram.crawler.analyze_image', return_value={'phash': 'abc', 'exif': {}, 'desc': 'test'}) as analyze_mock, \
         patch('instagram.crawler.store_instagram_image') as store_mock:
        
        result = crawl_and_analyze(mock_db, 'testuser', '/tmp', limit=10)
    
    analyze_mock.assert_called()
    store_mock.assert_called()
    assert result['processed'] == 1
```

**Step 2: Run test to verify it fails**

```bash
cd /home/cristian/lightroom_tagger && python -m pytest instagram/test_crawler.py::test_crawl_analyzes_fetched_images -v
```
Expected: FAIL - ModuleNotFoundError

**Step 3: Implement crawler**

```python
# instagram/crawler.py
from typing import Optional
from core.analyzer import analyze_image
from core.database import store_instagram_image

def crawl_and_analyze(db, username: str, output_dir: str, limit: int = 50) -> dict:
    """Crawl Instagram and analyze images.
    
    Returns:
        {processed: N, skipped: N, errors: N}
    """
    from instagram.scraper import crawl_instagram
    
    posts, url_to_path = crawl_instagram(None, output_dir, limit=limit)
    
    processed = 0
    errors = 0
    
    for post in posts:
        local_paths = url_to_path.get(post.post_url, [])
        for local_path in local_paths:
            try:
                analysis = analyze_image(local_path)
                record = {
                    'post_url': post.post_url,
                    'local_path': local_path,
                    **analysis
                }
                store_instagram_image(db, record)
                processed += 1
            except Exception as e:
                errors += 1
    
    return {
        'processed': processed,
        'skipped': len(posts) - processed,
        'errors': errors
    }
```

**Step 4: Run test to verify it passes**

```bash
cd /home/cristian/lightroom_tagger && python -m pytest instagram/test_crawler.py::test_crawl_analyzes_fetched_images -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add instagram/crawler.py instagram/test_crawler.py
git commit -m "feat(crawler): create instagram crawler with analysis"
```

---

## Task 6: Matcher Module

**Files:**
- Create: `core/matcher.py`
- Create: `core/test_matcher.py`

**Step 1: Write the failing test**

```python
# core/test_matcher.py
import pytest
from unittest.mock import Mock, patch
from core.matcher import match_image, match_batch

def test_match_filters_by_exif():
    """Should filter candidates by EXIF first."""
    mock_db = Mock()
    
    insta_image = {
        'key': 'insta_test',
        'phash': 'a1b2c3d4e5f6g7h8',
        'exif': {'camera': 'Canon EOS R5', 'lens': 'RF 24-70mm'}
    }
    
    catalog_candidates = [
        {'key': 'cat1', 'phash': 'a1b2c3d4e5f6g7h8', 'exif': {'camera': 'Canon EOS R5', 'lens': 'RF 24-70mm'}, 'description': 'sunset'},
        {'key': 'cat2', 'phash': 'xyzxyzxyzxyzxy', 'exif': {'camera': 'Sony A7', 'lens': '24-70mm'}, 'description': 'portrait'},
    ]
    
    with patch('core.matcher.query_by_exif', return_value=[catalog_candidates[0]]), \
         patch('core.matcher.score_candidates', return_value=[{'catalog_key': 'cat1', 'total_score': 0.9}]):
        
        result = match_image(mock_db, insta_image, threshold=0.7)
    
    assert len(result) == 1
    assert result[0]['catalog_key'] == 'cat1'

def test_match_batch():
    """Should match multiple Instagram images."""
    mock_db = Mock()
    
    insta_images = [
        {'key': 'insta1', 'phash': 'abc', 'exif': {'camera': 'Canon'}},
        {'key': 'insta2', 'phash': 'xyz', 'exif': {'camera': 'Sony'}},
    ]
    
    with patch('core.matcher.match_image', return_value=[{'catalog_key': 'cat1'}]):
        result = match_batch(mock_db, insta_images, threshold=0.7)
    
    assert result['total_matches'] == 2
```

**Step 2: Run test to verify it fails**

```bash
cd /home/cristian/lightroom_tagger && python -m pytest core/test_matcher.py::test_match_filters_by_exif -v
```
Expected: FAIL - ModuleNotFoundError

**Step 3: Implement matcher**

```python
# core/matcher.py
from typing import List, Dict, Any
from tinydb import Query
from core.database import store_match
from core.phash import hamming_distance

def query_by_exif(db, insta_exif: dict, date_window_days: int = 7) -> List[dict]:
    """Query catalog by EXIF (camera, lens, date within window)."""
    Insta = Query()
    
    camera = insta_exif.get('camera')
    lens = insta_exif.get('lens')
    
    if not camera and not lens:
        return []
    
    conditions = []
    if camera:
        conditions.append(Insta['exif']['camera'] == camera)
    if lens:
        conditions.append(Insta['exif']['lens'] == lens)
    
    return db.table('catalog_images').search(conditions[0])

def score_candidates(insta_image: dict, candidates: list, phash_weight: float = 0.5, desc_weight: float = 0.5) -> List[dict]:
    """Score candidates by phash distance + description similarity."""
    results = []
    
    for candidate in candidates:
        phash_dist = hamming_distance(insta_image.get('phash', ''), candidate.get('phash', ''))
        phash_score = max(0, 1 - (phash_dist / 16))  # Normalize to 0-1
        
        desc_sim = text_similarity(insta_image.get('description', ''), candidate.get('description', ''))
        
        total = (phash_weight * phash_score) + (desc_weight * desc_sim)
        
        results.append({
            'catalog_key': candidate.get('key'),
            'insta_key': insta_image.get('key'),
            'phash_distance': phash_dist,
            'phash_score': phash_score,
            'desc_similarity': desc_sim,
            'total_score': total
        })
    
    return sorted(results, key=lambda x: x['total_score'], reverse=True)

def text_similarity(text1: str, text2: str) -> float:
    """Simple text similarity using common words."""
    if not text1 or not text2:
        return 0.0
    
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    if not words1 or not words2:
        return 0.0
    
    intersection = len(words1 & words2)
    union = len(words1 | words2)
    
    return intersection / union if union > 0 else 0.0

def match_image(db, insta_image: dict, threshold: float = 0.7, phash_weight: float = 0.5, desc_weight: float = 0.5) -> List[dict]:
    """Match single Instagram image against catalog."""
    insta_exif = insta_image.get('exif', {})
    
    candidates = query_by_exif(db, insta_exif)
    
    if not candidates:
        return []
    
    scored = score_candidates(insta_image, candidates, phash_weight, desc_weight)
    
    matches = [m for m in scored if m['total_score'] >= threshold]
    
    for match in matches:
        store_match(db, match)
    
    return matches

def match_batch(db, insta_images: list, threshold: float = 0.7, phash_weight: float = 0.5, desc_weight: float = 0.5) -> dict:
    """Match multiple Instagram images against catalog."""
    total_matches = 0
    total_candidates = 0
    
    for insta_image in insta_images:
        matches = match_image(db, insta_image, threshold, phash_weight, desc_weight)
        if matches:
            total_matches += 1
            total_candidates += len(matches)
    
    return {
        'total_matches': total_matches,
        'total_candidates': total_candidates
    }
```

**Step 4: Run test to verify it passes**

```bash
cd /home/cristian/lightroom_tagger && python -m pytest core/test_matcher.py::test_match_filters_by_exif -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add core/matcher.py core/test_matcher.py
git commit -m "feat(matcher): create multi-signal matcher module"
```

---

## Task 7: CLI Commands

**Files:**
- Modify: `core/cli.py`

**Step 1: Add enrich-catalog command**

```python
# core/cli.py - add to create_parser()
parser.add_command('enrich-catalog', help='Analyze Lightroom catalog images')
```

**Step 2: Implement enrich-catalog command**

```python
# core/cli.py - add function
def cmd_enrich_catalog(args, config):
    """Analyze and store metadata for catalog images."""
    from lightroom.enricher import enrich_catalog_images
    from core.database import init_database, init_catalog_table
    
    db_path = args.db or config.db_path
    if not db_path:
        print("Error: No database path provided")
        return 1
    
    db = init_database(db_path)
    init_catalog_table(db)
    
    catalog_path = args.catalog or config.small_catalog_path
    if not catalog_path:
        print("Error: No catalog path provided")
        return 1
    
    print(f"Analyzing images from: {catalog_path}")
    result = enrich_catalog_images(db, catalog_path, limit=args.limit)
    
    print(f"Processed: {result['processed']}")
    print(f"Skipped: {result['skipped']}")
    print(f"Errors: {result['errors']}")
    
    db.close()
    return 0
```

**Step 3: Add crawl-instagram command**

```python
# core/cli.py
def cmd_crawl_instagram(args, config):
    """Crawl Instagram and analyze images."""
    from instagram.crawler import crawl_and_analyze
    from core.database import init_database, init_instagram_table
    
    db_path = args.db or config.db_path
    if not db_path:
        print("Error: No database path provided")
        return 1
    
    db = init_database(db_path)
    init_instagram_table(db)
    
    username = args.username or config.instagram_url
    if not username:
        print("Error: No Instagram username provided")
        return 1
    
    print(f"Crawling Instagram: {username}")
    result = crawl_and_analyze(db, username, args.output_dir or '/tmp', limit=args.limit)
    
    print(f"Processed: {result['processed']}")
    print(f"Skipped: {result['skipped']}")
    print(f"Errors: {result['errors']}")
    
    db.close()
    return 0
```

**Step 4: Add match command**

```python
# core/cli.py
def cmd_match(args, config):
    """Match Instagram images against catalog."""
    from core.matcher import match_batch
    from core.database import init_database, init_matches_table, init_catalog_table, init_instagram_table
    from tinydb import Query
    
    db_path = args.db or config.db_path
    if not db_path:
        print("Error: No database path provided")
        return 1
    
    db = init_database(db_path)
    init_matches_table(db)
    init_catalog_table(db)
    init_instagram_table(db)
    
    threshold = args.threshold or 0.7
    phash_weight = args.phash_weight or 0.5
    
    Insta = Query()
    insta_images = db.table('instagram_images').all()
    
    if not insta_images:
        print("No Instagram images to match. Run crawl-instagram first.")
        return 1
    
    print(f"Matching {len(insta_images)} Instagram images...")
    result = match_batch(db, insta_images, threshold, phash_weight)
    
    print(f"Matched: {result['total_matches']} Instagram images")
    print(f"Total candidates: {result['total_candidates']}")
    
    db.close()
    return 0
```

**Step 5: Add tests for CLI commands**

```python
# core/test_cli_commands.py
import pytest
from unittest.mock import Mock, patch

def test_cli_enrich_catalog_calls_enricher():
    """CLI should delegate to enrich_catalog_images."""
    mock_args = Mock(db='/fake/db.json', catalog='/fake/catalog.lrcat', limit=None)
    mock_config = Mock()
    
    with patch('core.cli.enrich_catalog_images', return_value={'processed': 5, 'skipped': 0, 'errors': 0}) as mock:
        from core.cli import cmd_enrich_catalog
        result = cmd_enrich_catalog(mock_args, mock_config)
    
    assert result == 0

def test_cli_match_calls_matcher():
    """CLI should delegate to match_batch."""
    mock_args = Mock(db='/fake/db.json', threshold=0.7, phash_weight=0.5)
    mock_config = Mock()
    
    with patch('core.cli.match_batch', return_value={'total_matches': 3, 'total_candidates': 5}):
        with patch('core.cli.init_database') as mock_db:
            mock_db.return_value = Mock()
            from core.cli import cmd_match
            result = cmd_match(mock_args, mock_config)
    
    assert result == 0
```

**Step 6: Commit**

```bash
git add core/cli.py
git commit -m "feat(cli): add enrich-catalog, crawl-instagram, match commands"
```

---

## Summary

After implementation:
- `core/analyzer.py` - extracts phash + EXIF + description
- `core/matcher.py` - multi-signal matching with weighted scoring
- `lightroom/enricher.py` - processes catalog images on-demand
- `instagram/crawler.py` - crawls and analyzes Instagram images
- `core/database.py` - extended with 3 new tables
- CLI commands for each workflow step

**Plan complete.** Which execution approach would you like?
