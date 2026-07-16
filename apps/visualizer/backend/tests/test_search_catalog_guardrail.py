"""Guardrail (ADR-0015): web layer reaches catalog search only through search_catalog."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
_REPO_ROOT = _BACKEND_ROOT.parents[2]
_VISUALIZER_BACKEND = _REPO_ROOT / "apps/visualizer/backend"

_FORBIDDEN_NAMES: frozenset[str] = frozenset(
    {
        "run_nl_catalog_filter_llm",
        "run_nl_catalog_filter_llm_multi_turn",
        "run_tool_calling_search",
        "run_semantic_hybrid_search",
        "list_pin_similarity_candidate_keys",
    }
)


@dataclass(frozen=True)
class _SearchRunnerHit:
    rel_path: str
    line: int
    kind: str
    name: str


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


class _SearchRunnerVisitor(ast.NodeVisitor):
    def __init__(self, rel_path: str) -> None:
        self.rel_path = rel_path
        self.hits: list[_SearchRunnerHit] = []

    def _record(self, line: int, kind: str, name: str) -> None:
        self.hits.append(
            _SearchRunnerHit(
                rel_path=self.rel_path,
                line=line,
                kind=kind,
                name=name,
            )
        )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            imported = alias.name
            if imported in _FORBIDDEN_NAMES:
                self._record(node.lineno, "import", imported)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = _call_name(node)
        if name in _FORBIDDEN_NAMES:
            self._record(node.lineno, "call", name)
        self.generic_visit(node)


def _iter_scanned_backend_files() -> list[str]:
    rel_paths: list[str] = []
    for path in sorted(_VISUALIZER_BACKEND.rglob("*.py")):
        rel = path.relative_to(_REPO_ROOT).as_posix()
        if "/tests/" in rel or rel.endswith("/tests/conftest.py"):
            continue
        if path.name.startswith("test_"):
            continue
        rel_paths.append(rel)
    return rel_paths


def _scan_file(rel_path: str) -> list[_SearchRunnerHit]:
    path = _REPO_ROOT / rel_path
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    visitor = _SearchRunnerVisitor(rel_path)
    visitor.visit(tree)
    return visitor.hits


@pytest.mark.parametrize("rel_path", _iter_scanned_backend_files())
def test_no_direct_catalog_search_runners_in_web_layer(rel_path: str) -> None:
    hits = _scan_file(rel_path)
    if not hits:
        return
    lines = [
        f"{h.rel_path}:{h.line} [{h.kind}] {h.name}"
        for h in hits
    ]
    pytest.fail(
        "Direct catalog search runner import/call found in the web layer "
        "(ADR-0015). Use lightroom_tagger.core.catalog_search.search_catalog "
        "instead:\n"
        + "\n".join(lines)
    )


def test_guardrail_scans_images_search_blueprint() -> None:
    rel = "apps/visualizer/backend/api/images/search.py"
    assert rel in _iter_scanned_backend_files()
    assert not _scan_file(rel)


def _scan_source(source: str, rel_path: str = "fake/module.py") -> list[_SearchRunnerHit]:
    visitor = _SearchRunnerVisitor(rel_path)
    visitor.visit(ast.parse(source))
    return visitor.hits


def test_detector_flags_direct_runner_import() -> None:
    hits = _scan_source(
        "from lightroom_tagger.core.nl_catalog_search import run_nl_catalog_filter_llm\n"
    )
    assert len(hits) == 1
    assert hits[0].kind == "import"
    assert hits[0].name == "run_nl_catalog_filter_llm"


def test_detector_flags_direct_runner_call() -> None:
    hits = _scan_source(
        "def bad():\n"
        "    return run_semantic_hybrid_search(db, user_query='x', fts_match='x',\n"
        "        query_vec_blob=b'', limit=10, offset=0)\n"
    )
    assert len(hits) == 1
    assert hits[0].kind == "call"
    assert hits[0].name == "run_semantic_hybrid_search"


def test_detector_flags_attribute_runner_call() -> None:
    hits = _scan_source(
        "def bad():\n"
        "    return nl_catalog_search.run_tool_calling_search([], db=db)\n"
    )
    assert len(hits) == 1
    assert hits[0].name == "run_tool_calling_search"


def test_detector_ignores_search_catalog() -> None:
    assert not _scan_source(
        "from lightroom_tagger.core.catalog_search import search_catalog\n"
        "def good(db):\n"
        "    return search_catalog(db, 'cats', limit=10, offset=0)\n"
    )
