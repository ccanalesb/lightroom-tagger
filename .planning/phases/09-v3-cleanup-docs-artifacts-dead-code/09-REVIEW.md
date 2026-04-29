---
status: clean
phase: "09"
phase_name: v3-cleanup-docs-artifacts-dead-code
reviewed: 2026-04-29
depth: standard
files_reviewed: 10
findings:
  blocking: 0
  high: 0
  medium: 0
  low: 1
  info: 1
---

# Phase 09 — Code Review

Review covered all source files modified during Phase 09 execution (planning-doc edits excluded). Wave 1 (`09-01`/`09-02`) only touched `.planning/` markdown — out of scope for code review. The substantive code changes live in Wave 1 plan `09-03` (orphan-deletion in `api.ts`/`strings.ts`) and the Wave 2 lint-baseline cleanup commit `67db103` (8 frontend files, all small).

## Files Reviewed

| File | Phase 9 commit | Change kind |
|------|----------------|-------------|
| `apps/visualizer/frontend/src/services/api.ts` | `9f131f8` | delete `ImagesAPI.getCatalogSimilar` + `CatalogSimilarResponse` (orphan deletion) |
| `apps/visualizer/frontend/src/constants/strings.ts` | `0e38fc6` | delete 14 `CATALOG_SIMILAR_*` constants + section-comment refactor |
| `apps/visualizer/frontend/src/components/ui/badges/PerspectiveBadge.tsx` | `67db103` | `let mappedVariant` → `const` (never reassigned) |
| `apps/visualizer/frontend/src/data/ErrorBoundary.tsx` | `67db103` | drop empty `componentDidCatch` placeholder |
| `apps/visualizer/frontend/src/data/query.ts` | `67db103` | `let entry` → `const` (never reassigned) |
| `apps/visualizer/frontend/src/components/processing/JobQueueTab.tsx` | `67db103` | drop unused `_onInvalidateJobList` destructure |
| `apps/visualizer/frontend/src/components/catalog/ImageScoresPanel.tsx` | `67db103` | wrap `payload.current ?? []` in `useMemo([payload])` |
| `apps/visualizer/frontend/src/components/images/InstagramTab.tsx` | `67db103` | trim unnecessary useMemo deps (`dateFolder`, `sortByDate` covered by `toQueryParams`) |
| `apps/visualizer/frontend/src/components/processing/AnalyzeTab.tsx` | `67db103` | `// eslint-disable-next-line` on `buildDateMetadata` test export |
| `apps/visualizer/frontend/src/components/ui/ConfirmUndoAction.tsx` | `67db103` | `// eslint-disable-next-line` on `useUndoToast` hook export |

## Findings

### LOW — `JobQueueTab.tsx` interface still declares `onInvalidateJobList` but body no longer destructures it (#1)

**Location:** `apps/visualizer/frontend/src/components/processing/JobQueueTab.tsx:42`

The `JobQueueTabProps` interface still declares `onInvalidateJobList: () => void;` even though the function body no longer destructures or calls it. Consumers will still pass the prop (and TypeScript will require it because the field is non-optional) but the value is silently dropped.

**Why this is LOW, not blocking:**

- Tests pass (291 frontend tests green). No consumer relies on the function being called.
- The original code already aliased the prop to `_onInvalidateJobList` (leading underscore) — a long-standing signal that the prop is intentionally unused. The Phase 9 cleanup just removes the alias. Same observable contract.
- A separate cleanup pass to remove the prop entirely (and its callers) is the correct next step, but it widens the diff beyond Phase 9 scope (`files_modified` constraints in plan 09-03 + 09-04).

**Recommendation:** File a backlog item to remove the prop end-to-end (interface + caller passes). Out of scope for Phase 9.

### INFO — `ErrorBoundary.componentDidCatch` removed (#2)

**Location:** `apps/visualizer/frontend/src/data/ErrorBoundary.tsx:20-22` (old)

The lint cleanup deleted the empty `componentDidCatch(_error, _info)` placeholder method (it had a `// Could log here` comment). React's error boundary lifecycle still works — `getDerivedStateFromError` covers the state-update path; `componentDidCatch` is only needed for side effects (logging, metrics).

**Why this is INFO, not LOW:**

- The original method was empty; removal is a true no-op behaviorally.
- Future "log errors here" work was already a TODO breadcrumb that survives in git history.
- React docs list `componentDidCatch` as optional.

**Recommendation:** When the project adopts a centralized error logger, the method can be re-added at that point. No action needed now.

## Items Considered, Cleared

### `useMemo([payload])` in `ImageScoresPanel.tsx` — verified safe

`payload` is the `useQuery` return; the query layer (`apps/visualizer/frontend/src/data/query.ts`) returns the same cache entry's `value` until the entry is invalidated, at which point `useQuery` triggers a re-render with a new payload reference. Wrapping `payload.current ?? []` in `useMemo([payload])` is therefore strictly more stable than the previous bare expression (which created a new array literal on every render when `payload.current` was undefined).

### `InstagramTab.tsx` useMemo dep trim — verified safe

`toQueryParams` is itself `useCallback`-wrapped in `apps/visualizer/frontend/src/hooks/useFilters.ts:277-286` with `[committedValues]` as the dep. When `dateFolder` or `sortByDate` change, `committedValues` changes, `toQueryParams` reference changes, and the `listParams` useMemo invalidates correctly. The previous explicit `dateFolder, sortByDate` deps were redundant.

### Backend route `GET /api/images/catalog/<key>/similar` — preserved per D-03

The Phase 9 plan explicitly preserves the backend route + tests (`apps/visualizer/backend/api/images.py` + `tests/test_images_clip_similar_api.py`) even though the frontend client method was removed. Backend pytest sweep ran 338 tests including the `clip_similar_api` module — all pass. D-03 commitment honored.

### `CATALOG_STACK_SHOW` / `CATALOG_STACK_HIDE` preserved per plan

`rg "CATALOG_STACK_SHOW|CATALOG_STACK_HIDE" apps/visualizer/frontend/src` only finds them in `strings.ts` itself — they have no current consumers. The plan explicitly preserves them; full dead-code closure for stack constants is out of scope for Phase 9. Documented in `09-03-SUMMARY.md` as a follow-up.

## Verdict

**Status: clean** — no blocking, high, or medium findings. Two minor items (`LOW` and `INFO`) are acknowledged with recommendations but do not block phase closure.

The Phase 9 changes are dominated by deletions and trivial style fixes, all with strong test coverage:

- Frontend `tsc --noEmit` exits 0
- Frontend `npm run lint` exits 0 (pre-existing baseline cleared)
- Frontend `vitest run` 291 passed across 51 files
- Backend `pytest tests/` 338 passed (includes D-03 `clip_similar_api` coverage)
- Core `pytest lightroom_tagger/core/` 267 passed

No security concerns: deletions only, no new code paths that touch secrets/auth/IO. Documentation edits in plans 09-01 and 09-02 are markdown only.

---
*Reviewed: 2026-04-29 by orchestrator inline (gsd-execute-phase code_review_gate)*
