# Fix Matching Bugs Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix two bugs that cause zero vision matches: (1) model dropdown defaults to nonexistent model, (2) Ollama connection errors silently cached as UNCERTAIN.

**Architecture:** Bug 1 is a frontend default-selection issue in MatchingPage. Bug 2 is a Python error-handling issue spanning `analyzer.py` (silent catch) and `matcher.py` (caching errors). Final step clears stale cache.

**Tech Stack:** Python 3.10+ (pytest), TypeScript/React (vitest), SQLite

---

### Task 1: Ollama errors should raise, not return UNCERTAIN

Currently `run_vision_ollama` in `lightroom_tagger/core/analyzer.py:493` catches all exceptions and returns `'UNCERTAIN'`. Infrastructure errors (model not found, connection refused, timeout) should propagate so callers can distinguish "model can't decide" from "model didn't run".

**Files:**
- Test: `lightroom_tagger/core/test_analyzer.py`
- Modify: `lightroom_tagger/core/analyzer.py:450-495`

**Step 1: Write the failing tests**

```python
# In lightroom_tagger/core/test_analyzer.py

def test_run_vision_ollama_raises_on_model_not_found():
    """should raise RuntimeError when Ollama returns model not found."""
    import json
    import urllib.request
    from io import BytesIO
    from unittest.mock import MagicMock, patch

    from lightroom_tagger.core.analyzer import run_vision_ollama

    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({'error': "model 'gemma3:27b' not found"}).encode()
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch('urllib.request.urlopen', return_value=mock_response), \
         patch('builtins.open', side_effect=lambda p, m: BytesIO(b'\x00' * 10)):
        try:
            run_vision_ollama('/tmp/a.jpg', '/tmp/b.jpg')
            assert False, "Expected RuntimeError"
        except RuntimeError as e:
            assert 'not found' in str(e)


def test_run_vision_ollama_raises_on_connection_error():
    """should raise URLError when Ollama is unreachable."""
    from io import BytesIO
    from unittest.mock import MagicMock, patch
    from urllib.error import URLError

    from lightroom_tagger.core.analyzer import run_vision_ollama

    with patch('urllib.request.urlopen', side_effect=URLError('Connection refused')), \
         patch('builtins.open', side_effect=lambda p, m: BytesIO(b'\x00' * 10)):
        try:
            run_vision_ollama('/tmp/a.jpg', '/tmp/b.jpg')
            assert False, "Expected URLError"
        except URLError:
            pass
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/ccanales/personal/lightroom-tagger && source .venv/bin/activate && python3 -m pytest lightroom_tagger/core/test_analyzer.py::test_run_vision_ollama_raises_on_model_not_found lightroom_tagger/core/test_analyzer.py::test_run_vision_ollama_raises_on_connection_error -v`

Expected: FAIL — both currently return `'UNCERTAIN'` instead of raising.

**Step 3: Write minimal implementation**

In `lightroom_tagger/core/analyzer.py`, modify `run_vision_ollama` (around line 463-495):

```python
def run_vision_ollama(local_path: str, insta_path: str) -> str:
    """Compare two images using Ollama HTTP API with base64-encoded images."""
    import base64
    import json
    import urllib.request

    prompt = (
        "You are given two images. Determine if they depict the same subject or scene. "
        "Image 1 may be lower quality, compressed, or degraded. "
        "Focus on semantic content, not pixel-level accuracy.\n\n"
        "Reply with ONLY one word: SAME or DIFFERENT or UNCERTAIN"
    )

    images_b64 = []
    for path in (local_path, insta_path):
        with open(path, 'rb') as f:
            images_b64.append(base64.b64encode(f.read()).decode('utf-8'))

    payload = json.dumps({
        'model': get_vision_model(),
        'prompt': prompt,
        'images': images_b64,
        'stream': False,
    }).encode('utf-8')

    ollama_host = load_config().ollama_host
    req = urllib.request.Request(
        f'{ollama_host}/api/generate',
        data=payload,
        headers={'Content-Type': 'application/json'},
    )

    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode('utf-8'))

    if 'error' in data:
        raise RuntimeError(f"Ollama error: {data['error']}")

    output = data.get('response', '').strip().upper()

    if output.startswith('SAME') and 'DIFFERENT' not in output[:20]:
        return 'SAME'
    elif 'DIFFERENT' in output[:50]:
        return 'DIFFERENT'
    return 'UNCERTAIN'
```

Key change: removed the outer try/except. Infrastructure errors (`URLError`, `ConnectionError`, `TimeoutError`, `RuntimeError` from model-not-found) now propagate. Only genuine model responses produce `'UNCERTAIN'`.

**Step 4: Run tests to verify they pass**

Run: `cd /Users/ccanales/personal/lightroom-tagger && source .venv/bin/activate && python3 -m pytest lightroom_tagger/core/test_analyzer.py -v`

Expected: All pass, including existing tests.

**Step 5: Commit**

```bash
git add lightroom_tagger/core/test_analyzer.py lightroom_tagger/core/analyzer.py
git commit -m "fix: make run_vision_ollama raise on infrastructure errors instead of returning UNCERTAIN"
```

---

### Task 2: Don't cache vision results when the call errored

Currently `score_candidates_with_vision` in `lightroom_tagger/core/matcher.py:153-175` catches vision errors and still caches `UNCERTAIN/0.5`. When the error was infrastructure (model not found, timeout), the cached result prevents retries.

**Files:**
- Test: `lightroom_tagger/core/test_matcher.py`
- Modify: `lightroom_tagger/core/matcher.py:119-175`

**Step 1: Write the failing test**

```python
# In lightroom_tagger/core/test_matcher.py

def test_score_candidates_does_not_cache_on_vision_error():
    """should not cache vision result when compare_with_vision raises."""
    from unittest.mock import Mock, patch

    mock_db = Mock()

    insta_image = {
        'key': 'insta_test',
        'image_hash': 'a1b2c3d4e5f6g7h8',
        'description': 'sunset',
        'local_path': '/tmp/insta.jpg',
    }

    candidates = [
        {'key': 'cat1', 'image_hash': 'a1b2c3d4e5f6g7h8', 'description': 'sunset', 'local_path': '/tmp/local1.jpg'},
    ]

    with patch('lightroom_tagger.core.matcher.get_vision_comparison', return_value=None), \
         patch('lightroom_tagger.core.analyzer.compare_with_vision', side_effect=RuntimeError('model not found')), \
         patch('lightroom_tagger.core.matcher.store_vision_comparison') as store_mock, \
         patch('lightroom_tagger.core.phash.hamming_distance', return_value=0):

        results = score_candidates_with_vision(
            mock_db, insta_image, candidates,
            phash_weight=0.4, desc_weight=0.3, vision_weight=0.3,
        )

    assert len(results) == 1
    assert results[0]['vision_result'] == 'ERROR'
    assert results[0]['vision_score'] == 0.0
    store_mock.assert_not_called()
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/ccanales/personal/lightroom-tagger && source .venv/bin/activate && python3 -m pytest lightroom_tagger/core/test_matcher.py::test_score_candidates_does_not_cache_on_vision_error -v`

Expected: FAIL — currently caches the result and returns `UNCERTAIN/0.5`.

**Step 3: Write minimal implementation**

In `lightroom_tagger/core/matcher.py`, modify the vision comparison block (around line 148-175):

```python
        if vision_cached:
            vision_result = vision_cached['result']
            vision_score_val = vision_cached['vision_score']
        elif insta_path and local_path:
            try:
                vision_result = compare_with_vision(
                    local_path, insta_path,
                    log_callback=log_callback,
                    cached_local_path=cached_local_path,
                    compressed_insta_path=compressed_insta
                )
                vision_score_val = vision_score(vision_result)

                store_vision_comparison(
                    db, catalog_key, insta_key,
                    vision_result, vision_score_val,
                    get_vision_model()
                )
            except Exception as e:
                if log_callback:
                    log_callback('error', f'[{insta_filename}] Vision error for {catalog_key}: {e}')
                vision_result = 'ERROR'
                vision_score_val = 0.0
        else:
            vision_result = 'UNCERTAIN'
            vision_score_val = 0.5
```

Key change: the `except` block sets `vision_result = 'ERROR'` and `vision_score_val = 0.0`, and does NOT call `store_vision_comparison`. Next run will retry the pair.

**Step 4: Run tests to verify they pass**

Run: `cd /Users/ccanales/personal/lightroom-tagger && source .venv/bin/activate && python3 -m pytest lightroom_tagger/core/test_matcher.py -v`

Expected: All pass (note: 2 existing tests may still fail due to a pre-existing Mock issue — those are not related to this change).

**Step 5: Commit**

```bash
git add lightroom_tagger/core/test_matcher.py lightroom_tagger/core/matcher.py
git commit -m "fix: don't cache vision results when Ollama call errors out"
```

---

### Task 3: Model dropdown should fall back to first available model

The frontend hardcodes `selectedModel: 'gemma3:27b'` and only updates it when a model has `default: true` from the API. If the installed model has a different name (`gemma3:27b-cloud`), the dropdown keeps the nonexistent default.

**Files:**
- Test: `apps/visualizer/frontend/src/pages/__tests__/MatchingPage.test.tsx` (create)
- Modify: `apps/visualizer/frontend/src/pages/MatchingPage.tsx:58-59,150-157`

**Step 1: Write the failing test**

Create `apps/visualizer/frontend/src/pages/__tests__/MatchingPage.test.tsx`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('MatchingPage model selection', () => {
  it('should fall back to first available model when no default exists', async () => {
    const fetchMock = vi.fn();
    globalThis.fetch = fetchMock;

    fetchMock.mockImplementation((url: string) => {
      if (url.includes('/vision-models')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            models: [{ name: 'gemma3:27b-cloud', default: false }],
            fallback: false,
          }),
        });
      }
      if (url.includes('/jobs/active')) {
        return Promise.resolve({ ok: true, json: async () => [] });
      }
      if (url.includes('/matches')) {
        return Promise.resolve({ ok: true, json: async () => ({ matches: [], total: 0 }) });
      }
      if (url.includes('/cache/status')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ total_images: 0, cached_images: 0, missing: 0, cache_size_mb: 0, cache_dir: '' }),
        });
      }
      return Promise.resolve({ ok: true, json: async () => ({}) });
    });

    // Dynamically import to get fresh module
    const { render, screen, waitFor } = await import('@testing-library/react');
    const { MemoryRouter } = await import('react-router-dom');
    const { MatchingPage } = await import('../MatchingPage');

    render(
      <MemoryRouter>
        <MatchingPage />
      </MemoryRouter>
    );

    // Wait for models to load and check the select value
    await waitFor(() => {
      const modelSelect = document.querySelector('select') as HTMLSelectElement;
      if (modelSelect) {
        expect(modelSelect.value).toBe('gemma3:27b-cloud');
      }
    }, { timeout: 3000 });
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/ccanales/personal/lightroom-tagger/apps/visualizer/frontend && npx vitest run src/pages/__tests__/MatchingPage.test.tsx`

Expected: FAIL — `selectedModel` stays as `'gemma3:27b'` because no model has `default: true`.

**Step 3: Write minimal implementation**

In `apps/visualizer/frontend/src/pages/MatchingPage.tsx`:

Change line 59:
```typescript
const DEFAULT_OPTIONS = {
  selectedModel: '',  // Let API populate; empty = not yet loaded
  threshold: 0.7,
  phashWeight: 0.4,
  descWeight: 0.3,
  visionWeight: 0.3,
};
```

Change lines 150-157:
```typescript
    SystemAPI.visionModels()
      .then((data) => {
        if (!mounted) return;
        setAvailableModels(data.models);
        const defaultModel = data.models.find((m) => m.default) ?? data.models[0];
        if (defaultModel) setOptions((prev) => ({ ...prev, selectedModel: defaultModel.name }));
      })
      .catch(console.error);
```

Key change: `?? data.models[0]` falls back to first available model. Empty `selectedModel` default prevents submitting a stale hardcoded value.

**Step 4: Run test to verify it passes**

Run: `cd /Users/ccanales/personal/lightroom-tagger/apps/visualizer/frontend && npx vitest run src/pages/__tests__/MatchingPage.test.tsx`

Expected: PASS

**Step 5: Commit**

```bash
git add apps/visualizer/frontend/src/pages/__tests__/MatchingPage.test.tsx apps/visualizer/frontend/src/pages/MatchingPage.tsx
git commit -m "fix: model dropdown falls back to first available model when no default found"
```

---

### Task 4: Clear stale vision comparison cache

4658 vision comparisons are cached as `UNCERTAIN` from the broken model calls. These must be purged so re-matching retries them. Also reset `last_attempted_at` on dump media.

**Files:**
- Modify: `library.db` (SQL statements)

**Step 1: Clear stale comparisons**

```bash
cd /Users/ccanales/personal/lightroom-tagger && source .venv/bin/activate && python3 -c "
import sqlite3
db = sqlite3.connect('library.db')

deleted = db.execute('DELETE FROM vision_comparisons WHERE result = \"UNCERTAIN\"').rowcount
print(f'Deleted {deleted} stale UNCERTAIN comparisons')

reset = db.execute('UPDATE instagram_dump_media SET last_attempted_at = NULL WHERE processed = 0').rowcount
print(f'Reset {reset} dump media attempted flags')

db.commit()
db.close()
"
```

**Step 2: Verify**

```bash
python3 -c "
import sqlite3
db = sqlite3.connect('library.db')
db.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
vc = db.execute('SELECT COUNT(*) as cnt FROM vision_comparisons').fetchone()
dm = db.execute('SELECT COUNT(*) as cnt FROM instagram_dump_media WHERE last_attempted_at IS NOT NULL').fetchone()
print(f'Remaining comparisons: {vc[\"cnt\"]}')
print(f'Dump media with attempted_at: {dm[\"cnt\"]}')
"
```

Expected: Remaining comparisons: ~2 (the DIFFERENT ones), dump media with attempted_at: 0

**Step 3: Commit**

No code commit needed — this is a data fix.

---

### Task 5: Run all tests

```bash
# Backend core tests
cd /Users/ccanales/personal/lightroom-tagger && source .venv/bin/activate
python3 -m pytest lightroom_tagger/core/test_analyzer.py lightroom_tagger/core/test_matcher.py -v

# Backend API tests
cd apps/visualizer/backend && PYTHONPATH=. python3 -m pytest tests/ -v

# Frontend tests
cd ../frontend && npx vitest run
```

Expected: All new tests pass. Pre-existing failures in `test_matcher.py` (Mock.keys issue) are unrelated.
