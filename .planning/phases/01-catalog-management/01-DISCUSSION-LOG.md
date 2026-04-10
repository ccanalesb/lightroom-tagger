# Phase 1: Catalog Management - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-10
**Phase:** 01-catalog-management
**Areas discussed:** Catalog registration, Search/filter depth, Photo identity strategy, Read-only enforcement

---

## Catalog Registration (CAT-01)

| Option | Description | Selected |
|--------|-------------|----------|
| Config + UI settings panel | Keep config-driven path, add UI to read/write same config | ✓ |
| In-app registration flow | New API/UI to register .lrcat files as a separate concept | |
| Config-only (no UI) | Keep current env var / config.yaml approach | |

**User's choice:** Config stays as source of truth, but surface it in a UI settings panel so it's modifiable without touching config files. CLI must not be compromised.
**Notes:** User explicitly stated "the config is ok, but we should also be able to modify it from the UI without compromising the CLI too."

---

## Search/Filter Depth (CAT-03)

| Option | Description | Selected |
|--------|-------------|----------|
| All search dimensions | keyword, rating, date range, color label, posted status | ✓ |
| Keyword + existing | Add keyword text search to existing posted + month filters | |
| Claude decides | Let Claude pick what makes sense | |

**User's choice:** All of them — expose all existing core/database.py search functions in the web UI.
**Notes:** None.

---

## Photo Identity Strategy (CAT-04)

| Option | Description | Selected |
|--------|-------------|----------|
| Lightroom `id_local` as primary | Use LR's native integer ID, keep date+filename as secondary | ✓ |
| Keep date+filename key | Current approach with collision risk | |
| Composite key (folder+date+filename) | Reduce collisions without changing to LR ID | |

**User's choice:** Use Lightroom's `id_local` as recommended.
**Notes:** User confirmed with "that works."

---

## Read-Only Enforcement (CAT-05)

| Option | Description | Selected |
|--------|-------------|----------|
| Add `?mode=ro` to reader connection | One-line change in `connect_catalog()` for guaranteed read-only | ✓ |
| Keep current approach | Rely on SELECT-only queries without enforcement | |

**User's choice:** "Please do" — implement the read-only mode change.
**Notes:** None.

---

## Claude's Discretion

- Filter UI layout and control placement
- Whether to refactor list_catalog_images to SQL-level filtering in this phase

## Deferred Ideas

None.
