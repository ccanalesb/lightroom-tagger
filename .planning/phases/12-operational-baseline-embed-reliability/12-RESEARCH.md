# Phase 12 Research: Operational baseline & embed reliability

## Executive Summary

Most embed plumbing (`skip_reason_counts`, preflight sampling, `JobDetailModal` wiring) already exists but **does not yet match Phase 12 decisions**: preflight aborts only at **100%** sampled failures (`_EMBED_PREFLIGHT_FAIL_RATIO = 0.7` is used for warnings, not hard fail), OPS-03 UI still shows **all** reason rows (including zeros and `encode_failed`) with labels that diverge from the locked copy in `12-UI-SPEC.md`, and OPS-04 log spam comes from **`compress_image()` unconditionally `print`-ing on every JPEG pass** inside `_describe_image_via_provider()`—so **every** catalog describe re-compresses the (possibly cached) input and emits a line **even when a vision-cache hit already returned a compressed path**. OPS-05 `TestDefaults` is **green** in this checkout. OPS-01 is likely a **narrow frontend sweep**: only **SearchPage** presently surfaces `no_clip_embedding`; there is **no** TS consumer of `GET …/similar`’s `"Visual similarity is unavailable"` string today.

---

## OPS-01: Embed Job Discoverability

### Current State

**Backend pathways**

- **`no_clip_embedding` metadata:** `_chat_pin_context()` in ```86:104:apps/visualizer/backend/api/images.py``` catches `NoClipEmbeddingError` from `list_pin_similarity_candidate_keys` and returns `{"pin_state": "inactive", "fallback_reason": "no_clip_embedding"}`.

- **`"Visual similarity is unavailable"` HTTP:** ```913:941:apps/visualizer/backend/api/images.py``` maps `NoClipEmbeddingError` from `run_clip_similar_for_seed` to **404** JSON `"Visual similarity is unavailable"`.

**Frontend surfaces (repo-wide)**

- **`no_clip_embedding`:** **`SearchPage.tsx` only** — chat response metadata drives `pinInactiveReason` / `pinSimilarityWarning` and renders help + **`Link`** targets **`PROCESSING_CATALOG_CACHE_ROUTE`** and **`PROCESSING_JOB_QUEUE_ROUTE`** (~lines 423–446, 462–483) using **`SEARCH_PIN_HELP_EMBED`**, **`SEARCH_PIN_LINK_CACHE`**, **`PROCESSING_OPEN_JOB_QUEUE`**.

- **Literal `"Visual similarity is unavailable"` in frontend:** **no matches** (`rg` over `apps/visualizer/frontend`). The catalog similar route is unused by current UI (`ImageDetailModal` test asserts on-demand similarity was removed).

**Implication:** Surfaces **other than SearchPage that need OPS-01** are **not present in code today** unless new call sites appear (e.g. a future component calling `ImagesAPI` `…/similar`) or undocumented routes. Phase work is **`rg`-driven sweep** + align any **new** similarity-unavailable UX to the SearchPage pattern documented in **`12-UI-SPEC.md`** (reuse **`SEARCH_PIN_HELP_EMBED`** / **`SEARCH_PIN_LINK_CACHE`** / **`PROCESSING_JOB_QUEUE_ROUTE`** parity).

### Implementation Approach

1. Sweep: `grep` / `rg` for `no_clip_embedding`, `NoClipEmbeddingError`, `fallback_reason`, `Visual similarity`, `similar`/catalog similar usage in **`*.tsx`**, **`*.ts`**.

2. For each hit (today: **confirm SearchPage-only**): add the same **`Link`** block pattern as ```428:446:apps/visualizer/frontend/src/pages/SearchPage.tsx``` (idle + results branches).

3. Constants already live in ```562:566:apps/visualizer/frontend/src/constants/strings.ts``` (among others)—**do not fork copy** per `12-UI-SPEC`.

4. **`CatalogCacheTab.tsx`:** already the Processing embed entry point; OPS-01 does **not** require new triggers there unless a **separate** error surface is found.

### Risks

- **False-negative sweep** if similarity errors are surfaced via generic HTTP error handlers without substring match—extend search to **`404`** handling on image/similar endpoints if such a client is added.

- **REQUIREMENTS.md OPS-01** text still says “trigger directly from error state”; **phase CONTEXT (D-01)** overrides with **navigation link only**. Plans must follow **CONTEXT / UI-SPEC**, not stale requirement wording.

---

## OPS-02: Path-Failure Preflight

### Current State

**Module constants** (`handlers.py`):

- `_EMBED_PREFLIGHT_SAMPLE_SIZE = 25` (within stakeholder **20–50** range).
- `_EMBED_PREFLIGHT_FAIL_RATIO = **0.7**` — used **only** to decide whether to emit the soft **warning** branch, **not** to hard-abort except at **100%** sample failure.
- **Test RNG:** `_PREFLIGHT_RNG_SEED: int | None = None` (CONTEXT referred to `_EMBED_PREFLIGHT_SEED`; **actual hook is `_PREFLIGHT_RNG_SEED`** at ```72:75:apps/visualizer/backend/jobs/handlers.py```). Tests monkeypatch **`job_handlers._PREFLIGHT_RNG_SEED`**.

**Preflight logic snapshot** (~```2940:3005:apps/visualizer/backend/jobs/handlers.py```):

1. Builds `sample_failures` only for **`no_row`**, **`empty_path`**, **`unresolved_or_missing`** (**not** `encode_failed`; compression failures are exercised separately via `classify_path` after preflight).

2. Random `sample()` over `remaining` keys (deterministic when seed set).

3. `fail_ratio = sample_failed_count / sample_size`.

4. **`if fail_ratio >= _EMBED_PREFLIGHT_FAIL_RATIO`:**
   - **Always** builds `preflight_msg` and branches:
   - **Hard stop** only when **`fail_ratio >= 1.0` and not `chain_mode`:** `runner.fail_job(... severity='critical')`.
   - Otherwise **`add_job_log` warning** `"Continuing — missing files will be skipped per-file."**

5. **`_catalog_cache_chain`:** **`chain_mode`** — even **100%** sample failure **does not** fail the job (**test_batch_embed_image_preflight_does_not_abort_in_chain_mode**).

**Gap vs D-03–D-06:** Decision **D-04** requires **>**50%** unreachable → **hard stop** with a **single actionable message** (counts + NAS/mount hypothesis + retry). **Current code conflicts:** >50% but <100% continues with a warning.

**Classification alignment:** **`unreachable`** in CONTEXT maps to existing **`unresolved_or_missing`** plus **`empty_path`** plus **`no_row`** — already counted in `sample_failed_count`.

### Implementation Approach

1. **Introduce explicit threshold constant** or repurpose **`_EMBED_PREFLIGHT_FAIL_RATIO`** to **`0.5`** and treat **`>` half** as:  
   **`sample_failed_count * 2 > sample_size`** (strict **>** 50%; edge case exactly 50% is **continuation** vs **abort** — planner must pick one sentence in CONTEXT).

2. **On abort:** `update_job_status` / **`runner.fail_job`** with message shape like **"`{n}/{sample_size}` sampled paths unreachable — … mounted share … Retry after mount."** (CONTEXT example); **`add_job_log(..., 'error', ...)`** once (see job-log contract).

3. **Bypass full embed loop:** return before iterating `remaining` when aborted (mirror early return after `fail_job` today at 100%).

4. **Keep `chain_mode` exception** unless CONTEXT is updated — today tests expect **warn-only** even at 100% in chain (**```938:986:apps/visualizer/backend/tests/test_handlers_batch_embed_image.py```**).

5. **Adjust / add tests:**
   - **`test_batch_embed_image_preflight_warns_and_continues_on_partial_miss`** — currently **7/8** missing with **`_EMBED_PREFLIGHT_FAIL_RATIO`** patched to **0.5**: job **continues**. Under D-04 this becomes an **abort** case → **rewrite** or **rename** to **failure** expectation.
   - **`test_batch_embed_image_preflight_fails_fast_when_paths_inaccessible`** — asserts **100%** sample fail; stays valid as one case; add **`>50%` but `<100%`** abort case.

### Risks

- **Breaking users** who relied on **soft continuation** at 60–99% misses—product intent in Phase 12 is **fail-fast** for mount catastrophes.

- **Sample randomness:** reproduce failures in CI via **`_PREFLIGHT_RNG_SEED`** and small synthetic DBs (**existing pattern** in tests).

- **`encode_failed`** deliberately excluded from preflight sample (**```2942:2946:apps/visualizer/backend/jobs/handlers.py```**) — aligns with skipping “compression unavailable” false positives (**```659:704:apps/visualizer/backend/tests/test_handlers_batch_embed_image.py```**).

---

## OPS-03: "Why Skipped" Summary

### Current State

**Backend result payload** on success (**```3124:3132:apps/visualizer/backend/jobs/handlers.py```**):

```python
{
  'embedded': int,
  'skipped': int,
  'failed': int,
  'total': int,
  'skip_reason_counts': {
    'no_row': int,
    'empty_path': int,
    'unresolved_or_missing': int,
    'encode_failed': int,
  },
}
```

Zeros are still written for every key on completion / zero-work (**```2815:2820```**).

**Semantic mapping to D-07**

| Decision label   | Existing key                   |
|-----------------|--------------------------------|
| Missing file    | **`unresolved_or_missing`** (+ possibly treat **`encode_failed`** separately per UI-SPEC) |
| Empty path      | **`empty_path`**               |
| No DB row       | **`no_row`**                   |

**UI today:** **`JobDetailModal.tsx`** (**```299:315, 466:477```**) reads **`skip_reason_counts`**, builds **`embedReasonCounts`** from **`EMBED_REASON_LABELS`**:

- ```345:349:apps/visualizer/frontend/src/constants/strings.ts``` — **`Missing catalog row`**, **`Missing filepath`**, **`Path missing/unreachable`**, **`Encode failed`** — **not** the exact **UI-SPEC** strings (**Missing file**, **Empty path**, **No DB row**).

**Visibility:** **`embedReasonCounts.map`** renders **every** keyed row regardless of **`count === 0`** (**contradicts D-09 / UI-SPEC**).

**12-UI-SPEC** additionally suggests **narrowing visible rows to three buckets** for the OPS-03 table; **`encode_failed`** may remain in JSON / full result preview only—**plan must reconcile D-07 (three buckets)** vs legacy fourth bucket (**decision for planner**).

### Implementation Approach

1. **Backend (optional tightening):** If planners want stable API names matching UI, could add **`skip_breakdown`** alias or rename keys — **prefer** keeping **`skip_reason_counts`** keys stable and **only changing UI mapping** unless other clients depend on strings (unlikely).

2. **Frontend:**  
   - New **string constants** per **UI-SPEC** table (centralized in **`strings.ts`**).  
   - Map **`unresolved_or_missing` → Missing file**, **`empty_path` → Empty path**, **`no_row` → No DB row**.  
   - **`.filter(({ count }) => count > 0)`** before render.  
   - If **`encode_failed`** remains a first-class ops metric, either a **fourth conditional row** (if count > 0) or **defer** per UI-SPEC “out of scope” note.

3. **Hide entire card** when no reason has **count > 0** (unless product wants aggregate title always—UI-SPEC says hide or show nothing).

4. **Vitest:** extend **`JobDetailModal`** tests (if present) or add focused test with **mock job.result.skip_reason_counts**.

### Risks

- **Double-truth:** raw JSON preview in modal shows machine keys vs friendly labels — acceptable.

- **Instagram `catalog_and_instagram` scope:** `no_row` can mean missing **catalog row or dump row** — label **“No DB row”** remains accurate enough; refine copy only if UX feedback says otherwise.

---

## OPS-04: Compression Log Noise

### Current State

**Orphan recovery** (**```170:206:apps/visualizer/backend/app.py```**) re-queues **`running`** jobs with **checkpoint v1** to **`pending`**—**no compression** here. OPS-04 is **not** a bug in **`_recover_orphaned_jobs`**.

**Resume path:** pending **`batch_analyze`** runs **`_handle_batch_analyze_inner` → `_run_describe_pass`** (**```2393:2404```** with **`nested_analyze_checkpoint=True`**).

**Noise source:**

- **`compress_image`** in ```158:202:lightroom_tagger/core/analyzer.py``` prints **` Compressed: …KB -> …KB`** (and **`Compression failed: …`** on errors) **`flush=True`** to **stdout**.

- **`_describe_image_via_provider`** (**```376:383:lightroom_tagger/core/analyzer.py```**) **always** calls **`compress_image(viewable)`** on the path passed to **`describe_image`**.

- **`describe_matched_image`** (**```84:92:lightroom_tagger/core/description_service.py```**) uses **`get_or_create_cached_image`** then passes **`cached_path` or filepath** into **`describe_image`** — so **cache hits avoid DB/file work** but **`describe_image` still re-compresses** to new temp JPEGs ⇒ **log line every image**.

### Implementation Approach

1. **Silent path (match D-10/D-11):**  
   - **Option A (localized):** add **`silent: bool`** (or **`log_compression=...`**) to **`compress_image`**; **`_describe_image_via_provider`** passes **`silent=True`** when **`is_vision_cache_valid`** OR when input already under cache-dir / already JPEG under size ceiling — planner defines rule.  
   - **Option B (broader):** replace **`print`** with **`logging.debug`** behind logger — removes terminal flood globally but loses quick stdout unless logging configured.

2. **Summary log:** In **`_run_describe_pass`**, when **`nested_analyze_checkpoint`** is **True**, count images where **`get_or_create_cached_image`** returned valid path **`and`** describe skipped re-compression (**instrumentation** from **Option A**) — **`add_job_log(..., 'info', …)`** once after the describe stage with D-11 wording (e.g. “N images already compressed, skipped.”), **only if N > 0**. Alternatively count inside **`describe_matched_image`** via callback — more invasive.

3. **`prepare_catalog`** path already distinguishes **`already_cached`** vs **`newly_cached`** — pattern reference **```988:1053:apps/visualizer/backend/jobs/handlers.py```**.

### Risks

- **Operational visibility:** removing prints without **`DEBUG`** fallback may hinder local troubleshooting—prefer **structured job log summary** (`D-11`) + optional debug logging.

- **Instagram describes** (`describe_instagram_image`) bypass **`get_or_create_cached_image`** (**```127:131:description_service.py```**) ⇒ still hit **`compress_image`** every call—scope **CONTEXT** mentions **`batch_analyze`** specifically; clarify whether Instagram branch needs same treatment.

---

## OPS-05: TestDefaults Verification

### Current State

**`tests/test_providers_api.py` — `TestDefaults`**

1. **`test_should_return_defaults`:** `GET /api/providers/defaults` **200**, JSON **`vision_comparison.provider`** and **`description.provider`** equal **`ProviderRegistry().defaults`** (asserts live registry—not hardcoded).

2. **`test_put_defaults_should_update_defaults`:** **PATCH**‑style **`PUT`** with mocked **`ProviderRegistry`** merge.

3. **`test_put_defaults_should_reject_empty_body`**, **`test_put_defaults_should_reject_invalid_key`.**

**Executed:** `pytest apps/visualizer/backend/tests/test_providers_api.py::TestDefaults` → **4 passed** (checkout **2026-05-05**).

---

## Validation Architecture

### Test Coverage Plan

| Area | Existing | Extend / Add |
|------|----------|----------------|
| **Embed preflight** | **`test_handlers_batch_embed_image.py`** — exhaustive preflight suite | Update expectations for **`>50%`** abort; add middle case; preserve **chain_mode** behavior |
| **Skip counts** | **`test_batch_embed_image_reports_grouped_skip_reason_counts`** | Assert payload keys stable after any rename; frontend filter **> 0** |
| **Orphan recovery** | **`test_orphan_recovery.py`** — `batch_analyze` v1 checkpoint re-queue | Optionally add assertion that restarting describe does **not** spam logs—likely **heavy** / better as **analyzer** unit test **`compress_image` silent flag** |
| **Providers defaults** | **`test_providers_api.py::TestDefaults`** | Re-run **`pytest …::TestDefaults -x`** at phase kickoff (**D-12**) |

**Suggested new tests**

1. **`test_compress_image_silent`** (or **`test_describe_via_provider_skips_duplicate_compression_logs`**) — `capsys` or mock `print`.

2. **`JobDetailModal` RTL** — embed diagnostics shows **only** non-zero buckets with UI-SPEC labels.

---

## Implementation Order

1. **OPS-05** — zero code if green; unblock CI conscience (**minutes**).

2. **OPS-02 + tests** — behavior change touches **`handlers.py`** and several **`test_handlers_batch_embed_image`** cases; **`job-handler-clear.sh` / UI contract:** touch **`CatalogCacheTab.tsx`** or **ProcessingPage** minimally if hooks require (**per `.cursor/rules/job-ui-contract.mdc`**).

3. **OPS-04** — **`analyzer.py` / description_service.py` / optional `_run_describe_pass` summary** — orthogonal to OPS-02; pair with **`test_handlers_batch_analyze.py`** or **`compress_image`** unit test.

4. **OPS-03** — frontend-only string + filter changes + Vitest (**depends** on finalized payload naming—likely **parallel** once OPS-02 backend freeze).

5. **OPS-01** — confirm sweep (**likely no TS changes** besides comments or **one** latent consumer discovered).

**Dependencies**

- OPS-03 **consumes** same **`skip_reason_counts`** OPS-02 does not erase (preflight abort may skip payload—failure path uses **`fail_job`** not **`skip_reason_counts`** breakdown).

---

## RESEARCH COMPLETE
