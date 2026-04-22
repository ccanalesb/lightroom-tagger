# Phase 6: Images Page Visual Consistency - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-21
**Phase:** 06-images-page-visual-consistency
**Areas discussed:** Badge API consolidation, Inline-in-description pattern, Match card shape, PerspectiveBadge

---

## Badge API Consolidation

| Option | Description | Selected |
|--------|-------------|----------|
| A. Structural unification | All badges under one folder, specialized badges wrap `<Badge>` | ✓ |
| B. Visual token standardization | Keep separate folders, align spacing/border/rounding | Partial ✓ |
| C. Barrel export only | Single index.ts re-exporting from wherever they live | ✓ (combined with A) |

**User's choice:** Structural unification + harmonized visual tokens (with intentional size differences preserved) + single barrel export as public API
**Notes:** "I think I like the barrel export but with structural unification and a little bit of B" — confirmed that "a little bit of B" means conservative harmonization, not forcing everything to identical sizing. Inline JSDoc chosen for documentation over separate markdown file.

---

## Inline-in-description Pattern (UI-02)

| Option | Description | Selected |
|--------|-------------|----------|
| A. Chip row under each item | Badge row beneath image/title in tile view, like ImageMetadataBadges | ✓ |
| B. Badges woven into prose | Badges inline mid-sentence within description text | |

**User's choice:** Option A — chip row beneath image/title
**Notes:** Applies to all three Images page tabs (Instagram, Catalog, Matches). Same chip set as Best Photos (Posted, rating ★, Pick, AI) — "in all, instagram, catalog and matches, same as best photos."

---

## Match Card Shape (UI-03)

| Option | Description | Selected |
|--------|-------------|----------|
| A. Two-panel card | Instagram thumbnail + Catalog thumbnail side by side | |
| B. Single image + richer metadata | Instagram image + metadata row below (filename, N candidates, score) | ✓ |
| C. Card wrapper style only | Keep single-image ImageTile, just match card shell styling | |

**User's choice:** Option B — single Instagram image + metadata row below
**Notes:** User requested ASCII diagrams to decide. Unvalidated groups show "N candidates" only in metadata row — no per-candidate drilling. Validated groups show catalog filename.

---

## PerspectiveBadge

| Option | Description | Selected |
|--------|-------------|----------|
| A. Name only | `[Street]` — label tag | |
| B. Name + score with color | `[Street 8.2]` in perspective color | ✓ |
| C. Score only with color | `[8.2]` color-coded, relies on context | |

**User's choice:** Option B — name + score + per-perspective color
**Notes:** User noted the visual precedent already exists inside the AI description section of the image modal. Initially deferred showing PerspectiveBadge on BestPhotosGrid and TopPhotosStrip to next phase, then pulled it into Phase 6 scope. Top 1 perspective by score shown per tile on both surfaces.

---

## Claude's Discretion

- Unified badge folder name
- Exact color mapping per perspective
- Whether PerspectiveBadge appends to ImageMetadataBadges row or renders below it
- ScorePill migration decision

## Deferred Ideas

- All 4 perspective scores per tile (top-1 only in Phase 6)
- PerspectiveBadge on other surfaces beyond BestPhotosGrid and TopPhotosStrip
