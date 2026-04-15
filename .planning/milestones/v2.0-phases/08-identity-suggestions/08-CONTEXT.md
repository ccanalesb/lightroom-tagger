# Phase 8 — Identity & “what to post next” — context & decisions

**Phase:** 8  
**Requirements:** IDENT-01, IDENT-02, IDENT-03  
**Milestone:** v2.0 Advanced Critique & Insights

## Intent

Surface **ranked “best photos”** from persisted perspective scores, a **style fingerprint** derived from **score patterns and lightweight rationale token stats** (no embeddings), and **actionable “what to post next”** candidates with **explicit reasons** tied to scores and posting gaps. All logic runs against the **single active library DB** (same catalog scope as the rest of the visualizer).

## Roadmap alignment

[ROADMAP.md](../../ROADMAP.md) lists three execution rows (08-01…08-03). **This milestone uses two plan files:** `08-01-PLAN.md` (**Wave 1 — backend**: ranking, fingerprint computation, suggestion heuristics, APIs, tests) and `08-02-PLAN.md` (**Wave 2 — frontend**: Best Photos, Style Fingerprint, Suggestions UI). The roadmap table may be updated at phase kickoff to reflect this consolidation.

## Data sources (current schema)

| Concern | Primary tables / columns |
|--------|---------------------------|
| Current scores | `image_scores` (`image_key`, `image_type`, `perspective_slug`, `score`, `rationale`, `model_used`, `prompt_version`, `is_current`, `scored_at`) — use **`is_current = 1`** and **`image_type = 'catalog'`** for catalog-facing features |
| Perspective registry | `perspectives` (`slug`, `display_name`, `active`) — fingerprint and weighting should respect **`active = 1`** for “official” axes; inactive slugs with legacy scores may still exist in DB |
| Catalog rows | `images` (`key`, `filename`, `date_taken`, `rating`, `instagram_posted`, …) |
| Posted history / gaps | `instagram_dump_media` + **`matches.validated_at IS NOT NULL`** (same population as `posting_analytics.posted_dump_media_cte_sql`) and/or `images.instagram_posted` — **keep semantics aligned** with Phase 7 |

## Decisions

| ID | Decision | Rationale |
|----|----------|-----------|
| D-40 | **Aggregate “best” score:** compute a **weighted mean** of **current** catalog scores across **active** perspectives only. Default **equal weights** (`1` each); weights are **fixed constants in code** for v1 of this phase (no user-facing weight editor). Store per-image **breakdown** in API (`per_perspective: [{slug, score, prompt_version, model_used}]`) so the UI can label contributors (IDENT-01 / roadmap criterion 1). |
| D-41 | **Coverage guards:** an image is **eligible for ranking** only if it has a current score for **at least `min_perspectives`** (default: **2** or **ceil(0.5 × active_perspective_count)**, whichever is smaller — pick one rule in implementation and document in response `meta`). If **no** images meet coverage, return **empty list** + **`coverage_note`** explaining insufficient scoring (roadmap criterion 4). |
| D-42 | **Style fingerprint — no embeddings:** fingerprint = **(a)** catalog-wide **mean (or median) score per active perspective**, **(b)** **histogram** or bucket counts of aggregate scores, **(c)** **top N rationale tokens** (see D-43), **(d)** **evidence links**: example `image_key` list for “strong in slug X” (e.g. top 3 by that perspective’s score among covered images). |
| D-43 | **Rationale keywords:** tokenize `rationale` with **simple Unicode-aware word splitting** + **lowercase** + **minimal English stopword set** (reuse or mirror `posting_analytics._EN_STOPWORDS` pattern — **shared helper** or duplicated small frozenset to avoid import cycles). Drop tokens shorter than 3 chars; **no** stemming, **no** NLP libraries. Frequencies are **global** across current catalog scores (IDENT-02 evidence, not semantic topics). |
| D-44 | **“What to post next” candidates:** start from **`images.instagram_posted = 0`** intersect **coverage-eligible** scored images. Rank by **aggregate score** with **tie-breakers** (`date_taken` desc, `key` asc). Attach **`reasons: string[]`** and optional **`reason_codes`** (`high_score_unposted`, `cadence_gap`, `underrepresented_theme`, etc.) derived only from **observable rules** (D-45–D-47). |
| D-45 | **Cadence / gap signal:** reuse **Phase 7** semantics: compute **recent posting count** over a window (e.g. last **30** vs prior **60** days) using **`posted_dump_media`** CTE or call existing `get_posting_frequency` internally. If recent cadence is **below** a simple threshold vs baseline, add a **cadence_gap** hint to suggestions `meta` and optionally boost unposted high scorers (document exact rule in code comments). |
| D-46 | **Theme / “underrepresented” (heuristic):** compare **top rationale tokens** from scores attached to **posted** catalog images (via `matches` → catalog key) vs **unposted** high scorers; if a token appears disproportionately in posted rationales and is **absent or rare** in an unposted candidate’s rationale text, emit **`underrepresented_theme`** with the token named in the reason string. This is **frequency-only**, not NLP similarity. |
| D-47 | **Backend module placement:** add **`lightroom_tagger/core/identity_service.py`** for pure SQLite/Python aggregation (keeps `posting_analytics.py` focused on dump timing/captions). **Thin Flask blueprint** **`api/identity.py`** registered at **`/api/identity`** (preferred over overloading `/api/analytics` so Phase 9 can compose both). |
| D-48 | **API shapes:** JSON responses include **`meta`** objects: `perspectives_included`, `weighting`, `coverage_rule`, `scored_image_count`, `timezone_assumption` where time is involved (reuse UTC language from analytics). **No PII logging** of full rationales at INFO. |
| D-49 | **Frontend placement:** add an **“Identity”** nav route (e.g. `/identity`) as **primary** surface; optional **deep link** or compact widgets on **Analytics** page deferred unless time permits (08-02 calls this out). |

## Non-goals (reinforcing REQUIREMENTS.md)

- **Embedding-based** style similarity or clustering.
- **Full NLP** on captions (beyond existing Phase 7 simple stats); fingerprint **does not** require new caption models.
- **Multi-catalog** identity or cross-library aggregation.

## References

- `lightroom_tagger/core/database.py` — `image_scores` helpers, `query_catalog_images`, `list_perspectives`
- `lightroom_tagger/core/posting_analytics.py` — `posted_dump_media_cte_sql`, frequency helpers
- `apps/visualizer/backend/api/analytics.py`, `api/scores.py` — Flask patterns
- `apps/visualizer/frontend/src/pages/AnalyticsPage.tsx`, `src/services/api.ts` — UI and client patterns

---
*Created: 2026-04-12 — GSD planner (Phase 8).*
