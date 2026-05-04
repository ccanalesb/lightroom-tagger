---
phase: 04-stack-detection
plan: "04-02"
subsystem: api
tags: [flask, config, react, stack-detection, STACK-01]

requires:
  - phase: 04-01
    provides: library DB schema for stacks (indirect; this plan is config/API/UI only)
provides:
  - `stack_burst_delta_ms` on `Config` with YAML default 2000 and `update_config_yaml_stack_burst_delta_ms`
  - `GET`/`PUT /api/config/stack-detection` on `lt_config` blueprint
  - `ConfigAPI.getStackDetection` / `putStackDetection` and `StackDetectionSettingsPanel` on Processing Settings tab
affects:
  - 04-stack-detection (handler job will read `load_config` default; user can change via UI)

tech-stack:
  added: []
  patterns:
    - "Settings panels mirror Catalog: load on mount, save + refresh, `invalidateAll(['jobs.health'])` on put"

key-files:
  created:
    - apps/visualizer/frontend/src/components/processing/StackDetectionSettingsPanel.tsx
  modified:
    - lightroom_tagger/core/config.py
    - apps/visualizer/backend/api/lt_config.py
    - apps/visualizer/frontend/src/services/api.ts
    - apps/visualizer/frontend/src/components/processing/SettingsTab.tsx

key-decisions:
  - "PUT rejects non-integer JSON numbers (`type is int` only) and values below 1 with `error_bad_request`"

patterns-established:
  - "Stack burst default persisted in root `config.yaml` via the same path-specific YAML updater pattern as catalog/Instagram dump paths"

requirements-completed: ["STACK-01"]

duration: 1min
completed: 2026-04-24
---

# Phase 4 Plan 04-02: Config stack_burst_delta_ms, API, and StackDetectionSettingsPanel Summary

**Default burst window `stack_burst_delta_ms` (2000 ms) is loaded from `Config`/`config.yaml`, exposed via `GET/PUT /api/config/stack-detection`, and editable in Processing → Settings with the same load/save/error pattern as the catalog path panel.**

## Performance

- **Duration:** ~1 min
- **Started:** 2026-04-24T14:04:59Z
- **Completed:** 2026-04-24T14:05:35Z
- **Tasks:** 3
- **Files modified/created:** 5

## Accomplishments

- `Config.stack_burst_delta_ms`, `load_config` default, and `update_config_yaml_stack_burst_delta_ms` with minimum 1 ms validation.
- Flask `get_stack_detection` / `put_stack_detection` on `/stack-detection` with integer-only `PUT` body and 400 for missing key, wrong type, or `value < 1`.
- Frontend `ConfigAPI` methods, new settings panel (readonly saved value + numeric draft, help copy for `batch_stack_detect`), wired after Instagram dump in `SettingsTab`.

## Task Commits

Each task was committed atomically:

1. **Task T1: Extend Config dataclass, defaults, and YAML updater** - `83ab74d` (feat)
2. **Task T2: Flask routes GET/PUT /stack-detection on lt_config blueprint** - `b71f17c` (feat)
3. **Task T3: Frontend ConfigAPI + StackDetectionSettingsPanel + SettingsTab** - `a158f6a` (feat)

**Plan metadata:** `docs(04-02): add plan completion summary for stack config and settings UI` (follows `a158f6a` — T3)

## Files Created/Modified

- `lightroom_tagger/core/config.py` - `stack_burst_delta_ms` field, defaults, `update_config_yaml_stack_burst_delta_ms`
- `apps/visualizer/backend/api/lt_config.py` - `GET`/`PUT` stack-detection routes
- `apps/visualizer/frontend/src/services/api.ts` - `getStackDetection`, `putStackDetection`
- `apps/visualizer/frontend/src/components/processing/StackDetectionSettingsPanel.tsx` - new panel
- `apps/visualizer/frontend/src/components/processing/SettingsTab.tsx` - render new panel

## Decisions Made

- Integer-only `PUT` bodies use `type(value) is not int` so JSON floats and booleans are rejected explicitly, matching the plan’s “must be int” rule.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Verification (plan-level)

- `python -c "from lightroom_tagger.core.config import Config, load_config; c=Config(); assert c.stack_burst_delta_ms==2000"` — **PASS**
- `cd apps/visualizer/backend && python -m pytest tests/test_lt_config_api.py -q` — **6 passed** (no `-k stack` cases yet; plan noted 04-04 may add them)
- `cd apps/visualizer/frontend && npx tsc --noEmit` — **PASS**

## Self-Check: PASSED

- Key deliverables on disk: `StackDetectionSettingsPanel.tsx` present; `rg` acceptance criteria from PLAN tasks verified during execution.

## Next Phase Readiness

- Config default and API are ready for `batch_stack_detect` to resolve `delta_ms` vs `load_config().stack_burst_delta_ms` (per CONTEXT D-07). Next plan in this phase can wire the job handler and tests.

---
*Phase: 04-stack-detection*
*Completed: 2026-04-24*
