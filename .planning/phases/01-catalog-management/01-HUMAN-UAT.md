---
status: partial
phase: 01-catalog-management
source: [01-VERIFICATION.md]
started: 2026-04-10T17:37:41Z
updated: 2026-04-10T17:37:41Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Register + browse catalog
expected: Set catalog via UI, confirm config.yaml and GET /api/config/catalog reflect the path; browse pages with a large library.db and confirm responsiveness.
result: [pending]

### 2. Filters with populated data
expected: With populated data, confirm GET /api/images/catalog with keyword, min_rating, dates, color_label, posted, month returns total matching the filtered set; mirror in UI.
result: [pending]

### 3. Stable identity across sessions
expected: After refresh and sign-out/sign-in, open the same photo and confirm the same id/key semantics; optionally re-run CLI scan and confirm id updates without breaking references.
result: [pending]

### 4. Read-only safety
expected: Confirm Lightroom or another tool can keep the catalog open while browsing; no unexpected .lrcat modification from read paths (spot-check file mtime or Lightroom expectations).
result: [pending]

### 5. Catalog 500 regression fix
expected: curl GET /api/images/catalog?limit=50&offset=0 against a running dev server with real LIBRARY_DB returns HTTP 200 with images and total.
result: [pending]

### 6. UI states (error, empty, filtered-zero)
expected: Simulate API failure (e.g., wrong port) and confirm filters stay visible, error copy shows, and empty DB vs filtered-zero remain distinct.
result: [pending]

## Summary

total: 6
passed: 0
issues: 0
pending: 6
skipped: 0
blocked: 0

## Gaps
