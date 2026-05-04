# Phase 4: Stack Detection — Research

## RESEARCH COMPLETE

### 1. Batch Job Pattern (`handle_batch_text_embed`)

Canonical structure in `apps/visualizer/backend/jobs/handlers.py`:

- **Cancel scope:** Outer handler wraps work in `with cancel_scope.install(lambda: runner.is_cancelled(job_id)):` then delegates to `_handle_batch_text_embed_inner` (lines 2255–2258).
- **Library DB:** `_resolve_library_db_or_fail` → `init_database(db_path)`; `lib_db.close()` in `finally`.
- **Early validation:** Wrong `image_type` → `runner.fail_job(job_id, message, severity='warning')` and return (no exception).
- **Work list:** Builds `full_list` via DB helpers (`list_catalog_keys_needing_text_embedding` vs `…_force`); `total_at_start = len(full_list)`.
- **Fingerprint:** `fp = fingerprint_batch_text_embed(metadata, full_list)` — **ordered pairs matter for describe; text embed sorts inside fingerprint** (see §3).
- **Checkpoint load:** Reads `get_job` → `metadata.checkpoint` with `checkpoint_version == 1`, `job_type == 'batch_text_embed'`, matching `fingerprint`; else logs `checkpoint mismatch…` and starts fresh. Restores `processed_pairs` as a `set`.
- **Progress:** `runner.update_progress(job_id, pct, message)` — initial 5% with counts; then `5 + (embedded/total)*95` during work; `update_progress` also appends an **info** job log with the same `current_step` string (via `add_job_log` inside `update_job_status` path in runner).
- **Checkpoint persist:** `persist_progress()` checks `len(processed_pairs) > _CHECKPOINT_MAX_ENTRIES` (100_000) → `runner.fail_job(…, 'checkpoint too large…')`; else `runner.persist_checkpoint(job_id, { job_type, fingerprint, processed_pairs sorted, total_at_start })`.
- **Per-unit writes:** Each embedding write wrapped in `with library_write(lib_db):` around `upsert_image_text_embedding`.
- **Cancellation:** Frequent `if runner.is_cancelled(job_id): runner.finalize_cancelled(job_id); return` after batch flush and at end; mid-flush returns after cancel.
- **Completion:** If job already `failed` (e.g. checkpoint size), return; else `runner.clear_checkpoint(job_id)` then `runner.complete_job(job_id, result_dict)`.
- **Errors:** Broad `except Exception` → `_failure_severity_from_exception` → `runner.fail_job(job_id, str(e), severity=severity)`.
- **Result payload shape:** `{ 'embedded': int, 'skipped': int, 'failed': int, 'total': int }` (note: `failed` is not incremented on embed paths today — known gap from Phase 3 review).

**Orphan recovery:** `app._recover_orphaned_jobs` re-queues any `status=running` job whose `metadata.checkpoint` has `checkpoint_version == 1` (job-type agnostic). Any new job that calls `persist_checkpoint` with that shape gets restart-safe resume.

---

### 2. Database Schema & Migration Pattern

**`init_database`** (`lightroom_tagger/core/database.py`):

- Creates core tables with `CREATE TABLE IF NOT EXISTS`, then runs migrations: `_migrate_add_column`, `_migrate_images_schema`, indexes, `_migrate_unified_image_keys`, `_backfill_*`, `_migrate_image_descriptions_fts`, `_migrate_image_text_embeddings_vec0`, `seed_perspectives_from_prompts_dir`, `conn.commit()`.
- **Recent vec migration pattern:** `_migrate_image_text_embeddings_vec0` gates on `PRAGMA user_version` (3→4), uses `DROP TABLE IF EXISTS` + `CREATE VIRTUAL TABLE … vec0`, then bumps `user_version` (lines 773–791). For ordinary relational tables, **`CREATE TABLE IF NOT EXISTS` + indexes** (no version bump) is also idiomatic elsewhere via `_migrate_add_column`.

**`_migrate_add_column`:** `PRAGMA table_info` → `ALTER TABLE … ADD COLUMN` if missing; safe to call repeatedly.

**`library_write(conn)`:** Process-wide RLock + `BEGIN IMMEDIATE`, retry on busy, nested re-entrant support when `conn.in_transaction`. All stack writes should use this (per CONTEXT).

**`images` table (confirmed):** Primary key column is **`key`** (not `image_key`). Columns relevant to Phase 4: **`date_taken` TEXT**, **`rating` INTEGER DEFAULT 0**, **`phash` TEXT**. Index: `idx_images_date_taken`.

**`image_descriptions` table:** Has `summary`, `subjects`, `perspectives` JSON, etc. **There is no single “aggregate AI score” column.** Scoring is normalized in **`image_scores`** (per perspective, `is_current = 1`, `image_type = 'catalog'`) with **`perspectives`** defining active slugs.

**Gap vs CONTEXT D-02 wording:** CONTEXT says LEFT JOIN `image_descriptions` for aggregate score; the codebase’s established “AI strength” signal is **`image_scores` + equal-weight mean over active perspectives** (`compute_image_aggregate_scores` / `_SCORES_BASE_SQL` in `lightroom_tagger/core/identity_service.py`). Planning should implement tier-2 using that definition (e.g. subquery `AVG(s.score) … GROUP BY s.image_key` with `INNER JOIN perspectives` and `is_current = 1`), not a nonexistent column on `image_descriptions`.

**Existing stack tables:** **None** in `database.py` — `image_stacks` / `image_stack_members` must be added.

---

### 3. Checkpoint System

**`merge_checkpoint_into_metadata`:** Shallow-copies job metadata and sets `checkpoint` to `{ "checkpoint_version": 1, **checkpoint_body }` (`checkpoint.py` 174–180).

**`fingerprint_catalog_keys`:** `sorted(keys)` + `total` → SHA-256 (enrich/prepare pattern).

**`fingerprint_batch_text_embed`:** Canonical JSON includes `date_filter`, `embedding_dim`, `embedding_model_id`, `force`, `image_type`, `min_rating`, **`pairs`** = **sorted** `"key|catalog"` strings (lines 76–97). **Work-list order is not in the fingerprint; permutation of input list does not change the hash.**

**For `fingerprint_batch_stack_detect` (to add):** Mirror the above ideas:

- Include **resolved `delta_ms`** (after `metadata.get("delta_ms") or `load_config().stack_burst_delta_ms`), so config/run overrides are part of identity.
- Include **`force`** semantics: normalize bool vs literal `"preserve_edited"` (CONTEXT D-05) into the payload consistently.
- Include any **date window / `min_rating`** if the job supports the same filters as `batch_text_embed` / describe (optional but consistent).
- Include **sorted catalog keys** (or sorted `key|catalog` strings) for the **initial work queue** so new images or changed eligibility invalidate the checkpoint.

**Checkpoint body:** Same structural pattern as `batch_text_embed`: `job_type`, `fingerprint`, `total_at_start`, `processed_*` — for stacks, a **`processed_image_keys`** list (sorted on persist) or equivalent is natural; enforce `_CHECKPOINT_MAX_ENTRIES` like other handlers.

**Docstring:** Extend the module docstring in `checkpoint.py` with a **`batch_stack_detect`** bullet when implemented.

---

### 4. Config System

**`Config` dataclass** (`lightroom_tagger/core/config.py`): Fields map 1:1 from YAML keys loaded in `load_config()` via `Config(**data)` after merging `defaults` for missing keys (lines 71–112).

**To add `stack_burst_delta_ms: int = 2000`:**

1. Add field on `Config`.
2. Add default in `load_config`’s `defaults` dict (e.g. `"stack_burst_delta_ms": 2000`).
3. Optionally extend `_load_from_env` if env override is desired (not required by CONTEXT).

**Persistence:** There is **no generic “write whole config”** API. Path-specific updaters exist: `update_config_yaml_catalog_path`, `update_config_yaml_instagram_dump_path`. For stack settings, add something like **`update_config_yaml_stack_burst_delta_ms`** (read YAML, set key, `yaml.safe_dump` preserving other keys) — same style as catalog/dump.

---

### 5. Frontend Settings Panel Pattern

**`SettingsTab.tsx`:** Thin layout: heading + `<CatalogSettingsPanel />` + `<InstagramDumpSettingsPanel />` (`apps/visualizer/frontend/src/components/processing/SettingsTab.tsx`). **Insert `<StackDetectionSettingsPanel />`** after catalog/Instagram or in the same `space-y-6` list.

**`CatalogSettingsPanel` / `InstagramDumpSettingsPanel`:** Local `useState` for saved vs draft values, `useEffect` + `refresh` calling **`ConfigAPI.get*`** on mount, **Save** → **`ConfigAPI.put*`** → `refresh`. Errors surfaced as text. Instagram panel also shows **`JobsAPI.create`** — not needed for stack delta.

**API client:** `ConfigAPI` in `apps/visualizer/frontend/src/services/api.ts` uses `/config/catalog` and `/config/instagram-dump`. **New methods** should call new routes, e.g. `GET/PUT /api/config/stack-detection` with JSON `{ stack_burst_delta_ms: number }`, and `put*` should **`invalidateAll`** for any queries that depend on config if introduced (catalog/dump invalidate broad keys — stack can follow a minimal pattern or match).

**Backend:** `api/lt_config.py` — Flask blueprint `lt_config`; register **`GET`/`PUT`** routes parallel to instagram-dump; validate integer **≥ 1** (or sensible min/max). Tests follow `test_lt_config_api.py` (monkeypatch `LT_CONFIG_YAML`).

---

### 6. Job Registration

**`JOB_TYPES_REQUIRING_CATALOG`** (`apps/visualizer/backend/library_db.py`, lines 38–50): `frozenset` listing job types whose handlers open the library DB. **Add `'batch_stack_detect'`.** Comment: keep in sync with handlers that call `init_database` on library path.

**`JOB_HANDLERS`** (`handlers.py` end): **Add `'batch_stack_detect': handle_batch_stack_detect`.**

**Health/API:** `test_jobs_api.py` / `test_library_db.py` assert catalog-dependent types — extend with `batch_stack_detect`.

---

### 7. Burst Grouping Algorithm Design

**Inputs:** Candidate rows with parseable `date_taken`, sorted by capture time; parameter `delta_ms`.

**Recommended approach:**

1. **SQL:** Load `key`, `date_taken`, `rating` (and optionally pre-joined aggregate score) for candidates **not in `image_stack_members`** (incremental), with **`date_taken IS NOT NULL AND date_taken != ''`** — still validate parse in Python for “bad” strings.
2. **Parse:** In Python, `datetime.fromisoformat` or similar; **exclude** rows that fail → count toward `images_skipped_no_date` (CONTEXT D-09).
3. **Sort:** By `(timestamp, key)` ascending for deterministic burst chains.
4. **Single pass (sort-and-scan):** Walk ordered list; start a new group when `curr - prev > delta_ms` (using `.timestamp()*1000` or timedelta). **O(n)** after sort; easy to checkpoint by “number of keys scanned” or “last processed key.”
5. **Stack creation:** Only groups with **≥ 2 images** are stacks; singletons are not inserted (typical burst semantics; confirm in PLAN if single-image “stacks” are forbidden).

**SQL window alternative:** `LAG` on timestamp diff to assign `burst_id`, then `GROUP BY burst_id` — viable if timestamps are computed in SQL (`julianday`, etc.). **SQLite date format heterogeneity** makes Python parsing safer for “bad date” policy.

**Representative in one query (per stack):** Given a list of `keys` in one burst, run:

```sql
SELECT i.key
FROM images i
LEFT JOIN (
  SELECT s.image_key AS image_key, AVG(s.score) AS ai_score
  FROM image_scores s
  INNER JOIN perspectives p ON p.slug = s.perspective_slug AND p.active = 1
  WHERE s.is_current = 1 AND s.image_type = 'catalog'
  GROUP BY s.image_key
) agg ON agg.image_key = i.key
WHERE i.key IN (/* burst keys */)
ORDER BY (i.rating > 0) DESC, i.rating DESC, COALESCE(agg.ai_score, 0) DESC, i.date_taken DESC, i.key DESC
LIMIT 1;
```

This matches D-02 cascade: prefer any positive rating, then higher rating, then higher mean AI score, then latest `date_taken`, then deterministic key tie-break.

---

### 8. Schema Design

**Status:** Tables **do not exist** yet. Suggested DDL (idempotent `CREATE TABLE IF NOT EXISTS`):

```sql
CREATE TABLE IF NOT EXISTS image_stacks (
  stack_id INTEGER PRIMARY KEY AUTOINCREMENT,
  representative_key TEXT NOT NULL,
  stack_size INTEGER NOT NULL DEFAULT 0,  -- optional denormalized; can be 0 and backfilled
  user_modified INTEGER NOT NULL DEFAULT 0,  -- SQLite boolean; scaffold for Phase 7
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_image_stacks_representative
  ON image_stacks(representative_key);

CREATE TABLE IF NOT EXISTS image_stack_members (
  stack_id INTEGER NOT NULL REFERENCES image_stacks(stack_id) ON DELETE CASCADE,
  image_key TEXT NOT NULL,
  PRIMARY KEY (stack_id, image_key)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_image_stack_members_image_key
  ON image_stack_members(image_key);
```

**Notes for planner:**

- CONTEXT allows **`stack_size`** as optional denormalized field; maintain on insert/update or derive in queries.
- **`representative_key`** must be non-null (D-03); UNIQUE on `representative_key` is optional — only if representative is always a member row (it should be).
- **`user_modified`:** DEFAULT 0 for Phase 4 (D-05 / Phase 7).
- **Rebuild / force:** Delete members then stacks (or `DELETE FROM image_stacks` with CASCADE) before rebuild; respect `preserve_edited` once Phase 7 exists (Phase 4: same as full rebuild per CONTEXT).

---

### 9. Job Lifecycle Calls

| Call | Signature / location |
|------|----------------------|
| `add_job_log` | `add_job_log(db: sqlite3.Connection, job_id: str, level: str, message: str)` — `apps/visualizer/backend/database.py` |
| `update_job_field` | `update_job_field(db, job_id, field, value)` — **allowed:** `metadata`, `result`, `error`, `current_step` only |
| `runner.complete_job` | `complete_job(self, job_id: str, result: dict)` — sets status completed, progress 100, log line, stores `result` |
| `runner.fail_job` | `fail_job(self, job_id: str, error: str, *, severity: str = 'error')` — `severity` in `warning` \| `error` \| `critical` |
| `runner.persist_checkpoint` | `persist_checkpoint(self, job_id: str, checkpoint_body: dict) -> None` |
| `runner.update_progress` | `update_progress(self, job_id: str, progress: int, current_step: str)` |
| `runner.clear_checkpoint` | `clear_checkpoint(self, job_id: str) -> None` |
| `runner.finalize_cancelled` | `finalize_cancelled(self, job_id: str) -> None` |

---

### 10. Test Patterns

- **`test_handlers_batch_text_embed.py`:** Uses `tmp_path` library DB, `init_database`, `monkeypatch.setenv("LIBRARY_DB", …)`, `mock_load_config` returning `MagicMock(db_path=…)`, **`MagicMock` runner** with `runner.db = MagicMock()`, `runner.is_cancelled` False, patches `add_job_log`, replaces heavy deps (`embed_texts`). Asserts `runner.complete_job` once and inspects result dict / SQL `COUNT(*)` on `image_text_embeddings`.
- **`test_job_checkpoint.py`:** Unit tests for **fingerprint stability** (order, force flag sensitivity) — add **`fingerprint_batch_stack_detect`** tests the same way.
- **`test_orphan_recovery.py`:** Generic checkpoint v1 behavior — no change required if checkpoint shape is standard.
- **`test_lt_config_api.py`:** Monkeypatch `LT_CONFIG_YAML` to temp file; `GET`/`PUT` new stack-detection route.
- **DB tests:** Optional `test_init_database_*` pattern for new tables (grep existing `test_init_database`).

**Suggested new cases for stack job:** zero work, one burst → one stack + members + representative, incremental skip already-stacked, null `date_taken` exclusion count, checkpoint resume mid-scan, `force` rebuild clears prior stacks, fingerprint mismatch clears checkpoint.

---

## Key Risks & Unknowns

1. **ROADMAP vs CONTEXT:** ROADMAP Phase 4 still lists STACK-02 (pHash) and pHash pass; **04-CONTEXT.md drops STACK-02** for this phase. Planner should align roadmap/traceability with CONTEXT so scope is **STACK-01 only**.
2. **REQUIREMENTS traceability:** `STACK-04` still states dependency on **STACK-01 and STACK-02**; if STACK-02 is dropped long-term, dependency docs may need a later edit (out of Phase 4 implementation but affects planning honesty).
3. **D-02 vs schema:** Representative tier-2 must use **`image_scores`** (and active perspectives), not `image_descriptions` aggregates.
4. **`date_taken` quality:** TEXT field; burst logic must match catalog’s string ordering only where safe; **prefer parsed numeric time** for deltas.
5. **`failed` counter / embed pattern:** `batch_text_embed` never increments `failed`; stack job should decide whether to track partial DB failures explicitly.
6. **Checkpoint size:** Large catalogs → many keys in `processed_image_keys`; same **100k** cap as other jobs.
7. **Representative UNIQUE:** If `representative_key` has UNIQUE index, migrating representative later (Phase 7) must update row consistently with membership.

---

## Files to Modify (confirmed list)

| Area | Path |
|------|------|
| Config | `lightroom_tagger/core/config.py` |
| DB schema + helpers | `lightroom_tagger/core/database.py` |
| Checkpoint | `apps/visualizer/backend/jobs/checkpoint.py` |
| Handler + registry | `apps/visualizer/backend/jobs/handlers.py` |
| Catalog job types | `apps/visualizer/backend/library_db.py` |
| Config API | `apps/visualizer/backend/api/lt_config.py` |
| Frontend API | `apps/visualizer/frontend/src/services/api.ts` |
| Settings UI | `apps/visualizer/frontend/src/components/processing/SettingsTab.tsx` |
| New panel | `apps/visualizer/frontend/src/components/processing/StackDetectionSettingsPanel.tsx` (or `components/images/` — CONTEXT says processing folder; mirror import path) |
| Tests | `apps/visualizer/backend/tests/test_handlers_batch_text_embed.py` (reference), **new** `test_handlers_batch_stack_detect.py`, `test_job_checkpoint.py`, `test_lt_config_api.py`, `test_library_db.py`, `test_jobs_api.py` |
| Optional | `lightroom_tagger/core/test_init_database_*.py` or existing DB migration tests if present |

*Optional doc-only:* `.planning/ROADMAP.md` Phase 4 bullets — update when planning STACK-02 descope officially.
