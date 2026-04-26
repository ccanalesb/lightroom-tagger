# Phase 8 research: Two-stage cascade matching (description batch + vision batch)

**Purpose:** Answer “What do I need to know to PLAN this phase well?” for implementing MATCH-01..MATCH-04 (see `.planning/ROADMAP.md` Phase 8 success criteria).

**Sources:** `08-CONTEXT.md`, `ROADMAP.md` Phase 8, `lightroom_tagger/core/matcher.py`, `lightroom_tagger/core/vision_client.py`, `lightroom_tagger/scripts/match_instagram_dump.py`, `apps/visualizer/backend/jobs/handlers.py`, `apps/visualizer/backend/jobs/checkpoint.py`, frontend `matchOptionsContext` / `AdvancedOptions` / `MatchingTab`, tests under `lightroom_tagger/core/test_matcher.py` and `apps/visualizer/backend/tests/test_handlers_single_match.py`.

---

## 1. Current implementation analysis

### 1.1 `find_candidates_by_date` (`matcher.py` ~601–634)

- **What it returns:** A **list of catalog image dicts** produced by `_deserialize_row` over `SELECT * FROM images` (full table scan), then filtered by:
  - `date_folder` on the Instagram row (must be 6 chars `YYYYMM`)
  - `date_taken` within `[window_start, post_date]` (90-day window by default)
  - **Video exclusion** via `VIDEO_EXTENSIONS` on file extension
- **Join with `image_descriptions`:** **No.** There is **no** `LEFT JOIN` today. The `images` table has its own `description` column (Lightroom/metadata caption), which is **not** the AI summary in `image_descriptions.summary`.
- **Implication for Phase 8:** SC-1 requires attaching **`image_descriptions.summary`** (catalog `image_type = 'catalog'`). Planner must choose SQL shape (e.g. `LEFT JOIN image_descriptions d ON i.key = d.image_key AND d.image_type = 'catalog'`) and a **clear field name** on the row dict so it does not silently confuse Lightroom `images.description` with AI summary (see §7).

### 1.2 `score_candidates_with_vision` (`matcher.py` ~136–548)

- **`desc_weight` / `vision_weight` today:** Both batch and sequential paths compute a **weighted total** from phash, **local** `text_similarity(insta, candidate)` on `insta_image['description']` and `candidate['description']`, and vision.
- **Important:** `text_similarity` is **Jaccard-like overlap on whitespace-split words** (`matcher.py` ~66–80), **not** an LLM semantic score. There is **no** `compare_descriptions_batch` call today.
- **`desc_available` gating:** If either side’s description string is empty/whitespace, **`desc_weight` is dropped** from `active_weights`, and remaining weights are **re-normalized** so their sum is 1 (`weight_sum` division). That **silently redistributes** description weight to phash/vision when the text signal is “missing” (batch path ~287–297, sequential ~494–504).
- **Conflict with 08-CONTEXT D-10:** Decisions require **no silent redistribution** when the description stage yields no usable scores (e.g. all candidates skipped as undescribed). **Planning must explicitly reconcile** legacy renormalization vs new cascade semantics (see §7).
- **`vision_weight`:** Always included in `active_weights['vision']` when vision ran; if vision did not run for a candidate, behaviour differs (batch zero-score path vs sequential).
- **Batch vision:** Uses `_call_batch_chunk` → `compare_images_batch` with **numeric candidate indices** matching enumerate order. Chunk size comes from **`batch_size`** (from caller; `match_instagram_dump` passes `config.vision_batch_size`, default **10** in `core/config.py` — roadmap text says “20” as product language; **verify config/env** vs SC-3 wording).
- **Instagram compression:** `InstagramCache.compress_instagram_image` runs **once per `score_candidates_with_vision` call** before the batch loop (~168–180), **unconditional** on weights. For **`vision_weight=0`**, Phase 8 (SC-4) requires **skipping** compression, vision cache, and vision API — planner must add **early branches** before this work.

### 1.3 `match_dump_media` (`match_instagram_dump.py` ~37–247) — orchestration

1. Resolve **unprocessed** Instagram dump rows (filters: `media_key`, date filters, or default queue).
2. **`find_candidates_by_date`** → catalog candidates; apply **rejected-pairs** filter.
3. Build **`dump_image`** for scoring:
   - `description` is set from **`dump_media.get('caption', '')`** — **Instagram post caption**, not `image_descriptions.summary` for the Instagram key.
4. Build **`vision_candidates`**: for each catalog row, `description` = **`catalog_img.get('description', '')`** — i.e. **Lightroom `images.description`**, not AI summary unless the join/population changes this.
5. **`score_candidates_with_vision`** with weights from job/config, `batch_size=config.vision_batch_size`, `batch_threshold=config.vision_batch_threshold`.
6. **Threshold filter:** `above_threshold = [r for r in results if r['total_score'] >= threshold]`; best match persisted.
7. **After match:** `describe_matched_image` / `describe_instagram_image` for **post-hoc** description generation (separate from matching signal).

**Broken “description signal” (root cause):** Catalog AI summaries live in **`image_descriptions.summary`**; matching uses **`images.description` + Instagram caption**. Phase 8 fixes this by join + **reference text = AI summary for Instagram** (08-CONTEXT D-02, D-03) and **catalog summaries** in the batch comparator.

---

## 2. `compare_images_batch` template (for `compare_descriptions_batch`)

**Location:** `lightroom_tagger/core/vision_client.py` ~172–315.

### Signature

```python
def compare_images_batch(
    client: openai_sdk.OpenAI,
    model: str,
    reference_path: str,
    candidates: list[tuple[int, str]],
    log_callback: LogCallback = None,
    max_tokens: int = 4096,
) -> dict[int, float]:
```

- **`candidates`:** `(candidate_id, path)` — IDs are **caller-defined integers** (matcher uses enumerate index).
- **Return:** `dict[int, float]` mapping **candidate id → confidence 0–100** (not 0–1). Empty `candidates` → `{}`.

### Prompt / response contract

- Model must return JSON with **`{"results": [{"id": <int>, "confidence": <0-100>}, ...]}`**.
- Parsing: strips optional ` ```json ` fences; reads `parsed["results"]`; for each item, `result_map[cid] = float(confidence)`.
- **Parse failure:** Logs warning, returns **`{cid: 0.0 for cid, _ in candidates}`** (all zeros, no raise).

### Errors

- SDK exceptions mapped via **`_map_openai_error`** (`vision_client.py` ~65–114) to **`ProviderError`** subclasses (`RateLimitError`, `PayloadTooLargeError`, `ContextLengthError`, etc.).
- **Claude:** `extra_body={"reasoning_effort": "none"}` when `"claude"` in model name (batch path ~243–245).

### Planner notes for `compare_descriptions_batch`

- **Same return shape** as above (`dict[int, float]`) per 08-CONTEXT D-04; implement with **`complete_chat_text`-style** messages (see `complete_chat_text` ~362–395) — **text-only** user/system content, **no** `_image_url_part`.
- Reuse **`_map_openai_error`** for identical error semantics.
- Consider parallel **max_tokens / JSON repair** behaviour to `compare_images_batch` (parse fallback returns zeros).

---

## 3. Integration points (exact areas to touch)

| Area | File / symbol | Change |
|------|----------------|--------|
| **Catalog AI summaries** | `find_candidates_by_date` (`matcher.py`) | Replace or augment `SELECT * FROM images` with **`LEFT JOIN image_descriptions`** (`image_type = 'catalog'`), expose `summary` (or merged field) on each candidate dict. |
| **Insta reference text** | `match_dump_media` (`match_instagram_dump.py`) | Load **AI summary** for `media_key` (DB lookup or join on dump query); **on-the-fly** `generate_description` if missing (D-03) before scoring. |
| **Two-stage scoring** | `score_candidates_with_vision` (`matcher.py`) | If `desc_weight > 0`: run **`compare_descriptions_batch`** per chunk **before** vision; merge scores with existing weight math **per 08-CONTEXT**; if `vision_weight > 0`: keep vision batch path; if `vision_weight == 0`: **skip** compression, vision API, vision cache. |
| **Vision batch helper** | `_call_batch_chunk` / `_score_and_store` (`matcher.py`) | Today `_score_and_store` only consumes **vision** confidences; will need **description confidences** fed into merged `desc_similarity` (or renamed semantic score 0–1) and possibly **skip** `store_vision_comparison` when no vision run. |
| **Job option** | `handle_vision_match` (`handlers.py` ~296–448) | Read **`skip_undescribed`** from `metadata` (default `true`), pass to **`match_dump_media`**; extend **`fingerprint_vision_match`** (`checkpoint.py` ~102–132) so checkpoint resume includes this flag. |
| **Checkpoint** | `fingerprint_vision_match` | Add **`skip_undescribed`** (and any new kwargs) to the canonical payload **or** document why fingerprint excludes them (prefer including for resume correctness). |

---

## 4. Frontend state flow (weights + future `skipUndescribed`)

### `matchOptionsContext.tsx`

- **State:** `MatchOptions`: `providerId`, `providerModel`, `threshold`, **`phashWeight`**, **`descWeight`**, **`visionWeight`**, `maxWorkers`.
- **Defaults:** `phashWeight: 0`, `descWeight: 0`, `visionWeight: 1` (description stage off by default in UI).
- **`updateOption`:** `setOptions((prev) => ({ ...prev, [key]: value }))` — **generic**; new fields extend `MatchOptions` + `DEFAULT_OPTIONS` the same way.
- **`weightsError`:** Fires when `phash + desc + vision ≠ 1` (`ADVANCED_WEIGHTS_MUST_SUM`).

### `AdvancedOptions.tsx`

- Receives **individual props** (`phashWeight`, `onPhashWeightChange`, …) — **not** the raw context object.
- **`MatchingTab`** spreads `{...options}` into `AdvancedOptions`, so new options need: **type**, **default**, **wiring** in `MatchingTab` (`onXChange={(v) => updateOption('x', v)}`).

### `MatchingTab.tsx` → job payload (~44–54)

- Builds `metadata`:
  - `threshold`
  - **`weights`: `{ phash, description, vision }`** — maps from `options.phashWeight`, `options.descWeight`, `options.visionWeight`
  - `max_workers`, optional `provider_id`, `provider_model`
  - Date: `last_months` or `year`
- **Pattern for `skip_undescribed`:** Add e.g. **`skip_undescribed: options.skipUndescribed`** (snake_case) alongside weights; mirror **`force_descriptions`** style boolean metadata already consumed in `handle_vision_match`.

---

## 5. Test infrastructure

### `lightroom_tagger/core/test_matcher.py`

- **`score_candidates_with_vision`:** Heavy use of **`unittest.mock.patch`** for `compare_with_vision`, `get_vision_comparison`, `InstagramCache`, `get_or_create_cached_image`, `ProviderRegistry`, **`compare_images_batch`** / **`_call_batch_chunk`**, `hamming_distance`.
- **`find_candidates_by_date`:** **`TestFindCandidatesByDate`** uses **`MagicMock`** DB with `execute().fetchall()` returning row dicts — asserts **video exclusion**.
- **New tests should:** Mock **`compare_descriptions_batch`** (once added), assert **call order** (description before vision per chunk), **`vision_weight=0`** → no vision client calls, and **weight merge** edge cases per D-10.

### `apps/visualizer/backend/tests/test_handlers_single_match.py`

- Patches **`match_dump_media`**, **`init_database`**, **`load_config`**, etc.
- Asserts **kwargs** passed to `match_dump_media` (`media_key`, **`weights`**).
- **Extend with:** `skip_undescribed` forwarded; optionally fingerprint test if exposed.

### Other related tests

- `lightroom_tagger/core/test_description_service.py` — patches `match_dump_media` / `find_candidates_by_date` for describe-after-match behaviour.

---

## 6. Risk areas

### 6.1 Backward compatibility (`vision_weight=1`, `desc_weight=0`)

- Default UI already uses **pure vision** weights. Pipeline must **skip** description batch and keep behaviour aligned with **current** vision + phash path (SC-7).
- Any change to **`desc_available` renormalization** affects totals even when `desc_weight=0` — verify **no unintended change** to pure-vision scores.

### 6.2 Weight redistribution vs 08-CONTEXT D-10

- **Current code:** Missing empty descriptions cause **desc weight to be removed** and **phash/vision weights scaled up**.
- **Phase 8 decision:** When description stage contributes **nothing** (all skipped), **do not** move that mass to vision — **explicit conflict** with current `active_weights` / `weight_sum` logic. Planning must specify the **new merge algorithm** (likely: fixed nominal weights for stages that ran; zero contribution for skipped stages).

### 6.3 `images.description` vs `image_descriptions.summary`

- Two different semantics; join must not confuse **Lightroom caption** with **AI summary** for scoring. Prefer explicit keys in candidate dicts or a single documented merge rule in `match_dump_media`.

### 6.4 Instagram reference text

- Today **`caption`** drives `insta_image['description']`. Phase 8 switches reference to **AI summary** (+ optional inline describe). **Tests** should cover: summary present, missing + `skip_undescribed` true/false, missing + inline describe.

### 6.5 DB / performance

- `find_candidates_by_date` currently scans **all** `images`. Adding `LEFT JOIN` keeps cost similar; long-term index on `date_taken` may help — **out of scope** unless planner chooses to optimize.

### 6.6 Vision cache / DB writes

- **`store_vision_comparison`** is called in batch `_score_and_store` for every scored candidate. If **`vision_weight=0`**, avoid storing **vision** rows or define semantics (SC-4).

### 6.7 Checkpoint resume

- If **`skip_undescribed`** or description-stage inputs change fingerprint, **in-flight jobs** must **not** silently reuse old checkpoints incorrectly.

---

## 7. Planning recommendations (suggested plan breakdown)

Suggested **3 plans** (waves as needed):

1. **Data + API layer**
   - SQL / `find_candidates_by_date` join + field naming; **`compare_descriptions_batch`** in `vision_client.py` (mirror `compare_images_batch` + tests).
   - Unit tests for parsing, error mapping, empty candidates.

2. **Matcher cascade + `match_dump_media`**
   - Instagram + catalog summary loading; inline describe for Instagram when allowed; **`skip_undescribed`** behaviour for catalog candidates; **`score_candidates_with_vision`** two-stage loop with **`vision_weight=0`** fast path (no compression / no vision API / no vision cache).
   - Extend **`test_matcher.py`** with mocked batch description + vision ordering.

3. **Handler + frontend + checkpoint**
   - `handle_vision_match`: metadata + **`fingerprint_vision_match`** update; **`MatchingTab` metadata** + **`AdvancedOptions`** toggle (disabled when `descWeight === 0`, default ON).
   - **`test_handlers_single_match`** + optional frontend test for payload.
   - Document **MATCH-01..04** traceability in phase `PLAN.md` / verification.

---

## Requirement traceability (Phase 8)

| ID | Anchor (from roadmap / context) |
|----|----------------------------------|
| **MATCH-01** | SC-1: `find_candidates_by_date` attaches AI summaries (`image_descriptions.summary`). |
| **MATCH-02** | SC-2: `compare_descriptions_batch` — one insta summary + N catalog summaries, same JSON shape as vision batch. |
| **MATCH-03** | SC-3, SC-4, SC-7: per-batch ordering; `vision_weight=0`; backward-compatible pure vision. |
| **MATCH-04** | SC-5–SC-8: `skip_undescribed`, weight-merge correctness, UI toggle + weights. |

---

## RESEARCH COMPLETE
