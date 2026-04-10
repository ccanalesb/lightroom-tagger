---
status: partial
phase: 01-catalog-management
source: [01-01-SUMMARY.md, 01-02-SUMMARY.md, 01-03-SUMMARY.md, 01-04-SUMMARY.md]
started: 2026-04-10T11:45:00Z
updated: 2026-04-10T12:00:00Z
---

## Current Test

[testing paused — 4 items outstanding (2 blocked, 2 skipped)]

## Tests

### 1. Read-only catalog protection
expected: Open a Lightroom catalog for browsing. The app reads the catalog without modifying it. In the code, default read connections use SQLite URI `mode=ro`. The `.lrcat` file's modification timestamp should NOT change after browsing.
result: pass

### 2. Catalog path registration via UI
expected: In the Catalog tab of the visualizer, a settings panel is visible at the top. It shows the currently configured catalog path (or empty if none set). Entering a valid `.lrcat` file path and clicking "Save catalog path" persists the path. Entering an invalid path (non-.lrcat or nonexistent) shows an error message.
result: issue
reported: "i see the catalog, but no images below, and seing a 500 error"
severity: major

### 3. Catalog path persists in config.yaml
expected: After saving a catalog path via the UI, opening `config.yaml` at the repo root shows the `catalog_path` key updated to the saved value. Reloading the page still shows the same path.
result: pass

### 4. Catalog photo pagination
expected: With a populated catalog, the Catalog tab shows photos in pages. Scrolling or navigating pages loads more photos without the app freezing. The total count displayed reflects the actual number of matching photos, not the page size.
result: issue
reported: "the catalog is populated but i can't see any images"
severity: major

### 5. Keyword search filter
expected: Typing a keyword in the search field and triggering the filter shows only photos matching that keyword in their filename, title, description, or keywords. The total count updates to reflect the filtered set.
result: issue
reported: "there is no search field at all"
severity: major

### 6. Rating filter
expected: Selecting a minimum star rating (e.g., 3 stars) from the "Min stars" dropdown filters the catalog to show only photos rated at or above that value. Selecting "any" shows all photos regardless of rating.
result: issue
reported: "there is no rating filter at all"
severity: major

### 7. Date range filter
expected: Setting a date range via the date_from and date_to date pickers shows only photos taken within that range. The total count reflects the filtered set.
result: issue
reported: "no date filter visible — same root cause as tests 5-6, filter UI not rendering"
severity: major

### 8. Color label filter
expected: Typing a color label (e.g., "Red") in the "Color label" field filters to photos with that color label. Case should not matter.
result: issue
reported: "no color label filter visible — same root cause as tests 5-7, filter UI not rendering"
severity: major

### 9. Clear filters
expected: After applying multiple filters, clicking a clear/reset button resets all filters (keyword, rating, date range, color label, posted, month) and shows the full unfiltered catalog again.
result: blocked
blocked_by: other
reason: "Filter UI not rendering — depends on tests 5-8 being fixed first"

### 10. Stable photo identity across sessions
expected: Note a specific photo's ID or key from the catalog view. Close the browser, reopen, navigate back to the same photo. The photo retains the same identity — it links to the same underlying asset, not a different row.
result: blocked
blocked_by: other
reason: "Cannot verify — images not loading (depends on test 2/4 fix)"

### 11. Key migration runs on existing library DB
expected: If you have an existing library.db with old-format keys (containing timestamps like `2024-01-15T14:30:00_photo.jpg`), starting the app triggers a one-time migration. After migration, keys are in `YYYY-MM-DD_filename` format. A `.pre-key-migration.bak` backup file appears next to the database.
result: skipped
reason: "User requested skip — focusing on critical UI issues first"

### 12. Read/write documentation
expected: The file `docs/CATALOG_READ_WRITE.md` exists and lists which modules read vs write the catalog. It mentions SQLite URI `mode=ro` for read paths.
result: skipped
reason: "User requested skip — focusing on critical UI issues first"

## Summary

total: 12
passed: 2
issues: 6
pending: 0
skipped: 2
blocked: 2
skipped: 0
blocked: 0

## Gaps

- truth: "In the Catalog tab, a settings panel is visible. Entering a valid .lrcat path and clicking Save catalog path persists the path. Images load below."
  status: failed
  reason: "User reported: i see the catalog, but no images below, and seing a 500 error"
  severity: major
  test: 2
  root_cause: ""
  artifacts: []
  missing: []
  debug_session: ""
- truth: "With a populated catalog, the Catalog tab shows photos in pages. Total count reflects actual matching photos."
  status: failed
  reason: "User reported: the catalog is populated but i can't see any images"
  severity: major
  test: 4
  root_cause: ""
  artifacts: []
  missing: []
  debug_session: ""
- truth: "Typing a keyword in the search field filters photos matching that keyword. Total count updates to reflect filtered set."
  status: failed
  reason: "User reported: there is no search field at all"
  severity: major
  test: 5
  root_cause: ""
  artifacts: []
  missing: []
  debug_session: ""
- truth: "A Min stars dropdown filters the catalog to photos rated at or above the selected value."
  status: failed
  reason: "User reported: there is no rating filter at all"
  severity: major
  test: 6
  root_cause: ""
  artifacts: []
  missing: []
  debug_session: ""
- truth: "Date range pickers filter photos to those taken within the selected range."
  status: failed
  reason: "User reported: no date filter visible — same root cause as tests 5-6, filter UI not rendering"
  severity: major
  test: 7
  root_cause: ""
  artifacts: []
  missing: []
  debug_session: ""
- truth: "Color label field filters photos by color label, case-insensitive."
  status: failed
  reason: "User reported: no color label filter visible — same root cause as tests 5-7, filter UI not rendering"
  severity: major
  test: 8
  root_cause: ""
  artifacts: []
  missing: []
  debug_session: ""
