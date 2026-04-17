---
id: SEED-003
status: dormant
planted: 2026-04-15
planted_during: v2.0 (milestone complete)
trigger_when: next UX improvements milestone or Identity page redesign
scope: Medium
---

# SEED-003: Rethink Identity page to clarify what photos are, what's posted, and what to post next

## Why This Matters

The current Identity page stacks three panels — Best Photos, Style Fingerprint, and Post Next Suggestions — but the relationship between them is unclear to the user. Key confusion points:

1. **Best Photos grid has no posted indicator.** You can't tell at a glance which of your "best" photos are already on Instagram and which aren't. The `instagram_posted` field exists in the data but isn't surfaced visually.
2. **"Best Photos" vs "Post Next" overlap is confusing.** Both show high-scoring images with thumbnails and scores, but the distinction — "best overall" vs "best to post now" — isn't visually obvious. A user has to read the help text to understand what each section means.
3. **No clear narrative flow.** The page answers three questions — "What's my style?", "What's my best work?", "What should I post next?" — but presents them as disconnected cards rather than a guided story.

This is a UX rethink, not just cosmetic polish. The page needs clearer visual hierarchy, posted-status indicators, and possibly a reorganized layout that guides the user from understanding their style to taking action.

## When to Surface

**Trigger:** Next UX improvements milestone or Identity page redesign

This seed should be presented during `/gsd-new-milestone` when the milestone
scope matches any of these conditions:
- UX polish or information architecture improvements to the visualizer
- Identity page redesign or rethink
- Improving clarity of posted vs unposted status across the app
- Making the app more actionable (guiding users toward posting decisions)

## Scope Estimate

**Medium** — A phase or two. The work likely involves:
1. Adding posted/unposted badges or visual treatment to BestPhotosGrid cards
2. Rethinking the page layout — possibly reordering sections, adding section intros that connect the narrative, or collapsing Best Photos into a summary with expandable detail
3. Differentiating "Post Next" more strongly from "Best Photos" (different card style, stronger CTA, or merging them into a single section with tabs/filters)
4. Potentially adding a quick-summary header that says "X of your Y best photos are already posted"

## Breadcrumbs

Related code and decisions found in the current codebase:

- `apps/visualizer/frontend/src/pages/IdentityPage.tsx` — page layout, just stacks three components vertically (line 8-17)
- `apps/visualizer/frontend/src/components/identity/BestPhotosGrid.tsx` — shows aggregate score and perspectives but no posted indicator; `instagram_posted` is in the data model (line 50) but not rendered in the card UI
- `apps/visualizer/frontend/src/components/identity/PostNextSuggestionsPanel.tsx` — shows reason codes and reasons for each suggestion, but visually similar to BestPhotosGrid
- `apps/visualizer/frontend/src/components/identity/StyleFingerprintPanel.tsx` — radar chart + distribution + tokens; self-contained but disconnected from the other panels
- `apps/visualizer/frontend/src/services/api.ts` — `IdentityAPI.getBestPhotos()` and `IdentityAPI.getSuggestions()` return similar structures
- `.planning/milestones/v2.0-phases/08-identity-suggestions/` — original phase that built the Identity page (context, plans, verification)

## Notes

The quickest win is adding a posted badge to BestPhotosGrid cards — the data is already there (`instagram_posted` in `bestPhotoToCatalogStub`), it just needs a visual indicator. The bigger rethink is restructuring the page so the three sections tell a story: "Here's your style fingerprint → Here's your best work (posted and not) → Here's what to post next." Consider whether Best Photos and Post Next should be merged into a single filterable view rather than two separate panels.
