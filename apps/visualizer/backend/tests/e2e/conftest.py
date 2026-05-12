import os
import pathlib
import shutil
import socket
import subprocess
import tempfile
import time
import sys
import urllib.error
import urllib.request

import pytest


def _find_free_port() -> int:
    """Bind to port 0, let the OS pick, then release — returns the chosen port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

TESTS_E2E_DIR = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_E2E_DIR))

backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, backend_dir)

from database import init_db
from harness.browser_session import BrowserSession

from fixtures.factory import ensure_writable_fixture_library


@pytest.fixture(scope="session")
def viz_e2e_base_url():
    port = _find_free_port()
    port_s = str(port)
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
        conn = init_db(str(jobs_db))
        if conn is not None:
            conn.close()
        lib_copy = tmpdir / "library.sqlite"
        # TEMP COPY: fixture library DB — shutil.copy2 of library_seed.db so the stack uses a writable isolated library SQLite file.
        ensure_writable_fixture_library(lib_copy)
        base_url = f"http://127.0.0.1:{port_s}"
        proc_env = os.environ | {
            "FLASK_PORT": "5099",
            "FLASK_HOST": "127.0.0.1",
            "FLASK_DEBUG": "false",
            "DATABASE_PATH": str(jobs_db.resolve()),
            "LIBRARY_DB": str(lib_copy.resolve()),
            "FRONTEND_URL": f"http://127.0.0.1:5099,http://localhost:5099",
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
                port_s,
                "--no-reload",
            ],
            cwd=backend_dir,
            env=proc_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 60.0
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(
                    f"{base_url}/api/status", timeout=5
                ) as resp:
                    if resp.getcode() == 200:
                        break
            except (urllib.error.URLError, OSError):
                pass
            time.sleep(0.25)
        else:
            raise RuntimeError(
                f"timeout waiting for GET api/status on 127.0.0.1:{port_s} (E2E stack health check)"
            )
        yield base_url
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
