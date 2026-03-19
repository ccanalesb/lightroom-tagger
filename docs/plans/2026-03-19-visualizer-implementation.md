# Visualizer Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a React 19 + Flask visualizer to monitor and control Lightroom Tagger workflow with real-timeWebSocket updates.

**Architecture:** Frontend (Vite/React) calls Backend REST API for data and connects via WebSocket for real-time job progress. Backend wraps existing core modules, manages job execution in background threads, and uses TinyDB for persistence.

**Tech Stack:** React 19, TypeScript, Vite, Zustand, Flask, Flask-SocketIO, Pillow, TinyDB

---

## Phase 1: Backend Foundation

### Task 1.1: Backend Configuration Setup

**Note:** Some files already exist from initial setup (`backend/.env`, `backend/example.env`, `backend/config.py`, `backend/requirements.txt`)

**Files:**
- Verify: `backend/.env`, `backend/example.env`, `backend/config.py`, `backend/requirements.txt`
- Create: `backend/.gitignore` (backend-specific ignores)

**Step 1: Verify existing configuration files**

Run: `cat backend/.env`
Expected: File exists with environment variables

Run: `cat backend/example.env`
Expected: File exists with example configuration

Run: `cat backend/config.py`
Expected: File exists with config loading from env

Run: `cat backend/requirements.txt`
Expected: File exists with Flask dependencies

**Step 2: Create backend-specific .gitignore**

Create: `backend/.gitignore`

```.gitignore
.env
*.pyc
__pycache__/
.pytest_cache/
thumbnails/
*.db-journal
```

**Step 3: Verify gitignore works**

Run: `git check-ignore -v backend/.env`
Expected: `backend/.gitignore:1:.env    backend/.env`

**Step 4: Commit**

```bash
git add backend/.gitignore
git commit -m "chore(backend): add backend-specific gitignore"
```

---

### Task 1.2: Flask App Factory

**Files:**
- Create: `backend/app.py`
- Create: `backend/api/__init__.py`
- Create: `tests/test_app.py`

**Step 1: Write failing test for Flask app factory**

Create: `tests/test_app.py`

```python
import pytest
from app import create_app

def test_create_app_returns_flask_app():
    app = create_app()
    assert app is not None
    assert app.name == 'backend'

def test_app_has_required_endpoints():
    app = create_app()
    client = app.test_client()
    
    response = client.get('/api/status')
    assert response.status_code == 200
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_app.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'app'"

**Step 3: Create minimal Flask app factory**

Create: `backend/api/__init__.py`

```python
# Empty file for API package
```

Create: `backend/app.py`

```python
from flask import Flask
from flask_cors import CORS
import config

def create_app():
    app = Flask(__name__)
    app.name = 'backend'
    
    CORS(app, origins=[config.FRONTEND_URL])
    
    from api import jobs, images, system
    app.register_blueprint(jobs.bp, url_prefix='/api/jobs')
    app.register_blueprint(images.bp, url_prefix='/api/instagram-images')
    app.register_blueprint(system.bp, url_prefix='/api')
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host=config.FLASK_HOST, port=config.FLASK_PORT, debug=config.FLASK_DEBUG)
```

**Step 4: Run test to verify it still fails (missing blueprint imports)**

Run: `pytest tests/test_app.py::test_create_app_returns_flask_app -v`
Expected: FAIL with "ImportError: cannot import name 'jobs' from 'api'"

**Step 5: Create minimal API blueprints**

Create: `backend/api/jobs.py`

```python
from flask import Blueprint, jsonify

bp = Blueprint('jobs', __name__)

@bp.route('/', methods=['GET'])
def list_jobs():
    return jsonify([])

@bp.route('/', methods=['POST'])
def create_job():
    return jsonify({'id': 'test', 'status': 'pending'}), 201
```

Create: `backend/api/images.py`

```python
from flask import Blueprint, jsonify

bp = Blueprint('images', __name__)

@bp.route('/', methods=['GET'])
def list_images():
    return jsonify([])
```

Create: `backend/api/system.py`

```python
from flask import Blueprint, jsonify

bp = Blueprint('system', __name__)

@bp.route('/status', methods=['GET'])
def get_status():
    return jsonify({'status': 'ok'})
```

**Step 6: Run test to verify it passes**

Run: `pytest tests/test_app.py -v`
Expected: PASS (2 tests)

**Step 7: Commit**

```bash
git add backend/app.py backend/api/__init__.py backend/api/jobs.py backend/api/images.py backend/api/system.py tests/test_app.py
git commit -m "feat(backend): add Flask app factory with minimal API blueprints"
```

---

### Task 1.3: Jobs Database Layer

**Files:**
- Create: `backend/database.py`
- Modify: `backend/database.py` (add jobs table)
- Create: `tests/test_database.py`

**Step 1: Write test for job creation**

Create: `tests/test_database.py`

```python
import pytest
import tempfile
import os
from database import init_db, create_job, get_job, update_job_status

def test_create_job():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_db(db_path)
        
        job_id = create_job(db, 'analyze_instagram', {'post_url': 'https://instagram.com/p/ABC'})
        
        assert job_id is not None
        job = get_job(db, job_id)
        assert job['type'] == 'analyze_instagram'
        assert job['status'] == 'pending'
        assert job['progress'] == 0

def test_update_job_status():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_db(db_path)
        
        job_id = create_job(db, 'vision_match', {})
        update_job_status(db, job_id, 'running', progress=25, current_step='Processing image 1/100')
        
        job = get_job(db, job_id)
        assert job['status'] == 'running'
        assert job['progress'] == 25
        assert job['current_step'] == 'Processing image 1/100'

def test_add_job_log():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_db(db_path)
        
        job_id = create_job(db, 'vision_match', {})
        add_job_log(db, job_id, 'info', 'Starting vision matching')
        
        job = get_job(db, job_id)
        assert len(job['logs']) == 1
        assert job['logs'][0]['level'] == 'info'
        assert job['logs'][0]['message'] == 'Starting vision matching'
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_database.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'database'"

**Step 3: Create database module for jobs**

Create: `backend/database.py`

```python
import os
from tinydb import TinyDB, Query
from datetime import datetime
import uuid

def init_db(db_path: str) -> TinyDB:
    """Initialize database with jobs table."""
    os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else '.', exist_ok=True)
    db = TinyDB(db_path)
    return db

def create_job(db: TinyDB, job_type: str, metadata: dict) -> str:
    """Create a new job and return job ID."""
    job_id = str(uuid.uuid4())
    
    job = {
        'id': job_id,
        'type': job_type,
        'status': 'pending',
        'progress': 0,
        'current_step': None,
        'logs': [],
        'result': None,
        'error': None,
        'created_at': datetime.now().isoformat(),
        'started_at': None,
        'completed_at': None,
        'metadata': metadata
    }
    
    db.table('jobs').insert(job)
    return job_id

def get_job(db: TinyDB, job_id: str) -> dict:
    """Get job by ID."""
    Job = Query()
    results = db.table('jobs').search(Job.id == job_id)
    return results[0] if results else None

def update_job_status(db: TinyDB, job_id: str, status: str, 
                      progress: int = None, current_step: str = None):
    """Update job status, progress, and step."""
    Job = Query()
    updates = {'status': status}
    
    if progress is not None:
        updates['progress'] = progress
    if current_step is not None:
        updates['current_step'] = current_step
    
    if status == 'running':
        updates['started_at'] = datetime.now().isoformat()
    elif status in ['completed', 'failed', 'cancelled']:
        updates['completed_at'] = datetime.now().isoformat()
    
    db.table('jobs').update(updates, Job.id == job_id)

def add_job_log(db: TinyDB, job_id: str, level: str, message: str):
    """Add log entry to job."""
    job = get_job(db, job_id)
    if not job:
        return
    
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'level': level,
        'message': message
    }
    
    logs = job.get('logs', [])
    logs.append(log_entry)
    
    Job = Query()
    db.table('jobs').update({'logs': logs}, Job.id == job_id)

def list_jobs(db: TinyDB, status: str = None, limit: int = 50) -> list:
    """List jobs, optionally filtered by status."""
    Job = Query()
    
    if status:
        results = db.table('jobs').search(Job.status == status)
    else:
        results = db.table('jobs').all()
    
    return sorted(results, key=lambda j: j['created_at'], reverse=True)[:limit]

def get_active_jobs(db: TinyDB) -> list:
    """Get all running jobs."""
    Job = Query()
    return db.table('jobs').search(Job.status == 'running')
```

**Step 4: Update app to use database**

Modify: `backend/app.py:13` (add database initialization)

```python
from flask import Flask
from flask_cors import CORS
import config
import os
from database import init_db

db = None

def create_app():
    global db
    app = Flask(__name__)
    app.name = 'backend'
    
    CORS(app, origins=[config.FRONTEND_URL])
    
    db_path = os.path.join(os.path.dirname(__file__), config.DATABASE_PATH)
    db = init_db(db_path)
    app.db = db
    
    from api import jobs, images, system
    app.register_blueprint(jobs.bp, url_prefix='/api/jobs')
    app.register_blueprint(images.bp, url_prefix='/api/instagram-images')
    app.register_blueprint(system.bp, url_prefix='/api')
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host=config.FLASK_HOST, port=config.FLASK_PORT, debug=config.FLASK_DEBUG)
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/test_database.py -v`
Expected: PASS (3 tests)

**Step 6: Commit**

```bash
git add backend/database.py backend/app.py tests/test_database.py
git commit -m "feat(backend): add jobs database layer with TinyDB"
```

---

### Task 1.4: Jobs REST API Endpoints

**Files:**
- Modify: `backend/api/jobs.py`
- Create: `tests/test_jobs_api.py`

**Step 1: Write test for jobs API**

Create: `tests/test_jobs_api.py`

```python
import pytest
import tempfile
import os
from app import create_app
from database import init_db

@pytest.fixture
def client():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        app = create_app()
        app.db = init_db(db_path)
        client = app.test_client()
        yield client

def test_list_jobs(client):
    response = client.get('/api/jobs/')
    assert response.status_code == 200
    assert response.json == []

def test_create_job(client):
    response = client.post('/api/jobs/', 
        json={'type': 'analyze_instagram', 'metadata': {'post_url': 'https://instagram.com/p/ABC'}}
    )
    assert response.status_code == 201
    assert 'id' in response.json
    assert response.json['status'] == 'pending'

def test_get_job(client):
    create_resp = client.post('/api/jobs/', 
        json={'type': 'vision_match', 'metadata': {}}
    )
    job_id = create_resp.json['id']
    
    response = client.get(f'/api/jobs/{job_id}')
    assert response.status_code == 200
    assert response.json['type'] == 'vision_match'

def test_get_active_jobs(client):
    client.post('/api/jobs/', 
        json={'type': 'vision_match', 'metadata': {}}
    )
    
    response = client.get('/api/jobs/active')
    assert response.status_code == 200
    assert len(response.json) == 0  # No running jobs yet
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_jobs_api.py -v`
Expected: FAIL with "404 Not Found" for POST endpoint

**Step 3: Implement jobs API endpoints**

Modify: `backend/api/jobs.py`

```python
from flask import Blueprint, jsonify, request, current_app
from database import create_job, get_job, list_jobs, get_active_jobs, update_job_status
import uuid

bp = Blueprint('jobs', __name__)

@bp.route('/', methods=['GET'])
def list_all_jobs():
    status = request.args.get('status')
    jobs = list_jobs(current_app.db, status=status)
    return jsonify(jobs)

@bp.route('/', methods=['POST'])
def create_new_job():
    data = request.json
    
    if not data or 'type' not in data:
        return jsonify({'error': 'type is required'}), 400
    
    job_type = data['type']
    metadata = data.get('metadata', {})
    
    job_id = create_job(current_app.db, job_type, metadata)
    job = get_job(current_app.db, job_id)
    
    return jsonify(job), 201

@bp.route('/<job_id>', methods=['GET'])
def get_job_details(job_id):
    job = get_job(current_app.db, job_id)
    
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    return jsonify(job)

@bp.route('/<job_id>', methods=['DELETE'])
def cancel_job(job_id):
    job = get_job(current_app.db, job_id)
    
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    if job['status'] == 'running':
        update_job_status(current_app.db, job_id, 'cancelled')
        return jsonify({'status': 'cancelled'})
    
    return jsonify({'error': 'Can only cancel running jobs'}), 400

@bp.route('/active', methods=['GET'])
def list_active_jobs():
    jobs = get_active_jobs(current_app.db)
    return jsonify(jobs)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_jobs_api.py -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add backend/api/jobs.py tests/test_jobs_api.py
git commit -m "feat(backend): implement jobs REST API endpoints"
```

---

### Task 1.5: WebSocket Setup with Flask-SocketIO

**Files:**
- Modify: `backend/app.py`
- Create: `backend/websocket/__init__.py`
- Create: `backend/websocket/events.py`
- Create: `tests/test_websocket.py`

**Step 1: Write test for WebSocket connection**

Create: `tests/test_websocket.py`

```python
import pytest
import socketio
from app import create_app
import tempfile
import os
from database import init_db

@pytest.fixture
def socketio_client():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        app = create_app()
        app.db = init_db(db_path)
        
        from flask_socketio import SocketIO
        socketio_server = SocketIO(app, cors_allowed_origins="*")
        
        client = socketio_server.test_client(app)
        yield client

def test_socket_connect(socketio_client):
    assert socketio_client.is_connected()

def test_socket_subscribe_to_job(socketio_client):
    socketio_client.emit('subscribe_job', {'job_id': 'test-job-id'})
    
    # Should receive confirmation
    received = socketio_client.get_received()
    assert len(received) > 0
    assert received[0]['name'] == 'subscribed'

def test_socket_emit_job_update(socketio_client):
    from flask_socketio import emit
    
    socketio_client.emit('subscribe_job', {'job_id': 'test-job-id'})
    
    # Server should be able to emit job updates
    # This will be tested more thoroughly in integration tests
    received = socketio_client.get_received()
    assert any(r['name'] == 'subscribed' for r in received)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_websocket.py -v`
Expected: FAIL with "ImportError: cannot import name 'SocketIO' from 'flask_socketio'"

**Step 3: Add Flask-SocketIO to requirements**

Modify: `backend/requirements.txt` (already has Flask-SocketIO, verify it's correct)

**Step 4: Implement WebSocket events**

Create: `backend/websocket/__init__.py`

```python
# WebSocket package
```

Create: `backend/websocket/events.py`

```python
from flask_socketio import emit, join_room, leave_room

def register_socket_events(socketio):
    @socketio.on('connect')
    def handle_connect():
        emit('connected', {'status': 'ok'})

    @socketio.on('disconnect')
    def handle_disconnect():
        pass

    @socketio.on('subscribe_job')
    def handle_subscribe_job(data):
        job_id = data.get('job_id')
        if job_id:
            join_room(f'job_{job_id}')
            emit('subscribed', {'job_id': job_id})

    @socketio.on('unsubscribe_job')
    def handle_unsubscribe_job(data):
        job_id = data.get('job_id')
        if job_id:
            leave_room(f'job_{job_id}')
            emit('unsubscribed', {'job_id': job_id})

    @socketio.on('cancel_job')
    def handle_cancel_job(data):
        job_id = data.get('job_id')
        # Job cancellation logic will be implemented in job runner
        emit('job_cancel_requested', {'job_id': job_id})
```

**Step 5: Integrate SocketIO into Flask app**

Modify: `backend/app.py`

```python
from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO
import config
import os
from database import init_db

db = None
socketio = None

def create_app():
    global db, socketio
    app = Flask(__name__)
    app.name = 'backend'
    
    CORS(app, origins=[config.FRONTEND_URL])
    socketio = SocketIO(app, cors_allowed_origins="*")
    
    db_path = os.path.join(os.path.dirname(__file__), config.DATABASE_PATH)
    db = init_db(db_path)
    app.db = db
    
    from api import jobs, images, system
    app.register_blueprint(jobs.bp, url_prefix='/api/jobs')
    app.register_blueprint(images.bp, url_prefix='/api/instagram-images')
    app.register_blueprint(system.bp, url_prefix='/api')
    
    from websocket.events import register_socket_events
    register_socket_events(socketio)
    
    return app

if __name__ == '__main__':
    app = create_app()
    socketio.run(app, host=config.FLASK_HOST, port=config.FLASK_PORT, debug=config.FLASK_DEBUG)
```

**Step 6: Run test to verify it passes**

Run: `pytest tests/test_websocket.py -v`
Expected: PASS (3 tests)

**Step 7: Commit**

```bash
git add backend/app.py backend/websocket/__init__.py backend/websocket/events.py tests/test_websocket.py
git commit -m "feat(backend): add Flask-SocketIO with job subscription events"
```

---

### Task 1.6: Job Runner Framework

**Files:**
- Create: `backend/jobs/__init__.py`
- Create: `backend/jobs/runner.py`
- Create: `backend/jobs/handlers.py`
- Create: `tests/test_job_runner.py`

**Step 1: Write test for job runner**

Create: `tests/test_job_runner.py`

```python
import pytest
import tempfile
import os
import time
from database import init_db, create_job, get_job
from jobs.runner import JobRunner

def test_job_runner_starts_job():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_db(db_path)
        
        runner = JobRunner(db)
        job_id = create_job(db, 'analyze_instagram', {'test': True})
        
        runner.start_job(job_id, 'analyze_instagram', {})
        
        job = get_job(db, job_id)
        assert job['status'] == 'running'
        assert job['started_at'] is not None

def test_job_runner_emits_progress_updates():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_db(db_path)
        
        progress_updates = []
        
        def mock_emit_progress(job_id, progress, step):
            progress_updates.append((progress, step))
        
        runner = JobRunner(db, emit_progress=mock_emit_progress)
        job_id = create_job(db, 'test_job', {})
        
        runner.update_progress(job_id, 50, 'Halfway done')
        
        assert len(progress_updates) == 1
        assert progress_updates[0] == (50, 'Halfway done')
        
        job = get_job(db, job_id)
        assert job['progress'] == 50
        assert job['current_step'] == 'Halfway done'

def test_job_runner_completes_job():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = init_db(db_path)
        
        runner = JobRunner(db)
        job_id = create_job(db, 'test_job', {})
        
        runner.complete_job(job_id, {'result': 'success'})
        
        job = get_job(db, job_id)
        assert job['status'] == 'completed'
        assert job['completed_at'] is not None
        assert job['result'] == {'result': 'success'}
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_job_runner.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'jobs'"

**Step 3: Implement job runner**

Create: `backend/jobs/__init__.py`

```python
# Job runner package
```

Create: `backend/jobs/runner.py`

```python
import threading
from database import get_job, update_job_status, add_job_log

class JobRunner:
    def __init__(self, db, emit_progress=None):
        self.db = db
        self.emit_progress = emit_progress or (lambda *args: None)
        self.active_jobs = {}
    
    def start_job(self, job_id: str, job_type: str, metadata: dict):
        """Mark job as running."""
        update_job_status(self.db, job_id, 'running', progress=0, current_step='Starting...')
        add_job_log(self.db, job_id, 'info', f'Job {job_type} started')
    
    def update_progress(self, job_id: str, progress: int, current_step: str):
        """Update job progress."""
        update_job_status(self.db, job_id, 'running', progress=progress, current_step=current_step)
        add_job_log(self.db, job_id, 'info', current_step)
        self.emit_progress(job_id, progress, current_step)
    
    def complete_job(self, job_id: str, result: dict):
        """Mark job as completed."""
        update_job_status(self.db, job_id, 'completed', progress=100)
        add_job_log(self.db, job_id, 'info', 'Job completed successfully')
        
        job = get_job(self.db, job_id)
        Job = Query()
        from tinydb import Query
        self.db.table('jobs').update({'result': result}, Query().id == job_id)
    
    def fail_job(self, job_id: str, error: str):
        """Mark job as failed."""
        update_job_status(self.db, job_id, 'failed')
        add_job_log(self.db, job_id, 'error', error)
        
        from tinydb import Query
        Job = Query()
        self.db.table('jobs').update({'error': error}, Job.id == job_id)
    
    def cancel_job(self, job_id: str):
        """Cancel a running job."""
        if job_id in self.active_jobs:
            self.active_jobs[job_id].cancel()
        update_job_status(self.db, job_id, 'cancelled')
        add_job_log(self.db, job_id, 'info', 'Job cancelled')
```

Create: `backend/jobs/handlers.py`

```python
"""Job type handlers - implemented in later tasks."""
from runner import JobRunner

def handle_analyze_instagram(runner: JobRunner, job_id: str, metadata: dict):
    """Analyze Instagram images."""
    # TODO: Implement in Phase 4
    runner.update_progress(job_id, 50, 'Analyzing images...')
    runner.complete_job(job_id, {'images_processed': 0})

def handle_vision_match(runner: JobRunner, job_id: str, metadata: dict):
    """Run vision matching."""
    # TODO: Implement in Phase 4
    runner.update_progress(job_id, 50, 'Running vision matching...')
    runner.complete_job(job_id, {'matches': []})

def handle_enrich_catalog(runner: JobRunner, job_id: str, metadata: dict):
    """Enrich catalog with metadata."""
    # TODO: Implement in Phase 4
    runner.update_progress(job_id, 50, 'Enriching catalog...')
    runner.complete_job(job_id, {'enriched': 0})

JOB_HANDLERS = {
    'analyze_instagram': handle_analyze_instagram,
    'vision_match': handle_vision_match,
    'enrich_catalog': handle_enrich_catalog,
}
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_job_runner.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add backend/jobs/__init__.py backend/jobs/runner.py backend/jobs/handlers.py tests/test_job_runner.py
git commit -m "feat(backend): add job runner framework with progress tracking"
```

---

## Phase 2: Frontend Foundation

### Task 2.1: Initialize Vite + React 19 Project

**Files:**
- Create: `frontend/` directory structure
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`

**Step 1: Create frontend directory and package.json**

Run: `cd /home/cristian/lightroom_tagger && mkdir -p frontend`

Create: `frontend/package.json`

```json
{
  "name": "lightroom-tagger-frontend",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "lint": "eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0",
    "preview": "vite preview",
    "test": "vitest",
    "test:ui": "vitest --ui"
  },
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "react-router-dom": "^6.20.0",
    "zustand": "^4.4.7",
    "socket.io-client": "^4.7.2"
  },
  "devDependencies": {
    "@testing-library/react": "^14.1.0",
    "@testing-library/jest-dom": "^6.1.5",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@typescript-eslint/eslint-plugin": "^6.10.0",
    "@typescript-eslint/parser": "^6.10.0",
    "@vitejs/plugin-react": "^4.2.0",
    "autoprefixer": "^10.4.16",
    "eslint": "^8.53.0",
    "eslint-plugin-react-hooks": "^4.6.0",
    "eslint-plugin-react-refresh": "^0.4.4",
    "jsdom": "^23.0.1",
    "postcss": "^8.4.31",
    "tailwindcss": "^3.3.5",
    "typescript": "^5.2.2",
    "vite": "^5.0.0",
    "vitest": "^1.0.4"
  }
}
```

Create: `frontend/vite.config.ts`

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/socket.io': {
        target: 'http://localhost:5000',
        ws: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.ts',
  },
})
```

Create: `frontend/src/test/setup.ts`

```typescript
import '@testing-library/jest-dom/vitest'
```

Create: `frontend/tsconfig.json`

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

Create: `frontend/tsconfig.node.json`

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
```

Create: `frontend/example.env`

```bash
VITE_API_URL=http://localhost:5000/api
VITE_WS_URL=http://localhost:5000
```

Create: `frontend/.env` (gitignored)

```bash
VITE_API_URL=http://localhost:5000/api
VITE_WS_URL=http://localhost:5000
```

**Step 2: Install dependencies**

Run: `cd frontend && npm install`
Expected: Packages installed successfully

**Step 3: Create test setup file**

Create: `frontend/src/test/setup.ts`

```typescript
import '@testing-library/jest-dom/vitest'
```

**Step 3: Create src structure and entry point**

Create: `frontend/src/main.tsx`

```typescript
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
```

Create: `frontend/src/App.tsx`

```typescript
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<div className="p-8"><h1 className="text-2xl font-bold">Lightroom Tagger</h1></div>} />
      </Routes>
    </Router>
  )
}

export default App
```

Create: `frontend/index.html`

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/vite.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Lightroom Tagger</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

Create: `frontend/src/index.css`

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen',
    'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue',
    sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}
```

Create: `frontend/tailwind.config.js`

```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
```

Create: `frontend/postcss.config.js`

```javascript
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
```

**Step 4: Verify dev server starts**

Run: `cd frontend && npm run dev`
Expected: Vite server starts on http://localhost:5173

Stop server (Ctrl+C)

**Step 5: Add frontend .gitignore**

Create: `frontend/.gitignore`

```
# Dependencies
node_modules/

# Build output
dist/

# Environment
.env
.env.local

# Editor
.vscode/
.idea/

# OS
.DS_Store
```

**Step 6: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): initialize Vite + React 19 + TypeScript project"
```

---

### Task 2.2: Constants & Types

**Files:**
- Create: `frontend/src/constants/strings.ts`
- Create: `frontend/src/types/job.ts`
- Create: `frontend/src/stores/socketStore.ts` (minimal, only WebSocket state)

**Step 1: Create strings constants**

Create: `frontend/src/constants/strings.ts`

```typescript
// App
export const APP_TITLE = 'Lightroom Tagger'

// Navigation
export const NAV_DASHBOARD = 'Dashboard'
export const NAV_INSTAGRAM = 'Instagram'
export const NAV_MATCHING = 'Matching'
export const NAV_JOBS = 'Jobs'

// Status
export const STATUS_PENDING = 'pending'
export const STATUS_RUNNING = 'running'
export const STATUS_COMPLETED = 'completed'
export const STATUS_FAILED = 'failed'
export const STATUS_CANCELLED = 'cancelled'

// Status Display
export const STATUS_LABELS: Record<string, string> = {
  pending: 'Pending',
  running: 'Running',
  completed: 'Completed',
  failed: 'Failed',
  cancelled: 'Cancelled',
}

// Messages
export const MSG_LOADING = 'Loading...'
export const MSG_NO_JOBS = 'No jobs found. Start a job to see it here.'
export const MSG_CONNECTED = 'Connected'
export const MSG_DISCONNECTED = 'Disconnected'
export const MSG_ERROR_PREFIX = 'Error:'

// API
export const API_DEFAULT_URL = 'http://localhost:5000/api'
export const WS_DEFAULT_URL = 'http://localhost:5000'
```

**Step 2: Define job types**

Create: `frontend/src/types/job.ts`

```typescript
export type JobStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'

export interface JobLog {
  timestamp: string
  level: 'info' | 'warning' | 'error'
  message: string
}

export interface Job {
  id: string
  type: string
  status: JobStatus
  progress: number
  current_step: string | null
  logs: JobLog[]
  result: any | null
  error: string | null
  created_at: string
  started_at: string | null
  completed_at: string | null
  metadata: Record<string, any>
}
```

**Step 3: Create minimal socket store (only WebSocket state)**

Create: `frontend/src/stores/socketStore.ts`

```typescript
import { create } from 'zustand'
import { io, Socket } from 'socket.io-client'
import { WS_DEFAULT_URL } from '../constants/strings'

interface SocketState {
  socket: Socket | null
  connected: boolean
  
  connect: () => void
  disconnect: () => void
}

const WS_URL = import.meta.env.VITE_WS_URL || WS_DEFAULT_URL

export const useSocketStore = create<SocketState>((set, get) => ({
  socket: null,
  connected: false,
  
  connect: () => {
    const socket = io(WS_URL)
    
    socket.on('connect', () => set({ connected: true }))
    socket.on('disconnect', () => set({ connected: false }))
    
    set({ socket })
  },
  
  disconnect: () => {
    get().socket?.disconnect()
    set({ socket: null, connected: false })
  },
}))
```

**Step 4: Verify builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 5: Commit**

```bash
git add frontend/src/constants/ frontend/src/types/ frontend/src/stores/socketStore.ts
git commit -m "feat(frontend): add constants and minimal socket store"
```

---

### Task 2.3: API Service (TDD)

**Files:**
- Create: `frontend/src/services/api.ts`
- Create: `frontend/src/services/__tests__/api.test.ts`

**Step 1: Write failing test for API service**

Create: `frontend/src/services/__tests__/api.test.ts`

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { JobsAPI } from '../api'

global.fetch = vi.fn()

describe('JobsAPI', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })
  
  it('should list all jobs', async () => {
    const mockJobs = [{ id: '1', type: 'test', status: 'pending' }]
    ;(global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockJobs,
    })
    
    const jobs = await JobsAPI.list()
    
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/jobs/'),
      expect.objectContaining({ headers: { 'Content-Type': 'application/json' } })
    )
    expect(jobs).toEqual(mockJobs)
  })
  
  it('should get job by id', async () => {
    const mockJob = { id: '123', type: 'test', status: 'running' }
    ;(global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockJob,
    })
    
    const job = await JobsAPI.get('123')
    
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/jobs/123'),
      expect.any(Object)
    )
    expect(job).toEqual(mockJob)
  })
  
  it('should create job', async () => {
    const mockJob = { id: '456', type: 'analyze', status: 'pending' }
    ;(global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockJob,
    })
    
    const job = await JobsAPI.create('analyze', { test: true })
    
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/jobs/'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ type: 'analyze', metadata: { test: true } }),
      })
    )
    expect(job).toEqual(mockJob)
  })
  
  it('should throw on error', async () => {
    ;(global.fetch as any).mockResolvedValueOnce({
      ok: false,
      status: 404,
      statusText: 'Not Found',
    })
    
    await expect(JobsAPI.get('nonexistent')).rejects.toThrow('404 Not Found')
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm test`
Expected: FAIL with "Cannot find module '../api'"

**Step 3: Create API service**

Create: `frontend/src/services/api.ts`

```typescript
import { Job } from '../types/job'
import { API_DEFAULT_URL } from '../constants/strings'

const API_URL = import.meta.env.VITE_API_URL || API_DEFAULT_URL

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  })
  
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`)
  }
  
  return response.json()
}

export const JobsAPI = {
  list: (status?: string) => 
    request<Job[]>(status ? `/jobs/?status=${status}` : '/jobs/'),
  
  get: (id: string) => 
    request<Job>(`/jobs/${id}`),
  
  create: (type: string, metadata?: Record<string, any>) =>
    request<Job>('/jobs/', {
      method: 'POST',
      body: JSON.stringify({ type, metadata }),
    }),
  
  getActive: () => 
    request<Job[]>('/jobs/active'),
  
  cancel: (id: string) => 
    request<void>(`/jobs/${id}`, { method: 'DELETE' }),
}

export const SystemAPI = {
  status: () => 
    request<{ status: string }>('/status'),
}
```

**Step 4: Run test to verify it passes**

Run: `cd frontend && npm test`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add frontend/src/services/api.ts frontend/src/services/__tests__/api.test.ts frontend/src/test/setup.ts
git commit -m "feat(frontend): add REST API service layer with tests"
```

---

### Task 2.4: Layout and Navigation (with constants)

**Files:**
- Create: `frontend/src/components/Layout.tsx`

**Step 1: Create Layout component using constants**

Create: `frontend/src/components/Layout.tsx`

```typescript
import { Outlet, NavLink } from 'react-router-dom'
import { APP_TITLE, NAV_DASHBOARD, NAV_INSTAGRAM, NAV_MATCHING, NAV_JOBS } from '../constants/strings'

export function Layout() {
  const navItems = [
    { to: '/', label: NAV_DASHBOARD },
    { to: '/instagram', label: NAV_INSTAGRAM },
    { to: '/matching', label: NAV_MATCHING },
    { to: '/jobs', label: NAV_JOBS },
  ]
  
  return (
    <div className="min-h-screen bg-gray-100">
      <nav className="bg-gray-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <h1 className="text-white font-bold text-xl">{APP_TITLE}</h1>
            <div className="flex space-x-4">
              {navItems.map(item => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    `px-3 py-2 rounded text-sm font-medium ${
                      isActive ? 'bg-gray-900 text-white' : 'text-gray-300 hover:bg-gray-700'
                    }`
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </div>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
        <Outlet />
      </main>
    </div>
  )
}
```

**Step 2: Update App.tsx**

Modify: `frontend/src/App.tsx`

```typescript
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { Layout } from './components/Layout'
import { JobsPage } from './pages/JobsPage'

function Dashboard() {
  return <div>Dashboard - Coming Soon</div>
}

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="instagram" element={<div>Instagram - Coming Soon</div>} />
          <Route path="matching" element={<div>Matching - Coming Soon</div>} />
          <Route path="jobs" element={<JobsPage />} />
        </Route>
      </Routes>
    </Router>
  )
}

export default App
```

**Step 3: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 4: Commit**

```bash
git add frontend/src/components/Layout.tsx frontend/src/App.tsx
git commit -m "feat(frontend): add Layout component using constants"
```

---

### Task 2.5: WebSocket Integration (removed - handled in JobsPage)

**Note:** WebSocket connection is now managed directly in JobsPage container component using useSocketStore. No need for separate hook - keeping it KISS.

---

## Testing & Verification

### Final Integration Test

**Step 1: Start backend**

Run: `cd backend && python app.py`

**Step 2: Start frontend**

Run: `cd frontend && npm run dev`

**Step 3: Test complete flow**

1. Open http://localhost:5173
2. Navigate to Jobs page
3. Create test job via API: `curl -X POST http://localhost:5000/api/jobs/ -H "Content-Type: application/json" -d '{"type":"test_job","metadata":{}}'`
4. Verify WebSocket connected indicator
5. Verify job appears in list

**Step 4: Run backend tests**

Backend:
```bash
cd backend && pytest tests/ -v
```

**Step 5: Build frontend**

Frontend:
```bash
cd frontend && npm run build
```

**Step 6: Final commit**

```bash
git add .
git commit -m "feat: complete Phase 1 and 2 of visualizer implementation"
```

**Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 3: Commit**

```bash
git add frontend/src/hooks/
git commit -m "feat(frontend): add useJobUpdates hook for WebSocket integration"
```

---

## Phase 3: Core Features (Jobs Page)

### Task 3.1: Jobs Page Components (TDD)

**Files:**
- Create: `frontend/src/components/__tests__/JobCard.test.tsx`
- Create: `frontend/src/components/__tests__/JobsList.test.tsx`
- Create: `frontend/src/components/JobCard.tsx`
- Create: `frontend/src/components/JobsList.tsx`

**Step 1: Write failing test for JobCard**

Create: `frontend/src/components/__tests__/JobCard.test.tsx`

```typescript
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { JobCard } from '../JobCard'
import { Job } from '../../types/job'

describe('JobCard', () => {
  const mockJob: Job = {
    id: 'test-job-123',
    type: 'analyze_instagram',
    status: 'pending',
    progress: 0,
    current_step: null,
    logs: [],
    result: null,
    error: null,
    created_at: '2024-03-19T10:00:00',
    started_at: null,
    completed_at: null,
    metadata: {},
  }
  
  it('should render job type and id', () => {
    render(<JobCard job={mockJob} />)
    
    expect(screen.getByText('analyze_instagram')).toBeInTheDocument()
    expect(screen.getByText('test-job')).toBeInTheDocument() // first 8 chars
  })
  
  it('should render pending status with correct color', () => {
    render(<JobCard job={mockJob} />)
    
    const statusBadge = screen.getByText('Pending')
    expect(statusBadge).toHaveClass('bg-yellow-100')
  })
  
  it('should render running status with progress bar', () => {
    const runningJob = { ...mockJob, status: 'running' as const, progress: 50, current_step: 'Processing' }
    render(<JobCard job={runningJob} />)
    
    expect(screen.getByText('Processing')).toBeInTheDocument()
    expect(screen.getByText('50%')).toBeInTheDocument()
  })
  
  it('should call onClick when clicked', () => {
    const handleClick = vi.fn()
    render(<JobCard job={mockJob} onClick={handleClick} />)
    
    screen.getByText('analyze_instagram').click()
    expect(handleClick).toHaveBeenCalledTimes(1)
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm test`
Expected: FAIL with "Cannot find module '../JobCard'"

**Step 3: Create JobCard presenter component**

Create: `frontend/src/components/JobCard.tsx`

```typescript
import { Job } from '../types/job'
import { STATUS_LABELS } from '../constants/strings'

interface JobCardProps {
  job: Job
  onClick?: () => void
}

const statusColors: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  running: 'bg-blue-100 text-blue-800',
  completed: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
  cancelled: 'bg-gray-100 text-gray-800',
}

export function JobCard({ job, onClick }: JobCardProps) {
  return (
    <div
      onClick={onClick}
      className="border rounded-lg p-4 hover:shadow-md transition-shadow cursor-pointer"
    >
      <div className="flex justify-between items-start mb-2">
        <div>
          <h3 className="font-semibold">{job.type}</h3>
          <p className="text-sm text-gray-500">{job.id.slice(0, 8)}</p>
        </div>
        <span className={`px-2 py-1 rounded text-xs font-medium ${statusColors[job.status]}`}>
          {STATUS_LABELS[job.status]}
        </span>
      </div>
      
      {job.status === 'running' && (
        <div className="mt-2">
          <div className="flex justify-between text-sm mb-1">
            <span>{job.current_step || 'Processing...'}</span>
            <span>{job.progress}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-blue-600 h-2 rounded-full"
              style={{ width: `${job.progress}%` }}
            />
          </div>
        </div>
      )}
      
      <div className="mt-2 text-xs text-gray-500">
        {new Date(job.created_at).toLocaleString()}
      </div>
    </div>
  )
}
```

**Step 4: Run test to verify it passes**

Run: `cd frontend && npm test`
Expected: PASS (4 tests for JobCard)

**Step 5: Write failing test for JobsList**

Create: `frontend/src/components/__tests__/JobsList.test.tsx`

```typescript
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { JobsList } from '../JobsList'
import { Job } from '../../types/job'
import { MSG_NO_JOBS } from '../../constants/strings'

describe('JobsList', () => {
  const mockJobs: Job[] = [
    {
      id: 'job-1',
      type: 'analyze',
      status: 'pending',
      progress: 0,
      current_step: null,
      logs: [],
      result: null,
      error: null,
      created_at: '2024-03-19T10:00:00',
      started_at: null,
      completed_at: null,
      metadata: {},
    },
    {
      id: 'job-2',
      type: 'vision_match',
      status: 'running',
      progress: 50,
      current_step: 'Processing',
      logs: [],
      result: null,
      error: null,
      created_at: '2024-03-19T11:00:00',
      started_at: null,
      completed_at: null,
      metadata: {},
    },
  ]
  
  it('should render all jobs', () => {
    render(<JobsList jobs={mockJobs} />)
    
    expect(screen.getByText('analyze')).toBeInTheDocument()
    expect(screen.getByText('vision_match')).toBeInTheDocument()
  })
  
  it('should call onJobClick when job is clicked', () => {
    const handleClick = vi.fn()
    render(<JobsList jobs={mockJobs} onJobClick={handleClick} />)
    
    screen.getByText('analyze').click()
    expect(handleClick).toHaveBeenCalledWith(mockJobs[0])
  })
  
  it('should show empty message when no jobs', () => {
    render(<JobsList jobs={[]} />)
    
    expect(screen.getByText(MSG_NO_JOBS)).toBeInTheDocument()
  })
})
```

**Step 6: Run test to verify it fails**

Run: `cd frontend && npm test`
Expected: FAIL with "Cannot find module '../JobsList'"

**Step 7: Create JobsList presenter component**

Create: `frontend/src/components/JobsList.tsx`

```typescript
import { Job } from '../types/job'
import { JobCard } from './JobCard'
import { MSG_NO_JOBS } from '../constants/strings'

interface JobsListProps {
  jobs: Job[]
  onJobClick?: (job: Job) => void
}

export function JobsList({ jobs, onJobClick }: JobsListProps) {
  if (jobs.length === 0) {
    return <div className="text-center py-12 text-gray-500">{MSG_NO_JOBS}</div>
  }
  
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {jobs.map(job => (
        <JobCard
          key={job.id}
          job={job}
          onClick={() => onJobClick?.(job)}
        />
      ))}
    </div>
  )
}
```

**Step 8: Run test to verify it passes**

Run: `cd frontend && npm test`
Expected: PASS (all tests)

**Step 9: Commit**

```bash
git add frontend/src/components/JobCard.tsx frontend/src/components/JobsList.tsx frontend/src/components/__tests__/
git commit -m "feat(frontend): add JobCard and JobsList components with tests"
```

Create: `frontend/src/components/JobCard.tsx`

```typescript
import { Job } from '../types/job'
import { STATUS_LABELS } from '../constants/strings'

interface JobCardProps {
  job: Job
  onClick?: () => void
}

const statusColors: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  running: 'bg-blue-100 text-blue-800',
  completed: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
  cancelled: 'bg-gray-100 text-gray-800',
}

export function JobCard({ job, onClick }: JobCardProps) {
  return (
    <div
      onClick={onClick}
      className="border rounded-lg p-4 hover:shadow-md transition-shadow cursor-pointer"
    >
      <div className="flex justify-between items-start mb-2">
        <div>
          <h3 className="font-semibold">{job.type}</h3>
          <p className="text-sm text-gray-500">{job.id.slice(0, 8)}</p>
        </div>
        <span className={`px-2 py-1 rounded text-xs font-medium ${statusColors[job.status]}`}>
          {STATUS_LABELS[job.status]}
        </span>
      </div>
      
      {job.status === 'running' && (
        <div className="mt-2">
          <div className="flex justify-between text-sm mb-1">
            <span>{job.current_step || 'Processing...'}</span>
            <span>{job.progress}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-blue-600 h-2 rounded-full"
              style={{ width: `${job.progress}%` }}
            />
          </div>
        </div>
      )}
      
      <div className="mt-2 text-xs text-gray-500">
        {new Date(job.created_at).toLocaleString()}
      </div>
    </div>
  )
}
```

**Step 3: Create JobsPage container component (integration test)**

**Note:** Container components are harder to test in isolation since they integrate with API/WebSocket. We'll test them via E2E tests or manual testing. For now, we create the component without unit tests.

Create: `frontend/src/pages/JobsPage.tsx`

```typescript
import { useEffect, useState } from 'react'
import { Job } from '../types/job'
import { JobsList } from '../components/JobsList'
import { JobsAPI } from '../services/api'
import { useSocketStore } from '../stores/socketStore'
import { MSG_LOADING, MSG_ERROR_PREFIX, MSG_CONNECTED, MSG_DISCONNECTED } from '../constants/strings'

export function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const { socket, connected, connect, disconnect } = useSocketStore()
  
  useEffect(() => {
    connect()
    return () => disconnect()
  }, [connect, disconnect])
  
  useEffect(() => {
    let mounted = true
    
    async function fetchJobs() {
      try {
        const fetchedJobs = await JobsAPI.list()
        if (mounted) {
          setJobs(fetchedJobs)
          setError(null)
        }
      } catch (err) {
        if (mounted) {
          setError(err instanceof Error ? err.message : 'Unknown error')
        }
      } finally {
        if (mounted) {
          setLoading(false)
        }
      }
    }
    
    fetchJobs()
    return () => { mounted = false }
  }, [])
  
  useEffect(() => {
    if (!socket || !connected) return
    
    socket.on('job_created', (job: Job) => {
      setJobs(prev => [job, ...prev])
    })
    
    socket.on('job_updated', (updatedJob: Job) => {
      setJobs(prev => prev.map(job => 
        job.id === updatedJob.id ? updatedJob : job
      ))
    })
    
    return () => {
      socket.off('job_created')
      socket.off('job_updated')
    }
  }, [socket, connected])
  
  if (loading) {
    return <div className="text-center py-8">{MSG_LOADING}</div>
  }
  
  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold">Jobs</h2>
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
          <span className="text-sm text-gray-600">
            {connected ? MSG_CONNECTED : MSG_DISCONNECTED}
          </span>
        </div>
      </div>
      
      {error && (
        <div className="mb-4 p-4 bg-red-50 text-red-800 rounded">
          {MSG_ERROR_PREFIX} {error}
        </div>
      )}
      
      <JobsList
        jobs={jobs}
        onJobClick={job => console.log('Job clicked:', job.id)}
      />
    </div>
  )
}
```

**Step 4: Test manually**

Run: `cd backend && python app.py`
Run: `cd frontend && npm run dev`

Open: http://localhost:5173/jobs
Expected: Jobs page loads with empty state

**Step 5: Create test job and verify**

Run: `curl -X POST http://localhost:5000/api/jobs/ -H "Content-Type: application/json" -d '{"type":"test_job","metadata":{}}'`

Refresh browser
Expected: Job appears in list, WebSocket connected indicator

**Step 6: Run all frontend tests**

Run: `cd frontend && npm test`
Expected: PASS (all tests)

**Step 7: Commit**

```bash
git add frontend/src/pages/JobsPage.tsx
git commit -m "feat(frontend): add Jobs page container component"
```

---

## Testing & Verification

### Final Integration Test

**Step 1: Start backend**

Run: `cd backend && python app.py`

**Step 2: Start frontend**

Run: `cd frontend && npm run dev`

**Step 3: Test complete flow**

1. Open http://localhost:5173
2. Navigate to Jobs page
3. Create test job via API
4. Verify WebSocket connection
5. Verify job list updates

**Step 4: Run all tests**

Backend:
```bash
cd backend && pytest tests/ -v
```

Frontend:
```bash
cd frontend && npm test
```

**Step 5: Final commit**

```bash
git add .
git commit -m "feat: complete Phase 1 and 2 of visualizer implementation"
```

---

## Next Phases (Future Work)

### Phase 3: Dashboard & Instagram Pages
- Dashboard stats cards
- Instagram image grid
- Image thumbnails

### Phase 4: Matching & Reports
- Run matching workflow
- Progress tracking
- Report viewing

### Phase 5: Polish
- Error notifications
- Loading skeletons
- Responsive design

---

## Architecture Decisions

1. **TinyDB for Jobs**: Reuse existing database pattern, no new dependencies
2. **Flask-SocketIO for WebSockets**: Better than SSE for bidirectional comms
3. **Minimal Zustand usage**: Only WebSocket connection state, use React state for page data
4. **Container/Presenter pattern**: Smart components fetch data, dumb components render props
5. **Constants file**: All UI strings in one place, DRY principle
6. **Vite over Create React App**: Faster dev experience, better TypeScript support
7. **Tailwind CSS**: Rapid UI development, consistent styling
8. **Job Runner Pattern**: Background threads in Flask, simple and effective for local use
9. **Environment Variables**: Keep real paths out of git, use .env files
10. **KISS**: Keep it simple, no over-engineering

---

## Testing Strategy

### Backend Tests
- Unit tests for database operations, job runner (pytest)
- Integration tests for REST API endpoints
- WebSocket connection tests

### Frontend Tests
- **Unit tests** (vitest + testing-library):
  - Constants file (trivial but validates structure)
  - API service functions (mocked fetch)
  - Presenter components (JobCard, JobsList)
  
- **Integration tests** (future):
  - Container components with API mocked
  - WebSocket integration
  
- **E2E tests** (future):
  - Playwright/Cypress for full workflow

### Test Run Commands
```bash
# Backend tests
cd backend && pytest tests/ -v

# Frontend tests
cd frontend && npm test

# Run frontend tests in watch mode
cd frontend && npm test -- --watch
```

---

## Deployment Notes

- Backend serves frontend build in production
- Environment variables set before build
- No authentication needed (local use)
- CORS configured for single frontend URL