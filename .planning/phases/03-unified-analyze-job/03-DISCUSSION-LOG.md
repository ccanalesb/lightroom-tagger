# Phase 3: Unified Analyze job - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-17
**Phase:** 03-unified-analyze-job
**Areas discussed:** Orchestration model, Failure handling between stages, Progress reporting, UI surface on Analyze tab, Tab name & route, Checkpoint & resume semantics

**Discussion mode:** `/gsd-next` routed auto-advance into discuss-phase; user selected `all` gray areas; deep-dive run in text mode (Cursor environment, no AskUserQuestion tool). User responded "Lock all except q3.1 a q4.2 b" — all recommendations accepted except 3.1 (fixed 50/50 split instead of weighted) and 4.2 (split force into two checkboxes instead of single renamed one).

---

## Area 1: Orchestration model

### Q1.1 — Refactor shape

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Extract shared helpers, rewire old handlers as thin wrappers | Highest reuse; existing tests pass unchanged | ✓ |
| (b) Copy/paste into `handle_batch_analyze` | Duplicated logic, more maintenance | |
| (c) Extract only selection logic | Partial reuse | |

**User's choice:** (a) — locked recommendation.
**Notes:** Refactor correctness measured by `test_handlers_batch_describe.py` / `test_handlers_batch_score.py` passing unchanged (SC-3).

### Q1.2 — Selection sharing

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Query once in `batch_analyze`, pass `(key,itype)` list to both passes | One DB round-trip, consistent image set | ✓ |
| (b) Each pass queries independently | Simpler handler, redundant queries, potential drift | |

**User's choice:** (a) — locked recommendation.
**Notes:** Makes "shared selection criteria" clause of SC-1 literally true. DB pre-filter for already-described / already-scored stays inside each helper.

---

## Area 2: Failure handling between stages

### Q2.1 — Per-image describe failure → score

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Score still attempts; missing description is warning-only | Matches current independent-handler behavior | ✓ |
| (b) Skip scoring images whose describe failed this run | In-memory failure tracking required | |

**User's choice:** (a) — locked recommendation.

### Q2.2 — Job outcome on partial failure

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Complete successful; counts in result dict | Consistent with current handler behavior | ✓ |
| (b) Mark failed if any stage has any failure | Noisy | |
| (c) Mark failed only on circuit-breaker trip | Too coarse | |

**User's choice:** (a) — locked recommendation.
**Notes:** Existing consecutive-failure circuit breaker in describe still short-circuits the analyze job before score starts.

---

## Area 3: Progress reporting

### Q3.1 — Progress split

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Fixed 50/50 | Simple, predictable even as perspective count varies | ✓ |
| (b) Weighted by estimated work (N vs N×M) | More accurate, harder to explain | |
| (c) Approximate bar + rich `current_step` text | Relies entirely on step text | |

**User's choice:** (a) — **user overrode recommendation from (b) → (a)**.
**Notes:** User explicitly picked simpler 50/50 over proportional weighting. Score typically does ~4× describe work; 50/50 is accepted as honest-enough.

### Q3.2 — `current_step` text

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Yes — "Describing" / "Scoring" | Users see which stage is running | ✓ |
| (b) No, just the progress bar | Less informative | |

**User's choice:** (a) — locked recommendation.

---

## Area 4: UI surface on Analyze tab

### Q4.1 — Button layout

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Analyze primary; separate buttons inside Advanced disclosure | Minimal visual churn, discoverable | ✓ |
| (b) Separate buttons behind a text link outside Advanced | Less discoverable | |
| (c) Three buttons always visible | Clutter | |

**User's choice:** (a) — locked recommendation.

### Q4.2 — Force checkbox

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Rename to "Force regenerate (both stages)", single checkbox | Simple | |
| (b) Split into two checkboxes: force describe / force score | More granular control | ✓ |
| (c) Keep single label, document dual meaning | Confusing | |

**User's choice:** (b) — **user overrode recommendation from (a) → (b)**.
**Notes:** Two independent checkboxes give users precise control — e.g. "rescore with new rubric but keep descriptions." Metadata keys become `force_describe` / `force_score`; advanced-path buttons translate to flat `force` for backwards compat with existing handlers.

---

## Area 5: Tab name & route

### Q5.1 — Rename scope

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Full rename (file, component, nav label, URL slug, tests) | Clean, one-time cost | ✓ |
| (b) Partial (keep `DescriptionsTab.tsx` filename) | Naming inconsistency | |
| (c) Visible-only (code stays `DescriptionsTab`) | Perpetuates debt | |

**User's choice:** (a) — locked recommendation.
**Notes:** File rename via `git mv` to preserve history. `BatchActionPanel.tsx` on the Descriptions *page* is a different surface, out of scope.

### Q5.2 — CardTitle and intro copy

| Option | Description | Selected |
|--------|-------------|----------|
| (a) "Analyze Images" / "Run AI description + scoring in a single job. Advanced options let you run stages separately." | Clear, concise | ✓ |
| (b) User writes custom copy | N/A | |

**User's choice:** (a) — locked recommendation.

---

## Area 6: Checkpoint & resume semantics

### Q6.1 — Checkpoint metadata shape

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Per-stage sub-checkpoints (`checkpoint.describe`, `checkpoint.score`) with `stage` entry-point field | Reuses existing fingerprint helpers unchanged | ✓ |
| (b) Flatter shape mixing pair types | Loses helper reuse | |
| (c) Custom schema | No clear benefit | |

**User's choice:** (a) — locked recommendation.

### Q6.2 — Fingerprint mismatch behavior

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Per-stage reset — describe mismatch resets describe only; score mismatch resets score only | Matches existing pattern | ✓ |
| (b) Any mismatch resets entire analyze checkpoint | Coarser, loses work unnecessarily | |

**User's choice:** (a) — locked recommendation.

### Q6.3 — Orphan recovery registration

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Register `batch_analyze` in orphan-recovery allowlist alongside `batch_describe` / `batch_score` | Required for crash-resilience parity | ✓ |

**User's choice:** (a) — confirmed. Required for parity with existing batch handlers.

---

## Claude's Discretion

- Exact helper function names (`_run_describe_pass` / `_run_score_pass` are suggested; planner may adjust)
- `log_prefix` behavior in wrapper paths (safe either way)
- Test-file layout for `batch_analyze` (new file recommended; not locked)
- Exact string keys in `constants/strings.ts` (follow `DESC_*` / `ANALYZE_*` conventions)
- Visual separator/heading for the "Run stages separately" subsection inside the Advanced disclosure

## Deferred Ideas

- Unified vision-match + describe (SEED-014 → v3.0)
- Filter-framework migration of the Analyze tab form (Phase 4)
- URL-syncing the advanced disclosure state and force checkboxes (rides with SEED-010)
- Weighted-by-work-units progress split (explicitly rejected in D-07; revisit if users report 50/50 feels misleading)
- Skip scoring for images whose describe failed this run (rejected in D-05)
- Unifying `BatchActionPanel.tsx` with the new Analyze tab flow (different surface, separate phase if at all)
- Single combined checkpoint fingerprint covering both stages (rejected in D-15/D-17)
