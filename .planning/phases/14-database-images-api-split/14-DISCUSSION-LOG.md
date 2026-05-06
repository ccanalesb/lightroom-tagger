# Phase 14: Database & Images API split - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-06
**Phase:** 14-database-images-api-split
**Areas discussed:** database.py domain grouping, images.py resource grouping, test_database.py co-split strategy, Blueprint preservation

---

## database.py domain grouping

| Option | Description | Selected |
|--------|-------------|----------|
| 7 modules (REQUIREMENTS.md) | Collapse schema/migrations into db_init, merge embeddings+similarity+vision_cache | |
| 10 modules (natural clusters) | Each concern gets its own file | ✓ |
| Hybrid 8 modules | Keep 7 from REQUIREMENTS.md + merged embeddings module | |

**User's choice:** 10-module split

**Follow-up — init/migrations module name:**

| Option | Description | Selected |
|--------|-------------|----------|
| `db_init.py` | Own module, re-exported from `__init__.py`; same pattern as Phase 13 `common.py` | ✓ |
| `db_schema.py` | Same as above, different name | |
| Inside `__init__.py` | Keeps startup logic at entry point; risk of circular imports | |

**User's choice:** `db_init.py` — accepted recommendation after tradeoff explanation

---

## images.py resource grouping

| Option | Description | Selected |
|--------|-------------|----------|
| 3 modules (REQUIREMENTS.md) | catalog+stacks, instagram+matches+dump, search | |
| 6 modules | catalog, stacks, instagram, matches, search, common | ✓ |

**User's choice:** 6-module split

**Follow-up — common.py scope:**

| Option | Description | Selected |
|--------|-------------|----------|
| Only cross-cutting helpers | Single-consumer helpers stay in primary module (Phase 13 D-05 rule) | ✓ |
| All helpers in common.py | Route modules kept clean; helpers centralized | |

**User's choice:** Phase 13 D-05 rule applies — single-consumer helpers stay in primary module

---

## test_database.py co-split strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Mirror module structure (1:1) | One test file per submodule; each imports only from its corresponding module | ✓ |
| Keep existing + add new | Existing test files stay, imports updated; new files only for uncovered submodules | |
| Consolidate then re-split | Merge all tests, then re-split along new boundaries | |

**User's choice:** Mirror the module structure 1:1

---

## Blueprint preservation for images.py

| Option | Description | Selected |
|--------|-------------|----------|
| `__init__.py` owns Blueprint | Submodules register on shared Blueprint; `app.py` unchanged | |
| Each submodule owns its own Blueprint | Separate Blueprints per resource group; `app.py` registers each | ✓ |

**User's choice:** Each submodule owns its own Blueprint

**Follow-up — URL prefix strategy:**

| Option | Description | Selected |
|--------|-------------|----------|
| Single `/api/images` prefix for all | No URL changes; frontend untouched | |
| Each Blueprint gets its own prefix | `/api/images/catalog`, `/api/images/stacks`, etc.; frontend URLs updated | ✓ |

**User's choice:** Each Blueprint gets its own URL prefix — explicitly accepted scope expansion
**Notes:** User confirmed after being warned this breaks 42 existing frontend fetch call sites. Frontend URL migration is in scope for Phase 14.

---

## Claude's Discretion

- Exact order of per-family migration commits within each split
- Whether `_sort_catalog_key_rows_newest_first` and `_non_empty_str_list_for_json_array_filter` go in `catalog.py` or a sub-helper
- Whether `seed_perspectives_from_prompts_dir` belongs in `scores.py` or `db_init.py`

## Deferred Ideas

- E2E testing (TEST-03, E2E-01..E2E-06) — Phases 17–18
- `cli.py` split — future milestone
