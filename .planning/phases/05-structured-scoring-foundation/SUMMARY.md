# Plan 05-01 — Execution summary

**Phase:** 05 — Structured scoring foundation  
**Plan:** Library DB migration — `image_scores` and `perspectives` tables  
**Date:** 2026-04-12

## Outcomes

- `init_database` now creates additive tables **`perspectives`** and **`image_scores`** with indexes `idx_image_scores_perspective_score`, `idx_image_scores_image`, and `idx_image_scores_current`, plus unique constraint **`uq_image_scores_versioned`**. Legacy **`image_descriptions`** DDL is unchanged.
- Typed helpers: `list_perspectives`, `get_perspective_by_slug`, `insert_image_score`, `supersede_previous_current_scores`, `get_current_scores_for_image`, all using parameterized SQL.
- Operator-facing notes: comment block **`## Queryable score fields (image_scores)`** documents each column and states that missing rows mean “not scored yet” for `LEFT JOIN` usage.
- **`lightroom_tagger/core/test_database_scores.py`** exercises versioned rows, `supersede_previous_current_scores`, and asserts a single current row with `prompt_version == "v2"` and `score == 7`.

## Commits

1. `feat(05-01): add image_scores and perspectives schema and helpers`
2. `test(05-01): cover image_scores supersede and current row semantics`

## Verification

| Check | Result |
|--------|--------|
| `pytest lightroom_tagger/core/test_database_scores.py -q` | Pass |
| `mypy lightroom_tagger/core/database.py` | **Fail** (pre-existing: `database.py` and imports report many errors; none introduced solely by the new scoring helpers block) |
| `ruff check lightroom_tagger/core/database.py lightroom_tagger/core/test_database_scores.py` | **Partial** — `test_database_scores.py` clean; `database.py` reports existing issues (e.g. W293, F841, B905) outside the new scoring section |

### Deviation (Rule 1)

Plan **verification** asked for mypy and ruff exit 0 on `database.py`. The file already fails those gates repo-wide; this plan did not refactor legacy signatures or whitespace to avoid scope creep. New code follows the same patterns as adjacent helpers and is covered by pytest.

## STATE / ROADMAP

Not modified (orchestrator-owned per wave instructions).

---

# Plan 05-03 — Execution summary

**Phase:** 05 — Structured scoring foundation  
**Plan:** Pydantic structured output validation, repair, retry, and golden fixtures  
**Date:** 2026-04-12

## Outcomes

- Runtime dependency **`pydantic>=2.0,<3`** added; `uv.lock` refreshed.
- New module **`lightroom_tagger/core/structured_output.py`**: `ScoreResponse` / `PerspectiveScorePayload`, deterministic `repair_json_text` (fence extraction aligned with `parse_description_response`, trailing-comma pass with documented string-limitation note), `parse_score_response`, `parse_score_response_with_retry` (optional `fixer` then optional `llm_fixer`, each at most once), `StructuredOutputError` with 200-char preview cap and `input too large` guard at 512k chars.
- **`lightroom_tagger/core/vision_client.py`**: `SCORE_JSON_REPAIR_SYSTEM`, `complete_chat_text`, `make_score_json_llm_fixer` for D-12 LLM JSON-only repair (no global default; Phase 6 binds client/model).
- **`lightroom_tagger/core/test_structured_output.py`**: golden fixtures `RAW_*`, fixer/llm_fixer paths, preview truncation, `score == 11` `ValidationError`, and `make_score_json_llm_fixer` wiring smoke test.

## Commits

1. `chore(05-03): add pydantic v2 dependency and refresh uv.lock`
2. `feat(05-03): add structured_output score JSON repair and validation`
3. `feat(05-03): add make_score_json_llm_fixer and text completion helper`
4. `test(05-03): add golden fixtures for structured score output`

## Verification

| Check | Result |
|--------|--------|
| `pytest lightroom_tagger/core/test_structured_output.py -q` | Pass |
| `ruff check lightroom_tagger/core/structured_output.py lightroom_tagger/core/vision_client.py lightroom_tagger/core/test_structured_output.py` | Pass |
| `mypy lightroom_tagger/core/structured_output.py lightroom_tagger/core/vision_client.py` | **Fail** (transitive imports pull `analyzer`, `database`, etc.; see Rule 4) |
| `mypy --follow-imports=silent` on the same two modules | Pass |

## Deviations (Rule 4)

1. **Mypy:** Plain `mypy` on the two library files follows imports into modules with pre-existing errors. Verification used `--follow-imports=silent` for an accurate check of the new/edited surface, matching the practical gate used when the rest of the package is not mypy-clean.
2. **`vision_client.py`:** Ruff `--fix` cleaned whitespace/import issues across the file (not only new helpers), and `typing.cast(Any, …)` wraps `messages` on four `chat.completions.create` sites so `mypy --follow-imports=silent` passes on `vision_client.py`.
3. **Plan text vs. implementation:** The plan’s “on `ValidationError`, if `repair_json_text` changed text and second parse succeeds” branch is not implemented as a separate step after `parse_score_response` fails, because `parse_score_response` already runs `repair_json_text` before validation; a second identical parse cannot succeed. `repaired_flag` is set when an injected `fixer` or `llm_fixer` recovers.

## STATE / ROADMAP

Not modified (orchestrator-owned per wave instructions).
