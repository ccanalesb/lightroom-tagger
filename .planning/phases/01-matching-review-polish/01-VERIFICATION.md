---
phase: 01-matching-review-polish
phase_number: 1
requirements: [POLISH-01, POLISH-02]
status: passed
must_haves_total: 17
must_haves_verified: 17
verified_at: 2026-04-17T17:59:47Z
---

# Phase 1 Verification

## Phase goal

Eliminate friction in the match confirmation flow so reviewing a batch no longer kicks the user back to the list on every decision.

## Success criteria

| # | Criterion | Evidence | Status |
|---|-----------|----------|--------|
| 1 | Rejecting a match keeps the modal open and surfaces a "Rejected" state | `MatchDetailModal.tsx`: after `MatchingAPI.reject`, `onClose()` is not called immediately; `rejectedAck` drives header `Badge` with `MATCH_DETAIL_REJECTED_LABEL` (lines 97–119, 143–146). Covered by `MatchDetailModal.reject.test.tsx`. | PASS |
| 2 | Multi-candidate groups auto-advance to the next candidate after reject | `findNextCandidateInOrder` (linear index+1) and delayed `onCandidateChange(nextCandidate)` with `MULTI_CANDIDATE_REJECT_ADVANCE_MS` (`MatchDetailModal.tsx` 29–35, 107–112). Vitest asserts advance after fake timer. | PASS |
| 3 | Matches list shows unvalidated groups above validated ones, sorted by newest photo (`created_at` with fallback) | Backend: `list_matches` sorts with bucket 0 = not `(all_rejected \|\| has_validated)`, bucket 1 otherwise; `_photo_ts_float` uses Instagram `created_at` then max catalog `date_taken` (`images.py` 713–736). Pagination after sort (`736–742`). Tests `test_list_matches_sorts_unvalidated_before_validated_bucket`, `test_list_matches_tombstone_all_rejected_after_validated`. Frontend: `MatchesTab.tsx` splits with `unvalidatedGroups` / `reviewedGroups` (142–144) preserving server-relative order within each slice. | PASS |

## Must-haves audit

| Must-have | Evidence (file:line or SUMMARY) | Status |
|-----------|--------------------------------|--------|
| Plan 01: `list_matches` returns unvalidated bucket first, then reviewed (validated + all_rejected) | `images.py` `_match_group_sort_key`: `sort_bucket = 1 if (g.get('all_rejected') or g.get('has_validated')) else 0` (728–734); `match_groups.sort` (736) | PASS |
| Plan 01: Pagination applies after the new sort | `images.py` 736–742: `sort` then `_clamp_pagination` then `match_groups[offset:offset+limit]` | PASS |
| Plan 01: Fully-rejected keys with no `matches` rows → synthetic `candidates: []`, `all_rejected: true` | `images.py` 663–702 (tombstone_only_keys loop + append dict) | PASS |
| Plan 02: Validate backfills missing Instagram `created_at` from catalog `date_taken` in same DB transaction | `database.py` `validate_match` uses `with db:` (1343–1353); `_backfill_instagram_created_at_from_catalog` reads `images.date_taken`, updates `instagram_images` or `instagram_dump_media` (1302–1340) | PASS |
| Plan 03: `MatchGroup.all_rejected` optional on `MatchGroup` | `api.ts` 772–781 | PASS |
| Plan 03: Phase 1 user-visible strings centralized (`strings.ts`); new copy not hardcoded for reject/tombstone/divider | `strings.ts` 481–490; `MatchDetailModal.tsx` imports `MATCH_DETAIL_REJECTED_*`; `MatchesTab.tsx` imports divider + tombstone constants | PASS |
| Plan 04: `handleRejectConfirm` does not call `onClose()` immediately after reject | `MatchDetailModal.tsx` 97–119: `onClose` only inside `setTimeout` using `MATCH_DETAIL_REJECTED_AUTOCLOSE_MS` | PASS |
| Plan 04: Inline `Badge` acknowledgment on reject success (D-01) | `MatchDetailModal.tsx` 143–146 (`rejectedAck` + `Badge` + `MATCH_DETAIL_REJECTED_LABEL`) | PASS |
| Plan 04: Validate and Reject disabled after reject success (D-02) | `MatchDetailModal.tsx` 153–154, 165–167 | PASS |
| Plan 04: Multi-candidate auto-advance via `onCandidateChange` (D-04) | `MatchDetailModal.tsx` 107–112; `MatchesTab.tsx` 197 `onCandidateChange={setSelectedMatch}` | PASS |
| Plan 04: Single-candidate or last candidate ~1.5s delayed auto-close (D-03, D-05) | `MatchDetailModal.tsx` 114–119 `MATCH_DETAIL_REJECTED_AUTOCLOSE_MS` (1500 in `strings.ts` 483) | PASS |
| Plan 04: Rejected row disappears from tab bar; no struck-out tabs (D-06) | Parent `useMatchGroups.handleRejected` removes candidate from `candidates` (45–77); `CandidateTabBar` receives updated `resolvedGroup.candidates` | PASS |
| Plan 04: Linear next-tab rule (D-07) | `findNextCandidateInOrder` returns `candidates[idx + 1]` only (`MatchDetailModal.tsx` 29–34) | PASS |
| Plan 05: Last reject → tombstone (`candidates: []`, `all_rejected: true`); `total` not decremented | `useMatchGroups.ts` 56–66 tombstone branch; no `setTotal` in hook file | PASS |
| Plan 05: `MatchesTab` preserves server order (two filters, no re-sort) | `MatchesTab.tsx` 142–144 `filter` only (order-preserving) | PASS |
| Plan 05: Validated divider only when both buckets non-empty; uses `MATCHES_VALIDATED_DIVIDER_LABEL` | `MatchesTab.tsx` 144, 167–173 | PASS |
| Plan 05: Tombstone cards use `MATCH_TOMBSTONE_*`; no `openReview` on tombstone | `TombstoneMatchGroupCard` (62–86) has no `Button`; `ReviewedMatchGroupCard` routes tombstones to `TombstoneMatchGroupCard` (96–99) | PASS |

## Requirement traceability

| Req ID | Implemented in | Tests | Status |
|--------|----------------|-------|--------|
| POLISH-01 | `MatchDetailModal.tsx` (reject flow, ack, timers, advance); `useMatchGroups.ts` (`handleRejected` tombstone); `MatchesTab.tsx` (modal guard, tombstone card) | `MatchDetailModal.reject.test.tsx`; `useMatchGroups.handleRejected.test.tsx` | PASS |
| POLISH-02 | `apps/visualizer/backend/api/images.py` (`list_matches` bucket sort, tombstone serialization); `lightroom_tagger/core/database.py` (`validate_match` + `_backfill_instagram_created_at_from_catalog`); `MatchesTab.tsx` (unvalidated vs reviewed presentation) | `test_match_groups.py` (sort + tombstone); `test_match_validation.py` (including `created_at` backfill tests) | PASS |

## Automated check results

Backend (`cd apps/visualizer/backend && PYTHONPATH=. uv run python -m pytest tests/test_match_groups.py tests/test_match_validation.py -v`):

```
tests/test_match_groups.py::test_matches_grouped_by_insta_key PASSED     [  7%]
tests/test_match_groups.py::test_single_match_still_grouped PASSED       [ 15%]
tests/test_match_groups.py::test_matches_include_instagram_image_from_dump_only PASSED [ 23%]
tests/test_match_groups.py::test_list_matches_sorts_unvalidated_before_validated_bucket PASSED [ 30%]
tests/test_match_groups.py::test_list_matches_tombstone_all_rejected_after_validated PASSED [ 38%]
tests/test_match_validation.py::test_validate_match_should_set_validated PASSED [ 46%]
tests/test_match_validation.py::test_unvalidate_match_should_clear_validated PASSED [ 53%]
tests/test_match_validation.py::test_validate_nonexistent_match_should_return_404 PASSED [ 61%]
tests/test_match_validation.py::test_validate_writes_catalog_date_to_instagram_created_at_write_when_missing PASSED [ 69%]
tests/test_match_validation.py::test_validate_writes_catalog_date_to_instagram_when_created_at_missing PASSED [ 76%]
tests/test_match_validation.py::test_reject_match_should_delete_and_blocklist PASSED [ 84%]
tests/test_match_validation.py::test_reject_validated_match_should_return_409 PASSED [ 92%]
tests/test_match_validation.py::test_reject_nonexistent_match_should_return_404 PASSED [100%]

============================== 13 passed in 0.56s ==============================
```

Frontend lint (`cd apps/visualizer/frontend && npm run lint`):

```
> lightroom-tagger-frontend@0.0.0 lint
> eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0
```

Frontend tests (`npm test -- --run MatchDetailModal.reject.test.tsx useMatchGroups.handleRejected.test.tsx`):

```
 ✓ src/hooks/__tests__/useMatchGroups.handleRejected.test.tsx  (1 test) 8ms
 ✓ src/components/matching/match-detail-modal/__tests__/MatchDetailModal.reject.test.tsx  (2 tests) 156ms

 Test Files  2 passed (2)
      Tests  3 passed (3)
```

**Note:** `tests/test_providers_api.py::TestDefaults::test_should_return_defaults` was not run; known pre-existing failure is out of scope for this phase per instructions.

## Gaps

None

## Human verification items (optional — only if something needs human eyes)

- Plan 05 manual smoke was not run in the implementing summaries: open Images → Matches, reject through to last candidate, confirm tombstone placement, divider when mixed buckets, and that the ~800ms / ~1500ms timings feel acceptable in the real UI.
- Subjective visual polish: `Badge` variants for “Rejected” / “No match”, divider typography, and disabled-button affordance are not asserted by automated tests.

## Summary

Phase 1 meets its goal end-to-end: the backend orders match groups for pagination-aware lists, validates with Instagram `created_at` backfill for stable sorting, and the frontend keeps the review modal open after reject with a clear inline state, advances candidates predictably, and retains fully-rejected groups as non-interactive tombstones without shrinking the paginated total incorrectly. All listed must-haves are evidenced in code, and the required pytest, Vitest, and ESLint gates passed in this verification run.
