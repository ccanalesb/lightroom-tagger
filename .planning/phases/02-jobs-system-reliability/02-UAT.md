---
status: complete
phase: 02-jobs-system-reliability
source: 02-01-SUMMARY.md, 02-02-SUMMARY.md, 02-03-SUMMARY.md, 02-04-SUMMARY.md
started: 2026-04-10T12:00:00Z
updated: 2026-04-10T19:15:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Cancel a Running Job via UI/API
expected: Start a long-running job (e.g., vision match or batch describe). While it's running, cancel it via the REST API or UI. The job should stop processing within a few iterations, the job status should change to "cancelled", and no further Lightroom writes should occur after cancellation.
result: pass

### 2. Cancel Prevents Double-Finish
expected: Cancel a running job. After it stops, the job should show "cancelled" status with the message "Job stopped after cancel request". Calling complete or fail on an already-cancelled job should be a no-op — no status flip to completed/failed.
result: pass

### 3. Lightroom Lock Detection
expected: Open the Lightroom catalog in Lightroom (so the .lrcat-lock file exists). Trigger a write operation (e.g., vision match that writes to catalog). The job should fail immediately with an error message containing "Close Lightroom before writing to catalog." instead of silently corrupting data.
result: pass

### 4. Catalog Backup Before Writes
expected: Run a vision match job that writes to the catalog. Check the catalog directory — a timestamped backup file (e.g., catalog.backup-2026-04-10T12-00-00) should appear. Run multiple write jobs — only the 2 most recent backups should be retained (older ones are rotated out).
result: pass

### 5. Job Failure Severity Badges on Job Cards
expected: Trigger different failure modes (e.g., locked catalog = critical, auth error = warning). In the job list, failed jobs should show a colored severity badge: "Warning" (warning color), "Error" (error color), or "Critical" (error color with ring). The badge appears directly on the job card in the list.
result: pass

### 6. Job Failure Severity in Job Detail Modal
expected: Click on a failed job to open its detail modal. The error severity badge (Warning/Error/Critical) should appear alongside the error message text, matching the same badge styling from the job card.
result: issue
reported: "pass, but the old job is reappear as in progress again"
severity: major

### 7. Pending Jobs Show as "Queued"
expected: Create a job that enters pending state. In the job list and job detail modal, the status should display as "Queued" (not "pending"). The underlying API value stays "pending" but the UI label reads "Queued".
result: pass

### 8. Job Detail Status Matches List Badge
expected: For any job status (Queued, Running, Completed, Failed, Cancelled), the status shown in the job detail modal should use the same label and styling as the status badge in the job list. No mismatched labels between list and detail views.
result: pass

### 9. Orphan Job Recovery After Server Restart
expected: Start a job, then kill and restart the server. The previously-running job should be marked as failed with a clear message explaining it was interrupted by a server restart and can be retried.
result: pass

### 10. Cancel Works Across All Long-Running Handlers
expected: Cancel jobs of different types — enrich catalog, batch describe, and prepare catalog cache. Each should respect cancellation within a few iterations, log a cancel message, and finalize cleanly without leaving resources open.
result: issue
reported: "job are not getting cancelled at all"
severity: major

## Summary

total: 10
passed: 8
issues: 2
pending: 0
skipped: 0
blocked: 0

## Gaps

- truth: "Cancelled job stays cancelled in UI and does not reappear as running"
  status: failed
  reason: "User reported: pass, but the old job is reappear as in progress again"
  severity: major
  test: 6
  root_cause: "runner.update_progress() unconditionally calls update_job_status(db, job_id, 'running', ...) which overwrites the 'cancelled' status back to 'running'. Each overwrite also emits a job_updated socket event that makes the UI flip the job back to in-progress."
  artifacts:
    - path: "apps/visualizer/backend/jobs/runner.py"
      issue: "update_progress (line 25) overwrites status to 'running' without checking current DB status"
    - path: "apps/visualizer/backend/app.py"
      issue: "emit_progress lambda (line 117) emits job_updated after every progress tick including when status was just overwritten back to running"
  missing:
    - "update_progress must check is_cancelled() or DB status before writing 'running' — skip the update if job is already cancelled"
    - "Alternatively, update_job_status should be a conditional UPDATE: SET status='running' WHERE status != 'cancelled'"
  debug_session: ""

- truth: "Cancelled jobs stop processing within a few iterations across all handler types"
  status: failed
  reason: "User reported: job are not getting cancelled at all"
  severity: major
  test: 10
  root_cause: "Same root cause as Test 6 — update_progress flips status back to 'running' after cancel. Additionally, the should_cancel/is_cancelled checks only run between full image iterations in handlers, but vision API calls take 5-15 seconds each, so there's a long window where cancel is ignored. The progress_callback fires more frequently than cancel checks, continually resetting status."
  artifacts:
    - path: "apps/visualizer/backend/jobs/runner.py"
      issue: "update_progress overwrites cancelled status back to running (line 25)"
    - path: "apps/visualizer/backend/jobs/handlers.py"
      issue: "Cancel checks are too infrequent — only between full image iterations, not between individual API calls"
    - path: "lightroom_tagger/scripts/match_instagram_dump.py"
      issue: "should_cancel only checked between images, not between vision API batch calls"
  missing:
    - "update_progress must bail out (no-op) when job is cancelled"
    - "Consider checking should_cancel more frequently inside match_dump_media (between batch API calls, not just between images)"
  debug_session: ""
