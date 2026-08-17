"""Architecture policy checks (line budget, layered imports) — see docs/architecture.md."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _line_count_source(source: str) -> int:
    if not source.endswith("\n"):
        return source.count("\n") + 1
    return source.count("\n")


def _line_count(path: Path) -> int:
    return _line_count_source(path.read_text(encoding="utf-8"))


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


# Shared, non-route infrastructure under api/ that every route area is meant to
# import (the OpenAPI spec singleton and the request/response schemas). The rule
# forbids coupling between route *areas*, not imports of this shared plumbing.
_SHARED_API_MODULES = frozenset({"openapi", "schemas"})


def _cross_sibling_api_import_violations(
    tree: ast.Module, anchor: str,
) -> list[tuple[str, int]]:
    """Pairs of (target_first_segment, lineno) for forbidden cross-sibling api imports."""
    hits: list[tuple[str, int]] = []
    for target, lineno in _gather_api_first_segments_from_module(tree):
        if target in _SHARED_API_MODULES:
            continue
        if target != anchor:
            hits.append((target, lineno))
    return hits


def _scan_cross_sibling_api_source(
    source: str, anchor: str, filename: str = "fake/api/scores/routes.py",
) -> list[tuple[str, int]]:
    tree = ast.parse(source, filename=filename)
    return _cross_sibling_api_import_violations(tree, anchor)


def _apps_import_violations(tree: ast.Module) -> list[str]:
    return [name for name in _gather_imported_top_names(tree) if name == "apps"]


def _scan_apps_import_source(
    source: str, filename: str = "fake/core/module.py",
) -> list[str]:
    tree = ast.parse(source, filename=filename)
    return _apps_import_violations(tree)


def _scan_line_budget_source(source: str, budget: int = 400) -> bool:
    return _line_count_source(source) > budget


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
        for target, lineno in _cross_sibling_api_import_violations(tree, anchor):
            assert target == anchor, (
                f"{path.relative_to(REPO_ROOT)}:{lineno}: imports api.{target}.* "
                f"but belongs under api/{anchor}/ (no cross-sibling api imports)"
            )


def test_detector_flags_cross_sibling_api_import() -> None:
    hits = _scan_cross_sibling_api_source(
        "from api.perspectives import get_perspective\n",
        anchor="scores",
    )
    assert hits == [("perspectives", 1)]


def test_detector_ignores_shared_api_modules_and_same_anchor() -> None:
    assert not _scan_cross_sibling_api_source(
        "from api.openapi import spec\nfrom api.schemas import ScoreOut\n",
        anchor="scores",
    )
    assert not _scan_cross_sibling_api_source(
        "from api.scores import routes\n",
        anchor="scores",
    )


def test_detector_flags_apps_package_import() -> None:
    assert _scan_apps_import_source("from apps.visualizer.backend.api import x\n") == ["apps"]
    assert _scan_apps_import_source("import apps.visualizer\n") == ["apps"]


def test_detector_ignores_non_apps_top_level_imports() -> None:
    assert not _scan_apps_import_source(
        "from lightroom_tagger.core.config import load_config\nimport flask\n"
    )


def test_detector_flags_source_over_line_budget() -> None:
    assert _scan_line_budget_source("x\n" * 401, budget=400)


def test_detector_ignores_source_at_or_under_line_budget() -> None:
    assert not _scan_line_budget_source("x\n" * 400, budget=400)
    assert not _scan_line_budget_source("x\n" * 399, budget=400)
