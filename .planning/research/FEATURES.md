# Features Research — v3.0 Intelligent Discovery

Industry patterns from photo management, DAM, and consumer libraries (e.g. Lightroom, Apple Photos, Google Photos, Mylio, embedding-first products). Framed for a **catalog + Instagram analysis** app with keyword filters, AI descriptions, pHash, and per-image scores.

---

## Natural Language Search

### Table Stakes

- **Conversational query in one place** — A primary search field that accepts free text; users expect it to *feel* like search, not a SQL prompt.
- **Fast perceived response** — Typing should show suggestions or a clear “searching” state; empty or wrong results need an explicit *zero state* (not a silent grid).
- **Reversible refinement** — After a natural-language (NL) search, users expect to narrow with existing filters (date, rating, “posted to Instagram or not”) without retyping the whole query. NL often maps to a **filter chip row** or **parsed constraints panel** they can edit.
- **Result explainability in principle** — At minimum: which constraints matched (date range, “not posted,” keyword “street”). In AI-assisted tools, a short *why* or *matched fields* is increasingly expected when marketing promises “intelligent” search.
- **Language tolerance** — Pluralization, light typos, and informal phrasing (“best pics from xmas”) without requiring exact field names from the data model.

### Differentiators

- **Compositional queries** that blend **catalog metadata**, **AI description fields**, and **app-specific state** (e.g. Instagram posted) in one utterance—most generic photo apps cannot combine “I haven’t posted this” with semantic “moody cityscapes” unless that state is first-class in the system.
- **Tie-ins to your existing scores and rationales** — Surfacing e.g. “high composite score + matches ‘street’ in subjects” as part of the *why* story, not as a second screen.
- **Transparent hybrid ranking** — Users trust results more when they see *structured* matches (date, not posted) *plus* semantic matches (description/mood) rather than a black-box relevance score.
- **Query → editable representation** — Turning “best street photo from December I haven’t posted” into visible chips: `December 20xx`, `not posted`, `rank/sort: best (score)`, `semantic: street` is far above table stakes for a small team if executed clearly.

### Anti-features / Avoid

- **Slow “think for 5 seconds” on every keystroke** — Feels broken compared to local filter UIs; debounce, progressive results, or separate “Run smart search” step for heavy models.
- **Narrative over substance** — Long LLM preambles or chatty assistant copy instead of *results + constraints*.
- **Inconsistent with the rest of the app** — NL search that returns a list that *ignores* the global FilterBar or uses different field semantics than manual filters; erodes trust.
- **Mystery ranking** with no recourse—users must be able to **sort** (e.g. by date, by score) or **restrict** when “best” is ambiguous.
- **Hallucinated filters** — Inventing a location or person that doesn’t exist in the catalog; strict grounding on indexed fields is safer than free-form “facts” about assets.

### UX Patterns

- **Placement** — **Global, persistent** search in the primary catalog toolbar (not buried in a submenu). Many apps also offer **in-context** search (selection-scoped) as a second entry; for v3.0, one global bar plus compatibility with your existing `useFilters` model is a strong default.
- **Result display** — **Dense grid of thumbnails** with *score* and 1–2 *signal lines* (e.g. capture date, posted badge). A **right rail or bottom sheet** for the selected item preserves scan speed.
- **Why-matched** — **Per-row or on-hover** “matched because…” using **short bullets** tied to: (1) *structured* constraints, (2) *semantic* hits (which description field or embedding bucket), (3) *score* if ranking by “best.” **Progressive disclosure**: one-line in grid; expand for full rationale.
- **Clarification** — When the query is ambiguous, **chips to confirm** (“December 2024 or any December?”) before replacing the whole result set; cheaper than a chat loop in many photo workflows.

### Complexity

- **High** — Parser or LLM-to-structured plan, **grounding** on real indexed fields, unified ranking with existing sorts and scores.
- Depends on **correct metadata** (dates, time zones) and a **single** “posted to Instagram” source of truth.
- **Ongoing** operational cost if every query uses a **hosted LLM**; mitigations: caching, heuristics for simple queries, or local small models for intent only.

---

## Photo Stacking

### Table Stakes

- **Group visually / temporally** — Bursts: **close capture timestamps**; near-duplicates: **perceptual hash or embedding similarity** with a tunable threshold.
- **One representative per stack** in browse views — The grid usually shows a **stack badge** and count; the **top/hero** image is the visible thumbnail.
- **Expand to see members** — Click or keyboard action to open the stack: strip, lightbox, or filmstrip of members.
- **User override** — Ability to **pick a different pick**, **remove** an image from a stack, and **unstack** or **merge** stacks; auto-grouping is never perfect.
- **Non-destructive** — Stacking is **metadata**; underlying files stay put (unless the product is explicitly about file merging).

### Differentiators

- **Cross-signal fusion** — Combining **time proximity** and **pHash/embedding** (your ≤2s + hamming 3–5) reduces false groups vs. time-only or hash-only in scenes with slow shutters or identical wallpaper shots.
- **Score propagation** — Propagating **your existing per-perspective scores or composite** to the stack, with a clear rule: *max, mean, or pick-only*; surfacing *propagation policy* in UI once avoids silent confusion.
- **Use-case link to Instagram** — *One post candidate per stack* or “this burst already has a posted winner” is a product-specific story that generic DAMs rarely treat as a first-class workflow.
- **Deferred compute** — Showing stacks *after* background clustering can feel magical if the app doesn’t block import.

### Anti-features / Avoid

- **Unmergeable auto-decisions** — Forcing a permanent stack the user can’t break; causes anxiety with client deliverables.
- **Mystery membership** — No visibility into *why* two images are grouped (time delta? hash distance?); support tickets follow.
- **Propagate scores without transparency** — Users assume the **hero** is what was scored; if another member inherited a high score, the UI should show that to avoid “wrong” ranking in exports.
- **Over-grouping in events** — Very tight time windows that merge unrelated shots in busy scenes; threshold UX or **split** tools are required.

### UX Patterns

- **Collapse/expand** — **Badge with count** on the hero thumb; **chevron** or **double-tap** to expand in-grid or in a **modal strip**. **Keyboard**: arrows move within stack when expanded.
- **Representative selection** — **Context menu: “Set as cover”**; sometimes **highest star rating** or **sharpest (EXIF/vision)** as default. Show a **dotted border** or **pin** on the current pick.
- **Split / merge** — **Drag out** to split (member becomes solo); **multi-select + Stack** to merge; **“Suggest stacks”** as a **review queue** (Google Photos style) is heavy but can be a later phase; minimal version is **manual merge + unstack**.
- **Visual density** — Option to **hide stack badges** for a clean client grid vs. **always show** for culling workflows—many tools put this in **View** settings.

### Complexity

- **Medium–high** — Time-windowed pairing (often block-sorted by capture time), pHash/embedding batch cost at scale, storage for hashes/embeddings.
- **Score propagation** needs explicit rules and UI when the **hero** changes.
- **Sensitive** to **bad EXIF** (missing/wrong time zones); stacks may need user correction tools.

---

## Visual Attribute Tags

### Table Stakes

- **Display as structured, filterable data** — Dominant color(s), abstract mood, boolean scene traits (e.g. repetition) must appear as **concrete values**, not only prose in a paragraph.
- **Faceted filter UI** — Users expect to **click a value** to filter, **multi-select** within a dimension (e.g. two mood tags), and **see counts** (optional but high value).
- **Stable vocabulary** (or managed synonyms) — Uncontrolled *mood* tags that vary every run (“forlorn” vs. “lonely”) destroy browse UX; either **canonical tags** with alias mapping, or user-visible **buckets** (e.g. *melancholy / calm / energetic*).
- **Alignment with existing pipeline** — Extracted at **describe time** (or a dedicated job) with **re-run** or **re-index** when the model/prompt set changes.

### Differentiators

- **Tight schema for your app** — E.g. `dominant_colors`, `mood_tags[]`, `has_repetition` as **queryable fields** *plus* tie-in to your **per-perspective scores and Instagram state** in one filter model—stronger than “colored label” in generic libraries.
- **Cross-field ranking** — Using attributes **with** text descriptions and scores in a single **FilterBar** (your `useFilters` pattern) is a differentiator for power users.
- **Explainable extraction** — Optional short *evidence* (“repetition: railings, windows”) is rare and builds trust; keep it *optional* in the UI to avoid clutter.

### Anti-features / Avoid

- **Tag sprawl** — Dozens of near-duplicate tags that fragment results; need **merging, hierarchies, or “smart groups.”**
- **Unfixable wrong tags** — No **manual override** or **hide tag**; users remember every wrong “mood” forever.
- **Blocking describe** — If attribute extraction is slow, **do not** block the main description; **async** with clear status per image.

### UX Patterns

- **Color** — **Swatches or chips** (e.g. red, blue) in the filter bar; **multi-select** for OR within colors is common. Some apps use a **2D color wheel** or *temperature* strip—richer, higher build cost. **Thumbnails** may show a **thin color bar** for quick scan.
- **Mood / abstract** — **Tag pills** in a **facet list**; OR vs AND semantics must be **obvious** (default is often **OR** within a facet, **AND** across facets). **Search inside facets** for long lists.
- **Booleans** — **Tri-state** is ideal for “has repetition”: *yes / no / any*; avoid binary-only if unknown is possible.
- **Provenance** — In detail view, a **small “AI” or “analyzed”** label with *last updated* supports trust without novel-length copy.

### Complexity

- **Medium** — Schema + migration, **backfill** for existing images, index strategy (JSON vs. dedicated columns), facet UX.
- **Ongoing** — Prompt/model tuning, **vocabulary** stability, optional user overrides.
- **Coupled** to the describe job pipeline: failures or retries should not block **core** description text.

---

## Visual Similarity Search

### Table Stakes

- **“More like this” from a clear entry point** — Context menu, toolbar button, or **kebab** on a single image: *Find similar* / *Visual matches*.
- **Result list with previews** — Grid of **thumbnails** with **similarity score or rank**; optional *distance* as percent or 1–100 for power users.
- **Exclude the query** — The source image is usually **omitted** or **pinned** at the top, never missing from context.
- **Scope awareness** — Search **within this catalog** (or **folder / collection** if your app has those) so results feel relevant, not the whole public web.

### Differentiators

- **Fusion with your signals** — Re-rank by **Instagram proximity**, **pHash** for *near* dup vs. **semantic** for *mood* matches; show *why* (“same scene” vs. “same palette and subject class”).
- **De-dupe with stacks** — If stacks exist, *collapse to one representative* in similarity results, or *show “3 similar in same stack”* to reduce noise.
- **Same embedding infra as NL** — One model/pipeline for **vector search** and **attribute space** (if you use a shared embedding for both) lowers total cost and keeps behavior consistent.

### Anti-features / Avoid

- **Nothing but look-alikes of one category** — Endless *same person from behind* with no use case; **re-rank** by variety or **diversity** options for portfolio picking.
- **Mystery neighbors** that are **crops/exports** of the same master—pHash and embeddings often cluster these; without **stacking** or **de-dupe**, the grid feels “broken.”
- **Surprise** copyright or external matches — **Only in-catalog** is mandatory unless you sell stock search.

### UX Patterns

- **Entry** — **Right-click** or **“…”** menu on image → **Find visually similar**; some apps add a **side panel** that stays open while clicking other seeds (compare Google Lens-style, heavier).
- **Layout** — **Query hero** at top or sticky left; **results grid** below. **Refine** with **time range, camera, or attribute facets** in a **left rail**—keeps the task “portfolio expansion” or “cull dupes” fast.
- **Cluster bands** — Optional **“Very similar / Related”** groupings (distance thresholds) help users **split near-dup culling** from **inspirational** neighbors.
- **Empty / weak matches** — Message: *“No close matches; showing best available”* with a **lower threshold** control only in advanced—avoid silent junk.

### Complexity

- **High (initial)** — Embedding generation and storage, vector index (e.g. HNSW, sqlite-vss, hosted vector store), re-embed on model upgrade.
- **Medium (ongoing)** — Distance thresholds, re-ranking with pHash/Instagram state, **de-dupe** with stacks to avoid near-identical rows.
- **Complements** stacking: same distance signals can inform both.

---

## Feature Dependencies

| Relationship | Notes |
|--------------|--------|
| **NL search ↔ visual attribute tags** | **Strong positive.** NL queries often decompose to **facets** (date, not posted) + **semantic** + **attributes**; attributes should be **first-class in the same filter/parse** story as free text. Tags without NL still add browse value. |
| **NL search ↔ similarity search** | **Strong positive.** “More like *this* but from December and not posted” is **hybrid**; shared **embedding** or **unified search API** avoids two inconsistent brains. **Dependency:** if both ship, **one query model** and **one ranking config** (or clear precedence rules) matter. |
| **Similarity ↔ photo stacking** | **Strong positive.** pHash/embedding for **stacks (near-dup branch)** and **similarity** can share code and **distance metrics**; without stacks, **similarity** grids often look **cluttered** with near-dupes. **Ordering:** building **stacks** first or **in parallel** helps **clean similarity** results. |
| **Stacks ↔ attribute tags** | **Moderate.** Scoring *propagation* to stack members should consider whether attributes are **per-frame** (burst with different color balance) or **stack-level** (inherit from cover). **Policy choice** required to avoid confusing filters. |
| **Instagram state ↔ all** | **Cross-cutting.** “Not posted” appears in **NL** and as a **filter**; **stacks** may choose a **post candidate**; **similarity** may **de-prioritize** already posted—requires **a single** “posted to IG” field in the search/NL/UX stack. |
| **AI descriptions / scores (existing) ↔ all** | **Foundational.** NL and facets should **read from the same** description + score + rationale fields; **stack picks** and **similarity** re-rank using **the same** score definitions you already show elsewhere. |
| **useFilters + FilterBar (existing) ↔ all** | **UX integration.** New modes (NL, similarity) should **emit compatible filter state** (chips, query object) so users don’t learn **two** mental models. **Technical debt risk** if NL is a second pipeline that can’t round-trip to the bar. |

**Suggested sequencing (dependency-aware, not a mandate):**  
1) **Data model** for attributes + **index** for catalog queries.  
2) **Embeddings** (powers similarity, optionally NL semantic).  
3) **Stacks** (reuses pHash/embedding, cleans grids).  
4) **NL layer** (parses to structured + semantic + your filters—most **integration** heavy).  
Parallel tracks are possible: **attributes** and **embeddings** often land before **full NL**; **stacks** can start with **time + pHash** before full embedding clustering.

---

## Cross-cutting: Complexity Summary

| Feature | Primary complexity | Main risks |
|--------|-------------------|------------|
| **Natural language search** | Query understanding + **grounding** + **ranking**; LLM or hybrid parsers | Wrong constraints, **latency**, inconsistency with manual filters |
| **Photo stacking** | Threshold tuning, **merge/split** UX, **score propagation** rules | **Over/under** grouping, user distrust, edge cases in time zones |
| **Visual attribute tags** | Schema, **vocabulary stability**, re-indexing, facet UX | **Tag sprawl**, model drift, **manual** correction gaps |
| **Visual similarity** | **Embeddings** + **vector index** + threshold UI | **Near-dup** noise, re-embedding cost, **fusion** with other signals |

This document is intended for **requirements drafting**: use **Table stakes** for non-negotiable scope, **Differentiators** for product positioning and prioritization, and **Anti-features** for explicit out-of-scope or guardrails in acceptance criteria.
