---
phase: 8
plan: "03"
status: complete
---

# Summary: Phase 8-03 — Job handler + React UI for skip_undescribed

## What was built

Vision-match jobs now read `skip_undescribed` from metadata (default `true`), pass it through to `match_dump_media`, and include it in `fingerprint_vision_match` so checkpoint resume invalidates when the flag changes. The Processing → Matching tab exposes a **Skip undescribed** checkbox under the description weight slider (default on, disabled when description weight is zero) and sends `skip_undescribed` in the job payload. A handler unit test asserts explicit `False` and default `True` pass-through.

## Key files

- apps/visualizer/backend/jobs/handlers.py — skip_undescribed read from metadata
- apps/visualizer/backend/jobs/checkpoint.py — skip_undescribed in fingerprint payload
- apps/visualizer/frontend/src/stores/matchOptionsContext.tsx — skipUndescribed option
- apps/visualizer/frontend/src/components/matching/AdvancedOptions.tsx — Skip undescribed toggle
- apps/visualizer/frontend/src/components/processing/MatchingTab.tsx — metadata + handler wired

## Self-Check: PASSED

## Test results

```
$ cd apps/visualizer/backend && PYTHONPATH=. python -m pytest tests/test_handlers_single_match.py -q
...                                                                      [100%]
3 passed in 0.32s
```

```
$ cd apps/visualizer/frontend && npx tsc --noEmit
(exit 0, no errors)
```
