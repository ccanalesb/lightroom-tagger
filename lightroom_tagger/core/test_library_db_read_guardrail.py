"""Guardrail (ADR-0008): no raw library-DB SQL in read-consumer call sites."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]

_TARGET_REL_PATHS = (
    "lightroom_tagger/core/search_tools.py",
    "apps/visualizer/backend/api/system.py",
    "apps/visualizer/backend/api/images/matches.py",
    "apps/visualizer/backend/api/images/instagram.py",
    "apps/visualizer/backend/api/images/catalog.py",
    "apps/visualizer/backend/api/images/search.py",
    "apps/visualizer/backend/api/images/stacks.py",
)

# Application-DB reads allowed by function name (jobs table only).
_ALLOWLISTED_FUNCTIONS: frozenset[tuple[str, str]] = frozenset(
    {
        ("apps/visualizer/backend/api/system.py", "_last_job_for_bucket"),
    }
)

_LIBRARY_TABLE_RE = re.compile(
    r"\b(?:FROM|JOIN|INTO|UPDATE|DELETE\s+FROM)\s+"
    r"(?:"
    r"images|image_descriptions(?:_fts)?|image_scores|perspectives|matches|"
    r"rejected_matches|instagram_images|instagram_dump_media|image_stacks|"
    r"image_stack_members|vision_cache|vision_comparisons|"
    r"catalog_similarity_groups|catalog_similarity_candidates|"
    r"image_clip_embeddings|image_text_embeddings|"
    r"match_pool_snapshots|match_pool_snapshot_members"
    r")\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class _RawExecuteHit:
    rel_path: str
    line: int
    function: str | None
    sql_preview: str


def _collect_string_literals(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
        return ["".join(parts)] if parts else []
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _collect_string_literals(node.left)
        right = _collect_string_literals(node.right)
        if left or right:
            return ["".join(left + right)]
    return []


def _is_db_execute_call(node: ast.Call) -> bool:
    func = node.func
    return isinstance(func, ast.Attribute) and func.attr == "execute"


class _DbExecuteVisitor(ast.NodeVisitor):
    def __init__(self, rel_path: str) -> None:
        self.rel_path = rel_path
        self._function_stack: list[str | None] = [None]
        self.hits: list[_RawExecuteHit] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._function_stack.append(node.name)
        self.generic_visit(node)
        self._function_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._function_stack.append(node.name)
        self.generic_visit(node)
        self._function_stack.pop()

    def visit_Call(self, node: ast.Call) -> None:
        if _is_db_execute_call(node):
            fn = self._function_stack[-1]
            if (self.rel_path, fn or "") not in _ALLOWLISTED_FUNCTIONS:
                sql_parts = (
                    _collect_string_literals(node.args[0]) if node.args else []
                )
                preview = sql_parts[0][:120].replace("\n", " ") if sql_parts else "<dynamic>"
                self.hits.append(
                    _RawExecuteHit(
                        rel_path=self.rel_path,
                        line=node.lineno,
                        function=fn,
                        sql_preview=preview,
                    )
                )
        self.generic_visit(node)


def _scan_file(rel_path: str) -> list[_RawExecuteHit]:
    path = _REPO_ROOT / rel_path
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    visitor = _DbExecuteVisitor(rel_path)
    visitor.visit(tree)
    return visitor.hits


def _library_table_hits(hits: list[_RawExecuteHit]) -> list[_RawExecuteHit]:
    out: list[_RawExecuteHit] = []
    for hit in hits:
        if hit.sql_preview == "<dynamic>":
            out.append(hit)
            continue
        if _LIBRARY_TABLE_RE.search(hit.sql_preview):
            out.append(hit)
    return out


@pytest.mark.parametrize("rel_path", _TARGET_REL_PATHS)
def test_no_raw_library_db_execute_in_read_consumers(rel_path: str) -> None:
    hits = _library_table_hits(_scan_file(rel_path))
    if not hits:
        return
    lines = [
        f"{h.rel_path}:{h.line} in {h.function or '<module>'}: {h.sql_preview!r}"
        for h in hits
    ]
    pytest.fail(
        "Raw library-DB db.execute found in ADR-0008 read consumer(s):\n"
        + "\n".join(lines)
    )


def test_guardrail_allowlists_jobs_reads_in_system_py() -> None:
    assert ("apps/visualizer/backend/api/system.py", "_last_job_for_bucket") in _ALLOWLISTED_FUNCTIONS
    assert not _library_table_hits(_scan_file("apps/visualizer/backend/api/system.py"))


def test_guardrail_scans_all_seven_target_files() -> None:
    assert len(_TARGET_REL_PATHS) == 7
