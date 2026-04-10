# Testing

## Framework

| Layer | Framework | Runner / config |
|-------|-----------|-----------------|
| Python (library + scripts) | **pytest** (>=7.4 in `pyproject.toml` optional `dev`) | `python -m pytest <path> -v` from repo root |
| Python (some legacy modules) | **unittest** (`unittest.TestCase`) | Coexists with pytest; pytest collects `Test*` classes |
| Visualizer backend | **pytest** + **Flask `test_client()`** | Tests under `apps/visualizer/backend/tests/` |
| Visualizer frontend | **Vitest** 1.x + **Testing Library** (`@testing-library/react`, `jest-dom`) | `npm test` / `vitest`; config embedded in `apps/visualizer/frontend/vite.config.ts` |

**Optional dependency:** `pytest-cov` is listed in `pyproject.toml` (`[project.optional-dependencies]` → `dev`) for coverage reports, but there is **no** checked-in `[tool.pytest.ini_options]` or `[tool.coverage.*]` block — coverage is **tool-available**, not centrally configured in this repo.

---

## Test Structure

### Python: `lightroom_tagger`

- **Colocated tests:** `test_<module>.py` beside the code under the same package, e.g.:
  - `lightroom_tagger/core/test_matcher.py`
  - `lightroom_tagger/lightroom/test_reader.py`
  - `lightroom_tagger/instagram/test_dump_reader.py`
- **Scripts:** Some pytest modules live under `lightroom_tagger/scripts/` (e.g. `test_match_instagram_dump.py`) — they exercise script-level behavior with `tmp_path` or similar.
- **Style mix:** Core tests tend to be **pytest** functions/classes; `lightroom/` and parts of `instagram/` still use **`unittest.TestCase`** (e.g. `lightroom_tagger/lightroom/test_reader.py`).

### Python: visualizer backend

- **Directory:** `apps/visualizer/backend/tests/`
- **Files:** `test_<area>.py` — e.g. `test_app.py`, `test_jobs_api.py`, `test_handlers_single_match.py`, `test_websocket.py`.
- **Path setup:** `apps/visualizer/backend/tests/conftest.py` prepends the backend directory to `sys.path`. Individual test files sometimes repeat `sys.path.insert` for imports like `from app import create_app`.
- **README / docs** may refer to `cd backend && pytest ../tests/` (worktree layout); in **this** repo, tests live in `apps/visualizer/backend/tests/` — typical invocation:

```bash
cd apps/visualizer/backend && PYTHONPATH=. python -m pytest tests/ -v
```

### TypeScript: visualizer frontend

- **Colocated `__tests__` directories**, e.g.:
  - `apps/visualizer/frontend/src/services/__tests__/api.test.ts`
  - `apps/visualizer/frontend/src/components/ui/__tests__/Alert.test.tsx`
  - `apps/visualizer/frontend/src/pages/__tests__/MatchingPage.test.tsx`
- **Setup:** `apps/visualizer/frontend/src/test/setup.ts` imports `@testing-library/jest-dom/vitest`.
- **Vitest config** (`apps/visualizer/frontend/vite.config.ts`): `environment: 'jsdom'`, `globals: true`, `setupFiles: './src/test/setup.ts'`.

### Running everything (from `README.md`)

```bash
cd apps/visualizer/backend && PYTHONPATH=. pytest tests/ -v
cd ../frontend && npm test -- --run
```

Core library, from repo root:

```bash
python -m pytest lightroom_tagger/ -v
```

---

## Mocking & Fixtures

### Python: `unittest.mock`

- **`patch`** targets the **import location used by the module under test** (standard pytest/unittest pattern), e.g. `patch('lightroom_tagger.core.matcher.query_by_exif', ...)` in `lightroom_tagger/core/test_matcher.py`.
- **`Mock` / `MagicMock`:** Heavy use for DB handles, Flask job runners, and SDK clients.
- **`pytest.fixture`:** e.g. `client` in `apps/visualizer/backend/tests/test_jobs_api.py` builds a temp SQLite path with `tempfile.TemporaryDirectory()`, calls `create_app()`, replaces `app.db` with `init_db(db_path)`, yields `app.test_client()`.

### Python: environment and I/O

- **`patch.dict(os.environ, ...)`** for API key presence tests (`lightroom_tagger/core/test_provider_registry.py`).
- **`tmp_path` / `TemporaryDirectory`:** Isolated DBs and filesystem state (jobs API tests, script tests).
- **`@patch('time.sleep')`:** Deterministic retry tests (`lightroom_tagger/core/test_retry.py`).

### Python: parametrize

- **`@pytest.mark.parametrize`** for exception hierarchy tables (`lightroom_tagger/core/test_provider_errors.py`).

### TypeScript: Vitest

- **`vi.fn()`** as `fetch` mock; **`globalThis.fetch`** reassigned in test files (see `README.md` note on `global` vs `globalThis` in TS).
- **`beforeEach(() => vi.clearAllMocks())`** for isolation (`apps/visualizer/frontend/src/services/__tests__/api.test.ts`).
- **`describe` / `it` / `expect`** with `async` tests for API wrappers.

### Flask handlers

- **Stacked `@patch` decorators** on a single test function to stub `load_config`, `init_database`, domain functions, and `add_job_log` — keeps handler unit tests fast and free of real DB/socket side effects (`apps/visualizer/backend/tests/test_handlers_single_match.py`).

---

## Coverage

- **Declared tool:** `pytest-cov>=4.1.0` in optional dev dependencies (`pyproject.toml`).
- **No committed baseline:** This repository does not define a standard `pytest --cov=...` invocation, threshold, or HTML report path in `pyproject.toml` or a dedicated config file.
- **Suggested usage** (ad hoc):

```bash
python -m pytest lightroom_tagger apps/visualizer/backend/tests \
  --cov=lightroom_tagger \
  --cov=apps/visualizer/backend \
  --cov-report=term-missing
```

(Adjust package paths to match what you install on `PYTHONPATH`; backend modules are not under `lightroom_tagger`.)

- **Frontend:** Vitest supports coverage via `@vitest/coverage-v8` or similar; not wired in `package.json` in the current snapshot — run only when you add the dependency and script.

### Current state (reference)

Coverage percentage is **not** stored as a badge or CI artifact in the explored configs; treat **green tests + lint** as the day-to-day quality bar unless you add CI coverage gates.

---

## Examples (quick reference)

**pytest function + patches:**

```6:27:lightroom_tagger/core/test_matcher.py
def test_match_filters_by_exif():
    """Should filter candidates by EXIF first."""
    mock_db = Mock()
    # ...
    with patch('lightroom_tagger.core.matcher.query_by_exif', return_value=[catalog_candidates[0]]), \
         patch('lightroom_tagger.core.matcher.score_candidates_with_vision', return_value=[{'catalog_key': 'cat1', 'total_score': 0.9}]):
        result = match_image(mock_db, insta_image, threshold=0.7)
    assert len(result) == 1
```

**Flask client fixture:**

```13:20:apps/visualizer/backend/tests/test_jobs_api.py
@pytest.fixture
def client():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        app = create_app()
        app.db = init_db(db_path)
        client = app.test_client()
        yield client
```

**Vitest + fetch mock:**

```1:11:apps/visualizer/frontend/src/services/__tests__/api.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { JobsAPI } from '../api'

const fetchMock = vi.fn()
globalThis.fetch = fetchMock

describe('JobsAPI', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })
```
