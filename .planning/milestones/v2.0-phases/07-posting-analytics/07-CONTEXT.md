# Phase 7 — Posting analytics — context & decisions

**Phase:** 7  
**Requirements:** POST-01, POST-02, POST-03, POST-04  
**Milestone:** v2.0 Advanced Critique & Insights

## Intent

Derive **posting cadence**, **timing patterns**, **caption/hashtag aggregates**, and **catalog vs posted gaps** from **Instagram export dump** data already in `library_db`. No engagement API; no Instagram Graph API.

## Roadmap alignment

[ROADMAP.md](../../ROADMAP.md) lists four placeholder plan rows (07-01…07-04). **Execution uses three plans:** `07-01` (all analytics **backend** + gap query API), `07-02` (charts + caption UI on **Analytics** route), `07-03` (gap **UI** integrated with Analytics or Images). Update the roadmap execution table when Phase 7 starts if you want titles to match these files.

## Data sources (current schema)

| Concern | Primary tables / columns |
|--------|---------------------------|
| Dump media rows | `instagram_dump_media` (`media_key`, `caption`, `date_folder`, `created_at`, `added_at`, `matched_catalog_key`, `processed`) |
| Human-confirmed post ↔ catalog | `matches.validated_at IS NOT NULL` plus `images.instagram_posted` / `instagram_post_date` maintained on validate/writeback |
| Catalog browse | `images` (`key`, `date_taken`, `rating`, `instagram_posted`, …) |

Implementers should **read** `validate_match` / catalog update paths in `lightroom_tagger/core/database.py` and matching handlers so “posted” semantics stay consistent with Phase 3.

## Decisions

| ID | Decision | Rationale |
|----|----------|-----------|
| D-30 | **Posted analytics population:** charts and caption rollups use rows that represent **confirmed posts** — filter to dump media with `matches.validated_at IS NOT NULL` for the `(catalog_key, insta_key)` pair where `insta_key = instagram_dump_media.media_key`, **or** equivalently `images.instagram_posted = 1` for the matched catalog key. Pick one canonical SQL join and document it in `posting_analytics` module docstring; avoid double-counting carousel duplicates if the dump stores one row per file. |
| D-31 | **Event timestamp for cadence & heatmap:** prefer **`instagram_dump_media.created_at`** when present and parseable as ISO-8601; else fall back to **`date_folder`** interpreted as **local calendar date at midnight UTC** (document in API `meta`). If `created_at` is missing for many rows, consider `added_at` only as ingest time — **do not** mix `created_at` and `added_at` in one series without labeling; default series uses `created_at` → `date_folder` only. |
| D-32 | **Frequency bucketing:** default **daily** counts for timeline; support optional `granularity=week|month` query param aggregating in SQL (`strftime` / date truncation). Empty buckets return **zero** in the series for chart continuity (or document sparse series — prefer zero-filled for Recharts). |
| D-33 | **Heatmap axes:** **day-of-week** 0–6 (SQLite `strftime('%w', …)` with Sunday=0) and **hour-of-day** 0–23 from UTC-normalized timestamp per D-31; API returns `cells: [{dow, hour, count}]` plus `timezone_note` string. |
| D-34 | **Hashtag tokenization:** extract `#` tokens from `caption` with regex `[#＃][\w]+` (Unicode word chars); lowercase for aggregation; strip trailing punctuation in a second pass if needed. Count **per-post** hashtag set vs **global** frequency — expose both: `top_hashtags` (global) and `posts_with_hashtags` / `avg_hashtags_per_post`. |
| D-35 | **Caption stats (simple):** median/avg caption length (characters), % posts with caption > 0 chars, top 20 hashtags, optional top **words** after removing hashtags and stopwords (English minimal list inline or small constant tuple — keep scope small). |
| D-36 | **Gap / unposted catalog:** list catalog rows where `instagram_posted = 0` (aligns with existing `query_catalog_images(posted=False)`). Pagination + filters: `date_from`, `date_to`, `min_rating`, optional `month` — reuse parameter names from catalog API for consistency. |
| D-37 | **Backend shape:** add **`lightroom_tagger/core/posting_analytics.py`** (or `analytics.py`) with pure SQL functions taking `sqlite3.Connection`; keep Flask thin in **`apps/visualizer/backend/api/analytics.py`** (new blueprint) **or** namespaced routes under `images` blueprint — **prefer new `analytics` blueprint** at `/api/analytics/...` for clarity. |
| D-38 | **Frontend:** new route **`/analytics`** with nav label **Analytics**; add **`recharts`** to `apps/visualizer/frontend/package.json` (listed in [.planning/research/STACK.md](../../research/STACK.md) but not yet installed in the app). |
| D-39 | **Gap UI placement:** primary entry on **Analytics** page as a third section or sub-tab **“Not posted”**; optional deep link from **Images → Catalog** filter `posted=false` — document in 07-03. |

## Non-goals

- Engagement metrics (likes, reach).
- Inferring timezone from EXIF beyond what the dump provides; users see explicit UTC / export assumptions (POST roadmap criterion 5).

## References

- `lightroom_tagger/core/database.py` — `query_catalog_images`, `instagram_dump_media`, `matches`
- `apps/visualizer/backend/api/images.py` — `@with_db`, pagination helpers
- `apps/visualizer/frontend/src/services/api.ts` — `ImagesAPI` patterns

---
*Created: 2026-04-12 — GSD planner subagent.*
