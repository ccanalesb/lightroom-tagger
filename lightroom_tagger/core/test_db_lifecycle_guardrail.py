"""Guardrail (ADR-0011): no hand-rolled init_database/connect_catalog lifecycle."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]

# CM internals, db_init, and handler CM factory.
_ALLOWLISTED_FILES: frozenset[str] = frozenset(
    {
        "lightroom_tagger/core/managed_connections.py",
        "lightroom_tagger/core/database/db_init.py",
        "apps/visualizer/backend/jobs/handlers/db_lifecycle.py",
    }
)

# Per-worker-thread callbacks that open/close their own sqlite connection.
_ALLOWLISTED_FUNCTIONS: frozenset[tuple[str, str]] = frozenset(
    {
        (
            "apps/visualizer/backend/jobs/handlers/matching.py",
            "process_single_image",
        ),
    }
)

_OPEN_FUNCS: frozenset[str] = frozenset({"init_database", "connect_catalog"})

_CLI_TARGET_PATHS: tuple[str, ...] = (
    "lightroom_tagger/core/cli.py",
    "lightroom_tagger/core/cli_library_db.py",
    "lightroom_tagger/core/cli_cmds_extra.py",
)


@dataclass(frozen=True)
class _HandRolledHit:
    rel_path: str
    line: int
    function: str | None
    opener: str
    var_name: str


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _is_open_call(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Call):
        return None
    name = _call_name(node)
    if name in _OPEN_FUNCS:
        return name
    return None


def _assign_target_names(target: ast.expr) -> list[str]:
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, ast.Tuple):
        return [n.id for elt in target.elts if isinstance(elt, ast.Name) for n in [elt]]
    return []


class _HandRolledLifecycleVisitor(ast.NodeVisitor):
    def __init__(self, rel_path: str) -> None:
        self.rel_path = rel_path
        self._function_stack: list[str | None] = [None]
        self._opened: dict[str, tuple[int, str]] = {}
        self.hits: list[_HandRolledHit] = []

    def _current_fn(self) -> str | None:
        return self._function_stack[-1]

    def _allowlisted_fn(self) -> bool:
        fn = self._current_fn()
        return (self.rel_path, fn or "") in _ALLOWLISTED_FUNCTIONS

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._function_stack.append(node.name)
        saved = self._opened
        self._opened = {}
        self.generic_visit(node)
        self._opened = saved
        self._function_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._function_stack.append(node.name)
        saved = self._opened
        self._opened = {}
        self.generic_visit(node)
        self._opened = saved
        self._function_stack.pop()

    def visit_Lambda(self, node: ast.Lambda) -> None:
        # ``lambda p: init_database(p)`` for make_managed_library_db is not a
        # hand-rolled lifecycle (close lives in db_lifecycle.py).
        saved = self._opened
        self._opened = {}
        self.generic_visit(node)
        self._opened = saved

    def visit_Assign(self, node: ast.Assign) -> None:
        opener = _is_open_call(node.value)
        if opener and not self._allowlisted_fn():
            for target in node.targets:
                for name in _assign_target_names(target):
                    self._opened[name] = (node.lineno, opener)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None:
            opener = _is_open_call(node.value)
            if opener and not self._allowlisted_fn() and isinstance(node.target, ast.Name):
                self._opened[node.target.id] = (node.lineno, opener)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "close"
            and isinstance(node.func.value, ast.Name)
            and not self._allowlisted_fn()
        ):
            var = node.func.value.id
            if var in self._opened:
                line, opener = self._opened[var]
                self.hits.append(
                    _HandRolledHit(
                        rel_path=self.rel_path,
                        line=line,
                        function=self._current_fn(),
                        opener=opener,
                        var_name=var,
                    )
                )
        self.generic_visit(node)


def _iter_handler_target_paths() -> list[str]:
    handlers_dir = _REPO_ROOT / "apps/visualizer/backend/jobs/handlers"
    rel_paths: list[str] = []
    for path in sorted(handlers_dir.glob("*.py")):
        rel = path.relative_to(_REPO_ROOT).as_posix()
        if rel in _ALLOWLISTED_FILES:
            continue
        if path.name in {"__init__.py", "db_lifecycle.py"}:
            continue
        rel_paths.append(rel)
    return rel_paths


def _target_rel_paths() -> list[str]:
    return list(_CLI_TARGET_PATHS) + _iter_handler_target_paths()


def _scan_file(rel_path: str) -> list[_HandRolledHit]:
    if rel_path in _ALLOWLISTED_FILES:
        return []
    path = _REPO_ROOT / rel_path
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    visitor = _HandRolledLifecycleVisitor(rel_path)
    visitor.visit(tree)
    return visitor.hits


@pytest.mark.parametrize("rel_path", _target_rel_paths())
def test_no_hand_rolled_db_lifecycle_outside_seam(rel_path: str) -> None:
    hits = _scan_file(rel_path)
    if not hits:
        return
    lines = [
        f"{h.rel_path}:{h.line} in {h.function or '<module>'}: "
        f"{h.opener}() assigned to {h.var_name!r} then manual .close()"
        for h in hits
    ]
    pytest.fail(
        "Hand-rolled library-DB/catalog lifecycle found outside ADR-0011 seam "
        "(use managed_library_db / managed_catalog / make_managed_library_db):\n"
        + "\n".join(lines)
    )


def test_guardrail_allowlists_cm_internals() -> None:
    for rel in _ALLOWLISTED_FILES:
        assert not _scan_file(rel)


def test_guardrail_allowlists_worker_thread_callback() -> None:
    rel = "apps/visualizer/backend/jobs/handlers/matching.py"
    assert (rel, "process_single_image") in _ALLOWLISTED_FUNCTIONS
    assert not _scan_file(rel)


def test_guardrail_scans_cli_and_handlers() -> None:
    paths = _target_rel_paths()
    assert "lightroom_tagger/core/cli.py" in paths
    assert "lightroom_tagger/core/cli_library_db.py" in paths
    assert "apps/visualizer/backend/jobs/handlers/analyze.py" in paths
    assert "apps/visualizer/backend/jobs/handlers/db_lifecycle.py" not in paths


def _scan_source(source: str, rel_path: str = "fake/module.py") -> list[_HandRolledHit]:
    visitor = _HandRolledLifecycleVisitor(rel_path)
    visitor.visit(ast.parse(source))
    return visitor.hits


def test_detector_flags_hand_rolled_init_database_close() -> None:
    hits = _scan_source(
        "def run(path):\n"
        "    db = init_database(path)\n"
        "    try:\n"
        "        return db.execute('SELECT 1')\n"
        "    finally:\n"
        "        db.close()\n"
    )
    assert len(hits) == 1
    assert hits[0].function == "run"
    assert hits[0].opener == "init_database"


def test_detector_flags_hand_rolled_connect_catalog_close() -> None:
    hits = _scan_source(
        "def scan(cat):\n"
        "    conn = connect_catalog(cat)\n"
        "    conn.close()\n"
    )
    assert len(hits) == 1
    assert hits[0].opener == "connect_catalog"


def test_detector_ignores_managed_library_db_with_block() -> None:
    assert not _scan_source(
        "def run(path):\n"
        "    with managed_library_db(path) as db:\n"
        "        return db.execute('SELECT 1')\n"
    )


def test_detector_ignores_make_managed_library_db_lambda() -> None:
    assert not _scan_source(
        "managed_library_db = make_managed_library_db(lambda p: init_database(p))\n"
        "def run(path):\n"
        "    with managed_library_db(path) as db:\n"
        "        return db\n"
    )
