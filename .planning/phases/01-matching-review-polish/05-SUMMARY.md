---
phase: "01"
plan: "05"
subsystem: "apps/visualizer/frontend"
requirements-completed:
  - POLISH-01
  - POLISH-02
key-files:
  created:
    - apps/visualizer/frontend/src/hooks/__tests__/useMatchGroups.handleRejected.test.tsx
  modified:
    - apps/visualizer/frontend/src/hooks/useMatchGroups.ts
    - apps/visualizer/frontend/src/components/images/MatchesTab.tsx
key-decisions:
  - "Last reject returns an in-place tombstone group (`all_rejected`, empty `candidates`) and no longer decrements `total`."
  - "Pagination merge replaces an existing row by `instagram_key` instead of skipping duplicates so a refreshed row can replace a prior version."
  - "Modal closes when the live group has no candidates: `liveMatch` resolves to null (no stale `selectedMatch` fallback) and `MatchDetailModal` mounts only when `liveGroup.candidates.length > 0` and `liveMatch` is truthy."
duration: "~25m"
completed: "2026-04-17"
---

# Plan 05 summary: MatchesTab bucket divider, tombstones, hook state

**One-liner:** MatchesTab tombstone cards + validated divider with useMatchGroups preserving server order.

## Tasks

| Task | Commit | Summary |
|------|--------|---------|
| 5.1 | `043512a` | `handleRejected` tombstone branch, merge-by-key pagination, Vitest for unchanged `total`. |
| 5.2 | `cc4046e` | Validated divider, tombstone vs actionable cards, stricter modal mount + `liveMatch` resolution. |

## Acceptance (per task)

| Gate | Result |
|------|--------|
| 5.1 `rg` + Vitest `useMatchGroups.handleRejected.test.tsx` | PASS |
| 5.1 `rg` tombstone branch (not `return []`) | PASS |
| 5.2 `rg` divider, tombstone strings, `openReview` / modal guard | PASS |

## Plan verification

| Command | Result |
|---------|--------|
| `cd apps/visualizer/frontend && npm run lint` | PASS |
| `cd apps/visualizer/frontend && npm test -- --run useMatchGroups` | PASS |
| `cd apps/visualizer/backend && PYTHONPATH=. uv run python -m pytest tests/test_match_groups.py tests/test_match_validation.py -q` | PASS (13 tests) |
| Manual smoke (Images → Matches) | Not run in this environment |

## Deviations

- **Backend verification command:** Plan text uses `python -m pytest`; this machine has no `python` on PATH. Used `uv run python -m pytest` from `apps/visualizer/backend` with `PYTHONPATH=.` — same tests, equivalent to project workflow (same as plan 01 summary).

## Self-Check: PASSED

All automated verification passed; `MatchDetailModal.tsx` was left unstaged (concurrent plan 04).
