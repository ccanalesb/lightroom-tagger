# Phase 14-02 Summary — `_legacy.py` split (domain families into submodules)

## Outcome

The monolithic `lightroom_tagger/core/database/_legacy.py` barrel was emptied in five domain slices per `14-02-PLAN.md`. Public API remains **`from lightroom_tagger.core.database import …`** via `database/__init__.py`.

### Commits (`refactor(14-02): …`)

1. **`db_init`** — `_dict_factory`, `init_database`, schema migrations (`db_init.py`).
2. **`catalog`** — `library_write`, `resolve_filepath`, catalog CRUD/query (`catalog.py`).
3. **`instagram` + `matches` + `streams (stacks)`** — combined in one refactor commit (`instagram.py`, `matches.py`, `stacks.py`): dump/crawl helpers, match validation, stack mutations and `StackMutationError`. *Rationale:* the shared `__init__.py` barrel and `_legacy.py` edits are tightly coupled across these three moves; splitting into three separate git commits would require replaying intermediate barrel states.

4. *(This document)* — `14-02-SUMMARY.md` only.

## Import rules (D-03)

- Submodules use **relative** imports only (`from .db_init import …`, `from ._legacy import …` for late-bound FTS helper, `from .catalog import library_write`, etc.).
- `matches.apply_instagram_match_to_stack_members` uses **`from .stacks import list_catalog_stack_member_keys`** inside the function to avoid import cycles at module load.
- `catalog._append_query_catalog_image_filters` lazy-imports **`build_description_fts_query`** from `._legacy` until description/search helpers move out of `_legacy` in a later phase.

## Verification

- `pytest lightroom_tagger/core/` — green after each pushed slice in this session.
- Top-level `def` / `class` count across `lightroom_tagger/core/database/*.py` — **124** (redistribution only).

## Not done here (orchestrator-owned)

- `STATE.md`, `ROADMAP.md` — not updated by this agent.

## Remaining in `_legacy.py`

Vision cache, comparisons, descriptions, embeddings, similarity, perspectives/scores — for follow-on plans (e.g. 14-03+) or further splits per `14-RESEARCH.md`.
