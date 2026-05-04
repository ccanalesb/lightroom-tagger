---
phase: 4
status: needs_work
reviewed: 2026-04-24
findings: 7
---

# Phase 4 — Stack detection: code review

## Scope

Reviewed the Phase 4 implementation: `image_stacks` / `image_stack_members` migration, `stack_burst_delta_ms` config, `/api/config/stack-detection`, `batch_stack_detect` handler, checkpoint fingerprint, frontend settings panel, and associated tests (paths per task description).

## Strengths

- **Burst core logic** — `_build_burst_segments` filters unparsable dates, sorts by `(timestamp, key)` for stability, and splits on `gap_ms > delta_ms` so the window is well-defined. Single-image runs advance checkpoint without creating empty stacks.
- **Schema** — Idempotent `CREATE TABLE IF NOT EXISTS`, `ON DELETE CASCADE` from `image_stacks` to `image_stack_members`, `UNIQUE(image_key)` on members, and `UNIQUE(representative_key)` on `image_stacks` are appropriate for v1.
- **Checkpointing** — `fingerprint_batch_stack_detect` includes `delta_ms`, `force_mode`, and a sorted key list; mismatch clears resume with a log line. `processed_image_keys` is capped and persisted after each segment.
- **Force / incremental** — `DELETE FROM image_stacks` for full-like modes; incremental work list excludes existing members. `preserve_edited` is explicitly documented as alias until STACK-05.
- **Tests** — Solid handler scenarios (empty catalog, burst + representative, no-date, incremental skip, `force` rebuild, resume). API + fingerprint tests cover the new surface; production INSERT placeholder fix (three `?`) is reflected in the implementation.

## Findings

### 1. Critical — Config source mismatch for `stack_burst_delta_ms` (job vs settings API)

- **Issue:** `GET/PUT /api/config/stack-detection` in `lt_config.py` uses an explicit repository-root `load_config(LT_CONFIG_YAML)`. `handle_batch_stack_detect` uses `load_config()` with the default `config_path="config.yaml"`, i.e. **the process current working directory** (typically `apps/visualizer/backend` per `library_db.py` comments), not the repo `config.yaml`.
- **Effect:** The UI can persist a custom burst window to the root `config.yaml` while the job still resolves `stack_burst_delta_ms` from a different file, missing file (defaults), or an unrelated local `config.yaml` — so the end-to-end “saved in Settings, used by `batch_stack_detect`” story is not reliable unless the caller passes `delta_ms` in job metadata.
- **Recommendation:** Resolve the library catalog config the same way as other server paths (e.g. `load_config` with the same repo-root path used in `library_db` / `lt_config`, or a shared helper). Add an integration test that does **not** mock `load_config` and proves the value written via the config API is what the handler reads (or document that only `metadata.delta_ms` is supported).

### 2. Important — `force` normalization ignores string forms

- **Issue:** `_normalize_stack_detect_force` only treats `metadata["force"] is True` as full and the literal `"preserve_edited"` for that mode. A JSON body like `"force": "full"` is truthy but **not** `is True`, so it falls through to **incremental** — easy mistake for API clients.
- **Recommendation:** Accept `"full"` / `"incremental"` explicitly, or coerce string `"true"`/`"full"`, and document the contract in the job API. Add a one-line test.

### 3. Important — Documented limitation of incremental mode (not a code bug)

- **Issue:** Docstring correctly states incremental work does not re-evaluate neighbors against prior stacks. Stacking can be wrong if the catalog gains new images that should join an existing edge burst. This is a product/algorithm limitation, not hidden.
- **Recommendation:** Keep in user-facing docs; optional future: periodic `force: true` or smarter boundary merge.

### 4. Suggestion — `stacks_updated` is always `0`

- **Issue:** Result shape includes `stacks_updated` for D-11 parity, but the handler only increments `stacks_created` and `images_stacked`. Always zero may confuse consumers.
- **Recommendation:** Remove from response until implemented, or set explicitly to `0` with a code comment in `complete_job` call (already effectively zero).

### 5. Suggestion — Misleading completion log on empty work list

- **Issue:** When `total_at_start == 0`, the log string still says `0 images skipped (no date_taken)`, which is wrong when the reason is an empty work list.
- **Recommendation:** Branch the message (empty work list vs no dates after fetch).

### 6. Suggestion — Schema: no FK from `image_stack_members.image_key` to `images.key`

- **Issue:** Orphan `image_key` values are possible if an image row disappears without cleaning members.
- **Recommendation:** Acceptable for v1 SQLite; add `REFERENCES images(key)` when/if SQLite FK enforcement is on and migrations are ready.

### 7. Suggestion — Test and API edge coverage

- **Gaps:** (a) `gap_ms == delta_ms` boundary (currently stays in the same segment because the comparison is `>` not `>=` — document or test so behavior is locked). (b) Unparseable non-empty `date_taken` strings (treated as skipped — worth one unit test on `_parse_date_taken_utc` / segment builder). (c) `PUT` rejects non-integer JSON numbers (e.g. `3000.0`) because of `type(value) is not int` — fine if intentional; otherwise accept `isinstance(value, int)` and reject floats, or `int()` with validation.

## Security

- Config routes mutate local `config.yaml` under the server’s repo; same trust model as existing catalog/Instagram-dump `PUT` handlers. **Input validation** for `stack_burst_delta_ms` (integer, ≥ 1) is correct. **No** path injection on this route.

## Verdict

**Status `needs_work`** because finding **#1** breaks the primary UX guarantee that the saved burst window applies to `batch_stack_detect` without a metadata override — a contract gap between the API and the handler, not just style.

## Positive note

The **INSERT** fix for `image_stacks` (three placeholders) and the **handler tests** (including real `JobRunner` checkpoint injection) are exactly the right level of coverage for a data-writing job; once config resolution is unified, this phase is in good shape to ship.
