# Phase 6: Images Page Visual Consistency - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-25
**Phase:** 06-images-page-visual-consistency
**Mode:** auto (`--auto`)
**Areas discussed:** Badge surface consolidation, Inline metadata chips, Match group tile composition, PerspectiveBadge rollout

---

## Badge Surface Consolidation

| Option | Description | Selected |
|--------|-------------|----------|
| A. Single `ui/badges` home | Keep one canonical badge folder and one barrel export path | ✓ |
| B. Keep split folders | Continue mixed `ui/Badge` + `ui/badges` imports | |
| C. New singular folder migration | Introduce a brand-new badge path and migrate all imports | |

**User's choice:** `[auto]` selected recommended default: A
**Notes:** Existing code already matches option A (`ui/badges/index.ts` barrel with shared exports), so auto mode locked the current canonical pattern.

---

## Inline Metadata Chips (UI-02)

| Option | Description | Selected |
|--------|-------------|----------|
| A. Shared `ImageMetadataBadges` row | Keep chips in `ImageTile` body under date, reused by all tile surfaces | ✓ |
| B. Per-tab custom chip markup | Catalog/Instagram/Matches each own chip rendering | |
| C. Prose metadata instead of chips | Remove chip row and display textual metadata lines | |

**User's choice:** `[auto]` selected recommended default: A
**Notes:** Auto mode retained dedupe behavior (`hidePostedMetadataBadge`) when overlay badges already carry Posted status.

---

## Match Group Tile Composition (UI-03)

| Option | Description | Selected |
|--------|-------------|----------|
| A. Shared tile shell + footer metadata | Keep `ImageTile` card shell; use footer for count/validated/filename semantics | ✓ |
| B. Dedicated custom wrapper card | New shell and layout specifically for match groups | |
| C. Overlay-only semantics | Push all metadata into thumbnail overlays | |

**User's choice:** `[auto]` selected recommended default: A
**Notes:** Current implementation already follows this shape via `MatchGroupTile` + `ImageTile.footer`, so auto mode locked the existing contract.

---

## PerspectiveBadge Rollout

| Option | Description | Selected |
|--------|-------------|----------|
| A. Dominant perspective only on approved surfaces | Top-1 perspective (`displayName + score`) in `BestPhotosGrid` and `TopPhotosStrip` | ✓ |
| B. All perspectives per tile | Render full perspective breakdown on every tile | |
| C. No perspective badge on tiles | Keep perspective info in detail-only surfaces | |

**User's choice:** `[auto]` selected recommended default: A
**Notes:** Auto mode followed `06-UI-SPEC.md` lock: dominant-only badge in tile footer with slug-based color mapping.

---

## Claude's Discretion

- Fine-tuned fallback styling for unknown perspective slugs
- Preserve score formatting conventions for compact readability
- Minor spacing adjustments around footer badge row when needed

## Deferred Ideas

- Render all four perspectives per tile (out of scope for this phase)
- Extend PerspectiveBadge to additional screens/surfaces
- Benchmark embedding recall todo remains deferred to matching/embedding phases
