---
status: complete
phase: 02-jobs-system-reliability
source: 02-01-SUMMARY.md, 02-02-SUMMARY.md, 02-03-SUMMARY.md, 02-04-SUMMARY.md
started: 2026-04-10T12:00:00Z
updated: 2026-04-10T19:30:00Z
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
result: pass
note: Initially reported cancelled jobs reappearing as in-progress — fixed by guarding update_progress and update_job_status against overwriting cancelled status.

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
result: pass
note: Initially failed — jobs kept running after cancel. Fixed by checking DB status in is_cancelled(), threading should_cancel into score_candidates_with_vision, and adding SQL guard in update_job_status.

## Summary

total: 10
passed: 10
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none — all issues resolved during UAT]
