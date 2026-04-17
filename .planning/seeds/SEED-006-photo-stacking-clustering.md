---
id: SEED-006
status: dormant
planted: 2026-04-15
planted_during: v2.0 (milestone complete)
trigger_when: when we focus on matching performance or optimization
scope: Large
---

# SEED-006: Cluster visually similar photos into stacks to reduce noise and speed up matching

## Why This Matters

Three problems converge around the lack of photo stacking:

1. **Best Photos is noisy.** The top-scored images often include many near-duplicates — burst shots, slight reframes, or similar compositions from the same session. The Best Photos grid shows them all individually, making it hard to see the actual variety of your best work.

2. **Matching is O(N×M) expensive.** Every Instagram image is compared against every catalog candidate using pHash + description similarity + vision API calls. If 20 catalog images are near-duplicates of each other, that's 20 redundant comparisons per Instagram image. Matching a stack representative instead of every member would cut vision API costs dramatically.

3. **Scoring redundancy.** Similar images get scored independently across all perspectives, burning API tokens on photos that would get nearly identical scores. Score the stack representative, inherit scores to members.

Photo stacking (clustering near-duplicates into groups with a representative "pick") is the foundational building block that solves all three. Lightroom itself has a stacking concept, so the mental model is already familiar.

## When to Surface

**Trigger:** When we focus on matching performance or optimization

This seed should be presented during `/gsd-new-milestone` when the milestone
scope matches any of these conditions:
- Matching performance, speed, or cost optimization
- Reducing API call volume for scoring or matching
- Identity page or Best Photos redesign (overlaps with SEED-003)
- Catalog organization or curation features
- Near-duplicate detection or deduplication

## Scope Estimate

**Large** — A full milestone. This touches every layer of the system:

1. **Clustering pipeline** — Build a job that clusters catalog images by pHash similarity (hamming distance ≤ threshold). Union-find or agglomerative clustering over the existing pHash values. Store stack membership in a new `image_stacks` table.
2. **Representative selection** — Pick the "best" image per stack (highest rating, highest aggregate score, or user-chosen). The representative is what shows up in Best Photos, matching, and scoring.
3. **Stack-aware matching** — Compare Instagram images against stack representatives only, then associate the match with the full stack. Reduces comparison count by the average stack size.
4. **Stack-aware scoring** — Score the representative, optionally propagate scores to stack members. Saves API tokens proportional to cluster size.
5. **Stack-aware identity** — Best Photos shows stacks collapsed (representative + count badge), expandable to see members. Post Next suggestions consider the whole stack.
6. **UI for stack management** — Browse stacks in the catalog, reassign representative, split/merge stacks, manual override. Potentially a dedicated "Stacks" view or an overlay on the existing catalog grid.
7. **Incremental updates** — When new images are imported, assign them to existing stacks or create new ones without re-clustering everything.

## Breadcrumbs

Related code and decisions found in the current codebase:

### pHash infrastructure (already exists)
- `lightroom_tagger/core/phash.py` — `hamming_distance()`, `compare_hashes()` with configurable threshold (default 5), `find_matches()` for brute-force pHash comparison
- `lightroom_tagger/core/database.py` — `images` table stores `phash` and `image_hash` per catalog image (line 215-217)
- `lightroom_tagger/core/database.py` — `instagram_images` table also stores `phash` (line 255)
- `lightroom_tagger/core/database.py` — `vision_cache` table stores `phash` for cached images (line 287)
- `lightroom_tagger/core/hasher.py` — hash generation for images

### Matching (would benefit from stacking)
- `lightroom_tagger/core/matcher.py` — `score_candidates()` and `match_instagram_image()` compare every candidate; stack representatives would reduce the candidate set
- `lightroom_tagger/core/matcher.py` — already uses pHash + description + vision weighted scoring (line 137); stacking uses only the pHash component

### Scoring (would benefit from stacking)
- `lightroom_tagger/core/scoring_service.py` — scores each image independently per perspective
- `lightroom_tagger/core/database.py` — `image_scores` table (line 329); stack propagation would write inherited scores for members

### Identity (would benefit from stacking)
- `apps/visualizer/frontend/src/components/identity/BestPhotosGrid.tsx` — shows individual photos; would show collapsed stacks instead
- `lightroom_tagger/core/identity_service.py` — aggregates scores for best photos; would aggregate at stack level

### Related seeds
- SEED-003 (rethink Identity page clarity) — stacking directly improves the Best Photos noise problem
- SEED-005 (natural language search) — search results would show stack representatives

## Notes

The clustering itself is straightforward — pHash hamming distance with union-find gives O(N²) worst case but is fast for typical catalog sizes (thousands, not millions). A threshold of 3-5 hamming distance catches burst shots and minor crops while keeping genuinely different compositions separate.

The key design decision is whether stacks are auto-generated or user-curated. Recommendation: auto-generate with a conservative threshold (hamming ≤ 3), let users split/merge/override. This mirrors Lightroom's own auto-stacking feature.

A phased rollout within the milestone:
- **Phase 1:** Clustering job + `image_stacks` table + basic stack browsing in catalog
- **Phase 2:** Stack-aware matching (compare against representatives only)
- **Phase 3:** Stack-aware scoring (score representative, propagate to members)
- **Phase 4:** Stack-aware identity (collapsed Best Photos, stack-aware Post Next)
- **Phase 5:** Stack management UI (split, merge, change representative)
