---
phase: 11
status: fixed
files_reviewed: 8
findings:
  critical: 0
  warning: 4
  info: 4
  total: 8
fixed:
  warning: 4
  info: 2
created: 2026-05-04
fixed_at: 2026-05-04
---

## Summary

No critical security flaws (SQL uses bound parameters in the reviewed consolidation paths; React text nodes avoid XSS). Several **warning**-level reliability and accessibility gaps and minor quality notes.

### CR-01 (WARNING): Catalog cache queries lack HTTP validation and will hard-fail the tab on errors

File: apps/visualizer/frontend/src/components/processing/CatalogCacheTab.tsx:67

`fetchCacheStats` never checks `response.ok`, parses JSON unconditionally (HTML error bodies or empty responses throw), and omits structured handling for non-JSON failures. Any thrown error propagates through `query()` → `useQuery`, which rethrows non-Promise errors during render and typically **crashes the subtree** unless an error boundary catches it. The same pattern applies to the other `useQuery` calls on this page (`catalog.similarity.groups`, `catalog.cache.pipeline-status`).

Suggested fix: After `fetch`, guard with `if (!response.ok) throw new Error(...)`. Optionally validate/shape the payload before returning. Wrap the tab (or individual queries) in an error boundary or switch to a hook that stores `{ data, error }` instead of throwing on rejection.

### CR-02 (WARNING): Instagram “undescribed only” describe path disagrees with consolidated date-window SQL

File: apps/visualizer/backend/jobs/handlers.py:1804

File: lightroom_tagger/core/database.py:2956

When `force` is false and `year` is unset, `_handle_batch_describe_inner` selects Instagram rows via `get_undescribed_instagram_images`, which filters months using **`m.created_at >= date('now', ?)` only**. The consolidated `_select_instagram_keys` path (used when `force` or `year` is set) applies **`COALESCE` from `created_at` with a `date_folder` synthetic fallback** so rows with missing `created_at` still fall into the window. Users can therefore see **different cohorts** for the same “last N months” depending on whether `force`/`year` toggles the code path—silent under-selection of work for dumps with null `created_at`.

Suggested fix: Align `get_undescribed_instagram_images` with the same `date_expr` used in `_select_instagram_keys`, or route the non-force Instagram branch through `_select_instagram_keys(..., undescribed_only=True)` for parity.

### CR-03 (WARNING): Confirm modal shell is missing expected dialog semantics and keyboard behavior

File: apps/visualizer/frontend/src/components/ui/ConfirmUndoAction.tsx:34

`ConfirmModalFrame` behaves visually like a modal but does not expose `role="dialog"`, `aria-modal="true"`, an `aria-labelledby` tie to the title, Escape-to-dismiss, or focus trapping/restoration. Backdrop click closes the dialog, but keyboard users and screen-reader users get a weaker, less predictable experience than a proper modal pattern.

Suggested fix: Use the project’s dialog primitive if one exists, or add `role="dialog"`, label/description wiring, `onKeyDown` for Escape (calling `onCancel`), and focus trap (e.g. `@radix-ui/react-dialog` / `focus-trap-react`) with return focus to the opener.

### CR-04 (WARNING): Search page swallows provider/model bootstrap failures

File: apps/visualizer/frontend/src/pages/SearchPage.tsx:119

`ProvidersAPI.listDescriptionModels()` errors are caught with `.catch(() => {})`, so the UI can reach `descriptionModelsLoadFinished` with **empty models and no user-visible error**, leaving “No tool-capable models configured” or stuck defaults without explaining a network or server failure.

Suggested fix: Capture the error in state, show `role="alert"` copy (and optional retry), or surface the same pattern used elsewhere for API load failures.

### CR-05 (INFO): Redundant conditional branches in consolidated catalog SQL builder

File: apps/visualizer/backend/jobs/handlers.py:296

The `if undescribed_only:` / `else:` arms both append `" AND " + " AND ".join(conditions)` identically. Works correctly but duplicates logic and invites future drift if only one branch is edited.

Suggested fix: Collapse to a single `if conditions:` block after the SQL skeleton is chosen.

### CR-06 (INFO): “Skip undescribed” label bypasses centralized strings

File: apps/visualizer/frontend/src/components/matching/AdvancedOptions.tsx:144

The checkbox label is hard-coded English while adjacent copy uses `constants/strings.ts`. This hurts consistency and localization.

Suggested fix: Add a constant next to the other advanced-option strings and import it here.

### CR-07 (INFO): Chat thread uses message index as React key

File: apps/visualizer/frontend/src/pages/SearchPage.tsx:291

`messages.map((m, i) => (<div key={i} ...`)) can cause incorrect reconciliation if messages are ever inserted/reordered (not an issue today while only appending).

Suggested fix: Use stable ids per message (timestamp, UUID, or monotonic counter in state) when the conversation model evolves.

### CR-08 (INFO): Reset control omits explicit `type="button"`

File: apps/visualizer/frontend/src/components/matching/AdvancedOptions.tsx:169

The reset control defaults to `type="submit"` in HTML. It is not inside a `<form>` in current `MatchingTab` usage, but the component is generic and could be embedded under a form later, accidentally submitting it.

Suggested fix: Add `type="button"` on the reset button.
