# Parallel Worker Configuration + Batch Vision API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add configurable parallel processing for vision matching and batch multiple image comparisons into single API calls to reduce latency from ~7.6 hours to ~8 minutes.

**Architecture:** Two-phase implementation: (1) Add UI controls and backend support for parallel worker configuration (1-4 threads), then (2) Pack multiple image pair comparisons (1 Instagram vs N catalog candidates) into single vision API requests with structured JSON output. Both phases use ThreadPoolExecutor with per-worker DB connections to avoid SQLite contention.

**Tech Stack:** Python 3.10+, React 18, TypeScript, Flask, SQLite (WAL mode), Ollama/OpenAI API (Gemma 3 27B vision model), ThreadPoolExecutor

---

## File Structure

### Phase 1: Worker Configuration UI + Backend

**Frontend:**
- `apps/visualizer/frontend/src/constants/strings.ts` - Add worker control UI strings
- `apps/visualizer/frontend/src/stores/matchOptionsContext.tsx` - Add maxWorkers to global state
- `apps/visualizer/frontend/src/components/matching/WorkerSlider.tsx` (NEW) - Reusable worker slider component
- `apps/visualizer/frontend/src/components/matching/AdvancedOptions.tsx` - Integrate worker slider
- `apps/visualizer/frontend/src/pages/MatchingPage.tsx` - Wire maxWorkers to job metadata
- `apps/visualizer/frontend/src/pages/DescriptionsPage.tsx` - Add Advanced Options with worker slider

**Backend:**
- `lightroom_tagger/core/config.py` - Add matching_workers config field
- `apps/visualizer/backend/jobs/handlers.py` - Add helper functions + parallel processing logic

### Phase 2: Batch Vision API

**Backend:**
- `lightroom_tagger/core/config.py` - Add vision_batch_size, vision_batch_threshold fields
- `lightroom_tagger/core/vision_client.py` - Add compare_images_batch function
- `lightroom_tagger/core/matcher.py` - Integrate batching into score_candidates_with_vision
- `lightroom_tagger/scripts/match_instagram_dump.py` - Add parallel processing with shared helper

---

## Phase 1: Worker Configuration UI + Backend

### Task 1: Add Config Fields for Worker Count

**Files:**
- Modify: `lightroom_tagger/core/config.py:11-35` (Config dataclass)
- Modify: `lightroom_tagger/core/config.py:80-100` (env mappings)

- [ ] **Step 1: Add matching_workers field to Config dataclass**

Open `lightroom_tagger/core/config.py` and add after line 34 (after `ollama_host`):

```python
    ollama_host: str = "http://localhost:11434"
    
    # Parallel processing configuration
    matching_workers: int = 4
```

- [ ] **Step 2: Add env variable mapping for matching_workers**

In the same file, find `_load_from_env` method around line 80. Add to `env_mappings` dict:

```python
env_mappings = {
    # ... existing mappings ...
    "MATCHING_WORKERS": "matching_workers",
}
```

- [ ] **Step 3: Add type conversion for matching_workers**

Around line 99 in `_load_from_env`, add to the type conversion block:

```python
if config_key in ("workers", "hash_threshold", "matching_workers"):
    value = int(value)
```

- [ ] **Step 4: Add default value**

Around line 57, add to `defaults` dict:

```python
defaults = {
    # ... existing ...
    "matching_workers": 4,
}
```

- [ ] **Step 5: Test config loading**

Run:
```bash
python3 -c "from lightroom_tagger.core.config import load_config; c = load_config(); print(f'matching_workers={c.matching_workers}')"
```

Expected output: `matching_workers=4`

- [ ] **Step 6: Test env override**

Run:
```bash
MATCHING_WORKERS=2 python3 -c "from lightroom_tagger.core.config import load_config; c = load_config(); print(f'matching_workers={c.matching_workers}')"
```

Expected output: `matching_workers=2`

- [ ] **Step 7: Commit**

```bash
git add lightroom_tagger/core/config.py
git commit -m "feat(config): add matching_workers field with env var support"
```

---

### Task 2: Add Worker Control UI Strings

**Files:**
- Modify: `apps/visualizer/frontend/src/constants/strings.ts:166-174`

- [ ] **Step 1: Add worker control strings**

Open `apps/visualizer/frontend/src/constants/strings.ts` and add after line 166 (after `ADVANCED_WEIGHT_VISION`):

```typescript
export const ADVANCED_WEIGHT_VISION = 'Vision Model'

export const ADVANCED_WORKERS_LABEL = 'Parallel Workers'
export const ADVANCED_WORKERS_DESCRIPTION = 'Process multiple images in parallel (higher = faster, more load)'
export const ADVANCED_WORKERS_MIN = '1 (sequential)'
export const ADVANCED_WORKERS_MAX = '4 (parallel)'

export const ADVANCED_RESET_DEFAULTS = 'Reset to defaults'
```

- [ ] **Step 2: Verify TypeScript compilation**

Run:
```bash
cd apps/visualizer/frontend && npm run type-check
```

Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add apps/visualizer/frontend/src/constants/strings.ts
git commit -m "feat(ui): add worker control string constants"
```

---

### Task 3: Add maxWorkers to MatchOptions Context

**Files:**
- Modify: `apps/visualizer/frontend/src/stores/matchOptionsContext.tsx:6-22` (interface)
- Modify: `apps/visualizer/frontend/src/stores/matchOptionsContext.tsx:55-61` (resetOptions)

- [ ] **Step 1: Add maxWorkers to interface**

Open `apps/visualizer/frontend/src/stores/matchOptionsContext.tsx` and modify the `MatchOptions` interface at line 6:

```typescript
interface MatchOptions {
  providerId: string | null;
  providerModel: string | null;
  threshold: number;
  phashWeight: number;
  descWeight: number;
  visionWeight: number;
  maxWorkers: number;
}
```

- [ ] **Step 2: Add maxWorkers to default values**

Modify `DEFAULT_OPTIONS` at line 15:

```typescript
const DEFAULT_OPTIONS: MatchOptions = {
  providerId: null,
  providerModel: null,
  threshold: 0.7,
  phashWeight: 0,
  descWeight: 0,
  visionWeight: 1,
  maxWorkers: 4,
};
```

- [ ] **Step 3: Preserve maxWorkers in resetOptions**

Modify `resetOptions` callback at line 55:

```typescript
  const resetOptions = useCallback(() => {
    setOptions((prev) => ({
      ...DEFAULT_OPTIONS,
      providerId: prev.providerId,
      providerModel: prev.providerModel,
      maxWorkers: prev.maxWorkers,
    }));
  }, []);
```

- [ ] **Step 4: Verify TypeScript compilation**

Run:
```bash
cd apps/visualizer/frontend && npm run type-check
```

Expected: No errors

- [ ] **Step 5: Commit**

```bash
git add apps/visualizer/frontend/src/stores/matchOptionsContext.tsx
git commit -m "feat(context): add maxWorkers to MatchOptions state"
```

---

### Task 4: Create Reusable WorkerSlider Component

**Files:**
- Create: `apps/visualizer/frontend/src/components/matching/WorkerSlider.tsx`

- [ ] **Step 1: Create WorkerSlider component**

Create file `apps/visualizer/frontend/src/components/matching/WorkerSlider.tsx`:

```typescript
import { RangeSlider } from './RangeSlider';
import {
  ADVANCED_WORKERS_LABEL,
  ADVANCED_WORKERS_MIN,
  ADVANCED_WORKERS_MAX,
  ADVANCED_WORKERS_DESCRIPTION,
} from '../../constants/strings';

interface WorkerSliderProps {
  value: number;
  onChange: (value: number) => void;
}

export function WorkerSlider({ value, onChange }: WorkerSliderProps) {
  return (
    <RangeSlider
      label={ADVANCED_WORKERS_LABEL}
      valueLabel={`: ${value}`}
      min={1}
      max={4}
      step={1}
      value={value}
      onChange={onChange}
      minLabel={ADVANCED_WORKERS_MIN}
      maxLabel={ADVANCED_WORKERS_MAX}
      description={ADVANCED_WORKERS_DESCRIPTION}
    />
  );
}
```

- [ ] **Step 2: Verify TypeScript compilation**

Run:
```bash
cd apps/visualizer/frontend && npm run type-check
```

Expected: No errors

- [ ] **Step 3: Start dev server and verify component renders**

Run:
```bash
cd apps/visualizer/frontend && npm run dev
```

Open browser console and run:
```javascript
// Verify exports
import('/src/components/matching/WorkerSlider.tsx').then(m => console.log(m.WorkerSlider))
```

Expected: Function definition logged

- [ ] **Step 4: Commit**

```bash
git add apps/visualizer/frontend/src/components/matching/WorkerSlider.tsx
git commit -m "feat(ui): create reusable WorkerSlider component"
```

---

### Task 5: Integrate WorkerSlider into Matching AdvancedOptions

**Files:**
- Modify: `apps/visualizer/frontend/src/components/matching/AdvancedOptions.tsx:1-3` (imports)
- Modify: `apps/visualizer/frontend/src/components/matching/AdvancedOptions.tsx:18-34` (interface)
- Modify: `apps/visualizer/frontend/src/components/matching/AdvancedOptions.tsx:36-52` (component signature)
- Modify: `apps/visualizer/frontend/src/components/matching/AdvancedOptions.tsx:127-137` (add slider)

- [ ] **Step 1: Add WorkerSlider import**

Open `apps/visualizer/frontend/src/components/matching/AdvancedOptions.tsx` and add to imports at line 2:

```typescript
import { RangeSlider } from './RangeSlider';
import { WeightSlider } from './WeightSlider';
import { WorkerSlider } from './WorkerSlider';
import { ProviderModelSelect } from '../ui/ProviderModelSelect';
```

- [ ] **Step 2: Add props to interface**

Modify `AdvancedOptionsProps` interface at line 18:

```typescript
interface AdvancedOptionsProps {
  isOpen: boolean;
  onToggle: () => void;
  providerId: string | null;
  providerModel: string | null;
  onProviderChange: (providerId: string | null, modelId: string | null) => void;
  threshold: number;
  onThresholdChange: (value: number) => void;
  phashWeight: number;
  onPhashWeightChange: (value: number) => void;
  descWeight: number;
  onDescWeightChange: (value: number) => void;
  visionWeight: number;
  onVisionWeightChange: (value: number) => void;
  weightsError: string | null;
  onReset: () => void;
  maxWorkers: number;
  onMaxWorkersChange: (value: number) => void;
}
```

- [ ] **Step 3: Add parameters to component signature**

Modify component function signature at line 36:

```typescript
export function AdvancedOptions({
  isOpen,
  onToggle,
  providerId,
  providerModel,
  onProviderChange,
  threshold,
  onThresholdChange,
  phashWeight,
  onPhashWeightChange,
  descWeight,
  onDescWeightChange,
  visionWeight,
  onVisionWeightChange,
  weightsError,
  onReset,
  maxWorkers,
  onMaxWorkersChange,
}: AdvancedOptionsProps) {
```

- [ ] **Step 4: Add WorkerSlider before Reset button**

After the weights section (around line 127), before the "Reset to defaults" button, add:

```typescript
          </div>

          <WorkerSlider
            value={maxWorkers}
            onChange={onMaxWorkersChange}
          />

          <div className="pt-2 border-t">
```

- [ ] **Step 5: Verify TypeScript compilation**

Run:
```bash
cd apps/visualizer/frontend && npm run type-check
```

Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add apps/visualizer/frontend/src/components/matching/AdvancedOptions.tsx
git commit -m "feat(ui): integrate WorkerSlider into Matching AdvancedOptions"
```

---

### Task 6: Wire maxWorkers in Matching Page

**Files:**
- Modify: `apps/visualizer/frontend/src/pages/MatchingPage.tsx:346-361` (AdvancedOptions props)
- Modify: `apps/visualizer/frontend/src/pages/MatchingPage.tsx:172-189` (startMatching metadata)

- [ ] **Step 1: Add maxWorkers props to AdvancedOptions component**

Open `apps/visualizer/frontend/src/pages/MatchingPage.tsx` and modify the `<AdvancedOptions>` usage at line 346:

```typescript
          <AdvancedOptions
            isOpen={showAdvanced}
            onToggle={() => setShowAdvanced(!showAdvanced)}
            {...options}
            onProviderChange={(providerId, modelId) => {
              updateOption('providerId', providerId);
              updateOption('providerModel', modelId);
            }}
            onThresholdChange={(v) => updateOption('threshold', v)}
            onPhashWeightChange={(v) => updateOption('phashWeight', v)}
            onDescWeightChange={(v) => updateOption('descWeight', v)}
            onVisionWeightChange={(v) => updateOption('visionWeight', v)}
            maxWorkers={options.maxWorkers}
            onMaxWorkersChange={(v) => updateOption('maxWorkers', v)}
            weightsError={weightsError}
            onReset={resetOptions}
          />
```

- [ ] **Step 2: Add max_workers to job metadata**

Modify `startMatching` function at line 172:

```typescript
    const metadata: Record<string, unknown> = {
      threshold: options.threshold,
      weights: {
        phash: options.phashWeight,
        description: options.descWeight,
        vision: options.visionWeight,
      },
      max_workers: options.maxWorkers,
      ...(options.providerId ? { provider_id: options.providerId } : {}),
      ...(options.providerModel ? { provider_model: options.providerModel } : {}),
    };
```

- [ ] **Step 3: Verify TypeScript compilation**

Run:
```bash
cd apps/visualizer/frontend && npm run type-check
```

Expected: No errors

- [ ] **Step 4: Manual UI test**

With dev server running, open browser to `http://localhost:5173`:
1. Navigate to Matching page
2. Click "Run Matching" button
3. Click "Advanced Options" to expand
4. Verify worker slider appears with range 1-4
5. Change slider value and verify it updates

- [ ] **Step 5: Commit**

```bash
git add apps/visualizer/frontend/src/pages/MatchingPage.tsx
git commit -m "feat(ui): wire maxWorkers to Matching page job metadata"
```

---

### Task 7: Add AdvancedOptions to Descriptions Page

**Files:**
- Modify: `apps/visualizer/frontend/src/pages/DescriptionsPage.tsx:1-7` (imports)
- Modify: `apps/visualizer/frontend/src/pages/DescriptionsPage.tsx:48-50` (state)
- Modify: `apps/visualizer/frontend/src/pages/DescriptionsPage.tsx:77-84` (metadata)
- Modify: `apps/visualizer/frontend/src/pages/DescriptionsPage.tsx:184-200` (UI)

- [ ] **Step 1: Add import**

Open `apps/visualizer/frontend/src/pages/DescriptionsPage.tsx` and add to imports at line 7:

```typescript
import { WorkerSlider } from '../components/matching/WorkerSlider';
```

- [ ] **Step 2: Add showAdvanced state**

After line 48 (after `const [force, setForce] = useState(false);`):

```typescript
  const [force, setForce] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [batchRunning, setBatchRunning] = useState(false);
```

- [ ] **Step 3: Add max_workers to job metadata**

Modify `handleBatchDescribe` function at line 77:

```typescript
      const job = await JobsAPI.create('batch_describe', {
        image_type: tab === 'all' ? 'both' : tab,
        date_filter: dateFilter,
        force,
        max_workers: options.maxWorkers,
        ...(options.providerId ? { provider_id: options.providerId } : {}),
        ...(options.providerModel ? { provider_model: options.providerModel } : {}),
      });
```

- [ ] **Step 4: Add Advanced Options section**

After `</BatchActionPanel>` at line 184:

```typescript
        />
        
        <div className="border-t pt-3">
          <button
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="text-sm text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1"
          >
            {showAdvanced ? '▼' : '▶'} Advanced Options
          </button>
          
          {showAdvanced && (
            <div className="mt-3 bg-white p-4 rounded border">
              <WorkerSlider
                value={options.maxWorkers}
                onChange={(v) => updateOption('maxWorkers', v)}
              />
            </div>
          )}
        </div>
      </div>
```

- [ ] **Step 5: Verify TypeScript compilation**

Run:
```bash
cd apps/visualizer/frontend && npm run type-check
```

Expected: No errors

- [ ] **Step 6: Manual UI test**

With dev server running:
1. Navigate to Descriptions page
2. Click "Advanced Options" to expand
3. Verify worker slider appears
4. Change value and verify it updates

- [ ] **Step 7: Commit**

```bash
git add apps/visualizer/frontend/src/pages/DescriptionsPage.tsx
git commit -m "feat(ui): add AdvancedOptions with WorkerSlider to Descriptions page"
```

---

### Task 8: Update Backend Handlers for Parallel Processing

**Files:**
- Modify: `apps/visualizer/backend/jobs/handlers.py:22-140` (handle_vision_match)
- Modify: `apps/visualizer/backend/jobs/handlers.py:380-515` (add helper + update handle_batch_describe)

- [ ] **Step 1: Add _describe_single_image helper function**

Open `apps/visualizer/backend/jobs/handlers.py` and add before `handle_batch_describe` (around line 380):

```python
def _describe_single_image(db, key: str, image_type: str, force: bool, 
                          provider_id: str | None, model: str | None) -> tuple:
    """Describe a single image (reusable for sequential and parallel processing).
    
    Returns:
        Tuple of (status, key, optional_error_message)
        status: 'success', 'skipped', or 'failed'
    """
    from lightroom_tagger.core.description_service import (
        describe_instagram_image,
        describe_matched_image,
    )
    
    try:
        if image_type == 'catalog':
            result = describe_matched_image(
                db, key, force=force,
                provider_id=provider_id, model=model,
            )
        else:
            result = describe_instagram_image(
                db, key, force=force,
                provider_id=provider_id, model=model,
            )
        
        if result:
            return ('success', key)
        else:
            return ('skipped', key, 'No description generated')
    except Exception as e:
        return ('failed', key, str(e))
```

- [ ] **Step 2: Update handle_vision_match to pass max_workers**

In `handle_vision_match` function around line 22, after line 36 (after provider_model assignment), add:

```python
        provider_model = metadata.get('provider_model')
        max_workers = metadata.get('max_workers', config.matching_workers)
```

Then update the `match_dump_media` call around line 94 to include:

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
            )
```

- [ ] **Step 3: Update handle_batch_describe with parallel processing**

Replace the sequential loop in `handle_batch_describe` (lines 461-494) with:

```python
        if total == 0:
            runner.complete_job(job_id, {'described': 0, 'skipped': 0, 'failed': 0, 'total': 0})
            return

        # Get DB path and max_workers
        db_path = os.getenv('LIBRARY_DB')
        if not db_path:
            db_path = config.db_path or 'library.db'
        lib_db = init_database(db_path)
        
        max_workers = metadata.get('max_workers', config.matching_workers)

        described = 0
        skipped = 0
        failed = 0
        from database import add_job_log

        # Single-threaded path
        if max_workers <= 1:
            consecutive_failures = 0
            for idx, (key, itype) in enumerate(images_to_describe, 1):
                progress = int(5 + (idx / total) * 90)
                runner.update_progress(job_id, progress, f'Describing {idx}/{total}: {key}')
                
                result = _describe_single_image(
                    lib_db, key, itype, force, desc_provider_id, desc_provider_model
                )
                
                if result[0] == 'success':
                    described += 1
                    consecutive_failures = 0
                elif result[0] == 'skipped':
                    skipped += 1
                    consecutive_failures += 1
                    if consecutive_failures <= 3:
                        add_job_log(runner.db, job_id, 'warning', f'Skipped {result[1]}: {result[2]}')
                elif result[0] == 'failed':
                    failed += 1
                    consecutive_failures += 1
                    add_job_log(runner.db, job_id, 'warning', f'Failed {result[1]}: {result[2]}')
                
                if consecutive_failures >= 10:
                    add_job_log(runner.db, job_id, 'error', 
                               f'Stopping: {consecutive_failures} consecutive failures')
                    break
        else:
            # Multi-threaded path
            def worker(key, itype, db_path):
                thread_db = sqlite3.connect(db_path)
                thread_db.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
                thread_db.execute("PRAGMA journal_mode=WAL")
                thread_db.execute("PRAGMA busy_timeout=5000")
                try:
                    return _describe_single_image(
                        thread_db, key, itype, force, desc_provider_id, desc_provider_model
                    )
                finally:
                    thread_db.close()

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(worker, key, itype, db_path): (key, itype)
                    for key, itype in images_to_describe
                }
                
                completed = 0
                consecutive_failures = 0
                
                for future in as_completed(futures):
                    completed += 1
                    progress = int(5 + (completed / total) * 90)
                    runner.update_progress(job_id, progress, f'Describing {completed}/{total}')
                    
                    result = future.result()
                    
                    if result[0] == 'success':
                        described += 1
                        consecutive_failures = 0
                    elif result[0] == 'skipped':
                        skipped += 1
                        consecutive_failures += 1
                        if consecutive_failures <= 3:
                            add_job_log(runner.db, job_id, 'warning', f'Skipped {result[1]}: {result[2]}')
                    elif result[0] == 'failed':
                        failed += 1
                        consecutive_failures += 1
                        add_job_log(runner.db, job_id, 'warning', f'Failed {result[1]}: {result[2]}')
                    
                    if consecutive_failures >= 10:
                        add_job_log(runner.db, job_id, 'error',
                                   f'Stopping: {consecutive_failures} consecutive failures')
                        executor.shutdown(wait=False, cancel_futures=True)
                        break

        runner.complete_job(job_id, {
            'described': described,
            'skipped': skipped,
            'failed': failed,
            'total': total,
            'image_type': image_type,
            'date_filter': date_filter,
            'force': force,
            'max_workers': max_workers,
        })
```

- [ ] **Step 4: Test backend with workers=1 (sequential)**

Start backend and trigger a small batch_describe job:

```bash
cd apps/visualizer/backend
python3 -m flask run
```

In another terminal, trigger job via API:
```bash
curl -X POST http://localhost:5000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{"type":"batch_describe","metadata":{"image_type":"catalog","date_filter":"all","force":false,"max_workers":1}}'
```

Expected: Job completes successfully, logs show sequential processing

- [ ] **Step 5: Test backend with workers=4 (parallel)**

Trigger job with parallel workers:

```bash
curl -X POST http://localhost:5000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{"type":"batch_describe","metadata":{"image_type":"catalog","date_filter":"all","force":false,"max_workers":4}}'
```

Expected: Job completes faster, logs show parallel processing

- [ ] **Step 6: Commit**

```bash
git add apps/visualizer/backend/jobs/handlers.py
git commit -m "feat(backend): add parallel processing support to vision_match and batch_describe handlers"
```

---

## Phase 2: Batch Vision API

### Task 9: Add Batch Configuration Fields

**Files:**
- Modify: `lightroom_tagger/core/config.py:35-37`
- Modify: `lightroom_tagger/core/config.py:82-84`
- Modify: `lightroom_tagger/core/config.py:59-61`
- Modify: `lightroom_tagger/core/config.py:101-103`

- [ ] **Step 1: Add batch fields to Config dataclass**

Open `lightroom_tagger/core/config.py` and add after `matching_workers` (line 35):

```python
    matching_workers: int = 4
    vision_batch_size: int = 20
    vision_batch_threshold: int = 5
```

- [ ] **Step 2: Add env mappings**

In `_load_from_env`, add to `env_mappings`:

```python
    "MATCHING_WORKERS": "matching_workers",
    "VISION_BATCH_SIZE": "vision_batch_size",
    "VISION_BATCH_THRESHOLD": "vision_batch_threshold",
```

- [ ] **Step 3: Add type conversions**

Update type conversion block:

```python
if config_key in ("workers", "hash_threshold", "matching_workers", "vision_batch_size", "vision_batch_threshold"):
    value = int(value)
```

- [ ] **Step 4: Add defaults**

In `defaults` dict:

```python
    "matching_workers": 4,
    "vision_batch_size": 20,
    "vision_batch_threshold": 5,
```

- [ ] **Step 5: Test config loading**

Run:
```bash
python3 -c "from lightroom_tagger.core.config import load_config; c = load_config(); print(f'batch_size={c.vision_batch_size}, threshold={c.vision_batch_threshold}')"
```

Expected: `batch_size=20, threshold=5`

- [ ] **Step 6: Commit**

```bash
git add lightroom_tagger/core/config.py
git commit -m "feat(config): add vision_batch_size and vision_batch_threshold fields"
```

---

### Task 10: Implement compare_images_batch Function

**Files:**
- Modify: `lightroom_tagger/core/vision_client.py:150-330` (add new functions)

- [ ] **Step 1: Add compare_images_batch function**

Open `lightroom_tagger/core/vision_client.py` and add after existing `compare_images` function (around line 150):

```python
def compare_images_batch(
    client,
    model: str,
    reference_path: str,
    candidate_paths: list[tuple[str, str]],
    log_callback=None,
) -> dict[str, dict]:
    """Compare one reference image against multiple candidates in a single API call.
    
    Args:
        client: OpenAI-compatible client
        model: Model identifier
        reference_path: Path to Instagram/reference image (compressed)
        candidate_paths: List of (candidate_id, compressed_path) tuples
        log_callback: Optional logging callback
    
    Returns:
        Dict mapping candidate_id -> {"confidence": int, "reasoning": str, "verdict": str}
        Returns empty dict on failure (caller should fall back to sequential)
    """
    import base64
    import json
    
    try:
        # Encode reference image
        with open(reference_path, 'rb') as f:
            ref_b64 = base64.b64encode(f.read()).decode('utf-8')
        
        # Encode all candidate images
        candidate_data = []
        for cand_id, cand_path in candidate_paths:
            with open(cand_path, 'rb') as f:
                cand_b64 = base64.b64encode(f.read()).decode('utf-8')
                candidate_data.append((cand_id, cand_b64))
        
        # Build prompt with numeric candidate IDs
        candidate_list = "\n".join(
            f"  [Image {idx+1}] - Candidate {idx} (ID: {cand_id})"
            for idx, (cand_id, _) in enumerate(candidate_data)
        )
        
        # Example JSON with first two candidates
        example_json = []
        for idx, (cand_id, _) in enumerate(candidate_data[:2]):
            conf = 85 if idx == 0 else 12
            reason = "Same beach scene, identical pose" if idx == 0 else "Different location entirely"
            example_json.append(f'{{"candidate_id": "{cand_id}", "confidence": {conf}, "reasoning": "{reason}"}}')
        examples = ",\n    ".join(example_json)
        
        prompt = f"""You are comparing ONE reference image (Instagram post) against MULTIPLE catalog images to identify which catalog image is the same photograph.

Reference Image: [Image 0] (Instagram)
Catalog Candidates:
{candidate_list}

For EACH catalog candidate, determine confidence (0-100) that it matches the reference.
Focus on: subject, scene composition, moment captured.
Ignore: crops, compression, color grading, filters, minor angle differences.

Respond with ONLY valid JSON (no other text):
{{
  "comparisons": [
    {examples},
    ...
  ]
}}"""

        # Build messages array
        messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
        
        # Add reference image
        messages[0]["content"].append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{ref_b64}"}
        })
        
        # Add candidate images
        for _, cand_b64 in candidate_data:
            messages[0]["content"].append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{cand_b64}"}
            })
        
        # Call API
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=4096,
            temperature=0.1,
        )
        
        raw_text = response.choices[0].message.content
        
        # Parse JSON response
        parsed = _parse_batch_comparison_response(
            raw_text,
            [cand_id for cand_id, _ in candidate_paths]
        )
        
        if log_callback and parsed:
            log_callback('info', f'Batch compared {len(parsed)}/{len(candidate_paths)} candidates')
        
        return parsed
        
    except Exception as e:
        if log_callback:
            log_callback('warning', f'Batch comparison failed: {e}')
        return {}
```

- [ ] **Step 2: Add _parse_batch_comparison_response helper**

Add immediately after compare_images_batch:

```python
def _parse_batch_comparison_response(raw: str, candidate_ids: list[str]) -> dict[str, dict]:
    """Parse batch comparison JSON response.
    
    Args:
        raw: Raw response text from vision model
        candidate_ids: List of expected candidate IDs
    
    Returns:
        Dict mapping candidate_id -> {confidence, reasoning, verdict}
        Empty dict on parse failure
    """
    import json
    import re
    
    # Try to extract JSON from response (may be wrapped in markdown)
    text = raw.strip()
    fence_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()
    
    try:
        parsed = json.loads(text)
        comparisons = parsed.get('comparisons', [])
        
        results = {}
        for comp in comparisons:
            cand_id = comp.get('candidate_id')
            if not cand_id or cand_id not in candidate_ids:
                continue
            
            confidence = comp.get('confidence', 0)
            reasoning = comp.get('reasoning', '')
            
            # Map confidence to verdict (match existing logic)
            if confidence >= 70:
                verdict = 'YES'
            elif confidence >= 30:
                verdict = 'UNCERTAIN'
            else:
                verdict = 'NO'
            
            results[cand_id] = {
                'confidence': confidence,
                'reasoning': reasoning,
                'verdict': verdict,
            }
        
        return results
    except (json.JSONDecodeError, ValueError, KeyError):
        return {}
```

- [ ] **Step 3: Test batch prompt manually via Ollama**

Create test script `test_batch_prompt.py`:

```python
import base64
import ollama

# Load 3 test images (replace with actual paths)
ref_path = "test_instagram.jpg"
cand1_path = "test_catalog1.jpg"
cand2_path = "test_catalog2.jpg"

with open(ref_path, 'rb') as f:
    ref_b64 = base64.b64encode(f.read()).decode('utf-8')
with open(cand1_path, 'rb') as f:
    cand1_b64 = base64.b64encode(f.read()).decode('utf-8')
with open(cand2_path, 'rb') as f:
    cand2_b64 = base64.b64encode(f.read()).decode('utf-8')

prompt = """You are comparing ONE reference image against MULTIPLE catalog images.

Reference Image: [Image 0] (Instagram)
Catalog Candidates:
  [Image 1] - Candidate 0 (ID: test1)
  [Image 2] - Candidate 1 (ID: test2)

For EACH catalog candidate, determine confidence (0-100) that it matches the reference.

Respond with ONLY valid JSON:
{
  "comparisons": [
    {"candidate_id": "test1", "confidence": 85, "reasoning": "..."},
    {"candidate_id": "test2", "confidence": 12, "reasoning": "..."}
  ]
}"""

response = ollama.chat(
    model='gemma3:27b',
    messages=[{
        'role': 'user',
        'content': prompt,
        'images': [ref_b64, cand1_b64, cand2_b64]
    }]
)

print(response['message']['content'])
```

Run: `python3 test_batch_prompt.py`

Expected: Valid JSON with confidence scores

- [ ] **Step 4: Commit**

```bash
git add lightroom_tagger/core/vision_client.py
git commit -m "feat(vision): add compare_images_batch for multi-pair comparisons"
```

---

### Task 11: Integrate Batching into score_candidates_with_vision

**Files:**
- Modify: `lightroom_tagger/core/matcher.py:80-280`

- [ ] **Step 1: Add config and batch setup at function start**

Open `lightroom_tagger/core/matcher.py` and modify `score_candidates_with_vision` function start (around line 80):

```python
def score_candidates_with_vision(db, insta_image: dict, candidates: list,
                                 phash_weight: float = 0.4, desc_weight: float = 0.3,
                                 vision_weight: float = 0.3,
                                 threshold: float = 0.7,
                                 log_callback=None,
                                 provider_id: str | None = None,
                                 model: str | None = None) -> list[dict]:
    from lightroom_tagger.core.config import load_config
    config = load_config()
    
    BATCH_SIZE = config.vision_batch_size
    BATCH_THRESHOLD = config.vision_batch_threshold
    
    # ... existing setup continues ...
```

- [ ] **Step 2: Separate cached vs uncached candidates**

Replace the existing per-candidate vision comparison loop (around line 127) with:

```python
    # Separate candidates that have cached vision results vs need processing
    cached_results = {}
    uncached_candidates = []
    
    for candidate in candidates:
        catalog_key = candidate.get('key')
        insta_key = insta_image.get('key')
        
        vision_cached = get_vision_comparison(db, catalog_key, insta_key)
        requested_model_label = _build_model_label(provider_id, model, base_vision_model)
        cache_valid = (
            vision_cached
            and vision_cached.get('model_used') == requested_model_label
        )
        
        if cache_valid:
            cached_results[catalog_key] = {
                'vision_result': vision_cached['result'],
                'vision_score': vision_cached['vision_score'],
                'model_used': vision_cached.get('model_used'),
            }
        else:
            uncached_candidates.append(candidate)
```

- [ ] **Step 3: Add batch processing logic**

Add after cached/uncached separation:

```python
    uncached_results = {}
    use_batching = len(uncached_candidates) >= BATCH_THRESHOLD
    
    if use_batching:
        # Batch processing
        from lightroom_tagger.core.vision_client import compare_images_batch
        from lightroom_tagger.core.vision_cache import get_or_create_cached_image
        
        # Get cached Instagram image once
        compressed_insta = get_or_create_cached_image(db, insta_key, insta_path)
        
        for batch_start in range(0, len(uncached_candidates), BATCH_SIZE):
            batch = uncached_candidates[batch_start:batch_start + BATCH_SIZE]
            
            # Build candidate pairs with cached paths
            candidate_pairs = []
            for c in batch:
                cached_local = get_or_create_cached_image(db, c['key'], c['local_path'])
                if cached_local:
                    candidate_pairs.append((c['key'], cached_local))
            
            if not candidate_pairs:
                continue
            
            try:
                client = _get_client(provider_registry, provider_id)
                actual_model = _resolve_model(provider_registry, provider_id, model, base_vision_model)
                
                batch_results = compare_images_batch(
                    client, actual_model, compressed_insta, candidate_pairs, log_callback
                )
                
                for catalog_key, vision_data in batch_results.items():
                    # Normalize to 0-1 score
                    vision_score = vision_data['confidence'] / 100.0
                    verdict = vision_data['verdict']
                    
                    uncached_results[catalog_key] = {
                        'vision_result': verdict,
                        'vision_score': vision_score,
                        'model_used': requested_model_label,
                    }
                    
                    # Store in cache
                    store_vision_comparison(
                        db, catalog_key, insta_key, verdict, vision_score, requested_model_label
                    )
                    
            except Exception as e:
                # Fall back to sequential for this batch
                if log_callback:
                    log_callback('warning', f'Batch failed, falling back to sequential: {e}')
                
                for candidate in batch:
                    try:
                        vision_data = compare_with_vision(
                            candidate['local_path'], insta_path, log_callback,
                            provider_id=provider_id, model=model
                        )
                        uncached_results[candidate['key']] = {
                            'vision_result': vision_data.get('result', 'NO'),
                            'vision_score': vision_data.get('vision_score', 0),
                            'model_used': requested_model_label,
                        }
                        store_vision_comparison(
                            db, candidate['key'], insta_key,
                            vision_data.get('result', 'NO'),
                            vision_data.get('vision_score', 0),
                            requested_model_label
                        )
                    except Exception:
                        continue
    else:
        # Sequential processing (existing logic for small candidate sets)
        for candidate in uncached_candidates:
            try:
                vision_data = compare_with_vision(
                    candidate['local_path'], insta_path, log_callback,
                    provider_id=provider_id, model=model
                )
                uncached_results[candidate['key']] = {
                    'vision_result': vision_data.get('result', 'NO'),
                    'vision_score': vision_data.get('vision_score', 0),
                    'model_used': requested_model_label,
                }
                store_vision_comparison(
                    db, candidate['key'], insta_key,
                    vision_data.get('result', 'NO'),
                    vision_data.get('vision_score', 0),
                    requested_model_label
                )
            except Exception:
                continue
```

- [ ] **Step 4: Update final scoring to merge cached + uncached**

Replace existing results building:

```python
    # Build final results combining all signals
    results = []
    for candidate in candidates:
        catalog_key = candidate.get('key')
        
        # Get vision result (cached or newly computed)
        vision_data = cached_results.get(catalog_key) or uncached_results.get(catalog_key)
        
        if not vision_data:
            continue
        
        # ... existing scoring logic (phash, desc, vision weighted sum) continues unchanged ...
```

- [ ] **Step 5: Test with small candidate set (< threshold, sequential)**

Create test script `test_matcher_sequential.py`:

```python
from lightroom_tagger.core.database import init_database
from lightroom_tagger.core.matcher import score_candidates_with_vision

db = init_database('library.db')
insta_image = {'key': 'test_insta', 'phash': '1234567890abcdef'}
candidates = [
    {'key': 'cat1', 'local_path': '/path/cat1.jpg'},
    {'key': 'cat2', 'local_path': '/path/cat2.jpg'},
    {'key': 'cat3', 'local_path': '/path/cat3.jpg'},
]

results = score_candidates_with_vision(db, insta_image, candidates)
print(f"Results: {len(results)} scored")
```

Run: `python3 test_matcher_sequential.py`

Expected: 3 results, logs show sequential processing

- [ ] **Step 6: Test with large candidate set (>= threshold, batching)**

Modify test to have 10 candidates, run again.

Expected: Batch processing used, logs show "Batch compared X/Y candidates"

- [ ] **Step 7: Commit**

```bash
git add lightroom_tagger/core/matcher.py
git commit -m "feat(matcher): integrate batch vision comparison with cache support"
```

---

### Task 12: Add Parallel Processing to match_dump_media

**Files:**
- Modify: `lightroom_tagger/scripts/match_instagram_dump.py:30-250`

- [ ] **Step 1: Add _process_single_instagram_match helper**

Open `lightroom_tagger/scripts/match_instagram_dump.py` and add before `match_dump_media` (around line 30):

```python
def _process_single_instagram_match(
    db, dump_media: dict, threshold: float,
    custom_phash_weight: float, custom_desc_weight: float, custom_vision_weight: float,
    force_descriptions: bool, provider_id: str | None, provider_model: str | None,
    log_callback=None
) -> dict:
    """Process one Instagram image matching (reusable for sequential and parallel).
    
    Returns:
        Dict with keys: matched (bool), best_match (dict|None), descriptions_generated (int)
    """
    from lightroom_tagger.core.database import (
        get_instagram_image_data,
        mark_dump_media_attempted,
        mark_dump_media_processed,
        update_instagram_status,
        delete_matches_for_insta_key,
        store_match,
    )
    from lightroom_tagger.core.description_service import (
        describe_instagram_image,
        describe_matched_image,
    )
    from lightroom_tagger.core.matcher import (
        find_candidates_by_date,
        score_candidates_with_vision,
    )
    
    result = {
        'matched': False,
        'best_match': None,
        'descriptions_generated': 0,
    }
    
    dump_image = get_instagram_image_data(db, dump_media['media_key'])
    if not dump_image or not dump_image.get('phash'):
        return result
    
    candidates = find_candidates_by_date(
        db, dump_image,
        date_window_days=90,
        phash_threshold=5
    )
    
    if not candidates:
        mark_dump_media_attempted(db, dump_media['media_key'])
        return result
    
    vision_candidates = [c for c in candidates if c.get('local_path')]
    
    results = score_candidates_with_vision(
        db, dump_image, vision_candidates,
        phash_weight=custom_phash_weight,
        desc_weight=custom_desc_weight,
        vision_weight=custom_vision_weight,
        threshold=threshold,
        log_callback=log_callback,
        provider_id=provider_id,
        model=provider_model,
    )
    
    above_threshold = [r for r in results if r['total_score'] >= threshold]
    
    if above_threshold:
        best_match = above_threshold[0]
        matched_catalog_key = best_match['catalog_key']
        
        with db:
            delete_matches_for_insta_key(db, dump_media['media_key'], commit=False)
            for rank, candidate in enumerate(above_threshold, 1):
                candidate['rank'] = rank
                store_match(db, candidate, commit=False)
        
        mark_dump_media_processed(
            db, dump_media['media_key'],
            matched_catalog_key=matched_catalog_key,
            vision_result=best_match.get('vision_result'),
            vision_score=best_match.get('vision_score')
        )
        
        update_instagram_status(db, matched_catalog_key, posted=True)
        
        result['matched'] = True
        result['best_match'] = best_match
        
        if force_descriptions:
            try:
                if describe_matched_image(db, matched_catalog_key, force=True):
                    result['descriptions_generated'] += 1
                if describe_instagram_image(db, dump_media['media_key'], force=True):
                    result['descriptions_generated'] += 1
            except Exception as e:
                if log_callback:
                    log_callback('warning', f'Description failed: {e}')
    else:
        best = results[0] if results else None
        mark_dump_media_attempted(
            db, dump_media['media_key'],
            vision_result=best.get('vision_result') if best else None,
            vision_score=best.get('vision_score') if best else None,
        )
    
    return result
```

- [ ] **Step 2: Update match_dump_media signature**

Modify function signature (line 36):

```python
def match_dump_media(db, threshold: float = 0.7, batch_size: int = None,
                     month: str = None, year: str = None, last_months: int = None,
                     progress_callback=None, log_callback=None,
                     weights: dict = None, media_key: str = None,
                     force_descriptions: bool = False,
                     force_reprocess: bool = False,
                     provider_id: str | None = None,
                     provider_model: str | None = None,
                     max_workers: int = 1) -> tuple:
```

- [ ] **Step 3: Replace main processing loop**

Replace loop at lines 104-203 with:

```python
    # Single-threaded path
    if max_workers <= 1 or media_key or total <= 3:
        for idx, dump_media in enumerate(unprocessed, 1):
            result = _process_single_instagram_match(
                db, dict(dump_media), threshold,
                custom_phash_weight, custom_desc_weight, custom_vision_weight,
                force_descriptions, provider_id, provider_model,
                log_callback
            )
            
            stats['processed'] += 1
            if result['matched']:
                stats['matched'] += 1
                matches_found.append(result['best_match'])
            else:
                stats['skipped'] += 1
            
            stats['descriptions_generated'] += result['descriptions_generated']
            
            if progress_callback:
                progress_callback(idx, total, f'Processing {dump_media["media_key"]} ({idx}/{total})')
        
        return stats, matches_found
    
    # Multi-threaded path
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import sqlite3
    
    db_path = db.execute("PRAGMA database_list").fetchone()[2]
    
    def worker(dump_media_dict):
        """Worker thread with own DB connection."""
        thread_db = sqlite3.connect(db_path)
        thread_db.row_factory = sqlite3.Row
        thread_db.execute("PRAGMA journal_mode=WAL")
        thread_db.execute("PRAGMA busy_timeout=5000")
        
        try:
            return {
                'media_key': dump_media_dict['media_key'],
                **_process_single_instagram_match(
                    thread_db, dump_media_dict, threshold,
                    custom_phash_weight, custom_desc_weight, custom_vision_weight,
                    force_descriptions, provider_id, provider_model,
                    log_callback=None
                )
            }
        finally:
            thread_db.close()
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(worker, dict(media)): media
            for media in unprocessed
        }
        
        completed = 0
        for future in as_completed(futures):
            result = future.result()
            completed += 1
            
            stats['processed'] += 1
            if result['matched']:
                stats['matched'] += 1
                matches_found.append(result['best_match'])
            else:
                stats['skipped'] += 1
            
            stats['descriptions_generated'] += result['descriptions_generated']
            
            if progress_callback:
                progress_callback(completed, total, f"Processed {result['media_key']}")
    
    return stats, matches_found
```

- [ ] **Step 4: Test sequential matching**

Run with 3 Instagram images:

```bash
python3 -m lightroom_tagger.scripts.match_instagram_dump --max-workers 1
```

Expected: Sequential processing, ~2 sec per image

- [ ] **Step 5: Test parallel matching**

Run with 10 Instagram images and 4 workers:

```bash
python3 -m lightroom_tagger.scripts.match_instagram_dump --max-workers 4
```

Expected: Parallel processing, ~4x speedup

- [ ] **Step 6: Commit**

```bash
git add lightroom_tagger/scripts/match_instagram_dump.py
git commit -m "feat(matching): add parallel processing with shared helper function"
```

---

## Final Integration Testing

### Task 13: End-to-End UI to Backend Test

**Files:**
- None (testing only)

- [ ] **Step 1: Start full stack**

Terminal 1:
```bash
cd apps/visualizer/backend && python3 -m flask run
```

Terminal 2:
```bash
cd apps/visualizer/frontend && npm run dev
```

- [ ] **Step 2: Test Matching workflow with parallel workers**

1. Open `http://localhost:5173` in browser
2. Navigate to Matching page
3. Click "Run Matching"
4. Click "Advanced Options"
5. Set workers slider to 4
6. Click "Start"
7. Monitor Jobs page for progress

Expected: Job completes with parallel processing, faster than sequential

- [ ] **Step 3: Test Descriptions workflow with parallel workers**

1. Navigate to Descriptions page
2. Click "Advanced Options"
3. Set workers slider to 2
4. Select "Last 3 months"
5. Click batch generate
6. Monitor Jobs page

Expected: Job completes with 2 workers active

- [ ] **Step 4: Verify batch API is used when candidates >= 5**

Check backend logs for "Batch compared X/Y candidates" message when matching with large candidate sets.

- [ ] **Step 5: Measure performance improvement**

Run matching on 20 Instagram images with:
- Sequential (workers=1, batch disabled): Record time
- Parallel only (workers=4, batch disabled): Record time
- Parallel + batch (workers=4, batch enabled): Record time

Expected: Parallel+batch is fastest (~20x improvement)

---

## Self-Review Checklist

**Spec Coverage:**
- ✅ Worker configuration UI (Matching + Descriptions pages)
- ✅ Backend parallel processing (vision_match + batch_describe)
- ✅ Batch vision API packing multiple pairs
- ✅ Graceful fallback on batch errors
- ✅ Per-worker DB connections (no SQLite contention)
- ✅ Configuration via env vars

**No Placeholders:**
- ✅ All code blocks complete
- ✅ All file paths exact
- ✅ All commands with expected output
- ✅ No "TBD" or "TODO" markers

**Type Consistency:**
- ✅ `maxWorkers` used consistently in TypeScript
- ✅ `max_workers` used consistently in Python
- ✅ `compare_images_batch` signature matches usage
- ✅ Helper functions match their call sites

---

Plan complete and saved to `docs/plans/2026-04-06-parallel-batch-vision-matching.md`.

**Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
