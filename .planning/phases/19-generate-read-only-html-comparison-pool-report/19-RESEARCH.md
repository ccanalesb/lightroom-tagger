# Phase 19 — Research: Read-only HTML comparison-pool report

**Role:** `gsd-phase-researcher` artifact for `/gsd-plan-phase 19`  
**Date:** 2026-05-12  
**Inputs read:** `19-CONTEXT.md`, `REQUIREMENTS.md`, `STATE.md`, `ROADMAP.md`, todo `2026-05-06-generate-read-only-html-comparison-pool-report.md`, plus codebase inspection below.

---

## 1. What the planner must deliver (from locked context)

Phase boundary is fixed: **offline diagnostic HTML** showing each **unmatched, attempted** Instagram dump row beside the **exact candidate pool** the matcher evaluated, with **scoring evidence** and **debug hidden by default**. No product UI, no writeback, no labeling workflow.

Locked decisions the plan **must not contradict** (see `19-CONTEXT.md`):

| ID | Constraint |
|----|------------|
| D-01 | Report uses **exact saved** candidate-pool snapshots for future runs. |
| D-02 | Legacy rows without snapshots: **reconstruct** from current DB + code path, **visibly labeled** as non-exact. |
| D-03 | Planning must add **durable pool capture** on the matching path (today only finals / partial pair cache exist). |
| D-04–D-05 | **CLI/offline** only; output openable **without** the visualizer frontend. |
| D-06–D-08 | Per-row: IG preview, `media_key`, every pool thumbnail, catalog keys, inline scores; **full** debug (prompt, reasoning, logs, paths) only in **collapsed** UI. |
| D-09–D-10 | Default = all unmatched attempted; filters: `--month`, `--job-id`, `--media-key`, `--limit`. |
| D-11–D-13 | Output = **folder** with `report.html` + `assets/`; **always** compress copied images; **no** raw filesystem paths in primary view (paths only in debug). |

**Roadmap dependency:** Phase 19 officially **depends on Phase 18** (E2E flows). For planning: Phase 18 does not block *design* of this CLI artifact, but execution order may assume E2E harness maturity; avoid coupling the report to E2E unless explicitly desired.

**Requirements matrix:** Current `REQUIREMENTS.md` (v4.0) does **not** yet map a requirement ID to Phase 19 — planner should propose traceability (e.g. diagnostic / ops-adjacent) or an explicit backlog ID.

---

## 2. Exact matcher anchor: where the evaluated pool exists today

**Function:** `match_dump_media` in `lightroom_tagger/scripts/match_instagram_dump.py`.

**Pipeline order (per media row):**

1. `find_candidates_by_date(db, dump_media, days_before=90)` — date window.
2. Drop rejected pairs (`get_rejected_pairs`).
3. **Representative-only** filter via `catalog_key_is_primary_grid_row`.
4. **CLIP shortlist:** `shortlist_catalog_candidates_by_clip(db, media_key, cand_keys, clip_top_k)` — ordering and membership of the shortlist define the pool entering vision scoring.
5. Build `vision_candidates`: list of dicts with `key`, `local_path` (via `resolve_catalog_path`), `image_hash` / phash, `description`, `ai_summary`, optional inline describe when `skip_undescribed=False`.
6. **The critical call:** `score_candidates_with_vision(db, dump_image, vision_candidates, ...)` → returns sorted `results` (list of dicts).

**Insertion point for pool capture:** Immediately **after** `score_candidates_with_vision` returns (around lines 325–347 in current file): both **`vision_candidates`** (pool membership + hydrated paths) and **`results`** (per-candidate evidence + total ordering) are in memory. No additional DB read can reconstruct the **CLIP-ordered shortlist + scoring outcome** for that run without new storage.

**Unmatched branch:** When `above_threshold` is empty, code calls `mark_dump_media_attempted` with best row’s `vision_result` / `vision_score` only — **not** the full ranked list or pool keys (lines 402–408).

**No-candidate / post-shortlist-empty branches:** `mark_dump_media_attempted` can run with **no** scoring (lines 179, 203); planner should define whether empty-pool rows appear in the report and what snapshot rows look like.

**Symbols to reference in plans:**

- `match_dump_media` — `lightroom_tagger/scripts/match_instagram_dump.py`
- `find_candidates_by_date` — `lightroom_tagger/core/matcher/candidates.py` (per CONTEXT)
- `shortlist_catalog_candidates_by_clip` — `lightroom_tagger/core/clip_similarity.py`
- `score_candidates_with_vision` — `lightroom_tagger/core/matcher/score_with_vision.py`

**Job orchestration (server path):** `handle_vision_match` in `apps/visualizer/backend/jobs/handlers/matching.py` calls `match_dump_media` with `log_callback` → `add_job_log`, `on_media_complete` → checkpoints `processed_media_keys` in **job metadata** (`checkpoint` / `processed_media_keys`). This is **not** in the library DB.

---

## 3. Evidence shapes already available

### 3.1 Per-candidate scoring dict (`score_candidates_with_vision` → each result)

Fields appended today include:

- `catalog_key`, `insta_key`
- `phash_distance`, `phash_score`
- `desc_similarity` (display-oriented; may differ when `desc_weight==0`)
- `vision_result`, `vision_score`, `vision_reasoning`
- `total_score`, `model_used`, `rate_limited` (boolean)

Sorted by `total_score` descending before return (`score_with_vision.py` ~395–398).

**Gap vs D-08 “prompt response”:** `vision_comparisons` and in-memory `vision_reasoning` capture **parsed** reasoning, not necessarily the **raw** LLM payload. If raw transcript is required, planner must specify capture in `compare_with_vision` / batch path or accept “reasoning + job log excerpts” as sufficient.

### 3.2 Tables (library DB) — `lightroom_tagger/core/database/library_bootstrap_schema.py`

| Table | Relevance |
|-------|-----------|
| `instagram_dump_media` | `media_key`, `file_path`, `processed`, `last_attempted_at`, `matched_catalog_key`, `vision_result`, `vision_score`, `date_folder`, caption, etc. |
| `matches` | Confirmed multi-row with `rank`, `vision_reasoning` (via `store_match` in `matches.py`). |
| `vision_comparisons` | PK `(catalog_key, insta_key)`: `result`, `vision_score`, `compared_at`, `model_used`. **No** rank, **no** pool membership proof. |
| `vision_cache` | Compressed catalog paths for vision; useful for diagnostics but **not** a pool snapshot. |

### 3.3 Reference pattern for “parent + ranked children”

`lightroom_tagger/core/database/similarity.py` — `insert_catalog_similarity_group` / `catalog_similarity_candidates`: proven pattern for **group_id**, **rank**, **candidate_key**, **similarity**, **why_matched**. Phase 19 needs an **Instagram-keyed** snapshot model (and optionally **job_id** / run timestamp), not catalog–catalog groups.

---

## 4. Persistence design questions the PLAN must resolve

1. **Schema:** New table(s) vs JSON blob column on `instagram_dump_media` vs separate `match_pool_snapshots` with child rows. Recommend **normalized child rows** if you need stable querying and incremental reports; **JSON** if snapshot is write-once, read-only, whole-blob export.
2. **Run identity:** Snapshot should be keyed by at least `(insta_key, run_timestamp)` or `(insta_key, vision_match_job_id)` so reruns do not silently overwrite history. D-01 implies **retaining** exact historical pools for **future** matching runs — planner should clarify “latest snapshot only” vs “append-only history.”
3. **`--job-id` filter:** Job UUIDs live in **visualizer** `jobs` / `job_logs` (`apps/visualizer/backend/database.py`), not in `library.db`. Checkpoint stores `processed_media_keys` but **not** per-row pool payloads. Options:
   - Require ** `--job-id` ** to open **both** DB paths (config-driven), intersect `instagram_dump_media` keys with checkpoint keys; **or**
   - Persist `source_job_id` on snapshot rows at capture time (capture hook needs `job_id` passed from `handle_vision_match` into `match_dump_media` — **signature change**); **or**
   - Define `--job-id` as “optional narrowing filter when job DB available,” else document limitation.
4. **Compression in DB vs at report time:** D-12 requires compressed **report** assets; snapshot storage can store **keys + scores** only and let the report generator compress thumbnails from resolved paths (with missing-file handling).

---

## 5. CLI / command patterns in the repo

- **Standalone script style:** `lightroom_tagger/scripts/match_instagram_dump.py` — `argparse`, `init_database(args.db)`, `--month`, `--media_key`-style filters already exist on the matcher entrypoint.
- **Packaged CLI:** `lightroom_tagger/core/cli.py` — `lightroom-tagger` subcommands (`scan`, `search`, `export`, …). Phase 19 could add `comparison-pool-report` **or** ship as **`python -m lightroom_tagger.scripts....`** to avoid growing `cli.py` (aligns with deferred “cli split” in REQUIREMENTS).
- **Config:** `load_config()` for `mount_point`, catalog paths, thresholds — report generator should resolve catalog files the same way as matching (`lightroom_tagger/core/path_utils.resolve_catalog_path`).

**Planner discretion (per CONTEXT):** exact submodule name and flag spelling beyond the four locked filters.

---

## 6. Image path resolution and thumbnail / compression patterns

- **Catalog paths:** `resolve_catalog_path(catalog_img.get('filepath', ''))` when building `vision_candidates` in `match_instagram_dump.py`.
- **Vision compression reuse:** `get_or_create_cached_image`, `InstagramCache.compress_instagram_image` in matcher pipeline; batch path uses `_build_compressed_batch_entries` (`vision_batch.py`).
- **Report-specific:** Existing `lightroom_tagger/scripts/generate_validation_report.py` — **`image_to_base64`** with PIL resize + JPEG quality 85, **inline** in HTML. Phase 19 **explicitly differs** (D-11): relative `assets/` files, **always** compress — planner should specify max dimension / quality and naming (`sha1` / index-based) to keep folders portable.

**Security / privacy:** D-13 — strip or gate absolute paths in primary HTML; use relative `src="assets/..."` only.

---

## 7. HTML / report generation patterns

- **Closest precedent:** `generate_validation_report.py` (card layout, flex comparison, badges) and `generate_subset_report.py` — string-built HTML, embedded images (subset report likely similar).
- **Phase 19 additions:** collapsible `<details>` / `<summary>` or minimal JS for “modal-like” panels; grid of **all** pool candidates (not just top-1); visible **reconstructed** banner when snapshot missing.

No React/visualizer involvement — static file output.

---

## 8. Selecting “unmatched attempted” rows (default report scope)

**Working definition for implementation research:**

- **Unmatched:** `instagram_dump_media.processed = 0` (no successful match committed as processed).
- **Attempted:** `last_attempted_at IS NOT NULL` **or** row was touched in a matching run (same as `mark_dump_media_attempted` semantics).

Edge cases for the plan:

- Rows **skipped** before scoring (no candidates / empty after CLIP) still call `mark_dump_media_attempted` in current code — include or exclude? (D-09 says “unmatched **attempted**” — include, with empty or singleton pool narrative.)
- **`--month`:** align with `date_folder` conventions (`YYYYMM` / folder structure as used by `get_instagram_by_date_filter` in `instagram.py`).

---

## 9. Reconstruction fallback (D-02)

When no snapshot exists, a **best-effort** path can:

1. Load `instagram_dump_media` row + catalog DB state.
2. Re-run **read-only** candidate discovery: `find_candidates_by_date` → filters → `shortlist_catalog_candidates_by_clip` with **current** embeddings and code version.
3. Join `vision_comparisons` / optional `matches` for pair evidence — **does not** prove historical pool.

**Landmine:** CLIP embeddings, stack membership, rejected pairs, and code changes make reconstruction **non-faithful**; UI must show a prominent **“reconstructed — not exact run evidence”** flag (D-02).

---

## 10. Risks and landmines

| Risk | Mitigation in plan |
|------|---------------------|
| **Silent overwrite** if one snapshot per insta_key | Key snapshots by run id + retain history or “latest wins” with explicit policy. |
| **Two-database job filter** | Document CLI inputs; optional `VISUALIZER_DB` env; or persist `job_id` on snapshot at capture. |
| **Large HTML** with many candidates | Pagination / per-section lazy collapsing; `limit` flag (D-10). |
| **Missing files** at report time | Placeholder tiles; still show keys and scores from DB. |
| **Raw prompt unavailable** | Scope D-08 to “available structured evidence + logs” or extend vision storage (bigger change). |
| **Matching path perf** | Persist snapshots in same transaction as `mark_dump_media_*` to avoid duplicate scoring. |

---

## 11. Verification / test strategy

**Unit-level:**

- Snapshot write: after mocked `score_candidates_with_vision`, assert DB rows (or blob) match expected ordering and scores.
- Report generator: given fixture DB + temp output dir, assert `report.html` exists, `assets/` non-empty, relative image refs resolve, **no** absolute paths in main body (regex test).
- Reconstruction branch: flag present when snapshot missing.

**Integration:**

- Extend existing matcher tests under `apps/visualizer/backend/tests/test_handlers_single_match.py` / stack integration only if capture hooks change job behavior; prefer tests on `match_dump_media` with temp SQLite (pattern in `test_match_instagram_dump.py`, `test_handlers_single_match.py`).

**Likely commands:**

```bash
pytest lightroom_tagger/scripts/test_match_instagram_dump.py -q
pytest apps/visualizer/backend/tests/test_handlers_single_match.py -q -k match_dump
# After new tests land:
pytest tests/ -q -k comparison_pool  # or scoped path per plan
```

**Manual / UAT:** Open `report.html` in browser from `file://`, verify offline images load, expand debug for one row (matches todo success criteria).

---

## 12. Validation architecture (Nyquist / GSD)

Per `.cursor/rules/gsd-live-validation.mdc`, **live browser E2E and HTTP curl** are mandatory when adding API routes or LLM integrations. This phase is **CLI-first** and **no backend endpoint** (D-04).

| Layer | Applicability |
|-------|----------------|
| Browser harness E2E | **Not required** for the static HTML deliverable unless a plan explicitly adds UI routes. |
| `curl` API checks | **N/a** if no new routes. |
| **LLM live validation** | **N/a** for report **generation** (read-only). If a plan **changes** `compare_with_vision` / batch scoring or adds capture that alters API calls, run matcher regression tests and consider a single golden “dry-run” with mocked vision. |
| Job lifecycle hooks | Apply only if `handle_vision_match` or checkpoint contract changes. |

**Minimum bar to mark phase passed:** deterministic automated tests for snapshot + HTML output + human spot-check checklist (file open, filters, reconstructed banner).

---

## 13. Files and symbols likely touched or read

| Path | Role |
|------|------|
| `lightroom_tagger/scripts/match_instagram_dump.py` | Pool capture hook after `score_candidates_with_vision`. |
| `lightroom_tagger/core/database/library_bootstrap_schema.py` + migrations in `db_init.py` | New DDL for snapshots. |
| New module e.g. `lightroom_tagger/core/database/match_pool_snapshots.py` (name TBD) | Insert/query snapshot rows. |
| `lightroom_tagger/scripts/generate_comparison_pool_report.py` (name TBD) | CLI + HTML + asset copy. |
| `lightroom_tagger/core/path_utils.py` | Reuse resolution helpers. |
| `lightroom_tagger/core/database/instagram.py` | Query helpers for unmatched attempted + month filter. |
| `lightroom_tagger/core/matcher/score_with_vision.py` | Read-only reference for evidence fields. |
| `apps/visualizer/backend/jobs/handlers/matching.py` | Optional: pass `job_id` into matcher for snapshot provenance / `--job-id`. |
| `lightroom_tagger/scripts/generate_validation_report.py` | HTML/CSS patterns (adapt to external assets). |

---

## 14. Assumptions the planner must preserve

1. **Do not** use “all catalog images” in the report — only **evaluated pool** (todo + D-06).
2. **Exact** historical fidelity requires **capture at match time**, not post-hoc inference from `vision_comparisons`.
3. **Read-only** report: no mutations to matches, rejections, or labels.
4. **Compressed assets** and **folder** output are mandatory output shape (D-11–D-12).
5. **Primary** narrative is visual: “was expected catalog image **in the grid**?” (CONTEXT specifics).

---

## 15. Open questions for PLAN.md (not blocking research)

1. Snapshot retention policy (latest only vs append-only history).
2. Whether CLI defaults include rows with **zero** scored candidates.
3. Exact HTML stack: vanilla vs small embedded CSS file; accessibility baseline (keyboard expand for `<details>`).
4. Whether to backfill snapshots by **re-running** matcher in dry mode (expensive; probably out of scope).

---

*End of research artifact — ready for `/gsd-plan-phase 19`.*
