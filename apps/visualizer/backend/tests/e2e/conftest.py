import os
import pathlib
import shutil
import subprocess
import tempfile
import time
import sys
import urllib.error
import urllib.request

import pytest

TESTS_E2E_DIR = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_E2E_DIR))

backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, backend_dir)

from database import init_db
from harness.browser_session import BrowserSession

from fixtures.factory import ensure_writable_fixture_library


@pytest.fixture(scope="session")
def viz_e2e_base_url():
    tmpdir = pathlib.Path(tempfile.mkdtemp(prefix="viz-e2e-"))
    proc = None
    try:
        subprocess.run(
            ["npm", "run", "build"],
            cwd=os.path.join(backend_dir, "..", "frontend"),
            env=os.environ | {"VITE_BACKEND_PORT": "5099"},
            check=True,
        )
        dist_dir = pathlib.Path(backend_dir).parent / "frontend" / "dist"
        jobs_db = tmpdir / "jobs.sqlite"
        init_db(str(jobs_db))
        lib_copy = tmpdir / "library.sqlite"
        # TEMP COPY: fixture library DB — shutil.copy2 of library_seed.db so the stack uses a writable isolated library SQLite file.
        ensure_writable_fixture_library(lib_copy)
        proc_env = os.environ | {
            "FLASK_PORT": "5099",
            "FLASK_HOST": "127.0.0.1",
            "FLASK_DEBUG": "false",
            "DATABASE_PATH": str(jobs_db.resolve()),
            "LIBRARY_DB": str(lib_copy.resolve()),
            "FRONTEND_URL": "http://127.0.0.1:5099,http://localhost:5099",
            "VISUALIZER_E2E_STATIC_DIST": str(dist_dir.resolve()),
        }
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "flask",
                "--app",
                "app:create_app",
                "run",
                "--port",
                "5099",
                "--no-reload",
            ],
            cwd=backend_dir,
            env=proc_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        deadline = time.monotonic() + 60.0
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(
                    "http://127.0.0.1:5099/api/status", timeout=5
                ) as resp:
                    if resp.getcode() == 200:
                        break
            except (urllib.error.URLError, OSError):
                pass
            time.sleep(0.25)
        else:
            raise RuntimeError(
                "timeout waiting for GET api/status on 127.0.0.1:5099 (E2E stack health check)"
            )
        yield "http://127.0.0.1:5099"
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def browser_session(viz_e2e_base_url):
    _ = viz_e2e_base_url
    session = BrowserSession()
    try:
        yield session
    finally:
        session.close()
