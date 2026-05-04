---
phase: 11
slug: v3-deferred-polish
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-04
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (backend) + vitest (frontend) |
| **Config file** | `pyproject.toml` / `apps/visualizer/frontend/vite.config.ts` |
| **Quick run command** | `cd apps/visualizer/frontend && npx tsc --noEmit && npx vitest run --reporter=verbose 2>&1 | tail -20` |
| **Full suite command** | `cd apps/visualizer/frontend && npx tsc --noEmit && npx vitest run && cd ../../.. && python -m pytest lightroom_tagger/ apps/visualizer/backend/ -q` |
| **Estimated runtime** | ~60 seconds |

---

## Sampling Rate

- **After every task commit:** Run `npx tsc --noEmit` (frontend tasks) or `python -m pytest -q -x` (backend tasks)
- **After every plan wave:** Run full suite command above
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Secure Behavior | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------------|-----------|-------------------|--------|
| aria-expanded fix | 01 | 1 | IN-08-01 | N/A | tsc | `npx tsc --noEmit` | ⬜ pending |
| strings.ts additions | 01 | 1 | IN-08-02 | N/A | tsc | `npx tsc --noEmit` | ⬜ pending |
| CatalogCacheTab copy | 01 | 1 | IN-08-02 | N/A | tsc + vitest | `npx tsc --noEmit && npx vitest run` | ⬜ pending |
| useUndoToast fix | 01 | 1 | Phase-7-low-4 | N/A | tsc + vitest | `npx tsc --noEmit && npx vitest run` | ⬜ pending |
| SearchPage embed CTA | 01 | 1 | D-04 | N/A | tsc + vitest | `npx tsc --noEmit && npx vitest run` | ⬜ pending |
| handlers.py comment | 01 | 1 | IN-08-03 | N/A | pytest | `python -m pytest apps/visualizer/backend/ -q` | ⬜ pending |
| database.py comments | 01 | 1 | Phase-7-low-3,5 | N/A | pytest | `python -m pytest lightroom_tagger/ -q` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. This is a comment/copy/a11y-only phase — no new test files are required, but existing test suites must stay green.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| aria-expanded toggles in screen reader | IN-08-01 | Requires browser/AT | Open MatchingTab, toggle Advanced Options, check aria-expanded attribute in DevTools |
| Message-only undo toast visible for 8s | Phase-7-low-4 | Requires live browser | Trigger an action that calls `offerUndo(msg)` without onUndo; confirm toast shows and auto-dismisses |
| SearchPage embed links navigate correctly | D-04 | Requires browser routing | Trigger no-CLIP pin warning, click links, confirm navigation to `/processing?tab=cache` and `/processing?tab=jobs` |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or documented manual step
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 not needed — existing infra covers scope
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
