# Plan: Reachability Observability & Anti-Hang Robustness (PRD 2 of 2)

> Depends on `2026-07-21-reachability-defer-not-abort.md` (PRD 1), which removes the
> false whole-job abort and establishes cache-first + defer-per-image as the baseline.
> This PRD adds the durable, operator-facing layer on top.

## Context

PRD 1 stops path-dependent jobs from falsely aborting: they now complete, describe every
image with a usable compressed copy, skip the rest, and report skip counts as a `warning`.
Two gaps remain once the bleeding is stopped:

1. **Hang risk on a genuinely dead NAS.** PRD 1 makes a dead-mount run *non-fatal*, but
   not *fast*. With the mount down or hung (SMB), the per-image `os.path.isfile` fallback
   for each *uncached* original can block — potentially ~30s per call on a hung share,
   across hundreds of files. There is no upfront check of whether the mount is actually
   healthy.

2. **No per-image traceability.** PRD 1's aggregate `skipped_by_reason` tells you *how
   many* and *why*, but not *which photos* to go re-sync, nor *how long* they've been
   missing. Answering "what do I need to restore to the NAS?" still requires ad-hoc
   queries against the filesystem.

## Goals

1. **Bounded mount-health probe** so a down/hung NAS is detected quickly and cheaply, and
   the pipeline defers all uncached work in one decision instead of hammering (or hanging
   on) a dead mount — while still describing every cache-available image.
2. **Lightweight per-image reachability telemetry** for traceability and inference —
   "missing since when", "gone N runs" — that is **never** consulted by work selection.
3. **A deferred-list view** so the operator can see exactly which files are unreachable
   and why, without scraping logs or hand-writing SQL.

## Design Decisions (locked during design review)

- **Decision — Positive-confirmation probe, not just `os.path.ismount()`.** A hung SMB
  share can report `ismount() == True` while reads block. Health therefore requires a
  cheap read (`os.scandir`/`stat` of the mount root or a sentinel) that **succeeds within
  a hard timeout** (constant, ~2–3s, tunable — not a magic literal).
- **Decision — Timeout ⇒ "down", never wait.** On probe timeout or error, treat the mount
  as down and defer all uncached work this run. The health check must never become the new
  stall.
- **Decision — A non-mount path is not an infra signal.** A path whose root isn't a mount
  this host knows about (e.g. `C:/…` Windows paths, local `.lrdata` previews) is classified
  by pattern as "not reachable from this host" and never contributes to the mount-health
  decision.
- **Decision — Telemetry is a mirror, not a gate.** Reachability telemetry lives in its own
  table and is **never read by any work-selection query**. This makes "no death sentence" a
  structural guarantee: selection physically cannot exclude an image based on past
  unreachability. Telemetry is written as a cheap inline label at the moment an image is
  described or deferred — not by a separate classification sweep (the cache-first check
  already decides work; the sweep would be dead weight).
- **Decision — Reasons are derived inline.** The deferral reason (`original_missing`,
  `windows_only`, `lrdata_preview`, `nas_mount_down`) is computed from the path + probe
  result when an image is deferred; no standalone pass.
- **Principle — No death sentence (carried from PRD 1).** `first_missing_at` self-clears
  when a file returns; `consecutive_misses` is purely for operator inference. Neither ever
  excludes an image from being re-checked.

## Implementation Plan

### Phase 1: Bounded mount-health probe

**File: `apps/visualizer/backend/jobs/handlers/path_diagnostics.py`**

- Add a `probe_mount_health(root, *, timeout_s=MOUNT_PROBE_TIMEOUT_S) -> bool` helper:
  - `os.path.ismount(root)` **and** a `stat`/`scandir` of the root that returns within
    `timeout_s` (run under a deadline, e.g. a worker thread with `join(timeout)`, so a
    hung mount cannot block the caller).
  - Any failure/timeout ⇒ `False` (down).
- Determine the root a candidate needs from the resolved path (config `mount_point`
  `/Volumes/ccanales`, or the auto-detected `/Volumes/<share>`).
- Integrate into the per-job flow (before the work loop):
  - **Mount healthy:** proceed as PRD 1 — per image, cache → describe; else original
    present → compress + describe; else defer (`original_missing`).
  - **Mount down:** **do not** touch the filesystem for uncached originals — defer them
    all immediately with reason `nas_mount_down`; still describe every cache-available
    image.
- Add `MOUNT_PROBE_TIMEOUT_S` as a named constant alongside `PREFLIGHT_SAMPLE_SIZE`.

### Phase 2: `image_reachability` telemetry table

**File: `lightroom_tagger/core/database.py` (+ migration in `apps/visualizer/backend/database.py`)**

```sql
CREATE TABLE image_reachability (
    image_key          TEXT PRIMARY KEY,   -- FK → images.key
    last_checked_at    TEXT,               -- ISO ts of last evaluation
    status             TEXT,               -- reachable | original_missing |
                                           -- never_compressible | windows_only |
                                           -- lrdata_preview | nas_mount_down
    resolved_path      TEXT,               -- concrete path stat()'d (traceability)
    first_missing_at   TEXT,               -- set when it goes missing; CLEARED on return
    consecutive_misses INTEGER DEFAULT 0   -- run-count, inference only
);
```

Helpers:
- `upsert_reachability(db, image_key, status, resolved_path)` — updates `last_checked_at`;
  on a missing status, sets `first_missing_at` if null and increments `consecutive_misses`;
  on `reachable`, clears `first_missing_at` and resets `consecutive_misses` to 0.

**Decision — separate table, not columns on `images`.** Keeps the 30-column catalog table
clean, signals "observability, not catalog truth", and can be wiped/rebuilt from a single
run. **No work-selection query may JOIN it.**

**Integration:** call `upsert_reachability` inline wherever the pipeline evaluates an image
(the describe/compress loop and the defer branch) — one write per evaluated image per run.
Described images drop out of the backlog, so their row simply stops updating (fine —
reachability is moot once described).

### Phase 3: Deferred-list report

**File: `apps/visualizer/backend/api/jobs.py` (or a small reachability route module)**

- `GET /api/jobs/<id>/deferred` (or `GET /api/reachability`) returns the current deferred
  set from `image_reachability`: grouped counts by `status`, plus a paginated list of
  `{image_key, filepath, resolved_path, status, first_missing_at, consecutive_misses}`.
- Also embed a few example paths per reason (say 5) directly in the job `result` from
  PRD 1, so the operator gets a taste inline and the full list on demand.

## Verification

- **Anti-hang:** simulate a hung mount (unreachable root); confirm `probe_mount_health`
  returns `False` within the timeout and the job defers all uncached work *quickly* while
  still describing cache-available images — no multi-minute stall.
- **Recovery (no death sentence):** mark a file missing across several runs (watch
  `consecutive_misses` climb, `first_missing_at` stay fixed); then restore the file and
  confirm the next run describes it and clears `first_missing_at` / resets the counter.
- **Selection isolation:** grep/assert that no selection query references
  `image_reachability`; a file with `consecutive_misses = 99` is still re-checked every run.
- **Report:** `GET .../deferred` returns accurate grouped counts matching the job's
  `skipped_by_reason`, plus the per-file list with durations.

## Rollout / Sequencing

1. Phase 1 (probe) — independent, immediately reduces wasted time on down/hung mounts.
2. Phase 2 (telemetry table + inline writes) — additive; safe with PRD 1 in place.
3. Phase 3 (report endpoint) — read-only, depends on Phase 2.
