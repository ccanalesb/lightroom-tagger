## RESEARCH COMPLETE

**Authority note:** `.planning/phases/11-v3-deferred-polish/11-CONTEXT.md` narrows several bullets that still read broadly in `.planning/ROADMAP.md` Phase 11 (e.g. `vision_judgments_total` **rename**, stack_size **audit**, tool schema **tightening**, full embed todo). For planning, treat **11-CONTEXT.md decisions D-01–D-04** as the binding scope: **comments + copy/a11y + Search navigation links only** (no behavior change to schema output, log keys, or stack column).

---

### 1. AdvancedOptions.tsx — aria-expanded fix

**Current disclosure control (no a11y state):**

```71:76:apps/visualizer/frontend/src/components/matching/AdvancedOptions.tsx
      <button
        onClick={onToggle}
        className="text-sm text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1"
      >
        {isOpen ? '▼' : '▶'} {ADVANCED_OPTIONS_TITLE}
      </button>
```

**Expandable panel (needs stable `id` for `aria-controls`):**

```78:79:apps/visualizer/frontend/src/components/matching/AdvancedOptions.tsx
      {isOpen && (
        <div className="mt-4 space-y-4 bg-white p-4 rounded border">
```

**State name:** prop is `isOpen` (boolean). Use **`aria-expanded={isOpen}`** on the same button.

**Exact change needed (per `11-UI-SPEC.md`):**

1. Add **`id`** on the panel wrapper (e.g. `id="advanced-options-panel"`) — render the wrapper whenever the section exists, or only when open; if the id is only present when open, `aria-controls` still works when expanded.
2. Set **`aria-controls="advanced-options-panel"`** (matching that id) on the button.
3. **Optional/defensive:** `type="button"` on the disclosure button (`11-CONTEXT.md` / UI-SPEC).

**Conventions already in file:** strings from `constants/strings.ts`; disclosure uses literal `▶`/`▼` — do not change. Second reset `<button>` at lines 166–171 already has no `type` — only the disclosure button is in scope for IN-08-01.

**Out-of-scope nit (planner awareness):** `Skip undescribed` at lines 133–141 is still inline English, not extracted to `strings.ts` — not part of Phase 11 gap list unless scope expands.

---

### 2. CatalogCacheTab.tsx — inline copy centralization

**Card title / intro (currently literals):**

```151:158:apps/visualizer/frontend/src/components/processing/CatalogCacheTab.tsx
        <CardHeader>
          <CardTitle>Catalog Vision Cache</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-text-secondary mb-6">
            The vision cache stores preprocessed Lightroom catalog images for fast AI comparison.
            Rebuilding the cache will process all catalog images and may take several minutes.
          </p>
```

**Stat grid labels + helpers (8 literals per stat row):**

```160:196:apps/visualizer/frontend/src/components/processing/CatalogCacheTab.tsx
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <div className="p-4 bg-surface rounded-base border border-border">
              <div className="flex items-start justify-between mb-2">
                <span className="text-sm text-text-secondary">Total Images</span>
...
              <p className="text-xs text-text-tertiary">Images in Lightroom catalog</p>
...
                <span className="text-sm text-text-secondary">Cached Images</span>
...
              <p className="text-xs text-text-tertiary">Processed for AI matching</p>
...
                <span className="text-sm text-text-secondary">Missing</span>
...
              <p className="text-xs text-text-tertiary">Not yet cached</p>
...
                <span className="text-sm text-text-secondary">Cache Size</span>
...
              <p className="text-xs text-text-tertiary">Disk space used</p>
```

**Progress label:**

```198:201:apps/visualizer/frontend/src/components/processing/CatalogCacheTab.tsx
          <div className="mb-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-semibold text-text">Cache Progress</span>
```

**Cache location footnote (prefix is literal; path is dynamic):**

```308:311:apps/visualizer/frontend/src/components/processing/CatalogCacheTab.tsx
          <div className="mt-4 p-3 bg-surface rounded-base border border-border">
            <p className="text-xs text-text-tertiary">
              <strong>Cache Location:</strong> {stats.cache_dir}
            </p>
```

**NAS troubleshooting (not present yet):** `11-CONTEXT.md` / UI-SPEC call for a **≤40-word** paragraph in this tab (e.g. below stats or near the cache-location block) as a **single new `strings.ts` constant** — network shares must be mounted/readable by the backend host.

**Key → literal mapping (UI-SPEC names align with exports to add):**

| Proposed key | Current literal |
|--------------|-----------------|
| `CATALOG_CACHE_CARD_TITLE` | `Catalog Vision Cache` |
| `CATALOG_CACHE_INTRO_BODY` | Two-sentence intro paragraph |
| `CATALOG_CACHE_STAT_TOTAL_LABEL` | `Total Images` |
| `CATALOG_CACHE_STAT_TOTAL_HELPER` | `Images in Lightroom catalog` |
| `CATALOG_CACHE_STAT_CACHED_LABEL` | `Cached Images` |
| `CATALOG_CACHE_STAT_CACHED_HELPER` | `Processed for AI matching` |
| `CATALOG_CACHE_STAT_MISSING_LABEL` | `Missing` |
| `CATALOG_CACHE_STAT_MISSING_HELPER` | `Not yet cached` |
| `CATALOG_CACHE_STAT_SIZE_LABEL` | `Cache Size` |
| `CATALOG_CACHE_STAT_SIZE_HELPER` | `Disk space used` |
| `CATALOG_CACHE_PROGRESS_LABEL` | `Cache Progress` |
| `CATALOG_CACHE_LOCATION_PREFIX` | `Cache Location:` (keep `<strong>{prefix}</strong> {path}` pattern) |
| *(new)* `CATALOG_CACHE_NAS_TROUBLESHOOTING` | *(compose per UI-SPEC)* |

**Align empty-state copy:** `CATALOG_CACHE_SIMILARITY_EMPTY` in `strings.ts` still says *“Advanced options”* while the disclosure title is `CATALOG_CACHE_PIPELINE_TITLE` (`Pipeline stages`) — UI-SPEC asks to align in the same change.

**Imports:** extend existing `../../constants/strings` import block at lines 17–44; no new runtime dependencies.

---

### 3. strings.ts — existing constants inventory

**Processing routes / job queue (exact values):**

```558:560:apps/visualizer/frontend/src/constants/strings.ts
export const PROCESSING_OPEN_JOB_QUEUE = 'Open Job Queue'
export const PROCESSING_JOB_QUEUE_ROUTE = '/processing?tab=jobs'
export const PROCESSING_CATALOG_CACHE_ROUTE = '/processing?tab=cache'
```

**Embed-related (exist; useful for copy consistency):** `PROCESSING_EMBED_CATALOG_*`, `CATALOG_CACHE_EMBED_CATALOG_LABEL` (`Embed catalog images only`), `CATALOG_CACHE_BUILD_CTA`, `PROCESSING_EMBED_CATALOG_QUEUED`, etc. (see ~`550`–`611` in `strings.ts`).

**Search pin:** **No** `SEARCH_PIN_*` exports today — Phase 11 must add keys for:

- Pin inactive sentence fragments (`Similarity pin inactive:` / `Results use your full catalog.`),
- Reason text for `no_clip_embedding` (replace hardcoded `'CLIP embedding missing for pinned image'` in SearchPage),
- Help line for embed discoverability,
- Link labels (can reuse **literal** `PROCESSING_OPEN_JOB_QUEUE` or add `SEARCH_PIN_LINK_*` aliases if UI-SPEC names are required).

---

### 4. ConfirmUndoAction.tsx — useUndoToast bug

**Bug:** `offerUndo` clears the toast when `onUndo` is omitted:

```112:124:apps/visualizer/frontend/src/components/ui/ConfirmUndoAction.tsx
  const offerUndo = useCallback(
    (message: string, onUndo?: () => Promise<void>) => {
      clearTimer()
      if (!onUndo) {
        setToast({ kind: 'hidden' })
        return
      }
      setToast({ kind: 'visible', message, onUndo })
      timerRef.current = setTimeout(() => {
        setToast({ kind: 'hidden' })
        timerRef.current = null
      }, timeoutMs)
    },
    [clearTimer, timeoutMs],
  )
```

**Consumer rendering blocks message-only:** `UndoToastBar` returns null unless `toast.onUndo` is set:

```148:149:apps/visualizer/frontend/src/components/ui/ConfirmUndoAction.tsx
export function UndoToastBar({ toast, undoLabel, onUndo, politeness = 'polite' }: UndoToastBarProps) {
  if (toast.kind !== 'visible' || !toast.onUndo) return null
```

**Fix approach (per UI-SPEC):**

1. When `onUndo` is omitted: `setToast({ kind: 'visible', message })` (no `onUndo`), start the same **`timeoutMs`** timer.
2. Update **`UndoToastBar`**: if `kind === 'visible'`, render the bar with `role="status"` and `aria-live={politeness}`; show **Undo button only when** `toast.onUndo` is defined.
3. **`runUndo`**: unchanged semantics — only runs when `toast.onUndo` exists.

**Call sites:** `rg offerUndo` → only `ImageDetailModal.tsx` passes **both** message and `onUndo` today; the hook is built for future message-only use per Phase 7 review.

**Tests:** no dedicated `ConfirmUndoAction` test file; consider a small `useUndoToast` / `UndoToastBar` unit test when implementing.

---

### 5. handlers.py — vision_judgments_total comment

**Log line (operator-facing `judgments=`):**

```565:576:apps/visualizer/backend/jobs/handlers.py
        def _emit_prefilter_summary(stats_snap: dict) -> None:
            add_job_log(
                runner.db,
                job_id,
                'info',
                (
                    'vision-match-prefilter-summary '
                    f"date_window_in={int(stats_snap.get('clip_prefilter_candidates_in', 0))} "
                    f"clip_shortlist_out={int(stats_snap.get('clip_prefilter_shortlist_total', 0))} "
                    f"judgments={int(stats_snap.get('vision_judgments_total', 0))}"
                ),
            )
```

**Job result payload key (unchanged per D-03):**

```720:727:apps/visualizer/backend/jobs/handlers.py
            result_payload = {
                ...
                'vision_judgments_total': stats.get('vision_judgments_total', 0),
```

**Accumulation (not in `handlers.py`):** counter increments in `lightroom_tagger/scripts/match_instagram_dump.py` (`stats['vision_judgments_total'] += len(vision_candidates)`). **D-03:** add an **inline comment** in `handlers.py` adjacent to the **log** and/or **result_payload** line clarifying: cumulative **shortlisted catalog candidates** scored through `score_candidates_with_vision`, not raw LLM HTTP call count — **do not** rename key or `judgments=` (log parsers).

**Planner gotcha:** `.planning/ROADMAP.md` Phase 11 still says “rename” for IN-08-03; **11-CONTEXT D-03 overrides** to comment-only.

---

### 6. database.py — stack_size + pin/schema comments

**Column definition (`stack_size`):**

```836:839:lightroom_tagger/core/database.py
        CREATE TABLE IF NOT EXISTS image_stacks (
            stack_id INTEGER PRIMARY KEY AUTOINCREMENT,
            representative_key TEXT NOT NULL,
            stack_size INTEGER NOT NULL DEFAULT 0,
```

**Mutations / alignment:** `UPDATE image_stacks SET ... stack_size = ?` at split (~1903–1909), merge (~1977–1983), and explicit recount after `set_representative` (~2024–2032). Comment **D-01** should explain: **`stack_size` is maintained on these paths**; **theoretical drift** vs `image_stack_members`; **`stack_metadata_for_api`** uses **live member count** (`len(member_keys)`) for API — see:

```1766:1791:lightroom_tagger/core/database.py
def stack_metadata_for_api(db: sqlite3.Connection, stack_id: int) -> dict | None:
    """Stack row plus member keys; ``stack_member_count`` matches live membership."""
    ...
        "stack_member_count": len(member_keys),
```

**Pin + tool schema (D-02, comment-only in core):** `get_catalog_schema` is implemented in **`lightroom_tagger/core/search_tools.py`** (`_exec_get_catalog_schema`), not in `database.py`. **`restrict_to_keys`** for catalog listing is enforced in **`query_catalog_images`**:

```1494:1501:lightroom_tagger/core/database.py
    if restrict_to_keys is not None:
        rk = [str(k) for k in restrict_to_keys if k]
        if not rk:
            clauses.append("1=0")
        else:
            ph = ",".join("?" * len(rk))
            clauses.append(f"i.key IN ({ph})")
            bindings.extend(rk)
```

**Planner choice:** place **D-02** operator-facing comment either at this **`restrict_to_keys`** block (execution scoped to pin) **and/or** at **`execute_tool`** / `_exec_get_catalog_schema` in `search_tools.py` if a single sentence should mention global schema counts vs restricted `search_catalog` — **11-CONTEXT** says `database.py` for D-02; if the sentence fits poorly, reconcile with `search_tools.py` in one small addition.

**ROADMAP drift:** still says “audit / tighten schema”; **11-CONTEXT** = **document and defer**, no output changes.

---

### 7. SearchPage.tsx — embed discoverability

**File location:** `apps/visualizer/frontend/src/pages/SearchPage.tsx` (not under `components/search/`).

**Metadata handling:**

```204:219:apps/visualizer/frontend/src/pages/SearchPage.tsx
      const meta = data.metadata as
        | { pin_state?: string; fallback_reason?: string }
        | null
        | undefined
      if (meta?.pin_state === 'inactive' && meta.fallback_reason) {
        const fr = meta.fallback_reason
        setPinSimilarityWarning(
          fr === 'no_clip_embedding'
            ? 'CLIP embedding missing for pinned image'
            : fr === 'invalid_pin_key'
              ? 'Pinned image is no longer in the catalog'
              : fr,
        )
      } else {
        setPinSimilarityWarning(null)
      }
```

**Warning UI (two branches — empty grid vs grid):**

```404:411:apps/visualizer/frontend/src/pages/SearchPage.tsx
              {pinSimilarityWarning ? (
                <p
                  role="status"
                  className="text-xs text-amber-600 dark:text-amber-400 self-stretch"
                >
                  Similarity pin inactive: {pinSimilarityWarning}. Results use your full catalog.
                </p>
```

```425:431:apps/visualizer/frontend/src/pages/SearchPage.tsx
              {pinSimilarityWarning ? (
                <p
                  role="status"
                  className="text-xs text-amber-600 dark:text-amber-400 mb-2"
                >
                  Similarity pin inactive: {pinSimilarityWarning}. Results use your full catalog.
                </p>
```

**Navigation today:** **no** `Link` / `useNavigate` in this file — only `react` imports. **Pattern elsewhere:** `CatalogCacheTab` uses `import { Link } from 'react-router-dom'` and `PROCESSING_JOB_QUEUE_ROUTE` / `window.location.assign` for queue.

**D-04 (11-CONTEXT):** when `pin_state === 'inactive'` and `fallback_reason === 'no_clip_embedding'`, add **help line** + **Link** to `PROCESSING_CATALOG_CACHE_ROUTE` + control/link to job queue (`PROCESSING_JOB_QUEUE_ROUTE` + `PROCESSING_OPEN_JOB_QUEUE`). **No** inline `JobsAPI.create('batch_embed_image', …)` in SearchPage.

**Embed CTA reference:** `CatalogCacheTab` enqueues via `runAdvancedJob('embed_catalog', 'batch_embed_image', { image_type: 'catalog' })` (~259–261).

**Test impact:** `SearchPage.test.tsx` uses `findByRole('status')` for the pin warning; adding **multiple** `role="status"` nodes may make queries ambiguous. Prefer **one** live region wrapping warning + help + links, or **specific** `aria-label` / testids.

---

### 8. Cross-cutting concerns

| Topic | Notes |
|--------|------|
| **Imports** | `SearchPage.tsx`: add `react-router-dom` `Link` (and optionally `Button` for queue if matching CatalogCacheTab success row — D-04 says links; UI-SPEC mentions secondary Button as option after enqueue, which does not apply without enqueue on SearchPage). |
| **`strings.ts`** | Centralize SearchPage pin strings + all CatalogCacheTab literals above + NAS blurb; fix `CATALOG_CACHE_SIMILARITY_EMPTY` wording vs `CATALOG_CACHE_PIPELINE_TITLE`. |
| **AdvancedOptions** | Only `strings.ts` imports today; a11y attributes + optional `type="button"` only. |
| **Backend tests** | Comment-only edits in `handlers.py` / `database.py` / `search_tools.py` — typically **no** test changes unless a docstring assertion is added. |
| **Frontend tests** | Update `SearchPage.test.tsx` if copy or roles change; `CatalogCacheTab.test.tsx` may need assertions if new troubleshooting paragraph appears. |
| **`.cursor/rules/job-ui-contract.mdc`** | Phase 11 comments-only touch to `handlers.py` still triggers the **“clear the flag”** workflow if the rule’s hook fires — pairing with a **frontend** file edit is already planned. |
| **Job handler hook** | Any `handlers.py` edit: confirm project hook expectations (often requires a processing-surface edit in same commit). |

---

*Research file: Phase 11 planner input. Source reads current as of repository state during research (2026-05-04).*
