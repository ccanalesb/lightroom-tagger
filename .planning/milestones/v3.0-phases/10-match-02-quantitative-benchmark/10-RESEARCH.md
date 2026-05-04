# Phase 10 — Research: MATCH-02 recall-only safety check

**Date:** 2026-05-01  
**Purpose:** What a planner needs to know to execute Phase 10 well (`10-CONTEXT.md` D-01–D-14).  
**Method:** Read canonical CONTEXT/REQUIREMENTS/STATE, Phase 8 prefilter context, and source in `lightroom_tagger/core` + `lightroom_tagger/scripts/match_instagram_dump.py`.

---

## 1. Exact function signatures (with import paths)

### `lightroom_tagger.core.clip_similarity`

```python
class NoClipEmbeddingError(Exception):
    def __init__(self, seed_key: str) -> None: ...

def shortlist_catalog_candidates_by_clip(
    db: sqlite3.Connection,
    insta_media_key: str,
    candidate_keys: list[str],
    top_k: int,
) -> list[str]: ...

def get_clip_embedding_blob_for_key(db: sqlite3.Connection, image_key: str) -> bytes | None: ...

KNN_K_MAX = 500  # caps effective top_k in shortlist path
```

**Important behavior:** `shortlist_catalog_candidates_by_clip` does **not** raise `NoClipEmbeddingError`. If the Instagram seed has no CLIP row, `get_clip_embedding_blob_for_key` returns `None` and the function returns **`[]`** (empty shortlist), same as the “no candidates” case. `NoClipEmbeddingError` is raised by `list_pin_similarity_candidate_keys` and `run_clip_similar_for_seed` when the *seed* has no embedding — not by the shortlist helper used in production matching.

**Planner implication (D-05 / skipped bucket):** Classify `skipped_no_embedding` with an explicit `get_clip_embedding_blob_for_key(db, insta_key) is None` **before** interpreting an empty shortlist. Do not rely on catching `NoClipEmbeddingError` around `shortlist_catalog_candidates_by_clip`.

### `lightroom_tagger.core.matcher`

```python
def find_candidates_by_date(db, insta_image: dict, days_before: int = 90) -> list:
    ...
```

Returns a list of catalog image dicts (deserialized rows) with at least `key`, `date_taken`, `filepath`, plus `ai_summary` from a `LEFT JOIN` on `image_descriptions` (`image_type = 'catalog'`). Returns **`[]`** if `insta_image['date_folder']` is missing or **not exactly length 6** (expects `YYYYMM`).

### `lightroom_tagger.core.database`

```python
def get_rejected_pairs(db: sqlite3.Connection) -> set[tuple[str, str]]:
    """Return set of (catalog_key, insta_key) pairs in the blocklist."""

def catalog_key_is_primary_grid_row(db: sqlite3.Connection, image_key: str) -> bool:
    ...

def get_instagram_dump_media(db: sqlite3.Connection, media_key: str) -> dict | None:
    ...

def init_database(db_path: str) -> sqlite3.Connection:
    ...
```

`get_rejected_pairs` reads `rejected_matches` (`SELECT catalog_key, insta_key`).

---

## 2. Candidate construction flow (production sequence to replicate)

From `match_dump_media` in `lightroom_tagger/scripts/match_instagram_dump.py` — apply **in order**:

1. **`rejected = get_rejected_pairs(db)`** — once per run (not per pair in the loop, but equivalent to per-pair membership test).
2. **`candidates = find_candidates_by_date(db, dump_media, days_before=90)`** — `dump_media` must be a dict containing at least **`media_key`** and **`date_folder`** (6-char `YYYYMM`). This is the same object shape as a row from `instagram_dump_media`.
3. **Rejected filter:**  
   `candidates = [c for c in candidates if (c.get('key'), media_key) not in rejected]`  
   where `media_key = dump_media['media_key']`.
4. **Representative-only filter:**  
   `candidates = [c for c in candidates if c.get('key') and catalog_key_is_primary_grid_row(db, c['key'])]`
5. **CLIP shortlist (benchmark target):**  
   `cand_keys = [c['key'] for c in candidates if c.get('key')]`  
   `short_keys = shortlist_catalog_candidates_by_clip(db, dump_media['media_key'], cand_keys, clip_top_k)`  
   with **`clip_top_k = 50`** per D-06.

Counts for reporting (align with D-09 / CSV):

- **`date_window_size`:** `len(find_candidates_by_date(...))` before rejected + rep filters (=`initial_candidate_count` in script).
- **`candidates_after_filters`:** `len(cand_keys)` after rejected + `catalog_key_is_primary_grid_row` (=`dw_in` before shortlist in script).

---

## 3. Database schema (relevant columns)

### `matches` (`database.py` DDL)

| Column | Role |
|--------|------|
| `catalog_key` | PK part |
| `insta_key` | PK part; same identifier as `instagram_dump_media.media_key` in the matching pipeline |
| `validated_at` | **Truth set:** `IS NOT NULL` → user-validated pair (D-03) |

### `instagram_dump_media`

| Column | Role |
|--------|------|
| `media_key` | Primary key; passed as `insta_media_key` to `shortlist_catalog_candidates_by_clip` |
| `date_folder` | Required for `find_candidates_by_date` (`YYYYMM`) |
| `file_path`, … | Embedding jobs require usable path (see `list_instagram_dump_keys_needing_clip_embedding`) |

### `image_clip_embeddings` (sqlite-vec `vec0`)

**There is no `image_type` column.** Migration `_migrate_image_clip_embeddings_vec0` defines:

- `embedding float[512] distance_metric=cosine`
- `image_key TEXT`

Instagram rows are stored with **`image_key = media_key`** (see `list_instagram_dump_keys_needing_clip_embedding`: `LEFT JOIN image_clip_embeddings ce ON ce.image_key = m.media_key`). Catalog keys and Instagram `media_key` share one flat namespace in this table; collision would be a data bug.

### `rejected_matches`

`(catalog_key, insta_key)` blocklist for the rejected filter step.

---

## 4. `DumpMedia` vs `matches` row — wiring the benchmark loop

- **Production matcher** receives **`dump_media`**: a dict from `instagram_dump_media` (or equivalent keys).
- **Validated pairs** give `(insta_key, catalog_key)` from `matches`.

**Recommended wiring:** For each `insta_key`, `dump_media = get_instagram_dump_media(db, insta_key)`. If **`None`**, the pair cannot reproduce production `date_folder` from the dump table — plan an explicit status (e.g. skip or error row) and document it; `find_candidates_by_date` cannot run without a valid `date_folder`.

**Type note:** `find_candidates_by_date` is typed as `insta_image: dict`; no separate `DumpMedia` NamedTuple in core. Any object with the right keys is sufficient.

---

## 5. Script structure pattern (follow `match_instagram_dump.py`)

Existing CLI pattern:

- Shebang + docstring.
- `sys.path.insert(0, str(Path(__file__).parent.parent.parent))` if run as file (same as `match_instagram_dump.py`).
- `argparse`: at minimum `--db` (default `library.db`), plus **`--out-dir`** (D-10/D-11/D-12) to write `10-RECALL.md` and `10-recall-data.csv` under the phase directory or a user path.
- `if not os.path.exists(args.db): print; sys.exit(1)`.
- `db = init_database(args.db)` + `try` / `finally: db.close()`.
- **No** Lightroom writer, **no** `match_dump_media` / vision / LLM.

**Module invocation (D-10):** `lightroom_tagger/scripts/__init__.py` exists; add `benchmark_clip_recall.py` with `def main():` and `if __name__ == '__main__': main()` so `python -m lightroom_tagger.scripts.benchmark_clip_recall` works. (Optional: console script entry in `pyproject.toml` — not required by CONTEXT.)

**Style:** `.planning/codebase/CONVENTIONS.md` — Black 100-col, Ruff, `mypy` strict + typed defs for new code.

---

## 6. Documentation touchpoints (D-13)

### MATCH-02 bullet (exact line to replace)

In `.planning/REQUIREMENTS.md` **line 40** (`10-CONTEXT.md` says “line 41”; file is 40 as of 2026-05-01):

```markdown
- [ ] **MATCH-02**: `vision_match` consults `image_clip_embeddings` to cosine-shortlist date-windowed catalog candidates before LLM judgment runs. Pre-filter reduces LLM comparison calls by ≥10× vs the Phase 7 baseline on a representative batch, while preserving recall on user-validated match pairs. Pipeline emits per-stage candidate counts (date-window in → embedding shortlist out → LLM judgments) in the job log.
```

Rewrite per D-13: remove the **≥10×** claim; state **measured** recall on validated pairs; link to `.planning/phases/10-match-02-quantitative-benchmark/10-RECALL.md`. Keep or adjust the **job log / per-stage counts** sentence if still accurate (Phase 8 D-07).

### Traceability table (exact row to update)

**Line 88** (table under “Traceability”):

```markdown
| MATCH-02 | 8, 10 | Partial — Phase 10 (gap closure: quantitative ≥10× benchmark on user-validated match pairs) |
```

Update to **Complete** (or equivalent) with wording that matches recall-only closure, per D-13.

### Todo move (D-14)

- **Exists:** `.planning/todos/pending/benchmark-embedding-recall.md`
- **Target:** `.planning/todos/done/benchmark-embedding-recall.md` with closing line linking `10-RECALL.md` and noting deferred cost benchmark / model A/B per D-14.

---

## 7. Gaps and risks

| Risk | Detail | Mitigation for planner |
|------|--------|------------------------|
| **Embedding absent vs empty shortlist** | `shortlist_*` returns `[]` when IG has no blob | Pre-check `get_clip_embedding_blob_for_key`; bucket `skipped_no_embedding` |
| **CONTEXT vs code: `NoClipEmbeddingError`** | 10-CONTEXT says catch it for shortlist; code does not raise it there | Use explicit blob check; reserve `NoClipEmbeddingError` only if calling APIs that raise it |
| **No `image_type` on CLIP table** | Docs sometimes say `image_type` + `image_key`; table is **key-only** | Key by `media_key` / catalog `key` only; document for Nyquist readers |
| **Missing `instagram_dump_media` row** | Validated `insta_key` with no dump row → no `date_folder` | Define status (skip / cannot_run) and report count |
| **Invalid `date_folder`** | `find_candidates_by_date` returns `[]` | Produces zero candidates; classify carefully (not a CLIP miss if validated key never entered candidate pool — likely **filtered_out** or edge “no window”) |
| **`filtered_out` semantics** | Validated `catalog_key` not in `cand_keys` after filters | Not a prefilter miss; exclude from “CLIP miss” numerator/denominator per D-09 |
| **`init_database` not read-only** | Opens RW SQLite, runs migrations path | D-01 says read-only *behavior*: avoid `store_*` / `apply_*`. Optional hardening: `file:path?mode=ro` URI (planner may decide if CI needs strict RO) |
| **Recall % definition** | Multiple denominators (all validated vs embedded vs tested) | Match D-11 funnel: report `total_validated`, `embedded`, `skipped_no_embedding`, tested, hits, misses; define headline recall as **hits / (hits + misses)** on pairs where validated catalog was **in** `cand_keys` and IG had embedding (adjust if product owner prefers including/excluding `filtered_out`) |
| **Stale validation vs stacks** | Representative changed since validation | `filtered_out` captures “not in rep-filtered set” — expected |

---

## 8. Validation architecture (Nyquist `VALIDATION.md` — read vs run)

**Verifiable from artifacts alone (`10-RECALL.md`, `10-recall-data.csv`):**

- Raw counts: validated total, embedded, skipped, filtered_out, hits, misses.
- Per-pair **`status`** ∈ `{hit, miss, filtered_out, skipped_no_embedding}` and fields: `insta_key`, `validated_catalog_key`, `date_window_size`, `candidates_after_filters`, `shortlist_size`, `shortlist_includes_validated` (or equivalent boolean).
- Miss list for operator action (D-03 / CONTEXT “miss table”).

**Requires executing the script (or reimplementing logic):**

- That candidate construction **actually** called `find_candidates_by_date` → `get_rejected_pairs` → `catalog_key_is_primary_grid_row` with `days_before=90` and `top_k=50`.
- That the DB snapshot had CLIP rows for the IG keys claimed as “embedded.”

**Suggested automated checks for a later phase (optional, not in D-10):** unit test that mocks DB / frozen rows and asserts taxonomy for hit, miss, filtered_out, skipped; or golden CSV on a tiny fixture DB.

---

## 9. `.cursor/rules` relevant to implementation

- **`backend-restart.mdc`:** If touching `lightroom_tagger/core/` alongside a live backend, follow restart discipline (Phase 10 script is CLI-only; core edits still trigger this rule for local dev).
- **`gsd-code-review-fix.mdc` / `gsd-live-validation.mdc`:** Apply per parent GSD workflow when closing the phase (live validation expectations for new endpoints **not** applicable here — no new API).

---

## 10. Summary for the planner

- Reuse **four** core pieces: `get_instagram_dump_media` (or equivalent dict), `find_candidates_by_date(..., days_before=90)`, `get_rejected_pairs`, `catalog_key_is_primary_grid_row`, then `shortlist_catalog_candidates_by_clip(..., top_k=50)`.
- Ground truth query: `SELECT catalog_key, insta_key FROM matches WHERE validated_at IS NOT NULL`.
- Prerequisite: IG CLIP rows in `image_clip_embeddings` for each `insta_key` (operator runs `batch_embed_image` with `image_type='catalog_and_instagram'` per D-04 / Phase 8).
- Deliverables: `lightroom_tagger/scripts/benchmark_clip_recall.py`, `10-RECALL.md`, `10-recall-data.csv`, REQUIREMENTS + traceability edits, todo move.

---

*Research complete against repo state 2026-05-01.*

## RESEARCH COMPLETE
