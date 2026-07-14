"""Guardrail (ADR-0014): no inline resolve→dispatch→parse outside the vision-op engine."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LIGHTROOM_ROOT = _REPO_ROOT / "lightroom_tagger"

# Engine module — the only place that may orchestrate resolve → dispatch → parse.
_ALLOWLISTED_FILES: frozenset[str] = frozenset(
    {
        "lightroom_tagger/core/vision_op.py",
        "lightroom_tagger/core/fallback.py",
        # different scope — text NL filter + multi-turn tool loop; see #139 Non-goals.
        "lightroom_tagger/core/nl_catalog_search.py",
    }
)


@dataclass(frozen=True)
class _InlineVisionOpHit:
    rel_path: str
    line: int
    function: str | None


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


class _VisionOpOrchestrationVisitor(ast.NodeVisitor):
    """Detect resolve_model + FallbackDispatcher + call_with_fallback in one scope."""

    def __init__(self, rel_path: str) -> None:
        self.rel_path = rel_path
        self._function_stack: list[str | None] = [None]
        self.hits: list[_InlineVisionOpHit] = []
        self._has_resolve_model = False
        self._has_fallback_dispatcher = False
        self._has_call_with_fallback = False
        self._scope_line = 1

    def _current_fn(self) -> str | None:
        return self._function_stack[-1]

    def _reset_scope_flags(self, line: int) -> None:
        self._has_resolve_model = False
        self._has_fallback_dispatcher = False
        self._has_call_with_fallback = False
        self._scope_line = line

    def _record_hit_if_orchestration(self) -> None:
        if (
            self._has_resolve_model
            and self._has_fallback_dispatcher
            and self._has_call_with_fallback
        ):
            self.hits.append(
                _InlineVisionOpHit(
                    rel_path=self.rel_path,
                    line=self._scope_line,
                    function=self._current_fn(),
                )
            )

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._function_stack.append(node.name)
        saved = (
            self._has_resolve_model,
            self._has_fallback_dispatcher,
            self._has_call_with_fallback,
        )
        self._reset_scope_flags(node.lineno)
        self.generic_visit(node)
        self._record_hit_if_orchestration()
        (
            self._has_resolve_model,
            self._has_fallback_dispatcher,
            self._has_call_with_fallback,
        ) = saved
        self._function_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._function_stack.append(node.name)
        saved = (
            self._has_resolve_model,
            self._has_fallback_dispatcher,
            self._has_call_with_fallback,
        )
        self._reset_scope_flags(node.lineno)
        self.generic_visit(node)
        self._record_hit_if_orchestration()
        (
            self._has_resolve_model,
            self._has_fallback_dispatcher,
            self._has_call_with_fallback,
        ) = saved
        self._function_stack.pop()

    def visit_Call(self, node: ast.Call) -> None:
        name = _call_name(node)
        if name == "resolve_model":
            self._has_resolve_model = True
        elif name == "FallbackDispatcher":
            self._has_fallback_dispatcher = True
        elif name == "call_with_fallback":
            self._has_call_with_fallback = True
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


def _scan_file(rel_path: str) -> list[_InlineVisionOpHit]:
    if rel_path in _ALLOWLISTED_FILES:
        return []
    path = _REPO_ROOT / rel_path
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    visitor = _VisionOpOrchestrationVisitor(rel_path)
    visitor.visit(tree)
    return visitor.hits


@pytest.mark.parametrize("rel_path", _iter_scanned_source_files())
def test_no_inline_vision_op_orchestration_outside_engine(rel_path: str) -> None:
    hits = _scan_file(rel_path)
    if not hits:
        return
    lines = [
        f"{h.rel_path}:{h.line} in {h.function or '<module>'}: "
        "inline resolve_model → FallbackDispatcher → call_with_fallback"
        for h in hits
    ]
    pytest.fail(
        "Inline vision-op orchestration found outside ADR-0014 engine "
        "(use run_vision_op / run_vision_op_persist with a VisionOpSpec):\n"
        + "\n".join(lines)
    )


def test_guardrail_allowlists_vision_op_engine() -> None:
    assert "lightroom_tagger/core/vision_op.py" in _ALLOWLISTED_FILES
    assert not _scan_file("lightroom_tagger/core/vision_op.py")


def test_guardrail_allowlists_fallback_dispatcher() -> None:
    assert "lightroom_tagger/core/fallback.py" in _ALLOWLISTED_FILES
    assert not _scan_file("lightroom_tagger/core/fallback.py")


def test_guardrail_allowlists_nl_catalog_search() -> None:
    assert "lightroom_tagger/core/nl_catalog_search.py" in _ALLOWLISTED_FILES
    assert not _scan_file("lightroom_tagger/core/nl_catalog_search.py")


def test_guardrail_scans_nl_catalog_search_when_unlisted() -> None:
    """Prove nl_catalog_search would fail without the explicit allow-list."""
    rel = "lightroom_tagger/core/nl_catalog_search.py"
    path = _REPO_ROOT / rel
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    visitor = _VisionOpOrchestrationVisitor(rel)
    visitor.visit(tree)
    assert visitor.hits, "nl_catalog_search should contain inline orchestration"


def _scan_source(source: str, rel_path: str = "fake/module.py") -> list[_InlineVisionOpHit]:
    visitor = _VisionOpOrchestrationVisitor(rel_path)
    visitor.visit(ast.parse(source))
    return visitor.hits


def test_detector_flags_inline_orchestration() -> None:
    hits = _scan_source(
        "def orchestrate(provider_id, model):\n"
        "    r = resolve_model(kind='description', provider_id=provider_id, model=model)\n"
        "    dispatcher = FallbackDispatcher(r.registry)\n"
        "    raw, p, m = dispatcher.call_with_fallback(\n"
        "        operation='score', fn_factory=lambda: None,\n"
        "        provider_id=r.provider_id, model=r.model,\n"
        "    )\n"
        "    return parse_score_vision_response(raw)\n"
    )
    assert len(hits) == 1
    assert hits[0].function == "orchestrate"


def test_detector_flags_description_shape_not_only_generate_description() -> None:
    """Orchestration is detected regardless of fn_factory / operation name."""
    hits = _scan_source(
        "def bad():\n"
        "    resolved = resolve_model(kind='description')\n"
        "    disp = FallbackDispatcher(resolved.registry)\n"
        "    disp.call_with_fallback(operation='describe', fn_factory=lambda: None,\n"
        "        provider_id=resolved.provider_id, model=resolved.model)\n"
    )
    assert len(hits) == 1


def test_detector_ignores_run_vision_op_callers() -> None:
    assert not _scan_source(
        "def good():\n"
        "    spec = build_score_op_spec('path', user_prompt='x')\n"
        "    return run_vision_op(spec)\n"
    )


def test_detector_ignores_resolve_model_only() -> None:
    assert not _scan_source(
        "def pick():\n"
        "  return resolve_model(kind='vision_comparison')\n"
    )
