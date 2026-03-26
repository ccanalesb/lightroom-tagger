from pathlib import Path
import subprocess
import sys


ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "apps" / "visualizer" / "backend"
DEV_UP_SCRIPT = ROOT_DIR / "scripts" / "dev-up.sh"


def test_backend_app_can_boot_from_backend_directory_without_extra_pythonpath():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from app import create_app; app = create_app(); print(app.name)",
        ],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("backend")


def test_dev_up_uses_repo_root_pythonpath_and_direct_vite_binary():
    content = DEV_UP_SCRIPT.read_text()

    assert 'PYTHONPATH="$ROOT_DIR${PYTHONPATH:+:$PYTHONPATH}" python3 app.py' in content
    assert 'exec "$FRONTEND_DIR/node_modules/.bin/vite"' in content
