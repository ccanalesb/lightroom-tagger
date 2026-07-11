"""Guardrail (ADR-0010): single JOB_TYPES registration surface."""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND_ROOT))

from jobs.registry import JOB_TYPES  # noqa: E402

_REPO_ROOT = _BACKEND_ROOT.parents[2]
_VISUALIZER_BACKEND = _REPO_ROOT / "apps/visualizer/backend"

# Canonical registration surface and its lazy derived projections.
_ALLOWLISTED_FILES: frozenset[str] = frozenset(
    {
        "apps/visualizer/backend/jobs/registry.py",
        "apps/visualizer/backend/jobs/handlers/__init__.py",
        "apps/visualizer/backend/library_db.py",
    }
)

# Snapshot expectations for registry behaviour — not a second registration surface.
_ALLOWLISTED_TEST_FILES: frozenset[str] = frozenset(
    {
        "apps/visualizer/backend/tests/test_job_registry.py",
    }
)

_JOB_TYPE_NAMES: frozenset[str] = frozenset(jt.name for jt in JOB_TYPES)

_FORBIDDEN_DERIVED_NAMES: frozenset[str] = frozenset(
    {
        "JOB_HANDLERS",
        "_JOB_HANDLERS",
        "JOB_TYPES_REQUIRING_CATALOG",
        "_JOB_TYPES_REQUIRING_CATALOG",
    }
)


@dataclass(frozen=True)
class _RegistrationHit:
    rel_path: str
    line: int
    kind: str
    detail: str


def _is_handler_name(node: ast.AST) -> bool:
    if isinstance(node, ast.Name) and node.id.startswith("handle_"):
        return True
    if isinstance(node, ast.Attribute) and node.attr.startswith("handle_"):
        return True
    return False


def _string_constants(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.List | ast.Set | ast.Tuple):
        out: list[str] = []
        for elt in node.elts:
            out.extend(_string_constants(elt))
        return out
    if isinstance(node, ast.Dict):
        out: list[str] = []
        for key in node.keys:
            if key is not None:
                out.extend(_string_constants(key))
        return out
    return []


def _job_type_keys_in_dict(node: ast.Dict) -> list[str]:
    keys: list[str] = []
    for key in node.keys:
        if key is None:
            continue
        for literal in _string_constants(key):
            if literal in _JOB_TYPE_NAMES:
                keys.append(literal)
    return keys


def _job_type_strings_in_container(node: ast.AST) -> list[str]:
    return [s for s in _string_constants(node) if s in _JOB_TYPE_NAMES]


class _RegistrationVisitor(ast.NodeVisitor):
    def __init__(self, rel_path: str) -> None:
        self.rel_path = rel_path
        self.hits: list[_RegistrationHit] = []

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in _FORBIDDEN_DERIVED_NAMES:
                if isinstance(node.value, ast.Dict):
                    self.hits.append(
                        _RegistrationHit(
                            rel_path=self.rel_path,
                            line=node.lineno,
                            kind="literal_derived_map",
                            detail=f"{target.id} must be derived from JOB_TYPES, not a literal dict",
                        )
                    )
                elif isinstance(node.value, ast.Call) and isinstance(
                    node.value.func, ast.Name
                ) and node.value.func.id in {"frozenset", "set"}:
                    strings = _job_type_strings_in_container(
                        node.value.args[0] if node.value.args else node.value
                    )
                    if len(strings) >= 2:
                        self.hits.append(
                            _RegistrationHit(
                                rel_path=self.rel_path,
                                line=node.lineno,
                                kind="literal_catalog_set",
                                detail=f"{target.id} must be derived from JOB_TYPES, not a literal set",
                            )
                        )
        self.generic_visit(node)

    def visit_Dict(self, node: ast.Dict) -> None:
        job_keys = _job_type_keys_in_dict(node)
        if len(job_keys) >= 2:
            handler_values = [
                v for v in node.values if v is not None and _is_handler_name(v)
            ]
            if len(handler_values) >= 2:
                self.hits.append(
                    _RegistrationHit(
                        rel_path=self.rel_path,
                        line=node.lineno,
                        kind="handler_dispatch_map",
                        detail=f"parallel job_type→handler map keys={sorted(set(job_keys))}",
                    )
                )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id in {"frozenset", "set"}:
            container = node.args[0] if node.args else None
            if container is not None:
                strings = _job_type_strings_in_container(container)
                if len(strings) >= 2:
                    self.hits.append(
                        _RegistrationHit(
                            rel_path=self.rel_path,
                            line=node.lineno,
                            kind="catalog_requirement_set",
                            detail=f"parallel catalog-requirement set types={sorted(set(strings))}",
                        )
                    )
        self.generic_visit(node)


def _iter_scanned_backend_files() -> list[str]:
    rel_paths: list[str] = []
    for path in sorted(_VISUALIZER_BACKEND.rglob("*.py")):
        rel = path.relative_to(_REPO_ROOT).as_posix()
        if rel in _ALLOWLISTED_FILES:
            continue
        if "/tests/" in rel or rel.endswith("/tests/conftest.py"):
            continue
        if path.name.startswith("test_"):
            continue
        rel_paths.append(rel)
    return rel_paths


def _scan_file(rel_path: str) -> list[_RegistrationHit]:
    path = _REPO_ROOT / rel_path
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    visitor = _RegistrationVisitor(rel_path)
    visitor.visit(tree)
    return visitor.hits


@pytest.mark.parametrize("rel_path", _iter_scanned_backend_files())
def test_no_parallel_job_type_registration_surface(rel_path: str) -> None:
    hits = _scan_file(rel_path)
    if not hits:
        return
    lines = [
        f"{h.rel_path}:{h.line} [{h.kind}] {h.detail}"
        for h in hits
    ]
    pytest.fail(
        "Parallel job-type registration surface found outside JOB_TYPES "
        "(ADR-0010). Add one JobType entry in jobs/registry.py instead:\n"
        + "\n".join(lines)
    )


def test_guardrail_allowlists_registry_and_derived_projections() -> None:
    for rel in _ALLOWLISTED_FILES:
        assert rel.startswith("apps/visualizer/backend/")
    assert not _scan_file("apps/visualizer/backend/jobs/registry.py")


def test_guardrail_allowlists_registry_snapshot_test() -> None:
    rel = "apps/visualizer/backend/tests/test_job_registry.py"
    assert rel in _ALLOWLISTED_TEST_FILES
    path = _REPO_ROOT / rel
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    visitor = _RegistrationVisitor(rel)
    visitor.visit(tree)
    assert visitor.hits, "snapshot test must contain the expected handler map"


def test_guardrail_scans_app_py() -> None:
    assert "apps/visualizer/backend/app.py" in _iter_scanned_backend_files()
    assert not _scan_file("apps/visualizer/backend/app.py")


def _scan_source(source: str, rel_path: str = "fake/module.py") -> list[_RegistrationHit]:
    visitor = _RegistrationVisitor(rel_path)
    visitor.visit(ast.parse(source))
    return visitor.hits


def test_detector_flags_parallel_handler_map() -> None:
    hits = _scan_source(
        "HANDLERS = {\n"
        "    'vision_match': handle_vision_match,\n"
        "    'batch_describe': handle_batch_describe,\n"
        "}\n"
    )
    assert any(h.kind == "handler_dispatch_map" for h in hits)


def test_detector_flags_parallel_catalog_set() -> None:
    hits = _scan_source(
        "NEEDS_CATALOG = frozenset({'vision_match', 'batch_describe'})\n"
    )
    assert any(h.kind == "catalog_requirement_set" for h in hits)
