# Phase 7 — Verification matrix (STACK-04, STACK-05, NLS-06)

**Artifact:** requirement trace and machine-verification outcomes for phase closeout.  
**Last updated:** 2026-04-26 (Plan 07-05)

| Requirement | Intent (summary) | Primary verification | Status |
|---------------|------------------|----------------------|--------|
| **STACK-04** | Instagram matching compares dump media to stack **representatives** only; confirmed matches **apply to stack members** with non-destructive conflict handling. | Backend: `apps/visualizer/backend/tests/test_handlers_single_match.py` (`test_match_dump_media_representative_only_*`, `test_match_dump_media_stack_apply_*`, `test_handle_vision_match_result_payload_includes_stack_apply_counts`); **integration:** `apps/visualizer/backend/tests/test_stack_matching_integration.py` (`test_integration_vision_match_representative_only_candidates`, `test_integration_vision_match_stack_apply_skips_conflict_and_surfaces_counts`). Frontend: `MatchesTab.test.tsx` (multi-candidate / partial-candidate status copy). | **PASS** |
| **STACK-05** | User can split, merge stacks, and change representative with persistence. | `apps/visualizer/backend/tests/test_images_stacks_api.py`; frontend `CatalogTab.test.tsx` (07-03). | **PASS** |
| **NLS-06** | Chat search: pin catalog image → visual similarity scope; single pin; replace pin; **inactive pin** + fallback messaging when similarity cannot use the pin. | Backend: `apps/visualizer/backend/tests/test_images_chat_search_api.py` (pin scenarios). Frontend: `apps/visualizer/frontend/src/pages/__tests__/SearchPage.test.tsx` (pin send, replace, inactive warning, E2E replace → inactive). | **PASS** |

## Critical paths checklist

| Path | Evidence | Status |
|------|----------|--------|
| Representative-only vision candidate set | Integration test asserts scoring receives rep key only; stats/logs include non-representative filter summary where applicable. | PASS |
| Full-stack apply with conflict skip | Integration test asserts `stack_apply_*` / job logs; DB non-overwrite for conflicting member covered in `test_handlers_single_match.py`; UI shows reduced candidate count in Matches tab test. | PASS |
| Pin replacement | SearchPage tests assert `pinned_image_key` tracks latest pin. | PASS |
| Inactive pin / similarity failure | SearchPage tests assert `role="status"` warning and metadata-driven copy. | PASS |

## Gaps / follow-ups

| Item | Owner | Next action |
|------|-------|-------------|
| None blocking for Phase 7 closeout | — | — |

## Commands (Plan 07-05)

```bash
cd /Users/ccanales/projects/lightroom-tagger && python -m pytest apps/visualizer/backend/tests/test_stack_matching_integration.py -q --tb=short
cd /Users/ccanales/projects/lightroom-tagger/apps/visualizer/frontend && npm test -- MatchesTab.test.tsx --run
cd /Users/ccanales/projects/lightroom-tagger/apps/visualizer/frontend && npm test -- SearchPage.test.tsx --run
cd /Users/ccanales/projects/lightroom-tagger && gsd-sdk query verify references .planning/phases/07-stacks-in-matching-pin-similarity/07-VERIFICATION.md || true
```
