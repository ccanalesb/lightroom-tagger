# Phase 9 — Insights dashboard — context & decisions

**Phase:** 9  
**Requirements:** DASH-01  
**Milestone:** v2.0 Advanced Critique & Insights

## Intent

Deliver a **single home surface** (`/`) that **composes** Phase 6–8 capabilities: **score distributions**, **posting cadence summary**, and **top-scored catalog highlights**, with **explicit loading / error / empty states** and **quick navigation** to deeper Analytics, Identity, and Processing flows. This phase is **curation and UX**, not new scoring or analytics logic.

## Roadmap alignment

[ROADMAP.md](../../ROADMAP.md) currently lists three placeholder rows (09-01…09-03). **Execution consolidates into two plans:** `09-01-PLAN.md` (Wave 1 — **optional** backend summary or explicit **no-backend** closeout) and `09-02-PLAN.md` (Wave 1–2 — **frontend** unified dashboard). Update the roadmap Phase 9 execution table at kickoff so plan titles match these files.

## Existing building blocks (no reinvention)

| Dashboard widget | Primary source | Client API (today) |
|------------------|----------------|-------------------|
| Catalog / match / posted counts | Server `/stats` | `SystemAPI.stats()` |
| Aggregate score distribution (histogram buckets) | Identity style fingerprint | `IdentityAPI.getStyleFingerprint()` → `aggregate_distribution` |
| Per-perspective summary (radar / means) | Same fingerprint | `per_perspective` (+ `perspectives` display names if needed) |
| Top-scored photos strip | Identity ranking | `IdentityAPI.getBestPhotos({ limit: 5–12 })` |
| Posting frequency (mini chart + cadence copy) | Phase 7 analytics | `AnalyticsAPI.getPostingFrequency` with a **fixed default window** (e.g. last 12 months, `granularity: 'week'` or `'month'` for fewer points) — **same UTC / disclaimer semantics** as `AnalyticsPage` |
| Jobs / pipeline pulse (optional KPI row) | Jobs list | `JobsAPI.list()` (already used on current dashboard) |

**Score histogram note:** There is no dedicated “raw score histogram” endpoint today; **fingerprint `aggregate_distribution`** is the intended catalog-wide aggregate view (aligned with Phase 8). If product later needs **per-perspective raw score** histograms, that is a **new** analytics query (out of scope for 09 unless 09-01 adds an endpoint).

## Decisions

| ID | Decision | Rationale |
|----|----------|-----------|
| D-50 | **Route:** Keep **`/`** as the unified insights home (matches current `App.tsx` index). Satisfies DASH-01 “without hunting through disconnected tabs” by making the **first nav item** the insights surface. |
| D-51 | **Naming:** Rename primary nav label and page title from **“Dashboard”** to **“Insights”** (update `NAV_DASHBOARD` string or introduce `NAV_INSIGHTS` in `constants/strings.ts`). Subtitle copy should describe **scores + posting + highlights**, not only Instagram matching. |
| D-52 | **Backend default:** **Do not add** a monolithic `/api/insights/overview` unless **measured** need (slow mobile, many round trips). Initial implementation **composes 3–5 parallel GETs** (`stats`, `getStyleFingerprint`, `getBestPhotos`, `getPostingFrequency`, optional `JobsAPI.list`). Document latencies in phase retrospective; add one aggregated endpoint only if p95 home load is unacceptable. |
| D-53 | **Date scope for mini posting chart:** Use the **same default 12-month range** as `AnalyticsPage` (`defaultRange()` pattern) unless a shorter **90-day** window reads better in a small chart — pick one in implementation and state it in UI footnote. **Do not** add full date controls on the home page in v1 of this phase (keeps composition simple); deep link to `/analytics` for full filters. |
| D-54 | **Fingerprint advisory copy:** Reuse or mirror **Phase 8** language that scores are **model- and rubric-version dependent** (`StyleFingerprintResponse.meta` / fingerprint panel patterns). |
| D-55 | **Empty / low coverage:** When `IdentityAPI.getBestPhotos` / fingerprint `meta` indicates **no eligible images** or **low coverage**, show the **server-provided** `coverage_note` (or equivalent) and CTAs: **Run scoring** → `/processing`, **Import dump** → config or Processing copy, **Analytics** if posts exist but identity is empty. |
| D-56 | **Top photos interaction:** Thumbnails or cards **link to catalog** — reuse the same navigation pattern as `BestPhotosGrid` / `ImagesPage` (e.g. `/images` with query or modal trigger if an established pattern exists). |
| D-57 | **Component structure:** Prefer **`components/insights/`** for home-only presentational pieces (mini frequency chart, distribution bar chart, radar summary, top-photos row, quick-link cards) to avoid bloating `DashboardPage.tsx` and to keep **Analytics** / **Identity** pages unchanged unless a small export refactor is clearly net-negative in LOC. |

## Non-goals

- New SQL aggregations or rubric logic (belongs in Phases 5–8).
- Duplicating full **Analytics** or **Identity** page feature set on `/`.
- Multi-catalog switching.

## References

- `apps/visualizer/frontend/src/pages/DashboardPage.tsx` — current minimal stats
- `apps/visualizer/frontend/src/pages/AnalyticsPage.tsx` — date range, `PostingFrequencyChart`, error handling
- `apps/visualizer/frontend/src/pages/IdentityPage.tsx` — composition of identity panels
- `apps/visualizer/frontend/src/services/api.ts` — `SystemAPI`, `AnalyticsAPI`, `IdentityAPI`, `JobsAPI`
- `apps/visualizer/frontend/src/components/identity/StyleFingerprintPanel.tsx` — radar / bar patterns to mirror or extract
- `apps/visualizer/frontend/src/components/analytics/PostingFrequencyChart.tsx` — Recharts props for mini variant

---
*Created: 2026-04-12 — GSD planner (Phase 9).*
