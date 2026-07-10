"""Guardrail (ADR-0009): no raw provider SDK calls outside the dispatcher seam."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LIGHTROOM_ROOT = _REPO_ROOT / "lightroom_tagger"

# Entire files that may issue raw SDK completions (HTTP wrapper layer + dispatcher).
_ALLOWLISTED_FILES: frozenset[str] = frozenset(
    {
        "lightroom_tagger/core/vision_client.py",
        "lightroom_tagger/core/vision_client_batch.py",
        "lightroom_tagger/core/fallback.py",
    }
)

# Function-level exceptions inside otherwise-scanned files.
_ALLOWLISTED_FUNCTIONS: frozenset[tuple[str, str]] = frozenset(
    {
        ("lightroom_tagger/core/provider_registry.py", "_probe_tool_calling"),
    }
)

_RAW_PROVIDER_METHODS: frozenset[tuple[str, str]] = frozenset(
    {
        ("completions", "create"),
        ("completions", "parse"),
        ("embeddings", "create"),
        ("images", "generate"),
    }
)


@dataclass(frozen=True)
class _RawProviderCallHit:
    rel_path: str
    line: int
    function: str | None
    chain: str


def _attr_chain(node: ast.AST) -> list[str]:
    chain: list[str] = []
    cur: ast.AST = node
    while isinstance(cur, ast.Attribute):
        chain.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        chain.append(cur.id)
    return list(reversed(chain))


def _is_raw_provider_call(node: ast.Call) -> bool:
    if not isinstance(node.func, ast.Attribute):
        return False
    chain = _attr_chain(node.func)
    if len(chain) < 2:
        return False
    method = (chain[-2], chain[-1])
    if method not in _RAW_PROVIDER_METHODS:
        return False
    if method[0] == "completions" and len(chain) >= 3 and chain[-3] != "chat":
        return False
    return True


class _ProviderCallVisitor(ast.NodeVisitor):
    def __init__(self, rel_path: str) -> None:
        self.rel_path = rel_path
        self._function_stack: list[str | None] = [None]
        self.hits: list[_RawProviderCallHit] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._function_stack.append(node.name)
        self.generic_visit(node)
        self._function_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._function_stack.append(node.name)
        self.generic_visit(node)
        self._function_stack.pop()

    def visit_Call(self, node: ast.Call) -> None:
        if _is_raw_provider_call(node):
            fn = self._function_stack[-1]
            if (self.rel_path, fn or "") not in _ALLOWLISTED_FUNCTIONS:
                self.hits.append(
                    _RawProviderCallHit(
                        rel_path=self.rel_path,
                        line=node.lineno,
                        function=fn,
                        chain=".".join(_attr_chain(node.func)),
                    )
                )
        self.generic_visit(node)


def _iter_scanned_source_files() -> list[str]:
    rel_paths: list[str] = []
    for path in sorted(_LIGHTROOM_ROOT.rglob("*.py")):
        if path.name.startswith("test_"):
            continue
        rel = path.relative_to(_REPO_ROOT).as_posix()
        if rel in _ALLOWLISTED_FILES:
            continue
        rel_paths.append(rel)
    return rel_paths


def _scan_file(rel_path: str) -> list[_RawProviderCallHit]:
    path = _REPO_ROOT / rel_path
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    visitor = _ProviderCallVisitor(rel_path)
    visitor.visit(tree)
    return visitor.hits


@pytest.mark.parametrize("rel_path", _iter_scanned_source_files())
def test_no_raw_provider_calls_outside_dispatcher_seam(rel_path: str) -> None:
    hits = _scan_file(rel_path)
    if not hits:
        return
    lines = [
        f"{h.rel_path}:{h.line} in {h.function or '<module>'}: {h.chain}"
        for h in hits
    ]
    pytest.fail(
        "Raw provider SDK call found outside ADR-0009 seam "
        "(use vision_client helpers inside FallbackDispatcher fn_factory):\n"
        + "\n".join(lines)
    )


def test_guardrail_allowlists_probe_tool_calling() -> None:
    assert (
        "lightroom_tagger/core/provider_registry.py",
        "_probe_tool_calling",
    ) in _ALLOWLISTED_FUNCTIONS
    assert not _scan_file("lightroom_tagger/core/provider_registry.py")


def test_guardrail_allowlists_vision_client_wrappers() -> None:
    for rel in (
        "lightroom_tagger/core/vision_client.py",
        "lightroom_tagger/core/vision_client_batch.py",
    ):
        assert rel in _ALLOWLISTED_FILES


def test_guardrail_scans_nl_catalog_search() -> None:
    assert "lightroom_tagger/core/nl_catalog_search.py" in _iter_scanned_source_files()
    assert not _scan_file("lightroom_tagger/core/nl_catalog_search.py")
