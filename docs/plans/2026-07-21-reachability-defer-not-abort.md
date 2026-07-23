# Plan: Reachability — Defer Per-Image, Never Abort the Job (PRD 1 of 2)

> Companion: `2026-07-21-reachability-observability.md` (PRD 2) builds the durable
> observability + anti-hang layer on top of this. Ship this one first.

## Context

Path-dependent jobs (`batch_analyze`, `batch_describe`, `batch_score`,
`batch_embed_image`, `batch_text_embed`, `vision_match`) run a shared **reachability
preflight** before doing work: `PathSkipDiagnostics.run_preflight`
(`apps/visualizer/backend/jobs/handlers/path_diagnostics.py:246`). It samples 25
images and, if **>50% are unreachable**, calls `runner.fail_job(..., severity='critical')`
and aborts the entire job on the assumption "the network share must not be mounted."

That heuristic is misfiring. It cannot tell the difference between:

- **(transient)** the NAS is genuinely down → abort + retry later is correct; and
- **(persistent)** the NAS is *up*, but the backlog is dominated by files that will
  never be reachable from this host → aborting is wrong and permanent.

### The concrete failure

Job `2428a212-75ae-4c81-a125-f74492b9fa83` (`batch_analyze`) retried ~10 times, each
attempt aborting instantly at the preflight with *"25/25 sampled paths unreachable."*
The NAS (`/Volumes/ccanales`) was mounted and readable the whole time. Measuring the
undescribed backlog against disk:

| Backlog slice (of 1156 undescribed) | Count | Needs the NAS? |
|---|---:|---|
| **Valid local compressed copy already on disk** | **132** | **No — describable right now** |
| Reachable original on the mounted share | ~134 | Only to compress (one-time) |
| No cache + original genuinely missing | ~890 | Yes — file must return |

Because a random 25-sample is dominated by the ~890 permanently/temporarily missing
files, the preflight trips its >50% rule on **every** run and kills the whole job —
**including the 132 images that need zero NAS access and would just work.**

### Root-cause principle (the key realization)

`classify_path` (`path_diagnostics.py:67`) already checks the **vision cache first**
and only falls back to the original file if no usable compressed copy exists. So:

> **Reachability gates *compression*, not description.** Describe / score / embed all
> consume the local compressed cache and are NAS-independent. The original file is
> required *only* to create a cache entry that does not yet exist.

The pipeline logic already honors this. The **preflight abort is the one component
that violates it** — it fails the whole job for a condition that only ever affects a
subset of *uncached* images.

## Goals

1. **Never hard-fail a path-dependent job for reachability reasons.** Always make the
   maximum progress possible: describe/score/embed everything with a usable image
   (cached original *or* present original); skip the rest.
2. **Surface *why* work was skipped** at the job level — counts by reason — so the
   operator is never forced to scrape logs.
3. Apply the fix **once, in the shared component**, so all six job types inherit it.

## Non-Goals (deferred to PRD 2)

- Bounded mount-health probe / anti-hang behavior on a dead NAS.
- Per-image `image_reachability` telemetry table (which files, since when, gone-N-runs).
- A deferred-list report endpoint.

## Design Decisions (locked during design review)

- **Decision — Cache-first is the law.** Selection for describe/score/embed is a single
  binary per image: *is there a usable image to send to the model?* = valid cache **OR**
  original resolves + is present. This already exists; we are removing the thing that
  overrides it. We do **not** add pattern-based pre-filters (e.g. excluding `C:/…` or
  `.lrdata` paths) — the cache-first + `stat` check excludes them for free at the cost
  of one cheap `stat`, no compression, no model call.
- **Decision — Defer, don't abort.** The preflight stops aborting. A missing image is
  skipped per-image (this is exactly what the existing `chain_mode` branch already does);
  the whole-job abort branch is deleted.
- **Decision — Complete with a warning, never `failed`.** A run with skips completes
  with `status='completed'` and `error_severity='warning'` plus a one-line summary. The
  schema already models `'warning'` as a non-fatal severity (`api/schemas/jobs.py`), so
  no new status value and no schema migration.
- **Decision — Fix the shared preflight for all six jobs at once.** They all route
  through the same `classify_path`; the semantics are already uniform. We make them
  uniformly correct instead of uniformly broken.
- **Principle — No death sentence.** Nothing about a skip is persisted or used to
  exclude an image from future runs. Every run re-derives reachability live from the
  filesystem, so recovery is automatic and instant the moment a file returns. Re-checking
  is cheap: a skipped image costs one `stat`, never a compression or a model call.

## Implementation Plan

### Phase 1: Remove the whole-job abort

**File: `apps/visualizer/backend/jobs/handlers/path_diagnostics.py`**

- In `run_preflight` (line ~186), delete the `fail_job(..., severity='critical')` abort
  path (lines ~246–253). The method no longer aborts.
- Keep a **heads-up log**: when the sample shows a high unreachable ratio, emit a single
  `warning`-level log ("N/N sampled images unreachable — continuing; missing files will
  be skipped per-image") — informational only, never terminal. This collapses the
  `chain_mode` / non-`chain_mode` split into one behavior: always continue.
- `run_preflight` effectively always returns `True`. Callers that branch on its return
  (`analyze.py:551`, `analyze.py:1046`, `embed.py`, `matching.py`) simplify accordingly.

### Phase 2: Surface skip reasons to the job result

The per-reason counters already exist on `PathSkipDiagnostics.skip_reason_counts`
(`no_row`, `empty_path`, `unresolved_or_missing`, `encode_failed`).

**Files: `analyze.py`, `embed.py`, `matching.py` (completion paths)**

- On completion, include the counters in the result payload passed to
  `runner.complete_job`, e.g.:
  ```json
  "result": {
    "described": 132,
    "skipped": 890,
    "skipped_by_reason": {
      "unresolved_or_missing": 809,
      "encode_failed": 50,
      "empty_path": 0,
      "no_row": 31
    }
  }
  ```
- When `skipped > 0`, set `error_severity='warning'` and a one-line `error` summary
  (e.g. *"Completed: described 132, skipped 890 — missing/unreachable 809, uncompressible
  50, no catalog row 31"*). This makes a mostly-missing run visibly different from a clean
  run in the jobs list without opening logs.

  **Decision — mechanism:** add a small runner helper (e.g.
  `runner.complete_with_warning(job_id, result, summary)`) rather than overloading
  `fail_job`, so "completed but noteworthy" stays distinct from "failed" in the state
  machine and in `error_count`/`warning_count` derivation.

### Phase 3: Update operator docs

**File: `docs/STORAGE_MOUNT_REQUIREMENTS.md`**

- Update the *Symptoms* table: the row *"Embed job fails immediately with 'sampled paths
  unreachable'"* is replaced by *"Job completes with a `warning` and a `skipped_by_reason`
  breakdown"*. Point operators at the result summary as the first diagnostic.

## Verification

- **Reproduce the win:** trigger `batch_analyze` against the current `library.db`. Expect
  the job to **complete** (not fail), describe the **132 cache-ready** images (plus any
  now-reachable originals), and report `skipped_by_reason` for the rest with
  `error_severity='warning'`.
- **Regression guard:** a run where the mount is genuinely down still completes (describing
  any cache-available images), reporting a high `unresolved_or_missing` count — it does not
  abort. (PRD 2 adds the probe that makes this case *fast*; PRD 1 only makes it *non-fatal*.)
- **All six job types** exercise the shared `run_preflight`; add/adjust tests so none of
  them can enter the deleted abort path.

## Rollout / Sequencing

- Single vertical slice touching one shared component + three completion paths + docs.
- Independent of PRD 2; PRD 2 assumes this behavior as its baseline.
