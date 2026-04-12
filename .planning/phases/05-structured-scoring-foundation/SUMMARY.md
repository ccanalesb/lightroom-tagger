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
