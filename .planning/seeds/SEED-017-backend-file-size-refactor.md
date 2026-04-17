---
id: SEED-017
status: dormant
planted: 2026-04-17
planted_during: v2.0 shipped — planning next milestone
trigger_when: Next refactor / tech-debt milestone
scope: Large
---

# SEED-017: Break up oversized backend files (DRY + KISS pass)

## Why This Matters

Backend files have grown well past the point where they fit in a reviewer's
head. Concrete sizes today:

| File | Lines |
|---|---|
| `lightroom_tagger/core/database.py` | 1867 |
| `apps/visualizer/backend/jobs/handlers.py` | 1604 |
| `lightroom_tagger/core/test_database.py` | 886 |
| `lightroom_tagger/cli.py` | 759 |
| `lightroom_tagger/core/analyzer.py` | 734 |
| `apps/visualizer/backend/api/images.py` | 715 |
| `lightroom_tagger/core/cli.py` | 644 |
| `lightroom_tagger/core/matcher.py` | 634 |
| `lightroom_tagger/core/identity_service.py` | 544 |

Consequences that compound every milestone:

- **Every change costs disproportionate time** to navigate, understand, and
  review. Finding the right function in a 1.6k-line file is itself a task.
- **Merge conflicts concentrate** in these files because every feature touches
  them.
- **Test files track the bloat** (`test_database.py` at 886 lines) — hard to
  tell which tests cover which behaviour.
- **DRY violations hide** in files this size — shared patterns get re-
  implemented because nobody scrolls far enough to notice the duplicate.
- **KISS violations** — handlers mix orchestration, validation, persistence,
  and response shaping in the same function bodies.

The frontend is mostly fine; this is a backend-specific problem. Splitting by
responsibility (DRY extraction of shared helpers, KISS single-purpose modules)
reduces future change cost across **every upcoming milestone**, which is why
this deserves a dedicated tech-debt slot rather than being bolted onto a
feature milestone.

## When to Surface

**Trigger:** Next refactor / tech-debt milestone.

Surface this seed during `/gsd-new-milestone` when the milestone scope matches
any of:

- Explicit refactor / tech-debt / maintainability milestone
- "Backend cleanup" or "reduce change cost" framing
- Any milestone where the stated goal includes speeding up future work rather
  than shipping new features

Do **not** surface for pure feature milestones — this work should not be
smuggled into a feature milestone as a side quest. It needs its own plan.

## Scope Estimate

**Large** — a full milestone.

Why large:

- 9+ files over 500 lines, several over 1000, one over 1800.
- Multiple layers involved: `lightroom_tagger/core/*` (domain),
  `apps/visualizer/backend/api/*` (HTTP), `apps/visualizer/backend/jobs/*`
  (job handlers), `lightroom_tagger/cli.py` + `lightroom_tagger/core/cli.py`
  (CLI entry points).
- Tests need to split alongside source to avoid 800-line test files swallowing
  the new module boundaries.
- A **module boundary policy going forward** needs to be written and enforced
  (e.g., target max file size, what belongs in a handler vs. a service vs. a
  repository), otherwise the same bloat returns within two milestones.

Suggested phase shape when this milestone runs (not a plan, just a sketch):

1. **Audit & policy** — measure current state, agree on max-size / structural
   rules, document in the backend readme or equivalent.
2. **Split `handlers.py`** — one module per job kind (or per job family),
   extract shared "load job, update progress, write result" helpers. This is
   the highest-traffic file and the biggest win.
3. **Split `core/database.py`** — separate by domain concern (catalog,
   instagram, matches, descriptions, identity, scores, jobs). Co-split the
   test file.
4. **Split `core/analyzer.py` / `core/matcher.py` / `core/identity_service.py`**
   — extract reusable scoring / filtering / persistence helpers; kill
   duplicated logic surfaced by the split.
5. **Split `api/images.py` and the CLIs** — by resource / by command group.
6. **Lint / CI guard** — add a file-size warning or equivalent so this
   doesn't silently regrow.

Risks / open questions:

- Import churn will be large — needs a disciplined phase with small commits
  to keep review tractable.
- Public import paths may change; audit external callers (scripts, notebooks,
  any downstream tooling) before renaming modules.
- Behaviour must not change. Test suite needs to be green between every
  split; this is a "move code, don't rewrite it" milestone.
- Resist the urge to "improve while splitting" — separate any behaviour
  changes into follow-up seeds/phases.

## Breadcrumbs

Primary targets (size-ordered):

- `lightroom_tagger/core/database.py` (1867)
- `apps/visualizer/backend/jobs/handlers.py` (1604)
- `lightroom_tagger/core/test_database.py` (886)
- `lightroom_tagger/cli.py` (759)
- `lightroom_tagger/core/analyzer.py` (734)
- `apps/visualizer/backend/api/images.py` (715)
- `lightroom_tagger/core/cli.py` (644)
- `lightroom_tagger/core/matcher.py` (634)
- `lightroom_tagger/core/identity_service.py` (544)

Secondary (watch list — likely to trigger splits too):

- `lightroom_tagger/instagram/browser.py` (441)
- `lightroom_tagger/core/posting_analytics.py` (435)
- `lightroom_tagger/core/vision_client.py` (427)
- `lightroom_tagger/instagram/dump_reader.py` (404)

Related seeds:

- SEED-001 — unified batch job (touches `handlers.py`; ideally lands **after**
  the handlers split so it targets focused modules rather than the 1.6k
  monolith, or the two coordinate).
- SEED-014 — unified vision match-and-describe (same consideration; avoid
  shipping into the pre-split `handlers.py`).

## Notes

Captured while planning the next milestone. User's framing: "handlers function
in the backend is too big… DRY and KISS… backend files are way too big, not
only handlers, in general." This seed is deliberately **large** and should run
as its own tech-debt milestone, not as a sidecar to feature work. The
compounding payoff is on every subsequent backend change, so the earlier it
runs, the more it's worth.
