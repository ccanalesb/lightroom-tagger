# Phase 15: Service modules & boundary policy — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-06
**Phase:** 15-service-modules-boundary-policy
**Areas discussed:** File split strategy, Duplicate logic targeting, Boundary policy format, CI enforcement

---

## File split strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Shared `core/utils/` module | Common helpers go into a shared package; each big file keeps domain logic | |
| Domain sub-packages | Each file becomes a package with internal submodules (like Phase 14 database/) | ✓ |
| Inline extraction, same directory | Sibling files like `analyzer_image_utils.py` without sub-packages | |
| You decide | Claude picks the cleanest approach | |

**User's choice:** Domain sub-packages — consistent with Phase 14 database pattern  
**Notes:** None

---

## Duplicate logic targeting

| Option | Description | Selected |
|--------|-------------|----------|
| Identical code only | Extract only verbatim duplicates across 2+ files | |
| Shared helpers + similar patterns | Duplicates AND logically shared utilities used by 2+ files | |
| Everything non-domain | Aggressively extract anything not core business logic, even if in only one file | ✓ |

**User's choice:** Aggressive extraction — anything non-core domain logic moves out  
**Notes:** Core domain logic = scoring, describing, ranking; everything else (path helpers, compression, parsing, provider dispatch) moves out

---

## Boundary policy format

| Option | Description | Selected |
|--------|-------------|----------|
| ADR in `.planning/` or `docs/adr/` | Formal Architecture Decision Record | |
| `CONTRIBUTING.md` section | Inline with contribution guidelines | |
| `pyproject.toml` comments + `docs/architecture.md` | Policy as code, discoverable from tooling | ✓ |
| `docs/architecture.md` standalone | Dedicated architecture doc referenced from CONTRIBUTING.md | |

**User's choice:** `pyproject.toml` comments + `docs/architecture.md`  
**Notes:** Rules discoverable from tooling, authoritative doc alongside

---

## CI enforcement

| Option | Description | Selected |
|--------|-------------|----------|
| `wc -l` shell script | Simple size gate, zero dependencies | ✓ (partial) |
| `ruff` custom rule | Integrated with Python tooling, requires plugin | |
| `flake8` plugin | Older ecosystem, more boilerplate | |
| `pytest` assertion | Tests assert line counts + runs in existing test suite | ✓ (partial) |

**User's choice:** Mix of option 1 and 4 — then clarified as both  
**Follow-up:** Boundary assertion strictness → Import-based (layer graph) + size assertion in same `test_architecture.py`  
**Notes:** `wc -l` for fast CI gate; `pytest` for size regression + import graph layer violation checks

---

## Claude's Discretion

- Exact submodule names for `matcher/` and `identity_service/` packages
- Whether matcher date-window queries fold into the database layer
- Exact location of `wc -l` CI script

## Deferred Ideas

None
