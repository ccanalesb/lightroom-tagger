# Phase 2: Jobs & System Reliability — Research Notes

**Purpose:** What you need to know to **plan** this phase well (not a full implementation spec).  
**Sources:** `02-CONTEXT.md`, `REQUIREMENTS.md`, `STATE.md`, `.cursor/rules/AGENTS.md`, canonical code paths listed in context.

---

## 1. Requirements snapshot (traceability)

| ID | Intent (from REQUIREMENTS) | Phase focus (from CONTEXT) |
|----|-----------------------------|-----------------------------|
| **SYS-01** | User sees job status (queued, running, complete, failed) | Mostly done; close gaps: cancelled UX consistency, cancellation wiring, orphaned-job behavior |
| **SYS-02** | User can cancel running jobs | Cooperative cancel via flag in `JobRunner.active_jobs`; REST must signal runner, not only DB |
| **SYS-03** | Backup catalog before any write | One backup per write job, max 2 rotated, timestamped, same dir as `.lrcat`; only when catalog is actually written |
| **SYS-04** | Clear, actionable errors | Severity badges (warning / error / critical) in UI; keep raw message text; details in logs |
| **SYS-05** | No writes while Lightroom has catalog open | Hard block if `.lrcat-lock` exists; check **before** backup |

**Naming mismatch to resolve in the plan:** requirements say “queued”; the codebase and DB use **`pending`**. Decide whether to rename in API/UI copy only or align schema/docs.

---

## 2. Current architecture (facts from the repo)

### 2.1 Job execution model

- A **daemon thread** `_job_processor` in `apps/visualizer/backend/app.py` polls `get_pending_jobs` every second, marks each job `running` via `JobRunner.start_job`, then invokes `JOB_HANDLERS[job_type](runner, job_id, metadata)` **synchronously** on the same thread.
- After the handler returns, it emits `job_updated` with the full job row.
- **Implication:** Only one handler runs at a time in practice (sequential `for job in pending`). Cancellation still matters because a long-running handler blocks the queue and the user expects stop semantics.

### 2.2 `JobRunner` (`apps/visualizer/backend/jobs/runner.py`)

- Methods: `start_job`, `update_progress`, `complete_job`, `fail_job`, `cancel_job`.
- `active_jobs` is **`{}` and never populated** in the current processor path.
- `cancel_job` does `self.active_jobs[job_id].cancel()` — expects an object with a `.cancel()` method. Nothing registers such objects today, so this path is **non-functional** as written.
- **Planning takeaway:** Replace or implement a small **cancellation handle** (e.g. a mutable object or dataclass with `cancelled: bool`, or `threading.Event`) registered in `start_job` and cleared in `complete_job` / `fail_job` / terminal cancel paths.

### 2.3 Cancel API (`apps/visualizer/backend/api/jobs.py`)

- `DELETE /api/jobs/<id>` sets status to `cancelled` in the DB **if** status is `running` or `pending`.
- It does **not** call `JobRunner.cancel_job` or set any in-memory flag.
- **Implication:** The handler keeps running; it may later call `complete_job` or `fail_job` and **overwrite** `cancelled` unless handlers respect cancellation and stop without completing.

### 2.4 Job schema (`apps/visualizer/backend/database.py`)

- Columns include `status`, `progress`, `current_step`, `logs` (JSON array), `result`, `error`, timestamps, `metadata`.
- `update_job_status` sets `completed_at` for `completed`, `failed`, and **`cancelled`**.
- `add_job_log` supports per-entry `level` (`info`, `warning`, `error` in practice).
- **There is no `error_severity` (or similar) column today** — SYS-04 severity in the **job summary** will need a schema or encoding decision (see §5).

### 2.5 Orphan recovery (`_recover_orphaned_jobs`)

- On app startup, every job with status `running` is marked **`failed`** with log “Job interrupted by server restart”.
- Jobs with status `pending` are untouched.
- **Planning considerations:** Distinguish “user cancelled but process died mid-write” vs “server restart” is hard without extra state; CONTEXT calls for **improvements** (wording, whether `pending` after crash is possible, idempotency of handlers).

### 2.6 Catalog write path (SYS-03 / SYS-05)

- Only **`handle_vision_match`** writes the Lightroom catalog today: after `match_dump_media`, it calls `update_lightroom_from_matches(catalog_path, matches)` when `catalog_path` exists (`lightroom_tagger/lightroom/writer.py`).
- `update_lightroom_from_matches` opens the catalog with `sqlite3.connect`, mutates keywords, commits. **No backup, no lock check.**
- Other handlers (`enrich_catalog`, `prepare_catalog`, `batch_describe`) touch the **library** DB, not the `.lrcat` — CONTEXT explicitly excludes them from catalog backup.

### 2.7 Matching loop (`lightroom_tagger/scripts/match_instagram_dump.py`)

- `match_dump_media` iterates `for idx, dump_media in enumerate(unprocessed, 1):` and calls `progress_callback` once per item at the end of each iteration.
- **Natural hook for cooperative cancellation:** optional `should_cancel()` (or pass runner) checked at the top of each iteration **before** heavy work, and optionally inside long sub-steps if needed.
- No such parameter exists yet — plan whether to extend `match_dump_media` signature or only cancel between “macro” phases inside `handle_vision_match` (weaker UX for long single-image vision batches).

### 2.8 Parallel handlers

- `handle_prepare_catalog` and `handle_batch_describe` use `ThreadPoolExecutor`. Cooperative cancellation is **harder**: workers do not see the runner unless you pass a shared cancel flag; you may need **batch boundaries** or stop submitting new futures and drain.

### 2.9 Frontend

- Types: `JobStatus` includes `cancelled` (`apps/visualizer/frontend/src/types/job.ts`). Job logs allow `info` | `warning` | `error` only — **no `critical`** in the type (plan whether log lines need `critical` or only job-level failure severity).
- `useJobSocket` listens for `job_updated` — no change required for basic observability.
- `JobDetailModal` maps `cancelled` → warning `Badge`; error block shows `displayJob.error` as monospace red text — **no severity tier** on the main error yet.
- `JobCard` uses `StatusBadge` + `jobStatus.ts` colors; **`cancelled` is already styled** in `statusBadgeClasses`.
- `JobQueueTab` optimistically sets cancelled on successful API cancel; server must eventually emit consistent state.

### 2.10 Design system (`apps/visualizer/frontend/DESIGN.md`)

- Badge variants: **default, success, warning, error, accent** — maps cleanly to CONTEXT’s warning / error / critical (plan how **critical** differs visually from **error**, e.g. stronger border or icon).

### 2.11 Existing backup patterns (reference only)

- `lightroom_tagger/core/database.py`: `shutil.copy2` to `db_path + ".pre-key-migration.bak"` before a one-time migration.
- `lightroom_tagger/lightroom/cleanup_wrong_links.py`: timestamped `shutil.copy2` to `{catalog.name}.backup-{timestamp}` in the catalog directory.

---

## 3. Gaps vs user decisions (D-01 … D-12)

| Decision | Gap |
|----------|-----|
| D-01 / D-02 | Register per-job cancel state in `active_jobs`; handlers must poll it. |
| D-03–D-06 | Implement rotation (max 2) + timestamp naming; call site = before first catalog write in the write job. |
| D-07–D-09 | Lock path convention must be verified on target OS; fail fast with fixed user-facing message before backup. |
| D-10 / D-11 | UI severity for **failed** jobs (and optionally warnings on completed-with-warnings) needs data model + `fail_job` / API payload updates. |
| D-12 | Cancelled end-to-end; avoid handler clobbering cancelled; orphan recovery messaging and edge cases. |

---

## 4. Planning questions the implementer must answer

### 4.1 Cancellation semantics

- When the user cancels a **`pending`** job: processor may already pick it up — is “cancelled” still valid if `start_job` ran? (Likely: check flag at start of handler and exit immediately without `complete_job`.)
- When cancelling **`running`:** should `cancel_job` in API also append a log line and emit `job_updated`?
- Should `complete_job` / `fail_job` **no-op** if status is already `cancelled`? (Recommended to avoid races.)

### 4.2 Where to put backup + lock checks

- **Option A:** `lightroom_tagger/lightroom/writer.py` at the start of `update_lightroom_from_matches` — centralizes all future catalog writes.
- **Option B:** Only in `handle_vision_match` — minimal blast radius but easy to miss the next write path (Phase 3/4).

CONTEXT points at handler lines 111–119; **Option A** better satisfies “before any write operation” long-term.

### 4.3 Backup rotation algorithm

- Discover existing `*.backup-*` or a fixed prefix pattern for **this catalog basename**; sort by mtime or embedded timestamp; delete oldest when adding a third.
- CONTEXT example uses ISO-like timestamp in the filename; align with filesystem-safe characters (e.g. replace `:` as in `cleanup_wrong_links`).

### 4.4 Lock file

- Confirm Lightroom’s exact lock filename/location for the user’s catalog (often alongside the `.lrcat`). Document in plan if network volumes or NAS affect visibility.

### 4.5 Severity classification (SYS-04)

- **Job-level failure:** extend `fail_job(job_id, error, severity=...)` or parse exception types (`ProviderError`, `OSError`, lock errors).
- **Warning vs critical:** e.g. disk full during backup → critical; missing optional path → warning.
- **UI:** add badge next to error title in `JobDetailModal`; optionally on `JobCard` for failed jobs.

### 4.6 Observability extras

- Optional log line “Catalog backup created: …” — CONTEXT leaves to discretion; aids support.

---

## 5. Risk register (for test planning)

| Risk | Mitigation idea |
|------|------------------|
| Large catalog (~1.2 GB) backup time / disk | Max 2 backups; run lock check first; consider logging start/end of copy |
| Race: cancel vs complete | Terminal-state guards in runner methods |
| `match_dump_media` long inner calls | Cancellation only between iterations may still feel stuck — document or add mid-loop hooks |
| ThreadPoolExecutor jobs | Document “cancel stops after current futures” or implement periodic flag checks in worker |
| SQLite WAL on library DB vs catalog | Different files; backup logic must target **`.lrcat` only** for SYS-03 |

---

## 6. Suggested verification matrix (UAT-oriented)

- Start vision match with matches → backup appears, at most two retained, oldest removed on third write job.
- With Lightroom open (lock present) → job fails fast with agreed message; **no** new backup file.
- Cancel during matching loop → job ends `cancelled`, no `complete_job`, partial work acceptable per product rules (document).
- Cancel pending job before start → remains or becomes cancelled without partial catalog write.
- Restart server with a `running` job → expected failure log; decide if copy should mention “restart” vs generic failure.
- Failed job with severity → badge visible in list/detail; raw `error` text unchanged.

---

## 7. Files likely touched (implementation checklist)

**Backend:** `jobs/runner.py`, `jobs/handlers.py`, `app.py` (processor / shared runner reference if cancel routes need it), `api/jobs.py`, `database.py` (if new columns), `lightroom/writer.py` (backup/lock), possibly `scripts/match_instagram_dump.py` (cancel callback).

**Frontend:** `types/job.ts`, `JobDetailModal.tsx`, `JobCard.tsx` or shared badge helper, maybe `services/api.ts` if response shape changes.

**Config:** `lightroom_tagger/core/config.py` / `config.yaml` only if backup count, paths, or messages need to be tunable.

---

## 8. Project constraints (from AGENTS.md)

- Catalogs are SQLite; writes are sensitive — aligns with SYS-03/SYS-05.
- Flask + SocketIO for jobs; Black/Ruff/Mypy on Python; ESLint max-warnings 0 on frontend.
- Prefer `utils/responses` patterns for new API errors if exposing structured errors to the client.

---

*Research compiled: 2026-04-10 · Phase: 02-jobs-system-reliability*
