"""Architecture policy checks (line budget, layered imports) — see docs/architecture.md."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _line_count(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    if not text.endswith("\n"):
        return text.count("\n") + 1
    return text.count("\n")


def _iter_core_py_files() -> list[Path]:
    root = REPO_ROOT / "lightroom_tagger" / "core"
    paths: list[Path] = []
    for p in sorted(root.rglob("*.py")):
        if p.name.startswith("test_"):
            continue
        paths.append(p)
    return paths


def test_core_python_files_respect_line_budget() -> None:
    for path in _iter_core_py_files():
        assert _line_count(path) <= 400, f"{path.relative_to(REPO_ROOT)} exceeds 400 lines"


def _gather_imported_top_names(tree: ast.Module) -> set[str]:
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.add(alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            out.add(node.module.split(".", 1)[0])
    return out


def test_core_modules_do_not_import_apps_packages() -> None:
    for path in _iter_core_py_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for name in _gather_imported_top_names(tree):
            assert name != "apps", f"{path} imports application package {name!r}"


def _api_anchor_first_segment(rel: Path) -> str | None:
    """First routing namespace under backend/api (e.g. identity, images, jobs)."""
    if rel.name == "__init__.py" and len(rel.parts) == 1:
        return None
    if len(rel.parts) == 1:
        return rel.stem
    return rel.parts[0]


def _gather_api_first_segments_from_module(tree: ast.Module) -> list[tuple[str, int]]:
    """Pairs of (target_first_segment, lineno) for absolute ``api.*`` references."""
    hits: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                nm = alias.name
                if not nm.startswith("api.") or len(nm) <= 4:
                    continue
                first = nm[4:].split(".")[0]
                if first:
                    hits.append((first, node.lineno))
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            if not node.module.startswith("api.") or len(node.module) <= 4:
                continue
            first = node.module[4:].split(".")[0]
            if first:
                hits.append((first, node.lineno))
    return hits


def test_api_modules_do_not_import_sibling_api_modules() -> None:
    api_root = REPO_ROOT / "apps" / "visualizer" / "backend" / "api"
    for path in sorted(api_root.rglob("*.py")):
        if path.name.startswith("test_"):
            continue
        rel = path.relative_to(api_root)
        anchor = _api_anchor_first_segment(rel)
        if anchor is None:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for target, lineno in _gather_api_first_segments_from_module(tree):
            assert target == anchor, (
                f"{path.relative_to(REPO_ROOT)}:{lineno}: imports api.{target}.* "
                f"but belongs under api/{anchor}/ (no cross-sibling api imports)"
            )
