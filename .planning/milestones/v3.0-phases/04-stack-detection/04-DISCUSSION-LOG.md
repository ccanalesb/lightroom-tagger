# Phase 4: Stack Detection — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-24
**Phase:** 04-stack-detection
**Areas discussed:** Job shape, Representative selection, Re-run semantics, Configuration

---

## Job Shape

| Option | Description | Selected |
|--------|-------------|----------|
| A) One unified job | `batch_stack_detect` runs burst pass then pHash pass in sequence | ✓ (burst only) |
| B) Two separate job types | `batch_stack_burst` + `batch_stack_phash` triggerable independently | |
| C) One job with passes flag | Single job, metadata selects which passes run | |

**User's choice:** Single `batch_stack_detect` job. User decided to **drop pHash entirely** — "doesn't offer anything to us." Burst-by-time pass only.

**Notes:** STACK-02 (pHash near-duplicate clustering) dropped from scope, not deferred.

---

## Representative Selection

| Option | Description | Selected |
|--------|-------------|----------|
| A) Highest Lightroom rating | Pick highest star rating in burst | ✓ (as tier 1) |
| B) Middle of sequence | Median by date_taken | |
| C) First in sequence | Lowest date_taken | |
| D) No automatic representative | Leave null until user picks (STACK-05) | |

**User's choice:** Three-tier cascade:
1. Highest Lightroom `images.rating` (non-zero)
2. Highest AI aggregate score (LEFT JOIN `image_descriptions`)
3. Last by `date_taken` (final fallback)

**Notes:** User clarified they don't use Lightroom star ratings personally but acknowledged others might. AI scoring is their primary quality signal. The cascade respects both workflows. Zero-rating tiebreak resolved to "last by date_taken" (user's preference — photographer tends to refine shot as burst progresses).

---

## Re-run Semantics

| Option | Description | Selected |
|--------|-------------|----------|
| A) Rebuild all | Drop and recreate all stacks on every run | |
| B) Incremental | Only process images not yet in any stack | ✓ (default) |
| C) Rebuild non-user-edited only | Requires user_modified flag | ✓ (as force option) |

**User's choice:** Incremental by default (consistent with project-wide pattern). `force` param in job metadata:
- `false` / omitted: incremental
- `true`: rebuild all
- `"preserve_edited"`: rebuild non-user-modified stacks only (forward-looking for Phase 7)

**Notes:** User noted "the project follows B pattern all over the place but allowing the user to rebuild at will." Also requested the preserve_edited option be baked in now so Phase 7 doesn't need to change the job contract.

---

## Configuration

| Option | Description | Selected |
|--------|-------------|----------|
| A) Job metadata only | Pass delta_ms per-run, no persistence | |
| B) Config file | Stored in config.yaml, persistent | ✓ (as default) |
| C) Hardcoded default | No user control in Phase 4 | |

**User's choice:** Config file stores the persistent default (`stack_burst_delta_ms: 2000`). Job metadata `delta_ms` overrides per-run. New `StackDetectionSettingsPanel` in existing `SettingsTab` exposes the persistent default — same pattern as `CatalogSettingsPanel`.

---

## Claude's Discretion

- Exact SQL strategy for burst grouping (window function vs sort-and-scan)
- Whether `image_stacks` stores denormalized `stack_size`
- Exact migration helper name and structure
- Checkpoint fingerprint composition
- Whether settings panel uses existing or new config API endpoint

## Deferred Ideas

- STACK-02 pHash near-duplicate clustering — dropped entirely (not deferred)
- Stack UI (STACK-03) — Phase 6
- Stack-aware matching (STACK-04, STACK-05) — Phase 7
