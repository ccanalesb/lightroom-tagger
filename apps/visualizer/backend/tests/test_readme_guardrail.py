"""Guardrail: README commands, paths, config keys, and page routes stay truthful."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[4]
_VERIFY_SCRIPT = _REPO_ROOT / "scripts" / "verify_readme.py"


def test_readme_has_no_dead_ends():
    result = subprocess.run(
        [sys.executable, str(_VERIFY_SCRIPT)],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout
