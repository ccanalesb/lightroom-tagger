#!/usr/bin/env python3
"""Verify README.md has no dead ends: commands, paths, config keys, env vars, and routes."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, fields
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
README = REPO_ROOT / "README.md"

APP_TSX = REPO_ROOT / "apps" / "visualizer" / "frontend" / "src" / "App.tsx"

# Paths referenced in README that are allowed to be created by the reader.
_OPTIONAL_PATHS = frozenset({"library.db", "config.yaml", "export.json"})

# Every oracle below is derived from the source of truth at run time, never
# copied into this file. A hardcoded list would drift the moment a command or
# page is added or removed — and a stale oracle passing on a stale README is
# exactly the rot this script exists to catch (the README documented
# `lightroom-import-dump` for months after it was deleted).

_CONFIG_FIELD_NAMES: frozenset[str] | None = None
_CONFIG_ENV_VAR_NAMES: frozenset[str] | None = None
_CLI_SUBCOMMANDS: frozenset[str] | None = None
_VISUALIZER_PAGES: frozenset[str] | None = None
_CONSOLE_SCRIPTS: frozenset[str] | None = None


def _config_field_names() -> frozenset[str]:
    global _CONFIG_FIELD_NAMES
    if _CONFIG_FIELD_NAMES is None:
        from lightroom_tagger.core.config import Config

        _CONFIG_FIELD_NAMES = frozenset(f.name for f in fields(Config))
    return _CONFIG_FIELD_NAMES


def _config_env_var_names() -> frozenset[str]:
    global _CONFIG_ENV_VAR_NAMES
    if _CONFIG_ENV_VAR_NAMES is None:
        from lightroom_tagger.core.config import CONFIG_ENV_MAPPINGS

        _CONFIG_ENV_VAR_NAMES = frozenset(CONFIG_ENV_MAPPINGS)
    return _CONFIG_ENV_VAR_NAMES


def _cli_subcommands() -> frozenset[str]:
    """Subcommand names straight off the CLI registry."""
    global _CLI_SUBCOMMANDS
    if _CLI_SUBCOMMANDS is None:
        from lightroom_tagger.core.cli_commands import COMMANDS

        _CLI_SUBCOMMANDS = frozenset(command.name for command in COMMANDS)
    return _CLI_SUBCOMMANDS


def _visualizer_pages() -> frozenset[str]:
    """Non-redirect routes parsed out of App.tsx.

    Splitting on ``<Route`` gives one chunk per route whose text runs up to the
    next route, so a ``<Navigate>`` inside a chunk belongs to that route and
    marks it a redirect rather than a page.
    """
    global _VISUALIZER_PAGES
    if _VISUALIZER_PAGES is not None:
        return _VISUALIZER_PAGES

    pages: set[str] = set()
    for chunk in APP_TSX.read_text(encoding="utf-8").split("<Route")[1:]:
        if "<Navigate" in chunk:
            continue
        if re.match(r"\s+index\b", chunk):
            pages.add("/")
            continue
        match = re.search(r'path="([^"]+)"', chunk)
        if match is None:
            continue
        path = match.group(1)
        pages.add(path if path.startswith("/") else f"/{path}")

    _VISUALIZER_PAGES = frozenset(pages)
    return _VISUALIZER_PAGES


@dataclass
class Finding:
    kind: str
    detail: str


def _extract_bash_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    for match in re.finditer(r"```bash\n(.*?)```", text, re.DOTALL):
        blocks.append(match.group(1))
    return blocks


def _extract_cli_invocations(bash_blocks: list[str]) -> list[str]:
    """Every ``lightroom-*`` console script, not just the surviving one.

    Matching only ``lightroom-tagger`` would let the exact historical rot
    through: the README documented ``lightroom-import-dump`` and
    ``lightroom-match-dump`` long after #225 deleted them, and a checker blind
    to those names would have reported the README clean.
    """
    invocations: list[str] = []
    pattern = re.compile(
        r"(?:^|[;&|]\s*|\n)\s*"
        r"(?:(?:lightroom-[a-z0-9-]+)|(?:python(?:3)?\s+-m\s+lightroom_tagger))"
        r"(?:\s+[^\n#;|&]*)?",
        re.MULTILINE,
    )
    for block in bash_blocks:
        for match in pattern.finditer(block):
            line = match.group(0).strip()
            if line:
                invocations.append(line)
    return invocations


def _console_scripts() -> frozenset[str]:
    """Console-script names declared in pyproject's ``[project.scripts]``."""
    global _CONSOLE_SCRIPTS
    if _CONSOLE_SCRIPTS is None:
        import tomllib

        with open(REPO_ROOT / "pyproject.toml", "rb") as handle:
            manifest = tomllib.load(handle)
        _CONSOLE_SCRIPTS = frozenset(manifest.get("project", {}).get("scripts", {}))
    return _CONSOLE_SCRIPTS


def _subcommand_from_invocation(invocation: str) -> str | None:
    tokens = invocation.split()
    # lightroom-tagger <subcommand> ...
    if tokens[0] == "lightroom-tagger":
        if len(tokens) < 2:
            return None
        return tokens[1]
    # python -m lightroom_tagger <subcommand> ...
    if "lightroom_tagger" in tokens:
        idx = tokens.index("lightroom_tagger")
        if idx + 1 < len(tokens):
            return tokens[idx + 1]
    return None


def _extract_repo_paths(text: str) -> set[str]:
    paths: set[str] = set()
    # Markdown links: [label](path)
    for match in re.finditer(r"\]\(([^)#?]+)\)", text):
        candidate = match.group(1).strip()
        if _looks_like_repo_path(candidate):
            paths.add(candidate.rstrip("/"))
    # Inline backtick paths
    for match in re.finditer(r"`((?:[\w.-]+/)+[\w.-]+(?:\.[\w]+)?)`", text):
        candidate = match.group(1)
        if _looks_like_repo_path(candidate):
            paths.add(candidate)
    # config.yaml at repo root (mentioned without backticks)
    if "config.yaml" in text:
        paths.add("config.yaml")
    return paths


def _looks_like_repo_path(candidate: str) -> bool:
    if candidate.startswith(("http://", "https://", "mailto:")):
        return False
    if candidate.startswith("/"):
        return False
    if " " in candidate:
        return False
    if candidate in {".", ".."}:
        return False
    # Require at least one path segment or a known root file
    return "/" in candidate or candidate.endswith(
        (".md", ".yaml", ".yml", ".py", ".json", ".txt", ".sh")
    )


def _extract_config_yaml_keys(text: str) -> set[str]:
    keys: set[str] = set()
    for match in re.finditer(r"```ya?ml\n(.*?)```", text, re.DOTALL):
        block = match.group(1)
        try:
            parsed = yaml.safe_load(block)
        except yaml.YAMLError:
            continue
        if isinstance(parsed, dict):
            keys.update(parsed.keys())
    return keys


def _extract_documented_env_vars(text: str) -> set[str]:
    """Env vars from the README's environment-overrides callout."""
    env_vars: set[str] = set()
    for line in text.splitlines():
        if not line.startswith("Environment overrides"):
            continue
        for match in re.finditer(r"`([A-Z][A-Z0-9_]+)`", line):
            env_vars.add(match.group(1))
    return env_vars


def _extract_named_pages(text: str) -> set[str]:
    """Extract URL paths from the Pages table in README."""
    pages: set[str] = set()
    in_pages = False
    for line in text.splitlines():
        if line.startswith("### Pages"):
            in_pages = True
            continue
        if in_pages and line.startswith("### "):
            break
        if in_pages and line.startswith("|") and not line.startswith("|------"):
            # URLs in the table are backticked (`/images`); without stripping the
            # backticks nothing ever matched and this check silently passed.
            cells = [c.strip().strip("`").strip() for c in line.strip("|").split("|")]
            if len(cells) >= 2 and cells[1].startswith("/"):
                pages.add(cells[1].split()[0])
    return pages


def verify_readme(readme_path: Path = README) -> list[Finding]:
    findings: list[Finding] = []
    text = readme_path.read_text(encoding="utf-8")
    bash_blocks = _extract_bash_blocks(text)

    known_subcommands = _cli_subcommands()
    known_scripts = _console_scripts()
    for invocation in _extract_cli_invocations(bash_blocks):
        script = invocation.split()[0]
        if script.startswith("lightroom-") and script not in known_scripts:
            findings.append(
                Finding("cli", f"Undeclared console script {script!r} in: {invocation!r}")
            )
            continue
        subcommand = _subcommand_from_invocation(invocation)
        if subcommand is None:
            findings.append(Finding("cli", f"Missing subcommand: {invocation!r}"))
        elif subcommand not in known_subcommands:
            findings.append(
                Finding("cli", f"Unknown subcommand {subcommand!r} in: {invocation!r}")
            )

    for rel_path in sorted(_extract_repo_paths(text)):
        if rel_path in _OPTIONAL_PATHS:
            continue
        full = REPO_ROOT / rel_path
        if not full.exists():
            findings.append(Finding("path", f"Missing path: {rel_path}"))

    known = _config_field_names()
    for key in sorted(_extract_config_yaml_keys(text)):
        if key not in known:
            findings.append(Finding("config", f"Unknown config key in README example: {key!r}"))

    known_env = _config_env_var_names()
    for env_var in sorted(_extract_documented_env_vars(text)):
        if env_var not in known_env:
            findings.append(
                Finding("env", f"Unknown config env var in README: {env_var!r}")
            )

    real_pages = _visualizer_pages()
    for page in sorted(_extract_named_pages(text)):
        if page not in real_pages:
            findings.append(Finding("route", f"README lists non-page route: {page!r}"))

    return findings


def run_smoke(*, port: int = 5001, timeout_s: float = 60.0) -> list[Finding]:
    """Clean-clone smoke: pip install, init db, boot backend, hit /api/jobs/health."""
    findings: list[Finding] = []
    with tempfile.TemporaryDirectory(prefix="lt-readme-smoke-") as tmp:
        clone_dir = Path(tmp) / "clone"
        subprocess.run(
            ["git", "clone", str(REPO_ROOT), str(clone_dir)],
            check=True,
            capture_output=True,
            text=True,
        )
        venv_python = clone_dir / ".venv" / "bin" / "python"
        subprocess.run(
            [sys.executable, "-m", "venv", str(clone_dir / ".venv")],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [str(venv_python), "-m", "pip", "install", "-e", "."],
            cwd=clone_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [
                str(venv_python),
                "-m",
                "pip",
                "install",
                "-r",
                "apps/visualizer/backend/requirements.txt",
            ],
            cwd=clone_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        db_path = clone_dir / "library.db"
        subprocess.run(
            [str(venv_python), "-m", "lightroom_tagger", "init", "--db", str(db_path)],
            cwd=clone_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        if not db_path.exists():
            findings.append(Finding("smoke", "lightroom-tagger init did not create library.db"))
            return findings

        env = {
            **dict(__import__("os").environ),
            "LIBRARY_DB": str(db_path),
            "FLASK_PORT": str(port),
            "FLASK_HOST": "127.0.0.1",
        }
        backend_dir = clone_dir / "apps/visualizer/backend"
        proc = subprocess.Popen(
            [str(venv_python), "app.py"],
            cwd=backend_dir,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            deadline = time.monotonic() + timeout_s
            health_url = f"http://127.0.0.1:{port}/api/jobs/health"
            while time.monotonic() < deadline:
                try:
                    with urllib.request.urlopen(health_url, timeout=1.0) as resp:
                        if resp.status == 200:
                            break
                except (urllib.error.URLError, TimeoutError):
                    pass
                time.sleep(0.5)
            else:
                findings.append(
                    Finding("smoke", f"Backend did not return 200 from {health_url} within {timeout_s}s")
                )
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--readme",
        type=Path,
        default=README,
        help="Path to README.md (default: repo root README)",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run clean-clone smoke test (slow; needs network for pip if deps missing)",
    )
    args = parser.parse_args(argv)

    findings = verify_readme(args.readme)
    if args.smoke:
        findings.extend(run_smoke())

    if findings:
        for item in findings:
            print(f"[{item.kind}] {item.detail}", file=sys.stderr)
        return 1
    print("README verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
