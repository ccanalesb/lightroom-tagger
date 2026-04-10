# Phase 2: Jobs & System Reliability - Context

**Gathered:** 2026-04-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Observable job lifecycle, cooperative cancellation, backup-before-write discipline, actionable errors with severity, and Lightroom-open guardrails. This is the safety and reliability layer that Phases 3 (Instagram sync) and 4 (AI analysis) depend on for write-safety and job UX.

</domain>

<decisions>
## Implementation Decisions

### Job Cancellation (SYS-02)
- **D-01:** Cooperative cancellation flag. Set a `cancelled` flag that handlers check between iterations (e.g., between images in a batch loop). The thread finishes its current unit of work then stops gracefully. This matches the existing per-image loop structure in `handle_batch_describe` and `handle_vision_match`.
- **D-02:** The `JobRunner.active_jobs` dict (currently unused) should track cancellation state. The cancel endpoint sets the flag; handler loops check it.

### Backup-Before-Write (SYS-03)
- **D-03:** Backup the `.lrcat` catalog file before every job that writes to it (currently only keyword writeback via `update_lightroom_from_matches`). One backup per write-job, not per image.
- **D-04:** Keep a maximum of 2 backups. Rotate out the oldest when a third would be created. Prevents disk bloat from the 1.2 GB catalog.
- **D-05:** Backup location and naming: same directory as the catalog, timestamped (e.g., `FinalCatalog-v13-3.lrcat.backup-2026-04-10T14-30-00`).
- **D-06:** Only triggered when a job actually writes to the catalog — jobs that only touch the library DB (describe, enrich, prepare cache) do not trigger backup.

### Lightroom-Open Detection (SYS-05)
- **D-07:** Hard block on writes when Lightroom has the catalog open. Check for the `.lrcat-lock` file that Lightroom creates when the catalog is open.
- **D-08:** Refuse to start any write job if the lock file exists. User gets a clear error: "Close Lightroom before writing to catalog."
- **D-09:** Check happens before the backup step — no wasted backup copy if Lightroom is open.

### Error Message Quality (SYS-04)
- **D-10:** Severity badges in the UI — tag errors as warning/error/critical. Keep the original error message text as-is (no rewriting to user-friendly strings).
- **D-11:** Raw error details remain in job logs for debugging. The UI shows severity level visually alongside the original message.

### Job Status Observability (SYS-01)
- **D-12:** Job lifecycle states already exist in the DB schema (pending, running, completed, failed, cancelled). Socket.IO live updates already emit `job_updated`. Frontend components (`JobCard`, `JobDetailModal`, `JobQueueTab`, `useJobSocket`) already render status. This requirement is largely satisfied — phase work focuses on closing gaps (cancelled state UI, cooperative cancellation wiring, orphaned job recovery improvements).

### Claude's Discretion
- Exact polling interval or mechanism for cooperative cancellation checks (per-iteration vs periodic)
- Severity classification logic (which errors map to warning vs error vs critical)
- UI placement and styling of severity badges in existing job components
- Whether to add a "backup created" log entry to the job or a separate notification

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Job infrastructure (backend)
- `apps/visualizer/backend/jobs/runner.py` — `JobRunner` class with `start_job`, `update_progress`, `complete_job`, `fail_job`, `cancel_job` methods. `active_jobs` dict exists but is unpopulated.
- `apps/visualizer/backend/jobs/handlers.py` — `JOB_HANDLERS` dict, `handle_vision_match` (calls `update_lightroom_from_matches`), `handle_batch_describe`, `handle_enrich_catalog`, `handle_prepare_catalog`
- `apps/visualizer/backend/database.py` — Job table schema, `create_job`, `update_job_status`, `add_job_log`, `get_pending_jobs`, `get_active_jobs`
- `apps/visualizer/backend/app.py` — `_job_processor` background thread, `_recover_orphaned_jobs`, Flask app factory
- `apps/visualizer/backend/api/jobs.py` — REST endpoints: list, create, get, cancel (`DELETE`), retry, active

### Catalog writer
- `lightroom_tagger/lightroom/writer.py` — `connect_catalog()`, `update_lightroom_from_matches()`, `add_keyword_to_images_batch()`. No backup logic currently. Opens catalog with plain `sqlite3.connect()`.

### Job frontend
- `apps/visualizer/frontend/src/types/job.ts` — `Job` interface, `JobStatus` type (pending/running/completed/failed/cancelled)
- `apps/visualizer/frontend/src/hooks/useJobSocket.ts` — Socket.IO hook for live job updates
- `apps/visualizer/frontend/src/components/jobs/JobCard.tsx` — Job card display
- `apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx` — Job detail view with logs
- `apps/visualizer/frontend/src/components/jobs/JobsList.tsx` — Job list
- `apps/visualizer/frontend/src/components/processing/JobQueueTab.tsx` — Processing page tab
- `apps/visualizer/frontend/src/utils/jobStatus.ts` — Status utilities

### Existing backup patterns (reference)
- `lightroom_tagger/core/database.py` lines ~348-356 — Key migration backup pattern using `shutil.copy2` to `.pre-key-migration.bak`
- `lightroom_tagger/lightroom/cleanup_wrong_links.py` lines ~28-30 — Timestamped backup pattern: `<catalog>.backup-<timestamp>`

### Configuration
- `lightroom_tagger/core/config.py` — `Config` dataclass, `load_config()`, `catalog_path` field
- `config.yaml` — Runtime config with `catalog_path` pointing to the active `.lrcat`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `JobRunner` — Already has `cancel_job` method and `active_jobs` dict, just needs wiring
- `_recover_orphaned_jobs` — Pattern for handling interrupted jobs on restart
- `cleanup_wrong_links.py` backup pattern — `shutil.copy2` with timestamped naming, directly reusable for catalog backup
- `ProviderError` hierarchy — Existing severity/category pattern for AI errors, extensible to system errors
- `useJobSocket` hook — Already handles live `job_updated` events, no changes needed for status observability
- `JobCard`/`JobDetailModal` — Existing job UI components to extend with severity badges and cancelled state

### Established Patterns
- Handlers follow `handler(runner, job_id, metadata)` signature with try/except calling `runner.fail_job`
- Job logs accumulated via `add_job_log(db, job_id, level, message)` with levels: info, warning, error
- Socket.IO emits `job_updated` with full job object after state changes
- `with_db` decorator for connection management in Flask routes

### Integration Points
- `handle_vision_match` lines 111-119 — Insert backup + lock check before `update_lightroom_from_matches` call
- `JobRunner.cancel_job` — Wire `active_jobs` dict to track cancellation flags per job
- Handler loops (e.g., `handle_batch_describe` image iteration) — Add cancellation flag check between iterations
- `cancel_job` REST endpoint (`api/jobs.py`) — Needs to signal the runner, not just flip DB status
- `JobCard.tsx` / `JobDetailModal.tsx` — Add severity badge rendering for error/warning/critical

</code_context>

<specifics>
## Specific Ideas

- Catalog is 1.2 GB (`/Users/ccanales/lightroom/FinalCatalog/FinalCatalog-v13-3.lrcat`) — backup copies are non-trivial, hence the max-2 rotation
- The only current catalog write path is keyword writeback after match confirmation — backup/lock-check only needs to gate that path today
- Lightroom creates a `.lrcat-lock` file when the catalog is open — this is the detection mechanism

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-jobs-system-reliability*
*Context gathered: 2026-04-10*
