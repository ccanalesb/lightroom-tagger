# Phase 10: Batch scoring fix and integration bug fixes - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-14
**Phase:** 10-batch-scoring-fix-and-integration-bugs
**Areas discussed:** Unscored image selection, Suggestions pagination, Identity key disambiguation

---

## Unscored image selection

| Option | Description | Selected |
|--------|-------------|----------|
| New dedicated DB helper `get_unscored_catalog_images` | Mirrors `get_undescribed_catalog_images` but LEFT JOINs `image_scores` with `is_current=1`. Returns images missing a current score for any of the requested perspective slugs. | |
| Per-perspective check inline | Keep image selection broad and filter at scoring time by checking if quadruple already has `is_current=1`. Simpler query, more work units in memory. | |
| You decide | Claude picks the best approach during planning. | ✓ |

**User's choice:** Claude's discretion
**Notes:** User deferred the implementation approach decision to planning. The key constraint is that the fix must select images without *scores*, not without *descriptions*.

---

## Suggestions pagination

| Option | Description | Selected |
|--------|-------------|----------|
| Wire offset through + add total count | Pass `offset` into `suggest_what_to_post_next`, slice candidates, return `total` in response. Enables proper pagination in frontend. | ✓ |
| Wire offset only | Just pass offset through and slice. No `total` field — frontend uses "load more" until empty. | |
| You decide | Claude picks. | |

**User's choice:** Wire offset through + add total count
**Notes:** None.

---

## Identity key disambiguation

| Option | Description | Selected |
|--------|-------------|----------|
| Compound `(image_key, image_type)` throughout | Change all grouping, sorting, and metadata lookups to use the pair. Most thorough. | |
| Filter to catalog-only in `_SCORES_BASE_SQL` | Add `AND s.image_type = 'catalog'`. Identity features are catalog-facing per D-40. One-line fix. | ✓ |
| You decide | Claude picks. | |

**User's choice:** Filter to catalog-only
**Notes:** User asked why this bug matters. After explanation that the key collision is theoretical (catalog keys are `YYYY-MM-DD_filename`, Instagram keys are numeric media IDs — they won't collide in practice), user chose the minimal one-line filter as sufficient. Originally considered dropping from Phase 10 entirely but kept the minimal fix.

---

## Claude's Discretion

- Unscored image selection approach (new DB helper vs inline SQL vs per-perspective filtering)

## Deferred Ideas

- Full compound `(image_key, image_type)` keying in identity_service — only needed if Instagram identity features are added later
