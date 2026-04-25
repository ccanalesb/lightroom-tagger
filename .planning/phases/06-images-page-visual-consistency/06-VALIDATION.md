---
phase: 6
slug: images-page-visual-consistency
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-25
---

# Phase 6 — Validation Strategy

> Retroactive Nyquist validation audit for Phase 6: Images page visual consistency.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Vitest + React Testing Library; TypeScript compiler |
| **Config file** | `apps/visualizer/frontend/vite.config.ts`, `apps/visualizer/frontend/tsconfig.json` |
| **Quick run command** | `cd apps/visualizer/frontend && ./node_modules/.bin/vitest run <test-file>` |
| **Full suite command** | `cd apps/visualizer/frontend && ./node_modules/.bin/tsc --noEmit && ./node_modules/.bin/vitest run` |
| **Estimated runtime** | ~10 seconds for full frontend suite in this repo state |

---

## Sampling Rate

- **After every task commit:** Run the targeted Vitest file for the changed component or adapter.
- **After every plan wave:** Run `cd apps/visualizer/frontend && ./node_modules/.bin/tsc --noEmit && ./node_modules/.bin/vitest run`.
- **Before `/gsd-verify-work`:** Full suite should be green; current unrelated failures are noted below.
- **Max feedback latency:** ~10 seconds for frontend suite, ~2 seconds for targeted Phase 6 tests.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 06-01 | 01 | 1 | UI-01 | — | Unified badge primitives render expected labels, variants, PerspectiveBadge formatting, and known slug colors. | component/unit | `cd apps/visualizer/frontend && ./node_modules/.bin/vitest run src/components/ui/__tests__/Badges.test.tsx` | yes | green |
| 06-02 | 02 | 2 | UI-02 | — | Instagram adapter sets AI metadata from descriptions; Instagram tab shows AI inline, omits Described, and preserves Matched footer. | unit/component | `cd apps/visualizer/frontend && ./node_modules/.bin/vitest run src/components/image-view/__tests__/adapters.test.ts src/components/images/__tests__/InstagramTab.test.tsx` | yes | green |
| 06-03 | 03 | 3 | UI-03 | — | Match group tiles show validated filename + badge/score, or candidate count only for unvalidated groups. | component | `cd apps/visualizer/frontend && ./node_modules/.bin/vitest run src/components/images/__tests__/MatchGroupTile.test.tsx` | yes | green |
| 06-04 | 04 | 4 | UI-01 | — | Dominant perspective appears in Best Photos and Dashboard strip tile footers. | unit/component | `cd apps/visualizer/frontend && ./node_modules/.bin/vitest run src/components/identity/pickDominantPerspective.test.ts src/components/identity/BestPhotosGrid.test.tsx src/components/insights/__tests__/TopPhotosStrip.test.tsx` | yes | green |

*Status: green = automated validation passes.*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| None. | — | All Phase 6 requirements have automated validation. | — |

---

## Validation Audit 2026-04-25

| Metric | Count |
|--------|-------|
| Gaps found | 4 |
| Resolved | 3 |
| Escalated | 1 |

### Tests Added Or Expanded

| Requirement | File | Behavior Covered |
|-------------|------|------------------|
| UI-01 | `apps/visualizer/frontend/src/components/ui/__tests__/Badges.test.tsx` | `PerspectiveBadge` display name preference, derived label, score formatting, known slug colors. |
| UI-02 | `apps/visualizer/frontend/src/components/images/__tests__/InstagramTab.test.tsx` | AI metadata chip, no `Described` overlay, matched footer and match percentage. |
| UI-01 | `apps/visualizer/frontend/src/components/insights/__tests__/TopPhotosStrip.test.tsx` | Dominant perspective footer in dashboard top photos strip. |
| UI-03 | `apps/visualizer/frontend/src/components/images/__tests__/MatchGroupTile.test.tsx` | Unvalidated tile: `msgMatchGroupCandidates(3)` via `within(image-tile)`; expects no `MATCH_VALIDATED` and no `80%` when `best_score` is set. |

### Verification Evidence

- `cd apps/visualizer/frontend && ./node_modules/.bin/vitest run src/components/ui/__tests__/Badges.test.tsx src/components/images/__tests__/InstagramTab.test.tsx src/components/images/__tests__/MatchGroupTile.test.tsx src/components/insights/__tests__/TopPhotosStrip.test.tsx` — exit 0, 23 tests passed.
- `cd apps/visualizer/frontend && ./node_modules/.bin/vitest run src/components/ui/__tests__/Badges.test.tsx src/components/image-view/__tests__/adapters.test.ts src/components/images/__tests__/InstagramTab.test.tsx src/components/images/__tests__/MatchGroupTile.test.tsx src/components/identity/pickDominantPerspective.test.ts src/components/identity/BestPhotosGrid.test.tsx` — exit 0, 30 tests passed.
- `cd apps/visualizer/frontend && ./node_modules/.bin/vitest run src/components/images/__tests__/MatchGroupTile.test.tsx` — exit 0, 2 tests passed after UI-03 regression was added and implementation was fixed.
- `cd apps/visualizer/frontend && ./node_modules/.bin/vitest run src/components/ui/__tests__/Badges.test.tsx src/components/image-view/__tests__/adapters.test.ts src/components/images/__tests__/InstagramTab.test.tsx src/components/images/__tests__/MatchGroupTile.test.tsx src/components/identity/pickDominantPerspective.test.ts src/components/identity/BestPhotosGrid.test.tsx src/components/insights/__tests__/TopPhotosStrip.test.tsx` — exit 0, 38 tests passed.
- `cd apps/visualizer/frontend && ./node_modules/.bin/tsc --noEmit` — passed as part of full-suite command before unrelated Vitest failures.
- Full `vitest run` currently has unrelated failures in `src/services/__tests__/api.test.ts` cache invalidation expectations and `src/pages/SearchPage.test.tsx` result-copy expectation.

## Validation Audit 2026-04-25 Follow-up

| Metric | Count |
|--------|-------|
| Gaps found | 1 |
| Resolved | 1 |
| Escalated | 0 |

### Resolution

- UI-03 regression now asserts unvalidated `MatchGroupTile` rows do not render `MATCH_VALIDATED` or a best-score percentage when `best_score` is present.
- `MatchGroupTile` now renders the best-score percentage only for validated groups; unvalidated groups render plain candidate count text only.

---

## Validation Sign-Off

- [x] All tasks have automated validation.
- [x] Sampling continuity: no 3 consecutive tasks without automated verification.
- [x] Wave 0 covers all missing references.
- [x] No watch-mode flags.
- [x] Feedback latency < 15s.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** compliant 2026-04-25; all Phase 6 requirements have automated validation.
