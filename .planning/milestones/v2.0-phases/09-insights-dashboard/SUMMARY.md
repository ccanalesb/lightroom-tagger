# Phase 9 — Insights dashboard — execution summary

## 09-01 — API composition (D-52 default path)

**Decision D-52** is recorded in `09-CONTEXT.md` (table row D-52): defer monolithic `/api/insights/overview` unless measured need; the home composes parallel GETs.

**Optional aggregated backend:** Skipped — no new Flask routes or `insights_overview.py`. Existing SQLite-backed endpoints are sufficient for fast parallel queries.

### Composition matrix (UI → HTTP → client)

| UI block | Method / path | TypeScript client | Notes |
|----------|---------------|-------------------|--------|
| KPI counts (catalog, Instagram, posted, matches) | `GET /stats` | `SystemAPI.stats()` | Small JSON (counts + `db_path`). |
| Aggregate score histogram | `GET /api/identity/style-fingerprint` | `IdentityAPI.getStyleFingerprint()` → `aggregate_distribution` | Bounded; no N+1. |
| Per-perspective radar | same response | `per_perspective` → `mean_score` | Same call as histogram. |
| Mini posting series | `GET /api/analytics/posting-frequency?...` | `AnalyticsAPI.getPostingFrequency()` | `date_from` / `date_to` / `granularity` fixed on home (e.g. 12 months, `month`). |
| Top-scored strip | `GET /api/identity/best-photos?limit=8` | `IdentityAPI.getBestPhotos({ limit: 8 })` | Bounded by `limit`. |
| Active jobs badge (optional) | `GET /jobs/` | `JobsAPI.list()` | Bounded list; filter client-side for pending/running. |

**N+1:** None of these list endpoints fan out per row on the client.

### Verification

- `pytest tests/test_identity_api.py tests/test_analytics_api.py tests/test_jobs_api.py -q` — **12 passed** (2026-04-12).

### Latency note

No local p95 multi-fetch benchmark in this pass; parallel GETs assumed acceptable per D-52 (fast SQLite). Revisit if real-world home load exceeds ~800 ms on LAN.

---

## 09-02 — Unified Insights home

**Implemented:** `/` (`DashboardPage`) composes parallel `Promise.allSettled` calls to `SystemAPI.stats`, `IdentityAPI.getStyleFingerprint`, `IdentityAPI.getBestPhotos({ limit: 8 })`, `AnalyticsAPI.getPostingFrequency` (12 months, `granularity: month`), and `JobsAPI.list` (active job count). Nav label **`NAV_INSIGHTS`** (“Insights”) in `Layout.tsx`.

**Components:** `src/components/insights/` — `InsightsKpiRow`, `ScoreDistributionChart`, `PerspectiveRadarSummary`, `MiniPostingFrequencyChart` (cadence: last 28 days vs prior 28 days by bucket start), `TopPhotosStrip` (thumbnails + `CatalogImageModal`), `InsightsQuickNav`.

**PostingFrequencyChart:** optional `compact` prop for the mini chart.

**Tests:** `DashboardPage.test.tsx` (Vitest + RTL) mocks APIs and asserts main headings.

**Verification:** `npm run build`, `npm run lint`, `npm test -- --run src/pages/DashboardPage.test.tsx` — all pass (2026-04-12).
