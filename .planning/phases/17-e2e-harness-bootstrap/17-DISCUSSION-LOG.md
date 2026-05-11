# Phase 17: E2E Harness Bootstrap — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-10
**Phase:** 17-e2e-harness-bootstrap
**Areas discussed:** Test runner & file layout, Browser harness mechanics, Catalog fixture, Stack start / teardown

---

## Test runner & file layout

| Option | Description | Selected |
|--------|-------------|----------|
| `tests/e2e/` subdirectory, shared config | Sibling to unit tests, excluded by marks | |
| `e2e/` sibling to `tests/` | Cleaner separation at backend root | |
| `tests/e2e/` with its own `pytest.ini` | Nested but separate config — `pytest tests/` never touches it | ✓ |

**User's choice:** Option 3 — own pytest.ini  
**Notes:** Unit run stays clean; explicit separate invocation for E2E.

---

## Browser harness mechanics

| Option | Description | Selected |
|--------|-------------|----------|
| pytest fixture only | Fixture opens CDP session, yields raw connection | |
| BrowserSession class + fixture | Helper class with nav/click/wait/get_text; fixture yields instance | ✓ |
| Thin wrapper + fixture | Same but minimal — tests can call CDP directly for anything not covered | |

**User's choice:** Option 2 — BrowserSession class  
**Notes:** Tests use `def test_foo(browser):` — class methods for common ops, raw CDP available as escape hatch.

---

## Catalog fixture

| Option | Description | Selected |
|--------|-------------|----------|
| Checked-in minimal `.lrcat` + seeded library DB | Static SQLite committed, factory seeds library DB | |
| Factory-only | Programmatic synthetic rows, no real catalog | |
| Real slice export | Script exports subset of actual catalog → committed fixture | ✓ |

**User's choice:** Option 3 — real catalog slice  
**Notes:** More realistic paths/metadata. One-time export step by developer; committed to `tests/e2e/fixtures/`.

---

## Stack start / teardown

| Option | Description | Selected |
|--------|-------------|----------|
| Assume both already running | Tests fail fast if stack not up | |
| Backend in-process, frontend assumed | Flask in thread, frontend pre-running | |
| Both assumed, health-check fixture | Session-scoped ping before any test | |
| Suite spins up own isolated instance | Second backend on separate port, temp fixture DB copy | ✓ |

**User's choice:** Suite spins up isolated stack  
**Notes:** After clarification on "assume running" — user prefers fully self-contained suite. Backend on `:5099`, temp copy of fixture DB, dev stack on `:5001` untouched.

**Frontend sub-decision:**

| Option | Description | Selected |
|--------|-------------|----------|
| Pre-built static assets | `vite build` once, served statically | ✓ |
| Vite dev server | Suite starts `vite dev` pointing at test port | |
| No frontend in Phase 17 | Harness-only, no UI spin-up | |

**User's choice:** Option 1 — pre-built static assets  
**Notes:** No Vite dev server dependency at test time.

---

## Claude's Discretion

- Exact test backend port (`:5099` suggested)
- Whether static assets served by Flask or separate `http.server`
- Sync vs async CDP calls in BrowserSession
- Fixture export script structure
- Temp DB copy mechanism

## Deferred Ideas

- Full user-flow coverage → Phase 18
- CI integration → out of scope for Phase 17
- Parallel E2E workers → premature
