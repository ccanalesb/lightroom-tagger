# Single-Image Matching Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the dead "Open Local File" button in the Instagram detail modal with a "Match This Photo" action that runs vision matching on a single image with inline progress, settings, and re-run support.

**Architecture:** Add `media_key` support to the existing `vision_match` job pipeline. The backend filters to a single Instagram image when `media_key` is present. A shared `MatchOptionsContext` at the app root holds model/threshold/weights state — consumed by both `MatchingPage` and `ImageDetailsModal`. Only one job runs at a time.

**Tech Stack:** React (frontend), Flask (backend), SQLite, Ollama vision API

**Brainstorm:** `docs/brainstorms/2026-03-27-single-image-matching-brainstorm.md`

---

## Task 1: Backend — Support single-image matching in `match_dump_media`

Add a `media_key` parameter to `match_dump_media` that scopes processing to one Instagram image.

**Files:**
- Modify: `lightroom_tagger/scripts/match_instagram_dump.py`
- Test: `lightroom_tagger/scripts/test_match_instagram_dump.py`

**Step 1: Write the failing test**

```python
# lightroom_tagger/scripts/test_match_instagram_dump.py
from unittest.mock import patch, MagicMock
from lightroom_tagger.scripts.match_instagram_dump import match_dump_media


@patch('lightroom_tagger.scripts.match_instagram_dump.init_catalog_table')
@patch('lightroom_tagger.scripts.match_instagram_dump.init_instagram_dump_table')
@patch('lightroom_tagger.scripts.match_instagram_dump.get_unprocessed_dump_media')
@patch('lightroom_tagger.scripts.match_instagram_dump.find_candidates_by_date')
def test_media_key_filters_to_single_image(mock_find, mock_get_unprocessed, mock_init_insta, mock_init_catalog):
    """When media_key is provided, only that image is processed."""
    db = MagicMock()
    target_row = {
        'media_key': '202603/12345',
        'file_path': '/tmp/test.jpg',
        'caption': '',
        'date_folder': '202603',
    }
    db.execute.return_value.fetchone.return_value = target_row

    mock_find.return_value = []

    stats, matches = match_dump_media(db, media_key='202603/12345')

    # Should query DB for specific media_key, not call get_unprocessed_dump_media
    mock_get_unprocessed.assert_not_called()
    assert stats['processed'] == 1
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/ccanales/personal/lightroom-tagger && source .venv/bin/activate && python3 -m pytest lightroom_tagger/scripts/test_match_instagram_dump.py::test_media_key_filters_to_single_image -v`

Expected: FAIL — `match_dump_media()` does not accept `media_key` parameter.

**Step 3: Write minimal implementation**

In `lightroom_tagger/scripts/match_instagram_dump.py`, add `media_key` parameter to `match_dump_media`:

```python
def match_dump_media(db, threshold: float = 0.7, batch_size: int = None,
                     month: str = None, year: str = None, last_months: int = None,
                     progress_callback=None, log_callback=None,
                     weights: dict = None, media_key: str = None) -> tuple:
```

Add early branch after `init_instagram_dump_table(db)` / `init_catalog_table(db)`:

```python
    if media_key:
        row = db.execute(
            "SELECT * FROM instagram_dump_media WHERE media_key = ?",
            (media_key,)
        ).fetchone()
        if not row:
            return stats, matches_found
        unprocessed = [dict(row) if not isinstance(row, dict) else row]
    elif month or year or last_months:
        # ... existing date filter logic ...
```

**Step 4: Run test to verify it passes**

Run: same command as Step 2.
Expected: PASS

**Step 5: Commit**

```bash
git add lightroom_tagger/scripts/match_instagram_dump.py lightroom_tagger/scripts/test_match_instagram_dump.py
git commit -m "feat: support single-image matching via media_key in match_dump_media"
```

---

## Task 2: Backend — Pass `media_key` through the job handler

**Files:**
- Modify: `apps/visualizer/backend/jobs/handlers.py` (line 96 — `match_dump_media` call)
- Test: `apps/visualizer/backend/tests/test_handlers_single_match.py`

**Step 1: Write the failing test**

```python
# apps/visualizer/backend/tests/test_handlers_single_match.py
from unittest.mock import patch, MagicMock


@patch('jobs.handlers.match_dump_media')
@patch('jobs.handlers.init_database')
@patch('jobs.handlers.load_config')
@patch('jobs.handlers.update_job_field')
@patch('jobs.handlers.os.path.exists', return_value=True)
@patch('jobs.handlers.os.getenv', return_value='/tmp/library.db')
def test_handle_vision_match_passes_media_key(mock_getenv, mock_exists, mock_update_field,
                                               mock_config, mock_init_db, mock_match):
    from jobs.handlers import handle_vision_match

    mock_config.return_value = MagicMock(
        vision_model='gemma3:27b', match_threshold=0.7,
        phash_weight=0.4, desc_weight=0.3, vision_weight=0.3,
        ollama_host='http://localhost:11434'
    )
    mock_match.return_value = ({'processed': 1, 'matched': 1, 'skipped': 0}, [])
    mock_init_db.return_value = MagicMock()

    runner = MagicMock()
    runner.db = MagicMock()

    handle_vision_match(runner, 'test-job-id', {'media_key': '202603/12345'})

    _, kwargs = mock_match.call_args
    assert kwargs.get('media_key') == '202603/12345'
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/ccanales/personal/lightroom-tagger/apps/visualizer/backend && python3 -m pytest tests/test_handlers_single_match.py -v`

Expected: FAIL — `media_key` not passed to `match_dump_media`.

**Step 3: Write minimal implementation**

In `apps/visualizer/backend/jobs/handlers.py`, modify the `match_dump_media` call (around line 96):

```python
            media_key = metadata.get('media_key')

            stats, matches = match_dump_media(
                db,
                threshold=custom_threshold,
                month=month,
                year=year,
                last_months=last_months,
                progress_callback=progress_callback,
                log_callback=log_callback,
                media_key=media_key,
            )
```

**Step 4: Run test to verify it passes**

Run: same command as Step 2.
Expected: PASS

**Step 5: Commit**

```bash
git add apps/visualizer/backend/jobs/handlers.py apps/visualizer/backend/tests/test_handlers_single_match.py
git commit -m "feat: pass media_key from job metadata to match_dump_media"
```

---

## Task 3: Frontend — Create shared `MatchOptionsContext`

Extract match options (model, threshold, weights) into a React context at the app root. Both `MatchingPage` and `ImageDetailsModal` consume it. Only one job runs at a time, so one shared state is correct.

**Files:**
- Create: `apps/visualizer/frontend/src/stores/matchOptionsContext.tsx`
- Modify: `apps/visualizer/frontend/src/pages/MatchingPage.tsx` (remove local options state, consume context)
- Modify: `apps/visualizer/frontend/src/App.tsx` (wrap with provider)

**Step 1: Create the context**

```typescript
// apps/visualizer/frontend/src/stores/matchOptionsContext.tsx
import { createContext, useContext, useEffect, useState, useCallback, useMemo, type ReactNode } from 'react';
import { SystemAPI } from '../services/api';
import { ADVANCED_WEIGHTS_MUST_SUM } from '../constants/strings';

interface MatchOptions {
  selectedModel: string;
  threshold: number;
  phashWeight: number;
  descWeight: number;
  visionWeight: number;
}

const DEFAULT_OPTIONS: MatchOptions = {
  selectedModel: '',
  threshold: 0.7,
  phashWeight: 0,
  descWeight: 0,
  visionWeight: 1,
};

interface MatchOptionsContextValue {
  options: MatchOptions;
  updateOption: <K extends keyof MatchOptions>(key: K, value: MatchOptions[K]) => void;
  resetOptions: () => void;
  availableModels: { name: string; default: boolean }[];
  weightsError: string | null;
}

const MatchOptionsContext = createContext<MatchOptionsContextValue | null>(null);

export function MatchOptionsProvider({ children }: { children: ReactNode }) {
  const [options, setOptions] = useState<MatchOptions>({ ...DEFAULT_OPTIONS });
  const [availableModels, setAvailableModels] = useState<{ name: string; default: boolean }[]>([]);

  useEffect(() => {
    SystemAPI.visionModels()
      .then((data) => {
        setAvailableModels(data.models);
        const defaultModel = data.models.find((m) => m.default) ?? data.models[0];
        if (defaultModel) setOptions((prev) => ({ ...prev, selectedModel: defaultModel.name }));
      })
      .catch(console.error);
  }, []);

  const updateOption = useCallback(<K extends keyof MatchOptions>(key: K, value: MatchOptions[K]) => {
    setOptions((prev) => ({ ...prev, [key]: value }));
  }, []);

  const resetOptions = useCallback(() => {
    setOptions((prev) => ({ ...DEFAULT_OPTIONS, selectedModel: prev.selectedModel }));
  }, []);

  const weightsError = useMemo(() => {
    const total = options.phashWeight + options.descWeight + options.visionWeight;
    return Math.abs(total - 1.0) >= 0.001 ? ADVANCED_WEIGHTS_MUST_SUM : null;
  }, [options.phashWeight, options.descWeight, options.visionWeight]);

  const value = useMemo(() => ({
    options,
    updateOption,
    resetOptions,
    availableModels,
    weightsError,
  }), [options, updateOption, resetOptions, availableModels, weightsError]);

  return (
    <MatchOptionsContext.Provider value={value}>
      {children}
    </MatchOptionsContext.Provider>
  );
}

export function useMatchOptions() {
  const ctx = useContext(MatchOptionsContext);
  if (!ctx) throw new Error('useMatchOptions must be used within MatchOptionsProvider');
  return ctx;
}
```

**Step 2: Wrap App with provider**

In `App.tsx`, import and wrap:

```typescript
import { MatchOptionsProvider } from './stores/matchOptionsContext';

// In the render, wrap the router:
<MatchOptionsProvider>
  {/* existing Router/Routes */}
</MatchOptionsProvider>
```

**Step 3: Refactor `MatchingPage.tsx` to consume context**

Remove from `MatchingPage.tsx`:
- `DEFAULT_OPTIONS` constant
- `availableModels` state
- `options` state
- `weightsError` state and its `useMemo`
- The `SystemAPI.visionModels()` `useEffect`
- `updateOption` helper
- `resetOptions` helper

Replace with:

```typescript
import { useMatchOptions } from '../stores/matchOptionsContext';

// Inside MatchingPage():
const { options, updateOption, resetOptions, availableModels, weightsError } = useMatchOptions();
```

The `AdvancedOptions` props remain the same — they just read from the context now instead of local state.

**Step 4: Verify MatchingPage still works**

Run: `cd /Users/ccanales/personal/lightroom-tagger/apps/visualizer/frontend && npx vitest run`

Expected: Existing tests pass.

**Step 5: Commit**

```bash
git add apps/visualizer/frontend/src/stores/matchOptionsContext.tsx apps/visualizer/frontend/src/App.tsx apps/visualizer/frontend/src/pages/MatchingPage.tsx
git commit -m "refactor: extract match options into shared MatchOptionsContext"
```

---

## Task 4: Frontend — Add single-image match UI to `ImageDetailsModal`

Replace "Open Local File" button with match UI. Consumes `useMatchOptions` from the shared context.

**Files:**
- Modify: `apps/visualizer/frontend/src/pages/InstagramPage.tsx`
- Modify: `apps/visualizer/frontend/src/constants/strings.ts` (add new string constants)

**Step 1: Add string constants**

In `apps/visualizer/frontend/src/constants/strings.ts`, add:

```typescript
export const MODAL_MATCH_THIS_PHOTO = 'Match This Photo';
export const MODAL_MATCH_RUNNING = 'Matching...';
export const MODAL_MATCH_RESULT_FOUND = 'Match found!';
export const MODAL_MATCH_RESULT_NONE = 'No match found';
export const MODAL_MATCH_VIEW_RESULTS = 'View on Matching page';
export const MODAL_MATCH_RETRY = 'Run Again';
```

**Step 2: Add imports to `InstagramPage.tsx`**

```typescript
import { JobsAPI } from "../services/api";
import { AdvancedOptions } from "../components";
import { useMatchOptions } from "../stores/matchOptionsContext";
import {
  // ... existing imports ...
  MODAL_MATCH_THIS_PHOTO,
  MODAL_MATCH_RUNNING,
  MODAL_MATCH_RESULT_FOUND,
  MODAL_MATCH_RESULT_NONE,
  MODAL_MATCH_VIEW_RESULTS,
  MODAL_MATCH_RETRY,
} from "../constants/strings";
```

Remove the `MODAL_OPEN_LOCAL_FILE` import — it's no longer used.

**Step 3: Add match state inside `ImageDetailsModal`**

Inside `ImageDetailsModal`, before the return:

```typescript
  const { options: matchOptions, updateOption, resetOptions, availableModels, weightsError } = useMatchOptions();
  const [matchState, setMatchState] = useState<'idle' | 'running' | 'done'>('idle');
  const [matchJob, setMatchJob] = useState<Job | null>(null);
  const [matchResult, setMatchResult] = useState<{ matched: number; score?: number } | null>(null);
  const [advancedOpen, setAdvancedOpen] = useState(false);

  useEffect(() => {
    setMatchState('idle');
    setMatchJob(null);
    setMatchResult(null);
    setAdvancedOpen(false);
  }, [image.key]);

  const startSingleMatch = async () => {
    setMatchState('running');
    setMatchResult(null);
    try {
      const job = await JobsAPI.create('vision_match', {
        media_key: image.key,
        vision_model: matchOptions.selectedModel,
        threshold: matchOptions.threshold,
        weights: {
          phash: matchOptions.phashWeight,
          description: matchOptions.descWeight,
          vision: matchOptions.visionWeight,
        },
      });
      setMatchJob(job);
      pollJob(job.id);
    } catch (err) {
      setMatchState('idle');
      console.error('Failed to start match:', err);
    }
  };

  const pollJob = (jobId: string) => {
    const interval = setInterval(async () => {
      try {
        const job = await JobsAPI.get(jobId);
        setMatchJob(job);
        if (job.status === 'completed' || job.status === 'failed') {
          clearInterval(interval);
          setMatchState('done');
          if (job.result) {
            setMatchResult({ matched: job.result.matched ?? 0, score: job.result.best_score });
          }
        }
      } catch {
        clearInterval(interval);
        setMatchState('done');
      }
    }, 2000);
  };
```

**Step 4: Replace the "Open Local File" button block**

Replace lines 379-399 of `InstagramPage.tsx` (the `<div className="flex gap-2">` block) with:

```tsx
            <div className="space-y-3">
              {image.post_url && (
                <a
                  href={image.post_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block w-full bg-blue-600 text-white text-center py-2 px-4 rounded-md hover:bg-blue-700 transition-colors text-sm font-medium"
                >
                  {MODAL_VIEW_ON_INSTAGRAM}
                </a>
              )}

              {matchState === 'idle' && (
                <button
                  onClick={startSingleMatch}
                  className="w-full bg-purple-600 text-white py-2 px-4 rounded-md hover:bg-purple-700 transition-colors text-sm font-medium"
                >
                  {MODAL_MATCH_THIS_PHOTO}
                </button>
              )}

              {matchState === 'running' && (
                <div className="flex items-center gap-2 py-2 px-4 bg-purple-50 rounded-md text-sm text-purple-700">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  {MODAL_MATCH_RUNNING}
                  {matchJob && ` ${matchJob.progress}%`}
                </div>
              )}

              {matchState === 'done' && matchResult && (
                <div className={`py-2 px-4 rounded-md text-sm ${matchResult.matched > 0 ? 'bg-green-50 text-green-700' : 'bg-gray-50 text-gray-600'}`}>
                  <p className="font-medium">
                    {matchResult.matched > 0 ? MODAL_MATCH_RESULT_FOUND : MODAL_MATCH_RESULT_NONE}
                    {matchResult.score != null && ` (score: ${matchResult.score.toFixed(2)})`}
                  </p>
                  <div className="flex gap-2 mt-2">
                    {matchResult.matched > 0 && (
                      <a href="/matching" className="text-xs text-blue-600 hover:underline">
                        {MODAL_MATCH_VIEW_RESULTS}
                      </a>
                    )}
                    <button
                      onClick={() => setMatchState('idle')}
                      className="text-xs text-purple-600 hover:underline"
                    >
                      {MODAL_MATCH_RETRY}
                    </button>
                  </div>
                </div>
              )}

              {matchState === 'done' && matchJob?.status === 'failed' && (
                <div className="py-2 px-4 rounded-md text-sm bg-red-50 text-red-700">
                  <p className="font-medium">Match failed: {matchJob.error || 'Unknown error'}</p>
                  <button
                    onClick={() => setMatchState('idle')}
                    className="text-xs text-purple-600 hover:underline mt-1"
                  >
                    {MODAL_MATCH_RETRY}
                  </button>
                </div>
              )}

              <AdvancedOptions
                isOpen={advancedOpen}
                onToggle={() => setAdvancedOpen(!advancedOpen)}
                availableModels={availableModels}
                selectedModel={matchOptions.selectedModel}
                onModelChange={(model) => updateOption('selectedModel', model)}
                threshold={matchOptions.threshold}
                onThresholdChange={(v) => updateOption('threshold', v)}
                phashWeight={matchOptions.phashWeight}
                onPhashWeightChange={(v) => updateOption('phashWeight', v)}
                descWeight={matchOptions.descWeight}
                onDescWeightChange={(v) => updateOption('descWeight', v)}
                visionWeight={matchOptions.visionWeight}
                onVisionWeightChange={(v) => updateOption('visionWeight', v)}
                weightsError={weightsError}
                onReset={resetOptions}
              />
            </div>
```

**Step 5: Commit**

```bash
git add apps/visualizer/frontend/src/pages/InstagramPage.tsx apps/visualizer/frontend/src/constants/strings.ts
git commit -m "feat: add single-image matching UI to Instagram detail modal"
```

---

## Task 5: Integration test — verify end-to-end

Run existing tests to check for regressions:

```bash
cd /Users/ccanales/personal/lightroom-tagger && source .venv/bin/activate && python3 -m pytest lightroom_tagger/ -v
cd apps/visualizer/frontend && npx vitest run
```

Manually verify:

1. Open `http://localhost:5173/instagram`, click an image
2. Confirm "Match This Photo" button appears (no "Open Local File")
3. Click it — see inline spinner/progress
4. On completion — see match/no-match summary
5. Open AdvancedOptions, tweak model, click "Run Again"
6. Open `http://localhost:5173/matching` — confirm batch matching still works with shared settings

**Step 1: Commit**

```bash
git add -A
git commit -m "feat: single-image matching from Instagram detail modal"
```
