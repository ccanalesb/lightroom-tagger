# Fix Custom Weights Not Passed to match_dump_media Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the bug where `handle_vision_match` computes `custom_weights` from job metadata but never passes them to `match_dump_media`, causing all jobs to use hardcoded default weights (phash=0.4, desc=0.3, vision=0.3) regardless of UI configuration. Also exclude video files from candidates, sort candidates and Instagram images newest-first for faster matching, and retroactively store rejected matches.

**Architecture:** One-line fix in `handlers.py` to pass `weights=custom_weights` to `match_dump_media()`. Video exclusion in `find_candidates_by_date`. Newest-first sort order for both Instagram images (in `get_instagram_by_date_filter`/`get_unprocessed_dump_media`) and catalog candidates (in `find_candidates_by_date`) so the most likely matches are compared first. Retroactive DB fix for matches rejected by the weights bug.

**Tech Stack:** Python, pytest, unittest.mock

**Bug Evidence:** Job `6d21f72e` logs `Weights: phash=0.00, desc=0.00, vision=1.00` (correct metadata) but scoring uses defaults — a 100% vision match produces `total=0.4286` (= 0.3/0.7, the default vision weight divided by default weight sum) instead of `total=1.0`.

---

### File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `apps/visualizer/backend/jobs/handlers.py:172-187` | Modify | Add `weights=custom_weights` to `match_dump_media()` call |
| `apps/visualizer/backend/tests/test_handlers_single_match.py` | Modify | Add test asserting weights are forwarded |
| `lightroom_tagger/core/matcher.py:597-622` | Modify | Skip video files in `find_candidates_by_date` |
| `lightroom_tagger/core/database.py:1221-1241` | Modify | Invalidate video cache entries in `is_vision_cache_valid` |
| `lightroom_tagger/core/test_matcher.py` | Modify | Test that video candidates are excluded |
| `lightroom_tagger/core/database.py:939-974` | Modify | Sort Instagram images newest-first in `get_instagram_by_date_filter` |
| `lightroom_tagger/core/database.py:897-936` | Modify | Sort Instagram images newest-first in `get_unprocessed_dump_media` |
| `library.db` | Data fix | Retroactively store matches rejected by weights bug in job `6d21f72e` |

---

### Task 1: Add test proving weights are forwarded

**Files:**
- Modify: `apps/visualizer/backend/tests/test_handlers_single_match.py`

- [ ] **Step 1: Write the failing test**

Add this test to `apps/visualizer/backend/tests/test_handlers_single_match.py`:

```python
@patch('database.add_job_log')
@patch('jobs.handlers.match_dump_media')
@patch('jobs.handlers.init_database')
@patch('jobs.handlers.load_config')
@patch('jobs.handlers.update_job_field')
@patch('jobs.handlers.os.path.exists', return_value=True)
@patch('jobs.handlers.os.getenv', return_value='/tmp/library.db')
def test_handle_vision_match_passes_custom_weights(mock_getenv, mock_exists, mock_update_field,
                                                    mock_config, mock_init_db, mock_match, _mock_add_log):
    from jobs.handlers import handle_vision_match

    mock_config.return_value = MagicMock(
        vision_model='gemma3:27b', match_threshold=0.7,
        phash_weight=0.4, desc_weight=0.3, vision_weight=0.3,
        ollama_host='http://localhost:11434',
        matching_workers=4,
    )
    mock_match.return_value = ({'processed': 1, 'matched': 0, 'skipped': 0}, [])
    mock_init_db.return_value = MagicMock()

    runner = MagicMock()
    runner.db = MagicMock()

    custom_weights = {'phash': 0.0, 'description': 0.0, 'vision': 1.0}
    handle_vision_match(runner, 'test-job-id', {'weights': custom_weights})

    _, kwargs = mock_match.call_args
    assert kwargs.get('weights') == custom_weights, (
        f"Expected weights={custom_weights}, got weights={kwargs.get('weights')}"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd apps/visualizer/backend && python -m pytest tests/test_handlers_single_match.py::test_handle_vision_match_passes_custom_weights -v
```

Expected: FAIL — `assert kwargs.get('weights') == {'phash': 0.0, 'description': 0.0, 'vision': 1.0}` fails because `weights` is `None` in the call kwargs (not passed).

- [ ] **Step 3: Commit failing test**

```bash
git add apps/visualizer/backend/tests/test_handlers_single_match.py
git commit -m "test: prove custom weights are not forwarded to match_dump_media"
```

---

### Task 2: Pass weights to match_dump_media

**Files:**
- Modify: `apps/visualizer/backend/jobs/handlers.py:172-187`

- [ ] **Step 1: Add `weights=custom_weights` to the call**

In `apps/visualizer/backend/jobs/handlers.py`, change the `match_dump_media` call (line 172-187) from:

```python
            stats, matches = match_dump_media(
                db,
                threshold=custom_threshold,
                month=month,
                year=year,
                last_months=last_months,
                progress_callback=progress_callback,
                log_callback=log_callback,
                media_key=media_key,
                force_descriptions=force_descriptions,
                force_reprocess=force_reprocess,
                provider_id=provider_id,
                provider_model=provider_model,
                max_workers=max_workers,
                should_cancel=lambda: runner.is_cancelled(job_id),
            )
```

to:

```python
            stats, matches = match_dump_media(
                db,
                threshold=custom_threshold,
                month=month,
                year=year,
                last_months=last_months,
                progress_callback=progress_callback,
                log_callback=log_callback,
                weights=custom_weights,
                media_key=media_key,
                force_descriptions=force_descriptions,
                force_reprocess=force_reprocess,
                provider_id=provider_id,
                provider_model=provider_model,
                max_workers=max_workers,
                should_cancel=lambda: runner.is_cancelled(job_id),
            )
```

- [ ] **Step 2: Run the test to verify it passes**

Run:
```bash
cd apps/visualizer/backend && python -m pytest tests/test_handlers_single_match.py -v
```

Expected: Both tests PASS — the new `test_handle_vision_match_passes_custom_weights` and the existing `test_handle_vision_match_passes_media_key`.

- [ ] **Step 3: Run all existing tests to check for regressions**

Run:
```bash
cd apps/visualizer/backend && python -m pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 4: Commit**

```bash
git add apps/visualizer/backend/jobs/handlers.py apps/visualizer/backend/tests/test_handlers_single_match.py
git commit -m "fix: forward custom weights from job metadata to match_dump_media

handle_vision_match computed custom_weights from job metadata but never
passed them to match_dump_media(), causing all jobs to silently use
hardcoded defaults (phash=0.4, desc=0.3, vision=0.3). A 100% vision
match with weights phash=0, desc=0, vision=1 scored total=0.4286,
below the 0.7 threshold — rejecting correct matches."
```

---

### Task 3: Skip video files in candidate selection and invalidate stale video cache entries

The catalog contains 51 video files (32 `.mp4`, 19 `.mov`) that are useless for vision comparison. One of them (`2025-02-13_f3260416_ftyp.mov`, 48MB) falls in the 90-day window for year=2025 jobs and causes 4 wasted API calls per Instagram image (batch 35/104 hits 413 every time, splits down to single-item, still too large). Videos should never be candidates.

Additionally, 47 video files have stale vision cache entries pointing to their original multi-GB paths. These need to be invalidated so `get_or_create_cached_image` returns `None` for them.

**Files:**
- Modify: `lightroom_tagger/core/matcher.py:597-622`
- Modify: `lightroom_tagger/core/database.py:1221-1241`
- Modify: `lightroom_tagger/core/test_matcher.py`

- [ ] **Step 1: Define VIDEO_EXTENSIONS constant**

Add to `lightroom_tagger/core/analyzer.py` next to the existing `RAW_EXTENSIONS`:

```python
VIDEO_EXTENSIONS = {'.mov', '.mp4', '.avi', '.mkv', '.wmv', '.m4v', '.3gp', '.webm', '.mts', '.m2ts'}
```

- [ ] **Step 2: Write failing test for video candidate filtering**

Add to `lightroom_tagger/core/test_matcher.py`:

```python
from lightroom_tagger.core.matcher import find_candidates_by_date


class TestFindCandidatesByDate:
    def test_excludes_video_files(self):
        """Video files (.mov, .mp4, etc.) should never appear as candidates."""
        db = MagicMock()
        rows = [
            {'key': 'img1', 'date_taken': '2025-01-15T12:00:00', 'filepath': '/photos/img1.arw'},
            {'key': 'vid1', 'date_taken': '2025-01-15T12:00:00', 'filepath': '/photos/vid1.mov'},
            {'key': 'vid2', 'date_taken': '2025-01-15T12:00:00', 'filepath': '/photos/vid2.MP4'},
            {'key': 'img2', 'date_taken': '2025-01-15T12:00:00', 'filepath': '/photos/img2.jpg'},
        ]
        db.execute.return_value.fetchall.return_value = rows

        insta_image = {'date_folder': '202502'}
        candidates = find_candidates_by_date(db, insta_image, days_before=90)

        keys = [c['key'] for c in candidates]
        assert 'img1' in keys
        assert 'img2' in keys
        assert 'vid1' not in keys
        assert 'vid2' not in keys
```

- [ ] **Step 3: Run test to verify it fails**

Run:
```bash
pytest lightroom_tagger/core/test_matcher.py::TestFindCandidatesByDate::test_excludes_video_files -v
```

Expected: FAIL — video candidates are currently included.

- [ ] **Step 4: Filter videos in `find_candidates_by_date`**

In `lightroom_tagger/core/matcher.py`, modify `find_candidates_by_date` (line 597-622). Add the import and filter:

```python
def find_candidates_by_date(db, insta_image: dict, days_before: int = 90) -> list:
    """Find catalog candidates within date window before Instagram posting."""
    from datetime import datetime, timedelta
    from lightroom_tagger.core.analyzer import VIDEO_EXTENSIONS

    date_folder = insta_image.get('date_folder', '')
    if len(date_folder) != 6:
        return []

    post_year = int(date_folder[:4])
    post_month = int(date_folder[4:6])
    post_date = datetime(post_year, post_month, 15)
    window_start = post_date - timedelta(days=days_before)

    candidates = []
    for row in db.execute("SELECT * FROM images").fetchall():
        img = _deserialize_row(row)
        filepath = img.get('filepath', '')
        if filepath:
            ext = os.path.splitext(filepath)[1].lower()
            if ext in VIDEO_EXTENSIONS:
                continue
        date_taken = img.get('date_taken', '')
        if not date_taken:
            continue
        try:
            img_date = datetime.fromisoformat(date_taken.replace('Z', '+00:00'))
            if window_start <= img_date <= post_date:
                candidates.append(img)
        except Exception:
            continue
```

- [ ] **Step 5: Run test to verify it passes**

Run:
```bash
pytest lightroom_tagger/core/test_matcher.py::TestFindCandidatesByDate -v
```

Expected: PASS.

- [ ] **Step 6: Invalidate video cache entries in `is_vision_cache_valid`**

In `lightroom_tagger/core/database.py`, modify `is_vision_cache_valid` (line 1221-1241). Add video extension check after the existing RAW extension check:

```python
def is_vision_cache_valid(db: sqlite3.Connection, catalog_key: str,
                           original_path: str) -> bool:
    """Check if cached image is still valid (mtime unchanged)."""
    cached = get_vision_cached_image(db, catalog_key)
    if not cached:
        return False
    comp = cached.get('compressed_path') or ''

    from lightroom_tagger.core.analyzer import RAW_EXTENSIONS, VIDEO_EXTENSIONS

    ext = os.path.splitext(original_path)[1].lower()
    if ext in RAW_EXTENSIONS:
        if comp == original_path:
            return False
        if comp == VISION_CACHE_OVERSIZED_SENTINEL:
            return False

    if ext in VIDEO_EXTENSIONS:
        return False
```

This ensures any cached video entry is always treated as invalid, so `get_or_create_cached_image` will re-process it and return `None` (since videos can't be compressed to < 512KB).

- [ ] **Step 7: Run all matcher and cache tests**

Run:
```bash
pytest lightroom_tagger/core/test_matcher.py lightroom_tagger/core/test_vision_cache.py -v
```

Expected: All PASS.

- [ ] **Step 8: Commit**

```bash
git add lightroom_tagger/core/analyzer.py lightroom_tagger/core/matcher.py lightroom_tagger/core/database.py lightroom_tagger/core/test_matcher.py
git commit -m "fix: exclude video files from vision matching candidates

Catalog contains 51 video files (.mov, .mp4) that cannot be vision-compared.
One 48MB .mov in the 2025 date range caused 4 wasted API calls per image
(413 payload too large -> split -> single-item still too large) for every
Instagram image processed. Videos are now filtered out in find_candidates_by_date
and stale video cache entries are invalidated in is_vision_cache_valid."
```

---

### Task 4: Sort Instagram images and candidates newest-first

Currently both the Instagram image list and catalog candidates are returned in SQLite insertion order (arbitrary). Sorting newest-first means the most likely matches (photos taken closest to Instagram posting date) are compared first, providing faster feedback and earlier matches.

**Three sort points:**

1. `get_instagram_by_date_filter` — returns Instagram images to process
2. `get_unprocessed_dump_media` — returns unprocessed Instagram images (no date filter)
3. `find_candidates_by_date` — returns catalog candidates per Instagram image

**Files:**
- Modify: `lightroom_tagger/core/database.py:939-974` (`get_instagram_by_date_filter`)
- Modify: `lightroom_tagger/core/database.py:897-936` (`get_unprocessed_dump_media`)
- Modify: `lightroom_tagger/core/matcher.py:597-622` (`find_candidates_by_date`)

- [ ] **Step 1: Add `ORDER BY date_folder DESC` to `get_instagram_by_date_filter`**

In `lightroom_tagger/core/database.py`, modify `get_instagram_by_date_filter` (line 972-973). Change:

```python
    where = " AND ".join(clauses) if clauses else "1=1"
    rows = db.execute(f"SELECT * FROM instagram_dump_media WHERE {where}", params).fetchall()
```

to:

```python
    where = " AND ".join(clauses) if clauses else "1=1"
    rows = db.execute(f"SELECT * FROM instagram_dump_media WHERE {where} ORDER BY date_folder DESC, media_key DESC", params).fetchall()
```

`date_folder` is `YYYYMM` so lexicographic DESC gives newest months first. `media_key` as secondary sort gives deterministic order within a month.

- [ ] **Step 2: Add `ORDER BY` to `get_unprocessed_dump_media`**

In `lightroom_tagger/core/database.py`, modify `get_unprocessed_dump_media` (line 930-936). Change:

```python
    where = " AND ".join(clauses) if clauses else "1=1"
    sql = f"SELECT * FROM instagram_dump_media WHERE {where}"
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    rows = db.execute(sql, params).fetchall()
```

to:

```python
    where = " AND ".join(clauses) if clauses else "1=1"
    sql = f"SELECT * FROM instagram_dump_media WHERE {where} ORDER BY date_folder DESC, media_key DESC"
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    rows = db.execute(sql, params).fetchall()
```

- [ ] **Step 3: Sort candidates newest-first in `find_candidates_by_date`**

In `lightroom_tagger/core/matcher.py`, at the end of `find_candidates_by_date`, after the loop builds the `candidates` list, add a sort before returning:

```python
    candidates.sort(key=lambda c: c.get('date_taken', ''), reverse=True)
    return candidates
```

This sorts catalog candidates by `date_taken` descending (newest first). Photos taken closest to the Instagram posting date appear first in the batch, so the model sees the most likely matches in the earliest batches.

- [ ] **Step 4: Run existing tests**

Run:
```bash
pytest lightroom_tagger/core/test_matcher.py -v
```

Expected: All PASS. Sorting doesn't change which candidates are included, only the order.

- [ ] **Step 5: Commit**

```bash
git add lightroom_tagger/core/database.py lightroom_tagger/core/matcher.py
git commit -m "perf: sort Instagram images and candidates newest-first

Instagram images are now processed newest-first (ORDER BY date_folder DESC)
so recent posts get matched before older ones. Catalog candidates are sorted
by date_taken DESC so photos taken closest to the posting date appear in the
earliest batches, giving the vision model the most likely matches first."
```

---

### Task 5: Retroactively store matches from job `6d21f72e`

Job `6d21f72e` (vision_match, gpt-5-mini, year=2025) found at least 2 images with 100% vision confidence that were rejected because `total=0.4286 < 0.7` due to the weights bug. These need to be inserted into the DB as matches. The job may find additional high-confidence results in images 35-95 that are also being rejected.

**Known rejected matches from job logs (as of image 34/95):**

| Instagram image | Catalog match | Vision score | Correct total (vision-only) |
|----------------|---------------|-------------|---------------------------|
| `17879231568205315` (date_folder `202504`) | `2025-02-23_f9131200` | 1.0 | 1.0 |
| `18048470654106859` (date_folder `202505`) | `2025-02-23_f9417408` | 1.0 | 1.0 |

- [ ] **Step 1: Wait for job `6d21f72e` to finish**

Check job status. If still running, wait. Do not cancel it — it may find additional matches in the remaining images (35-95). Once done, re-fetch the full logs and scan for any additional `vision >= 0.7` results that were rejected.

Run:
```bash
curl -s http://localhost:5001/api/jobs/6d21f72e-f51c-4a77-b039-edae35e97cb3 | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(f'Status: {data[\"status\"]}')
print(f'Current step: {data[\"current_step\"]}')
"
```

If still running, wait and re-check periodically. Once `status` is `completed` or `failed`, proceed.

- [ ] **Step 2: Scan final logs for all rejected matches**

Once the job finishes, re-fetch the full job response and extract every `Best result:` log line with `vision >= 0.7`:

```bash
curl -s http://localhost:5001/api/jobs/6d21f72e-f51c-4a77-b039-edae35e97cb3 | python3 -c "
import json, sys
data = json.load(sys.stdin)
for l in data['logs']:
    msg = l['message']
    if 'Best result:' in msg and 'vision=' in msg:
        try:
            idx = msg.index('vision=')
            score = float(msg[idx+7:].split(')')[0].split(',')[0].split(' ')[0])
            if score >= 0.7:
                print(msg)
        except:
            pass
"
```

This may return more than the 2 already known. Use the full list for Step 3.

- [ ] **Step 3: Insert matches into `library.db`**

For each rejected match from Step 2, use `store_match` from the Python API to insert. This handles `ON CONFLICT` upsert, sets `matched_at`, and is the same function used by normal matching.

```bash
cd /Users/ccanales/projects/lightroom-tagger && python3 -c "
from lightroom_tagger.core.database import init_database, store_match, mark_dump_media_processed, update_instagram_status

db = init_database('library.db')

# List of (insta_media_key, catalog_key, vision_score) from Step 2
# Update this list with ALL matches found in Step 2, not just these 2
rejected_matches = [
    ('17879231568205315', '2025-02-23_f9131200', 1.0),
    ('18048470654106859', '2025-02-23_f9417408', 1.0),
]

for insta_key, catalog_key, vision_score in rejected_matches:
    record = {
        'catalog_key': catalog_key,
        'insta_key': insta_key,
        'phash_distance': None,
        'phash_score': 0.0,
        'desc_similarity': 0.0,
        'vision_result': 'MATCH',
        'vision_score': vision_score,
        'total_score': vision_score,  # correct score with vision-only weights
        'model_used': 'github_copilot:gpt-5-mini',
        'rank': 1,
        'vision_reasoning': 'Retroactively stored — rejected by weights bug in job 6d21f72e',
    }
    result = store_match(db, record)
    print(f'Stored: {result}')

    mark_dump_media_processed(db, insta_key,
                               matched_catalog_key=catalog_key,
                               vision_result='MATCH',
                               vision_score=vision_score)
    print(f'Marked processed: {insta_key}')

    update_instagram_status(db, catalog_key, posted=True)
    print(f'Updated instagram status: {catalog_key}')

db.close()
print('Done')
"
```

Expected: Each match prints `Stored: <catalog_key> <-> <insta_key>`, `Marked processed`, `Updated instagram status`.

- [ ] **Step 4: Verify matches appear in the API**

```bash
curl -s http://localhost:5001/api/images/matches | python3 -c "
import json, sys
data = json.load(sys.stdin)
target_keys = {'17879231568205315', '18048470654106859'}
for group in data.get('match_groups', []):
    if group.get('instagram_key') in target_keys:
        print(f'Found: {group[\"instagram_key\"]} -> {group.get(\"matches\", [])}')
if not any(g.get('instagram_key') in target_keys for g in data.get('match_groups', [])):
    print('WARNING: Matches not found in API response')
"
```

Expected: Both `17879231568205315` and `18048470654106859` appear in the match groups.

- [ ] **Step 5: Verify matches appear in the UI using agent-browser**

Use the agent-browser skill to navigate to `http://localhost:5173/images?tab=matches` and verify:
1. The matches tab loads and shows match groups.
2. The two new matches (`17879231568205315` and `18048470654106859`) are visible in the list.
3. Clicking on one opens the match detail modal showing the catalog image paired with the Instagram image.

- [ ] **Step 6: Commit data fix documentation**

No code changes in this task — the DB was updated directly. Record what was done:

```bash
git add docs/plans/2026-04-12-fix-weights-not-passed-to-match-dump-media.md
git commit -m "docs: plan for weights bug fix and retroactive match insertion

Matches from job 6d21f72e (vision>=0.7, total=0.4286) were
retroactively stored after the weights forwarding bug was identified."
```

---

### Verification

After deploying (backend restart with Tasks 1-4 applied), re-run a single-image match with `phash=0.0, desc=0.0, vision=1.0` weights against an image known to have a match. Verify:
1. The best result shows `total ≈ 1.0` instead of `0.4286` (weights fix).
2. No video candidates appear in the batch (video exclusion).
3. Instagram images process newest month first, candidates within each image are newest-first (sort order).
4. Retroactively stored matches are visible in the UI at `/images?tab=matches`.
