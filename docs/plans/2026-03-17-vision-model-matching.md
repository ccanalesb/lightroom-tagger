# Vision Model Matching Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add vision model comparison (Qwen2.5-VL via Ollama) as third signal in matching, alongside phash and description similarity.

**Architecture:** Add vision comparison to analyzer module. Extend matcher to include vision scoring (one-by-one comparison with candidates). Add vision_weight parameter to CLI. Store vision results in matches table.

**Tech Stack:** Python, Ollama (qwen2.5-vl:7b), TinyDB

---

## Task 1: Vision Comparison Function in Analyzer

**Files:**
- Modify: `core/analyzer.py`
- Modify: `core/test_analyzer.py`

**Step 1: Write the failing test**

```python
# core/test_analyzer.py - add test
def test_compare_with_vision_returns_result():
    """Vision comparison should return SAME, DIFFERENT, or UNCERTAIN."""
    with patch('core.analyzer.run_vision_ollama', return_value='SAME'):
        result = compare_with_vision('/tmp/local.jpg', '/tmp/insta.jpg')
    
    assert result in ['SAME', 'DIFFERENT', 'UNCERTAIN']
    assert result == 'SAME'
```

**Step 2: Run test to verify it fails**

```bash
cd /home/cristian/lightroom_tagger && python3 -m pytest core/test_analyzer.py::test_compare_with_vision_returns_result -v
```
Expected: FAIL - function not defined

**Step 3: Write implementation**

```python
# core/analyzer.py - add function
def compare_with_vision(local_path: str, insta_path: str) -> str:
    """Compare two images using vision model via Ollama.
    
    Returns: 'SAME' | 'DIFFERENT' | 'UNCERTAIN'
    """
    return run_vision_ollama(local_path, insta_path)

def run_vision_ollama(local_path: str, insta_path: str) -> str:
    """Run Qwen2.5-VL via Ollama to compare images."""
    import subprocess
    import json
    
    prompt = """You are given two images. Determine if they depict the same subject or scene.
Image 1 may be lower quality, compressed, or degraded.
Focus on semantic content, not pixel-level accuracy.

Reply with ONLY: SAME / DIFFERENT / UNCERTAIN"""

    try:
        result = subprocess.run([
            'ollama', 'run', 'qwen2.5-vl:7b',
            f'Image 1: {local_path}',
            f'Image 2: {insta_path}',
            prompt
        ], capture_output=True, text=True, timeout=120)
        
        output = result.stdout.strip().upper()
        if 'SAME' in output:
            return 'SAME'
        elif 'DIFFERENT' in output:
            return 'DIFFERENT'
        return 'UNCERTAIN'
    except Exception:
        return 'UNCERTAIN'

def vision_score(result: str) -> float:
    """Convert vision result to score."""
    if result == 'SAME':
        return 1.0
    elif result == 'DIFFERENT':
        return 0.0
    return 0.5  # UNCERTAIN
```

**Step 4: Run test to verify it passes**

```bash
cd /home/cristian/lightroom_tagger && python3 -m pytest core/test_analyzer.py::test_compare_with_vision_returns_result -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add core/analyzer.py core/test_analyzer.py
git commit -m "feat(analyzer): add vision comparison via Ollama"
```

---

## Task 2: Add Vision Result to Database Schema

**Files:**
- Modify: `core/database.py`
- Modify: `core/test_database.py`

**Step 1: Write the failing test**

```python
# core/test_database.py - add test to TestInstagramStatus class
def test_store_match_includes_vision():
    """Store match should include vision result."""
    from core.database import store_match
    
    store_match(self.db, {
        'catalog_key': '2024-01-15_sunset.jpg',
        'insta_key': 'insta_2024-01-16_post123',
        'vision_result': 'SAME',
        'total_score': 0.85
    })
    
    Match = Query()
    result = self.db.table('matches').search(Match.catalog_key == '2024-01-15_sunset.jpg')
    assert len(result) == 1
    assert result[0]['vision_result'] == 'SAME'
```

**Step 2: Run test to verify it fails**

```bash
cd /home/cristian/lightroom_tagger && python3 -m pytest core/test_database.py::TestInstagramStatus::test_store_match_includes_vision -v
```
Expected: PASS (TinyDB is flexible, already stores any fields)

**Step 3: Commit**

```bash
git add core/test_database.py
git commit -m "test(database): verify vision_result stored in matches"
```

---

## Task 3: Update Matcher with Vision Scoring

**Files:**
- Modify: `core/matcher.py`
- Modify: `core/test_matcher.py`

**Step 1: Write the failing test**

```python
# core/test_matcher.py - add test
def test_score_candidates_includes_vision():
    """Should include vision score when comparing."""
    insta_image = {
        'key': 'insta_test',
        'phash': 'a1b2c3d4e5f6g7h8',
        'description': 'sunset over bay',
        'local_path': '/tmp/insta.jpg'
    }
    
    candidates = [
        {'key': 'cat1', 'phash': 'a1b2c3d4e5f6g7h8', 'description': 'sunset', 'filepath': '/tmp/local1.jpg'},
    ]
    
    with patch('core.matcher.compare_with_vision', return_value='SAME') as vision_mock:
        results = score_candidates_with_vision(
            insta_image, candidates,
            phash_weight=0.4, desc_weight=0.3, vision_weight=0.3
        )
    
    assert len(results) == 1
    assert results[0]['vision_result'] == 'SAME'
    assert results[0]['vision_score'] == 1.0
```

**Step 2: Run test to verify it fails**

```bash
cd /home/cristian/lightroom_tagger && python3 -m pytest core/test_matcher.py::test_score_candidates_includes_vision -v
```
Expected: FAIL - function not defined

**Step 3: Write implementation**

```python
# core/matcher.py - add functions
def score_candidates_with_vision(insta_image: dict, candidates: list, 
                                  phash_weight: float = 0.4, desc_weight: float = 0.3, 
                                  vision_weight: float = 0.3) -> List[dict]:
    """Score candidates including vision comparison (one-by-one)."""
    from core.phash import hamming_distance
    from core.analyzer import compare_with_vision, vision_score
    
    results = []
    
    for candidate in candidates:
        # phash score
        phash_dist = hamming_distance(insta_image.get('phash', ''), candidate.get('phash', ''))
        phash_score_val = max(0, 1 - (phash_dist / 16))
        
        # description score
        desc_sim = text_similarity(insta_image.get('description', ''), candidate.get('description', ''))
        
        # vision score (one-by-one)
        insta_path = insta_image.get('local_path')
        local_path = candidate.get('filepath')
        
        if insta_path and local_path:
            try:
                vision_result = compare_with_vision(local_path, insta_path)
                vision_score_val = vision_score(vision_result)
            except Exception:
                vision_result = 'UNCERTAIN'
                vision_score_val = 0.5
        else:
            vision_result = 'UNCERTAIN'
            vision_score_val = 0.5
        
        total = (phash_weight * phash_score_val) + \
                (desc_weight * desc_sim) + \
                (vision_weight * vision_score_val)
        
        results.append({
            'catalog_key': candidate.get('key'),
            'insta_key': insta_image.get('key'),
            'phash_distance': phash_dist,
            'phash_score': phash_score_val,
            'desc_similarity': desc_sim,
            'vision_result': vision_result,
            'vision_score': vision_score_val,
            'total_score': total
        })
    
    return sorted(results, key=lambda x: x['total_score'], reverse=True)
```

**Step 4: Update match_image to use vision**

```python
# core/matcher.py - update match_image function signature and implementation
def match_image(db, insta_image: dict, threshold: float = 0.7, 
                phash_weight: float = 0.4, desc_weight: float = 0.3, 
                vision_weight: float = 0.3) -> List[dict]:
    """Match single Instagram image against catalog with vision comparison."""
    insta_exif = insta_image.get('exif', {})
    
    candidates = query_by_exif(db, insta_exif)
    
    if not candidates:
        return []
    
    scored = score_candidates_with_vision(
        insta_image, candidates, 
        phash_weight, desc_weight, vision_weight
    )
    
    matches = [m for m in scored if m['total_score'] >= threshold]
    
    for match in matches:
        store_match(db, match)
    
    return matches

# Update match_batch too
def match_batch(db, insta_images: list, threshold: float = 0.7, 
                phash_weight: float = 0.4, desc_weight: float = 0.3, 
                vision_weight: float = 0.3) -> dict:
    """Match multiple Instagram images against catalog."""
    total_matches = 0
    total_candidates = 0
    
    for insta_image in insta_images:
        matches = match_image(
            db, insta_image, threshold, 
            phash_weight, desc_weight, vision_weight
        )
        if matches:
            total_matches += 1
            total_candidates += len(matches)
    
    return {
        'total_matches': total_matches,
        'total_candidates': total_candidates
    }
```

**Step 5: Run test to verify it passes**

```bash
cd /home/cristian/lightroom_tagger && python3 -m pytest core/test_matcher.py::test_score_candidates_includes_vision -v
```
Expected: PASS

**Step 6: Commit**

```bash
git add core/matcher.py core/test_matcher.py
git commit -m "feat(matcher): add vision scoring to matching"
```

---

## Task 4: Update CLI with Vision Weight

**Files:**
- Modify: `core/cli.py`

**Step 1: Add --vision-weight argument**

```python
# core/cli.py - add to match_parser
match_parser.add_argument(
    "--vision-weight",
    type=float,
    default=0.3,
    help="Vision model weight in scoring (default 0.3)"
)
```

**Step 2: Update cmd_match function**

```python
# core/cli.py - update cmd_match to pass vision_weight
def cmd_match(args, config):
    """Match Instagram images against catalog."""
    from core.matcher import match_batch
    from core.database import init_matches_table, init_catalog_table, init_instagram_table
    
    # ... existing code ...
    
    threshold = args.threshold or 0.7
    phash_weight = args.phash_weight or 0.4
    desc_weight = 0.3
    vision_weight = args.vision_weight or 0.3
    
    # ... rest of function, update the call:
    result = match_batch(db, insta_images, threshold, phash_weight, desc_weight, vision_weight)
```

**Step 3: Test CLI**

```bash
cd /home/cristian/lightroom_tagger && python3 -c "from core.cli import create_parser; p = create_parser(); p.parse_args(['match', '--help'])"
```
Expected: Shows --vision-weight option

**Step 4: Commit**

```bash
git add core/cli.py
git commit -m "feat(cli): add --vision-weight to match command"
```

---

## Summary

After implementation:
- `core/analyzer.py` - Added `compare_with_vision()` using Ollama Qwen2.5-VL
- `core/matcher.py` - Added `score_candidates_with_vision()` for one-by-one vision comparison
- `core/cli.py` - Added `--vision-weight` parameter (default 0.3)
- Database stores `vision_result` (SAME/DIFFERENT/UNCERTAIN) and `vision_score` in matches table

**Usage:**
```bash
lightroom-tagger match --db library.db --threshold 0.7 --vision-weight 0.3
```

**Plan complete.** Which execution approach would you like?
