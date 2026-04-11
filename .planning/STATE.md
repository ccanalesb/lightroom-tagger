---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_plan: 2
status: executing
last_updated: "2026-04-11T16:34:22.329Z"
last_activity: 2026-04-11
progress:
  total_phases: 4
  completed_phases: 3
  total_plans: 21
  completed_plans: 16
  percent: 76
---

# Planning state

**Project:** Lightroom Tagger & Analyzer  
**Roadmap:** [.planning/ROADMAP.md](./ROADMAP.md) (v1, 2026-04-10)

## Current focus

| Field | Value |
|-------|--------|
| Active milestone | v1 |
| Active phase | 4 — AI analysis |
| Phase status | In progress |
| Last completed plan | 04-06 — Vision pipeline safety nets (SR2, cache cap, batch pre-filter) |

## GSD progression

**Current Plan:** 2
**Total Plans in Phase:** 6
**Status:** Executing Phase 04 — 1/6 plans complete (04-06 done)
**Last Activity:** 2026-04-11

## v1 phase checklist

- [x] Phase 1 — Catalog management (CAT-01 … CAT-05) ✓
- [x] Phase 2 — Jobs & system reliability (SYS-01 … SYS-05) ✓
- [x] Phase 3 — Instagram sync (IG-01 … IG-06) ✓
- [ ] Phase 4 — AI analysis (AI-01 … AI-06)

## Traceability

Full requirement ↔ phase mapping: [REQUIREMENTS.md § Traceability](./REQUIREMENTS.md#traceability)

## Last update

- **2026-04-10:** ROADMAP.md and STATE.md created; REQUIREMENTS.md traceability filled from v1 roadmap.
- **2026-04-10:** Plan **02-01** executed — cooperative cancellation end-to-end: per-job `threading.Event`, `DELETE /api/jobs/<id>` sets DB then `signal_cancel`, processor and runner respect `cancelled` so `complete_job`/`fail_job` do not clobber; `vision_match` checks cancel between dump-media iterations via `should_cancel`.
- **2026-04-10:** Plan **02-02** executed — `writer.py` checks Lightroom lock paths before SQLite writes, rotated `shutil.copy2` backups (max 2) with `Catalog backup created:` logging; `handle_vision_match` fails the job with the fixed lock message when the writer raises.
- **2026-04-10:** Plan **02-03** executed — `jobs.error_severity` column and migration; `fail_job`/`retry`/`complete_job` persistence; handler exception classification; frontend `Job` type, `ERROR_SEVERITY_LABELS`, severity badges in job detail modal and job cards.
- **2026-04-10:** Plan **02-04** executed — `STATUS_LABELS.pending` → Queued; job detail status uses `STATUS_LABELS`; orphan recovery log copy in `app.py`; cooperative cancel in `handle_enrich_catalog`, `handle_batch_describe` (sequential + parallel), and `handle_prepare_catalog`.
- **2026-04-10:** Plan **03-01** executed — `list_matches` joins `instagram_dump_media` via `_enrich_instagram_media` (`dump_instagram_by_key`); regression test `ig_dump_only`; `handle_vision_match` sets `result.best_score` when `matches` non-empty. See [SUMMARY.md](./phases/03-instagram-sync/SUMMARY.md).
- **2026-04-10:** Plan **03-02** executed — `update_lightroom_from_matches` uses `Config.instagram_keyword` (default `Posted`); CLI success message uses the same; unit test covers configured keyword. See [03-02-SUMMARY.md](./phases/03-instagram-sync/03-02-SUMMARY.md).
- **2026-04-10:** Plan **03-03** executed — `instagram_dump_path` in core `Config` + `INSTAGRAM_DUMP_PATH`; YAML helper; `/api/config/instagram-dump` GET/PUT; `instagram_import` job handler calling `import_dump`. See [03-03-SUMMARY.md](./phases/03-instagram-sync/03-03-SUMMARY.md).
- **2026-04-10:** Plan **03-04** executed — `ConfigAPI` instagram-dump methods; `InstagramDumpSettingsPanel` on Processing **Settings** with server-path copy, save, optional `reimport` / `skip_dedup`, and **Run Import** (`JobsAPI.create('instagram_import', …)`). See [03-04-SUMMARY.md](./phases/03-instagram-sync/03-04-SUMMARY.md).
- **2026-04-10:** Plan **03-05** executed — `MatchesTab` lists `GET /api/images/matches` via `useMatchGroups` and `MatchingAPI.list`, opens `MatchDetailModal` for validate/reject, empty copy `MATCHES_TAB_EMPTY`, pagination with **Load more** (`fetchGroups(50, matchGroups.length)`). See [03-05-SUMMARY.md](./phases/03-instagram-sync/03-05-SUMMARY.md).
- **2026-04-10:** Plan **03-06** executed — catalog `posted` query integration tests; IG-06 trace comment on `ImagesAPI.listCatalog` in `CatalogTab`; `posted_to_instagram` in stats via SQL count. See [03-06-SUMMARY.md](./phases/03-instagram-sync/03-06-SUMMARY.md).
- **2026-04-11:** Plan **04-06** executed — `.sr2` in `RAW_EXTENSIONS`; `MAX_CACHED_IMAGE_KB` (512) with `__oversized__` vision_cache sentinel; batch candidate prep skips `None` from `get_or_create_cached_image`; `is_vision_cache_valid` invalidates RAW rows cached as original path or oversized sentinel. See [04-06-SUMMARY.md](./phases/04-ai-analysis/04-06-SUMMARY.md).

## Decisions (phase 4)

- **D-04-06:** **512KB** ceiling on vision cache files with **`__oversized__`** DB sentinel when conversion/compression cannot produce a small JPEG; **`.sr2`** included in **`RAW_EXTENSIONS`**; **batch vision** never receives **`None`** cache paths (skipped with one log line per Instagram image). **RAW** cache rows that point at the original file or the oversized sentinel **auto-invalidate** so improved RAW support can re-run without a manual cache wipe.

## Decisions (phase 3)

- **D-03-01:** Match list `instagram_image` resolves **legacy `instagram_images` first**, then **enriched `instagram_dump_media`** by `insta_key`, so dump-only keys still get thumbnails/metadata in the API without duplicating legacy rows.
- **D-03-02:** Lightroom writeback from matches applies **`Config.instagram_keyword`** (YAML / `LIGHTRoom_INSTAGRAM_KEYWORD`), with **empty-after-strip falling back to `Posted`**, so the posted token stays configurable without changing auto-match/writeback triggers.
- **D-03-03:** **Server-side** Instagram dump root is stored as **`instagram_dump_path`** in repo `config.yaml` (via PUT) and optionally overridden by **`INSTAGRAM_DUMP_PATH`**; the visualizer exposes it at **`GET`/`PUT` `/api/config/instagram-dump`**. **Ingest** is triggered by job type **`instagram_import`**, which runs **`import_dump`** against the configured path and library DB (`metadata.dump_path` overrides config/env for one-off runs).
- **D-03-04:** Processing **Settings** UI treats the Instagram dump as a **server filesystem path** (text field + help text), not a browser file picker; operators enqueue ingest with **`instagram_import`** and optional **`reimport`** / **`skip_dedup`** metadata aligned with the 03-03 handler.
- **D-03-05:** **Matches** tab loads match groups with an initial **`fetchGroups(100, 0)`** and **Load more** uses **`fetchGroups(50, matchGroups.length)`**; **`useMatchGroups`** merges paginated responses by **`instagram_key`** so offsets do not duplicate rows when the API overlaps windows.
- **D-03-06:** **IG-06:** Catalog **posted** filter is **`GET /api/images/catalog?posted=true|false`**, backed by **`images.instagram_posted`** in **`query_catalog_images`**; grid and modal badges stay **`Badge variant="success"`** with labels **Posted** / **Posted to Instagram**. **`GET /api/stats`** field **`posted_to_instagram`** is the count of rows with **`instagram_posted = 1`**.

## Decisions (phase 2)

- **D-02-01:** Cancel order for running jobs is **database `cancelled` first**, then in-memory `Event.set()`, so `start_job` and terminal transitions can race-safely consult DB status.

---
*This file is the canonical planning pointer for “where we are” between phase transitions.*
