# Phase 2: Jobs & System Reliability - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-10
**Phase:** 02-jobs-system-reliability
**Areas discussed:** Job cancellation, Backup-before-write strategy, Lightroom-open detection, Error message quality

---

## Job Cancellation

| Option | Description | Selected |
|--------|-------------|----------|
| Cooperative flag | Set a cancelled flag that handlers check between iterations. Thread finishes current unit of work then stops gracefully. | ✓ |
| Timeout-based | Let the thread run but cap total job duration. If exceeded, mark as failed. | |
| Immediate thread kill | Force-stop the thread. Fast but risks DB inconsistency. | |

**User's choice:** Cooperative flag
**Notes:** Matches the existing per-image loop structure in handlers. Safest for DB integrity.

---

## Backup-Before-Write Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Before every write session | Copy full .lrcat before any job that writes to catalog. One backup per job. | ✓ (with modification) |
| Once per day | Daily backup regardless of write count. | |
| Manual only | Prompt user to back up, don't automate. | |

**User's choice:** Before every write session, with max 2 backups and oldest rotation
**Notes:** User was initially unsure. After reviewing that catalog is 1.2 GB and only keyword writeback actually writes to catalog (not describe/enrich/cache jobs), agreed to per-write-session backup with a cap of 2 backups to avoid disk bloat. Only triggered when a job actually calls `update_lightroom_from_matches`.

---

## Lightroom-Open Detection

| Option | Description | Selected |
|--------|-------------|----------|
| Hard block | Check for .lrcat-lock file. Refuse write jobs if Lightroom has catalog open. | ✓ |
| Warning with override | Detect lock, warn user, let them proceed if they choose. | |
| Check only at write time | Don't check at job start, only right before the sqlite3.connect() write call. | |

**User's choice:** Hard block
**Notes:** Safest option. Check happens before backup to avoid wasted copies.

---

## Error Message Quality

| Option | Description | Selected |
|--------|-------------|----------|
| Categorized with actionable guidance | Map failures to user-friendly categories with retry suggestions. | |
| Severity badges only | Tag errors as warning/error/critical in UI, keep original message text. | ✓ |
| You decide | Claude picks best approach. | |

**User's choice:** Severity badges only
**Notes:** Simpler to implement. Original error text preserved for transparency. Raw details stay in job logs.

---

## Claude's Discretion

- Polling mechanism for cooperative cancellation checks
- Severity classification logic
- UI placement of severity badges
- Backup notification approach

## Deferred Ideas

None — discussion stayed within phase scope
