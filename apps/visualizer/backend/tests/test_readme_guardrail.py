"""Guardrail: README commands, paths, config keys, and page routes stay truthful."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[4]
_VERIFY_SCRIPT = _REPO_ROOT / "scripts" / "verify_readme.py"


def _load_verifier():
    spec = importlib.util.spec_from_file_location("verify_readme", _VERIFY_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    # @dataclass resolves string annotations through sys.modules, so the module
    # has to be registered before it executes.
    sys.modules["verify_readme"] = module
    spec.loader.exec_module(module)
    return module


def test_readme_has_no_dead_ends():
    result = subprocess.run(
        [sys.executable, str(_VERIFY_SCRIPT)],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout


@pytest.mark.parametrize(
    ("kind", "readme"),
    [
        # The command that actually rotted: deleted with #225, documented for months after.
        (
            "cli",
            "# X\n\n```bash\nlightroom-import-dump --db library.db\n```\n",
        ),
        # The key class that took the app down in #245.
        (
            "config",
            "# X\n\n```yaml\ncatalog_path: /a.lrcat\nmatch_threshold: 0.7\n```\n",
        ),
        # A redirect listed as if it were a page.
        (
            "route",
            "# X\n\n### Pages\n\n| Page | URL |\n|---|---|\n| Matching | `/matching` |\n",
        ),
        (
            "path",
            "# X\n\nSee [notes](docs/this-file-does-not-exist.md).\n",
        ),
    ],
)
def test_verifier_actually_fires(kind, readme, tmp_path):
    """A verifier that never fails is indistinguishable from no verifier.

    Each case is a real regression this check exists to catch, fed in as a
    synthetic README so the oracles are exercised rather than assumed.
    """
    verifier = _load_verifier()
    fake = tmp_path / "README.md"
    fake.write_text(readme, encoding="utf-8")

    findings = verifier.verify_readme(fake)

    assert kind in {f.kind for f in findings}, f"expected a {kind!r} finding, got {findings}"
