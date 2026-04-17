---
plan: 01
title: Backend paginated jobs list and logs_limit query param
wave: 1
depends_on: []
files_modified:
  - apps/visualizer/backend/database.py
  - apps/visualizer/backend/api/jobs.py
  - apps/visualizer/backend/tests/test_jobs_api.py
autonomous: true
requirements:
  - JOB-04
  - JOB-05
---

<objective>
Extend the jobs backend so (a) `GET /api/jobs/` returns the canonical `success_paginated()` envelope with honest `total` and respects `limit` / `offset` query params, and (b) `GET /api/jobs/<id>` accepts an optional `?logs_limit=N` param that truncates the returned `logs` array to the most recent N entries while exposing `logs_total` on the payload. No other API behaviour changes.
</objective>

<context>
Implements **D-06** (hybrid `logs_limit` strategy), **D-09** (clamp and `logs_limit=0` semantics), **D-10** (backwards-compat when `logs_limit` omitted), **D-11** (`logs_total` field), **D-12** (paginated envelope via existing `success_paginated()`), **D-13** (default `limit=50, offset=0` backwards-compat), and **D-14** (new `count_jobs` helper next to `list_jobs`). Every downstream plan in this phase depends on this API shape — no frontend work proceeds until this plan is green.
</context>

<tasks>
<task id="1.1">
<action>
In `apps/visualizer/backend/database.py`, extend `list_jobs` (currently at lines 154–165) to accept an `offset: int = 0` parameter and add it to both SQL branches. Replace the function body so the final signature is `def list_jobs(db: sqlite3.Connection, status: str = None, limit: int = 50, offset: int = 0) -> list:` and both queries become:

```python
if status:
    rows = db.execute(
        "SELECT * FROM jobs WHERE status = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (status, limit, offset)
    ).fetchall()
else:
    rows = db.execute(
        "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset)
    ).fetchall()
return [_deserialize_job(r) for r in rows]
```

Keep the docstring updated to mention `offset`. Do **not** change the default behaviour when callers pass only `status` — `limit=50, offset=0` matches today's behaviour exactly.

Immediately after `list_jobs`, add a new helper:

```python
def count_jobs(db: sqlite3.Connection, status: str = None) -> int:
    """Count jobs, optionally filtered by status."""
    if status:
        row = db.execute(
            "SELECT COUNT(*) AS c FROM jobs WHERE status = ?", (status,)
        ).fetchone()
    else:
        row = db.execute("SELECT COUNT(*) AS c FROM jobs").fetchone()
    return int(row["c"]) if row else 0
```

The `row["c"]` access is correct because the connection uses `_dict_factory` (see `database.py:8–10`), so `fetchone()` returns a `dict`.
</action>
<read_first>
- apps/visualizer/backend/database.py
- apps/visualizer/backend/utils/responses.py
- .planning/phases/02-job-queue-and-processing-ux/02-CONTEXT.md
- .planning/phases/02-job-queue-and-processing-ux/02-RESEARCH.md
</read_first>
<acceptance_criteria>
- `rg -n "def list_jobs\(db: sqlite3.Connection, status: str = None, limit: int = 50, offset: int = 0\)" apps/visualizer/backend/database.py` matches 1 line
- `rg -n "def count_jobs\(db: sqlite3.Connection, status: str = None\) -> int:" apps/visualizer/backend/database.py` matches 1 line
- `rg -n "OFFSET \?" apps/visualizer/backend/database.py` matches at least 2 lines inside `list_jobs`
- `rg -n "SELECT COUNT\(\*\) AS c FROM jobs" apps/visualizer/backend/database.py` matches exactly 2 lines (filtered + unfiltered branches)
- `cd apps/visualizer/backend && PYTHONPATH=. python -c "from database import list_jobs, count_jobs; print('OK')"` prints `OK`
</acceptance_criteria>
</task>

<task id="1.2">
<action>
In `apps/visualizer/backend/api/jobs.py`, update the import line (line 1) to add `count_jobs` and `success_paginated`:

```python
from database import add_job_log, count_jobs, create_job, get_active_jobs, get_job, list_jobs, update_job_field, update_job_status
from utils.responses import success_paginated
from flask import Blueprint, current_app, jsonify, request
```

Replace the entire `list_all_jobs` handler (lines 6–10) with:

```python
@bp.route('/', methods=['GET'])
def list_all_jobs():
    status = request.args.get('status')
    limit = request.args.get('limit', default=50, type=int)
    offset = request.args.get('offset', default=0, type=int)
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    jobs = list_jobs(current_app.db, status=status, limit=limit, offset=offset)
    total = count_jobs(current_app.db, status=status)
    return success_paginated(jobs, total=total, offset=offset, limit=limit)
```

Hard ceiling of `500` on `limit` is defensive — protects against pathological `?limit=999999` requests. The default of `50` matches the previous implicit cap so callers without query params see effectively the same number of rows wrapped in the new envelope (D-13).

Replace the entire `get_job_details` handler (lines 27–34) with:

```python
@bp.route('/<job_id>', methods=['GET'])
def get_job_details(job_id):
    job = get_job(current_app.db, job_id)

    if not job:
        return jsonify({'error': 'Job not found'}), 404

    logs_limit_raw = request.args.get('logs_limit', type=int)
    logs = job.get('logs') or []
    logs_total = len(logs)
    if logs_limit_raw is not None and logs_limit_raw > 0:
        effective_limit = max(1, min(logs_limit_raw, 10_000))
        if logs_total > effective_limit:
            job['logs'] = logs[-effective_limit:]
    job['logs_total'] = logs_total

    return jsonify(job)
```

Semantics (per D-09, D-10, D-11):
- `?logs_limit` omitted → `logs_limit_raw is None` → no truncation, `logs_total` still populated.
- `?logs_limit=0` → `logs_limit_raw == 0`, `0 > 0` is false → no truncation, `logs_total` populated (expand path).
- `?logs_limit=N` with N > 0 → clamp to `[1, 10_000]`, truncate to most recent N entries.

Do **not** change any of the other handlers (`create_new_job`, `cancel_job`, `retry_job`, `list_active_jobs`).
</action>
<read_first>
- apps/visualizer/backend/api/jobs.py
- apps/visualizer/backend/database.py
- apps/visualizer/backend/utils/responses.py
- .planning/phases/02-job-queue-and-processing-ux/02-RESEARCH.md
</read_first>
<acceptance_criteria>
- `rg -n "from database import add_job_log, count_jobs, create_job" apps/visualizer/backend/api/jobs.py` matches 1 line
- `rg -n "from utils.responses import success_paginated" apps/visualizer/backend/api/jobs.py` matches 1 line
- `rg -n "success_paginated\(jobs, total=total, offset=offset, limit=limit\)" apps/visualizer/backend/api/jobs.py` matches 1 line
- `rg -n "logs_total" apps/visualizer/backend/api/jobs.py` matches at least 2 lines
- `rg -n "request.args.get\('logs_limit', type=int\)" apps/visualizer/backend/api/jobs.py` matches 1 line
- `rg -n "request.args.get\('limit', default=50, type=int\)" apps/visualizer/backend/api/jobs.py` matches 1 line
- `cd apps/visualizer/backend && PYTHONPATH=. python -c "from api.jobs import bp; print('OK')"` prints `OK`
</acceptance_criteria>
</task>

<task id="1.3">
<action>
Rewrite `apps/visualizer/backend/tests/test_jobs_api.py` so the existing `test_list_jobs` (line 22–25) asserts the new envelope, and add five new tests covering pagination + logs truncation. Keep the existing `client` fixture (lines 13–20), `test_create_job`, `test_create_instagram_import_job`, `test_get_job`, `test_get_active_jobs` unchanged in behaviour.

Replace the `test_list_jobs` body (lines 22–25) with:

```python
def test_list_jobs(client):
    response = client.get('/api/jobs/')
    assert response.status_code == 200
    assert response.json['data'] == []
    assert response.json['total'] == 0
    assert response.json['pagination']['current_page'] == 1
    assert response.json['pagination']['limit'] == 50
    assert response.json['pagination']['offset'] == 0
    assert response.json['pagination']['has_more'] is False
```

After the final existing test (`test_get_active_jobs`), append:

```python
def _seed_jobs(client, count, job_type='vision_match'):
    ids = []
    for _ in range(count):
        resp = client.post('/api/jobs/', json={'type': job_type, 'metadata': {}})
        ids.append(resp.json['id'])
    return ids


def test_list_jobs_respects_limit_and_offset(client):
    _seed_jobs(client, 4)
    page_one = client.get('/api/jobs/?limit=2&offset=0').json
    page_two = client.get('/api/jobs/?limit=2&offset=2').json
    assert len(page_one['data']) == 2
    assert len(page_two['data']) == 2
    assert page_one['total'] == 4
    assert page_two['total'] == 4
    assert page_one['data'][0]['id'] != page_two['data'][0]['id']
    assert page_one['pagination']['current_page'] == 1
    assert page_two['pagination']['current_page'] == 2


def test_list_jobs_total_count_matches_status_filter(client):
    from database import update_job_status
    ids = _seed_jobs(client, 3)
    extra = _seed_jobs(client, 2)
    for job_id in extra:
        update_job_status(client.application.db, job_id, 'completed')
    pending = client.get('/api/jobs/?status=pending').json
    completed = client.get('/api/jobs/?status=completed').json
    assert pending['total'] == 3
    assert completed['total'] == 2
    assert all(j['status'] == 'pending' for j in pending['data'])
    assert all(j['status'] == 'completed' for j in completed['data'])


def test_list_jobs_default_limit_50(client):
    _seed_jobs(client, 60)
    response = client.get('/api/jobs/').json
    assert len(response['data']) == 50
    assert response['total'] == 60
    assert response['pagination']['has_more'] is True


def test_get_job_truncates_logs_when_logs_limit_set(client):
    from database import add_job_log
    create_resp = client.post('/api/jobs/', json={'type': 'vision_match', 'metadata': {}})
    job_id = create_resp.json['id']
    for i in range(30):
        add_job_log(client.application.db, job_id, 'info', f'log entry {i}')
    response = client.get(f'/api/jobs/{job_id}?logs_limit=10').json
    assert len(response['logs']) == 10
    assert response['logs_total'] == 30
    assert response['logs'][-1]['message'] == 'log entry 29'
    assert response['logs'][0]['message'] == 'log entry 20'


def test_get_job_logs_limit_zero_returns_all(client):
    from database import add_job_log
    create_resp = client.post('/api/jobs/', json={'type': 'vision_match', 'metadata': {}})
    job_id = create_resp.json['id']
    for i in range(5):
        add_job_log(client.application.db, job_id, 'info', f'log {i}')
    response = client.get(f'/api/jobs/{job_id}?logs_limit=0').json
    assert len(response['logs']) == 5
    assert response['logs_total'] == 5


def test_get_job_logs_total_present_when_no_param(client):
    from database import add_job_log
    create_resp = client.post('/api/jobs/', json={'type': 'vision_match', 'metadata': {}})
    job_id = create_resp.json['id']
    for i in range(3):
        add_job_log(client.application.db, job_id, 'info', f'log {i}')
    response = client.get(f'/api/jobs/{job_id}').json
    assert len(response['logs']) == 3
    assert response['logs_total'] == 3
```

Keep the existing `import os, sys, tempfile, pytest` imports at the top of the file. The `from database import ...` imports inside individual tests are deliberate (they require `sys.path` to already be set by the module-level insert on line 7).
</action>
<read_first>
- apps/visualizer/backend/tests/test_jobs_api.py
- apps/visualizer/backend/api/jobs.py
- apps/visualizer/backend/database.py
- .planning/phases/02-job-queue-and-processing-ux/02-RESEARCH.md
</read_first>
<acceptance_criteria>
- `rg -n "def test_list_jobs_respects_limit_and_offset" apps/visualizer/backend/tests/test_jobs_api.py` matches 1 line
- `rg -n "def test_list_jobs_total_count_matches_status_filter" apps/visualizer/backend/tests/test_jobs_api.py` matches 1 line
- `rg -n "def test_list_jobs_default_limit_50" apps/visualizer/backend/tests/test_jobs_api.py` matches 1 line
- `rg -n "def test_get_job_truncates_logs_when_logs_limit_set" apps/visualizer/backend/tests/test_jobs_api.py` matches 1 line
- `rg -n "def test_get_job_logs_limit_zero_returns_all" apps/visualizer/backend/tests/test_jobs_api.py` matches 1 line
- `rg -n "def test_get_job_logs_total_present_when_no_param" apps/visualizer/backend/tests/test_jobs_api.py` matches 1 line
- `cd apps/visualizer/backend && PYTHONPATH=. python -m pytest tests/test_jobs_api.py -v` exits 0
</acceptance_criteria>
</task>
</tasks>

<verification>
- `cd apps/visualizer/backend && PYTHONPATH=. python -m pytest tests/test_jobs_api.py -v` exits 0 with all tests (old + new) passing
- `cd apps/visualizer/backend && PYTHONPATH=. python -m pytest tests/ -v` exits 0 (no other tests broken)
- Manual: with visualizer backend running, `curl -s 'http://localhost:5001/api/jobs/?limit=2&offset=0' | python -m json.tool` shows keys `total`, `data`, `pagination` with `current_page: 1`
- Manual: `curl -s 'http://localhost:5001/api/jobs/<any-id>?logs_limit=1' | python -m json.tool` shows at most 1 entry in `logs` and a numeric `logs_total` field
</verification>

<must_haves>
- `GET /api/jobs/` returns the `success_paginated()` envelope shape used by `api/images.py`, `api/analytics.py`, and `api/identity.py` — no ad-hoc response shape.
- `GET /api/jobs/?limit=N&offset=M` paginates correctly: `len(data) <= limit`, `total` is an honest count of matching rows (respecting `status` filter when passed), `pagination.current_page = (offset // limit) + 1`.
- `GET /api/jobs/` with no query params still returns a usable response (top 50 most recent, wrapped in envelope) — the only breaking change is the shape, not the effective data set (D-13).
- `count_jobs(db, status=None)` exists in `database.py` next to `list_jobs` and mirrors its filter shape (D-14).
- `GET /api/jobs/<id>?logs_limit=N` returns at most N log entries (most recent), and the response always carries `logs_total` with the pre-truncation count.
- `GET /api/jobs/<id>` with no `logs_limit` param returns unlimited logs (backwards-compat, D-10) and still carries `logs_total`.
- `GET /api/jobs/<id>?logs_limit=0` returns unlimited logs (expand semantics, D-09).
- Backend test suite passes end-to-end (old tests updated where the response shape changed, new tests assert the new behaviour).
</must_haves>
