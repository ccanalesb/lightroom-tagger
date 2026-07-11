"""Guardrail (ADR-0010): no status-transition rules in api/jobs.py routes."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[4]
_TARGET_REL = "apps/visualizer/backend/api/jobs.py"

_JOB_STATUS_VALUES: frozenset[str] = frozenset(
    {"pending", "running", "completed", "failed", "cancelled"}
)

# count_jobs(status=...) filters in the processor-health endpoint are not transitions.
_ALLOWLISTED_CALLS: frozenset[tuple[str, str]] = frozenset(
    {
        ("get_processor_health", "count_jobs"),
    }
)


@dataclass(frozen=True)
class _TransitionRuleHit:
    line: int
    kind: str
    detail: str


def _is_status_literal(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value in _JOB_STATUS_VALUES
    )


def _status_literals_in_node(node: ast.AST) -> list[str]:
    if _is_status_literal(node):
        return [node.value]  # type: ignore[union-attr]
    if isinstance(node, ast.List | ast.Set | ast.Tuple):
        out: list[str] = []
        for elt in node.elts:
            out.extend(_status_literals_in_node(elt))
        return out
    return []


def _references_job_status(expr: ast.AST) -> bool:
    if isinstance(expr, ast.Name) and expr.id == "status":
        return True
    if isinstance(expr, ast.Subscript):
        if isinstance(expr.value, ast.Name) and expr.value.id == "job":
            key = expr.slice
            if isinstance(key, ast.Constant) and key.value == "status":
                return True
        if isinstance(expr.value, ast.Subscript):
            return _references_job_status(expr.value)
    if isinstance(expr, ast.Attribute) and expr.attr == "status":
        return True
    return False


def _call_name(func: ast.AST) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _update_job_status_target(node: ast.Call) -> str | None:
    if len(node.args) >= 3 and _is_status_literal(node.args[2]):
        return node.args[2].value  # type: ignore[union-attr]
    for kw in node.keywords:
        if kw.arg == "status" and _is_status_literal(kw.value):
            return kw.value.value  # type: ignore[union-attr]
    return None


class _TransitionRuleVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self._function_stack: list[str | None] = [None]
        self.hits: list[_TransitionRuleHit] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._function_stack.append(node.name)
        if node.body and isinstance(node.body[0], ast.Expr):
            # Skip module/function docstrings — they mention status names descriptively.
            self._skip_docstring(node.body[0])
            for stmt in node.body[1:]:
                self.visit(stmt)
        else:
            self.generic_visit(node)
        self._function_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.visit_FunctionDef(node)  # type: ignore[arg-type]

    def _skip_docstring(self, node: ast.Expr) -> None:
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return
        self.visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        fn_name = _call_name(node.func)
        fn = self._function_stack[-1]

        if fn_name in {"can_cancel", "can_retry"}:
            self.hits.append(
                _TransitionRuleHit(
                    line=node.lineno,
                    kind="transition_helper_in_route",
                    detail=f"{fn_name}() belongs in jobs/transitions.py",
                )
            )

        if fn_name == "update_job_status":
            status_arg = _update_job_status_target(node)
            if status_arg is not None:
                self.hits.append(
                    _TransitionRuleHit(
                        line=node.lineno,
                        kind="update_job_status_target",
                        detail=f"transition target {status_arg!r}",
                    )
                )

        if fn_name in {"frozenset", "set"}:
            literals = _status_literals_in_node(node.args[0] if node.args else node)
            if len(literals) >= 2:
                self.hits.append(
                    _TransitionRuleHit(
                        line=node.lineno,
                        kind="status_rule_set",
                        detail=f"status rule set {sorted(set(literals))}",
                    )
                )

        if fn_name == "count_jobs" and (fn, fn_name) in _ALLOWLISTED_CALLS:
            return

        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        left = node.left
        for op, comparator in zip(node.ops, node.comparators, strict=False):
            if isinstance(op, ast.In | ast.NotIn):
                if _references_job_status(left):
                    literals = _status_literals_in_node(comparator)
                    if literals:
                        self.hits.append(
                            _TransitionRuleHit(
                                line=node.lineno,
                                kind="status_membership_check",
                                detail=f"status legality check against {literals}",
                            )
                        )
            elif isinstance(op, ast.Eq | ast.NotEq):
                if _references_job_status(left) and _is_status_literal(comparator):
                    self.hits.append(
                        _TransitionRuleHit(
                            line=node.lineno,
                            kind="status_equality_check",
                            detail=f"status legality check == {comparator.value!r}",  # type: ignore[union-attr]
                        )
                    )
                if _references_job_status(comparator) and _is_status_literal(left):
                    self.hits.append(
                        _TransitionRuleHit(
                            line=node.lineno,
                            kind="status_equality_check",
                            detail=f"status legality check == {left.value!r}",  # type: ignore[union-attr]
                        )
                    )
        self.generic_visit(node)


def _scan_jobs_routes() -> list[_TransitionRuleHit]:
    path = _REPO_ROOT / _TARGET_REL
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    if (
        tree.body
        and isinstance(tree.body[0], ast.Expr)
        and isinstance(tree.body[0].value, ast.Constant)
        and isinstance(tree.body[0].value.value, str)
    ):
        visitor = _TransitionRuleVisitor()
        for stmt in tree.body[1:]:
            visitor.visit(stmt)
        return visitor.hits

    visitor = _TransitionRuleVisitor()
    visitor.visit(tree)
    return visitor.hits


def test_api_jobs_contains_no_status_transition_rules() -> None:
    hits = _scan_jobs_routes()
    if not hits:
        return
    lines = [f"{_TARGET_REL}:{h.line} [{h.kind}] {h.detail}" for h in hits]
    pytest.fail(
        "Status-transition rule literals found in api/jobs.py (ADR-0010). "
        "Move legality checks and update_job_status targets to jobs/transitions.py:\n"
        + "\n".join(lines)
    )


def test_guardrail_allowlists_processor_health_count_jobs_filters() -> None:
    assert ("get_processor_health", "count_jobs") in _ALLOWLISTED_CALLS
    assert not _scan_jobs_routes()


def test_detector_flags_inline_cancel_check() -> None:
    visitor = _TransitionRuleVisitor()
    visitor.visit(
        ast.parse(
            "def cancel_job():\n"
            "    if job['status'] in ('pending', 'running'):\n"
            "        pass\n"
        )
    )
    assert any(h.kind == "status_membership_check" for h in visitor.hits)


def test_detector_flags_update_job_status_in_route() -> None:
    visitor = _TransitionRuleVisitor()
    visitor.visit(
        ast.parse(
            "def cancel_job():\n"
            "    update_job_status(db, job_id, 'cancelled')\n"
        )
    )
    assert any(h.kind == "update_job_status_target" for h in visitor.hits)


def test_detector_ignores_outcome_edge_checks() -> None:
    visitor = _TransitionRuleVisitor()
    visitor.visit(
        ast.parse(
            "def cancel_job():\n"
            "    if outcome.edge == 'cancelled':\n"
            "        pass\n"
        )
    )
    assert not visitor.hits
