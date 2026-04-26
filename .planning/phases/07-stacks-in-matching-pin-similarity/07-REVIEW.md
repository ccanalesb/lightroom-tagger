# Phase 07 — Code review (stacks in matching + pin similarity)

**Reviewed commit range:** `f89be21`..`909c359` (07-01 through 07-05 plan execution)

**status:** clean

## Summary

Phase 07 delivers representative-only Instagram match candidates, stack-wide match apply with conflict skips, transactional stack mutations (split / merge / set representative), REST + Catalog/Image detail UI with confirm + undo for rep changes, pin-aware chat search (backend restrict + Search UX), and integration tests. One **high** gap and one **medium** API issue were found in review and **fixed** (see below).

## Findings by severity

### High (fixed)

1. **Catalog detail missing stack metadata** — `GET /api/images/catalog/<key>` built the payload from `get_image()` (`images` table only), so `stack_id`, `stack_member_count`, and `is_stack_representative` were absent unless the client passed them via list-row `initialImage`. The Image detail modal’s “Burst stack” editor (`CatalogDetailStackEditing`) depends on `stack_id`; without it, stack controls did not appear for direct detail loads (e.g. deep link, refresh, or any path without list context). **Fix:** `catalog_image_stack_row_fields()` in `lightroom_tagger/core/database.py` and merge into `_build_catalog_detail()` in `apps/visualizer/backend/api/images.py`. Tests: `test_images_detail_api.py`.

### Medium (fixed)

2. **`StackMutationError` with `status_code >= 500` mapped to HTTP 400** — e.g. invariant failure “merge produced an empty stack” was surfaced as a client error. **Fix:** stack mutation routes now return `error_server_error` for `status_code >= 500`.

### Low (no code change)

3. **Tool-calling + pin** — `get_catalog_schema` still describes global catalog counts when a pin is active; results remain restricted by `restrict_to_keys` in tool execution. Acceptable; optional future hardening would scope schema stats to the pin set.

4. **`useUndoToast.offerUndo`** — Calling with a message but no `onUndo` clears any visible toast without showing the message (edge case).

5. **`image_stacks.stack_size` vs live membership** — Detail/list use `stack_size` from the stack row; `stack_metadata_for_api` recomputes count from members. Small drift possible if data ever diverges; pre-existing pattern.

## Fixes applied

| Item | Change |
|------|--------|
| Detail stack parity | `catalog_image_stack_row_fields` + `_build_catalog_detail` update |
| HTTP semantics | Split/merge/representative handlers: 5xx `StackMutationError` → 500 |
| Tests | `test_images_detail_api.py`: solo stack fields + two-member stack |

**Fix commit:** `fix(07-review): catalog detail stack fields and stack API 5xx mapping` — verify with `git log -1 --oneline`.

## Tests run

- `pytest apps/visualizer/backend/tests/test_images_detail_api.py apps/visualizer/backend/tests/test_images_stacks_api.py apps/visualizer/backend/tests/test_stack_matching_integration.py apps/visualizer/backend/tests/test_images_chat_search_api.py` — **32 passed**
- `npm test -- --run` (SearchPage, CatalogTab, MatchesTab Vitest) — **13 passed**

## Files touched in review scope

Backend/core: `lightroom_tagger/core/database.py`, `lightroom_tagger/scripts/match_instagram_dump.py`, `apps/visualizer/backend/jobs/handlers.py`, `apps/visualizer/backend/api/images.py`, `lightroom_tagger/core/nl_catalog_search.py`, `lightroom_tagger/core/search_tools.py`, `lightroom_tagger/core/semantic_search.py`, `lightroom_tagger/core/clip_similarity.py`, related tests.

Frontend: `SearchPage.tsx`, `CatalogTab.tsx`, `ImageDetailModal.tsx`, `ConfirmUndoAction.tsx`, `api.ts`, `strings.ts`, `adapters.ts`, `RejectConfirmModal.tsx`, related tests.

Docs: `07-0[1-5]-*.md`, `07-VERIFICATION.md`.
