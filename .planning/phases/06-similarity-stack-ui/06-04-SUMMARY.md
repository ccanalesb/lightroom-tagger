---
phase: 06-similarity-stack-ui
plan: 4
subsystem: ui
tags: [react, clip, stacks, SIM-02, STACK-03, catalog, identity]

requires:
  - plan: 06-03-PLAN
    provides: GET /api/images/catalog/{key}/similar, GET /api/images/stacks/{id}/members, catalog DTO stack fields
provides:
  - ImagesAPI.getCatalogSimilar + getStackMembers with shared CatalogListQueryParams
  - Stack count badge (Badge variant default) + Show/Hide stack + member strip in Catalog and Best Photos
  - Image detail "More like this" + Visually similar grid, empty/no-embed/error/loading copy from strings
affects:
  - Phase 7 SearchPage reuse of getCatalogSimilar (types only, no SearchPage edits)

tech-stack:
  added: []
  patterns:
    - "Shared appendCatalogListSearchParams for listCatalog and getCatalogSimilar"
    - "BestPhotoSelection union for stack strip opening catalog members in ImageDetailModal"
    - "Nested ImageDetailModal for similar-result tiles"

key-files:
  created: []
  modified:
    - apps/visualizer/frontend/src/services/api.ts
    - apps/visualizer/frontend/src/constants/strings.ts
    - apps/visualizer/frontend/src/components/images/CatalogTab.tsx
    - apps/visualizer/frontend/src/components/identity/BestPhotosGrid.tsx
    - apps/visualizer/frontend/src/components/image-view/ImageDetailModal.tsx
    - apps/visualizer/frontend/src/components/images/__tests__/CatalogTab.test.tsx
    - apps/visualizer/frontend/src/components/identity/BestPhotosGrid.test.tsx
    - apps/visualizer/frontend/src/components/image-view/__tests__/ImageDetailModal.test.tsx

key-decisions:
  - "Stack count uses Badge variant default in both Catalog and Best Photos (UI-SPEC)"
  - "Similar tiles in the detail modal open a second ImageDetailModal (no SearchPage, no new routes)"

patterns-established:
  - "CatalogListQueryParams exported for Phase 7 search + similar handoff"

requirements-completed: [SIM-02, STACK-03]

duration: 45min
completed: 2026-04-25
---

# Phase 6 Plan 4: Similarity & stack UI (SIM-02 / STACK-03) summary

**CLIP similar and stack members are wired through `ImagesAPI`, with stack badges and expandable member strips on Catalog and Best Photos, and a “More like this” flow in the catalog image detail modal including Visually similar results and documented empty/error states.**

## Performance

- **Duration:** ~45 min
- **Tasks:** 3
- **Files modified:** 8 (code + tests + this summary)

## Accomplishments

- Extended `CatalogImage` / `IdentityBestPhotoItem` for stack metadata and similar-row `similarity`; added `getCatalogSimilar`, `getStackMembers`, and `CatalogListQueryParams` with shared query serialization for `listCatalog` and similar requests.
- Centralized all user-facing copy in `strings.ts` (including `formatStackCountBadge`, loading/error/empty for similar and members).
- Catalog and Best Photos render `{n} in stack` and Show/Hide stack with `aria-expanded` / `aria-controls`, a `role="region"` member strip, and lazy `getStackMembers` fetch with alert on failure.
- `ImageDetailModal` (catalog) adds “More like this” → `getCatalogSimilar` with nested modal for result tiles, 404 no-embed handling via error substring, and empty grid copy per UI-SPEC.

## Task commits

1. **Task 1: API + strings** — `1d4e04b` (feat)
2. **Task 2: Catalog + Best Photos stack UI** — `8559451` (feat)
3. **Task 3: Image detail similar** — `ed02d24` (feat)
4. **Docs: this SUMMARY** — `docs(06-04): complete similarity-stack UI plan 4 summary` (tip of branch after the three feature commits)

## Deviations from plan

None — plan scope kept to listed files; no `SearchPage` changes.

## Verifications run

- `npx tsc --noEmit` (pass)
- `npm run test -- --run BestPhotosGrid CatalogTab ImageDetailModal` (pass)
- `npm run lint` reports existing errors in other files; no new errors required changes in this plan’s files for the targeted goal.

## Self-Check: PASSED

- `06-04-SUMMARY.md` present; implementation matches 06-03 API paths (`/images/catalog/.../similar`, `/images/stacks/.../members`).

---
*Phase: 06-similarity-stack-ui · Plan: 4 · 2026-04-25*
