"""Unit tests and guardrails for matcher score_formula extraction."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

import pytest

from lightroom_tagger.core.matcher.score_formula import (
    compute_total_score,
    normalize_phash_score,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MATCHER_DIR = _REPO_ROOT / "lightroom_tagger" / "core" / "matcher"
_FORMULA_FILE = "lightroom_tagger/core/matcher/score_formula.py"

_WEIGHTED_SUM_RE = re.compile(
    r"\(?\s*phash_weight\s*\*.*?\+\s*\(?\s*desc_weight\s*\*.*?\+\s*\(?\s*vision_weight\s*\*",
    re.DOTALL,
)
_PHASH_NORMALIZE_RE = re.compile(
    r"1\s*-\s*\([^)]*/\s*16\s*\)",
)


# --- unit tests: normalize_phash_score ---


def test_normalize_phash_score_zero_distance() -> None:
    assert normalize_phash_score(0) == 1.0


def test_normalize_phash_score_max_distance() -> None:
    assert normalize_phash_score(16) == 0.0


def test_normalize_phash_score_beyond_max_clamped() -> None:
    assert normalize_phash_score(20) == 0.0


def test_normalize_phash_score_intermediate() -> None:
    assert normalize_phash_score(8) == 0.5


# --- unit tests: compute_total_score ---


def test_compute_total_score_default_weights() -> None:
    total = compute_total_score(1.0, 0.8, 0.6, 0.4, 0.3, 0.3)
    assert total == pytest.approx(0.4 + 0.24 + 0.18)


def test_compute_total_score_vision_weight_zero() -> None:
    total = compute_total_score(1.0, 0.5, 0.9, 0.4, 0.3, 0.0)
    assert total == pytest.approx(0.4 + 0.15)


# --- guardrail ---


@dataclass(frozen=True)
class _FormulaLeakHit:
    rel_path: str
    line: int
    pattern: str
    snippet: str


def _iter_matcher_py_files() -> list[Path]:
    return sorted(_MATCHER_DIR.glob("*.py"))


def _rel_path(path: Path) -> str:
    return path.relative_to(_REPO_ROOT).as_posix()


def _scan_source_for_formula_leaks(rel: str, source: str) -> list[_FormulaLeakHit]:
    hits: list[_FormulaLeakHit] = []
    for pattern_name, pattern in (
        ("weighted_sum", _WEIGHTED_SUM_RE),
        ("phash_normalize", _PHASH_NORMALIZE_RE),
    ):
        for match in pattern.finditer(source):
            line = source.count("\n", 0, match.start()) + 1
            snippet = match.group(0).replace("\n", " ").strip()
            hits.append(_FormulaLeakHit(rel, line, pattern_name, snippet))
    return hits


def _scan_file_for_formula_leaks(path: Path) -> list[_FormulaLeakHit]:
    rel = _rel_path(path)
    if rel == _FORMULA_FILE:
        return []
    return _scan_source_for_formula_leaks(rel, path.read_text(encoding="utf-8"))


def _scan_all_matcher_files() -> list[_FormulaLeakHit]:
    hits: list[_FormulaLeakHit] = []
    for path in _iter_matcher_py_files():
        hits.extend(_scan_file_for_formula_leaks(path))
    return hits


def _fail_on_leaks(hits: list[_FormulaLeakHit]) -> None:
    if not hits:
        return
    lines = [
        f"{h.rel_path}:{h.line} [{h.pattern}]: {h.snippet}"
        for h in hits
    ]
    pytest.fail(
        "Inline matcher score formula found outside score_formula.py:\n"
        + "\n".join(lines)
    )


def test_guardrail_no_inline_formula_in_matcher_package() -> None:
    _fail_on_leaks(_scan_all_matcher_files())


def test_guardrail_scans_score_with_vision() -> None:
    assert "lightroom_tagger/core/matcher/score_with_vision.py" in {
        _rel_path(p) for p in _iter_matcher_py_files()
    }
    assert not _scan_file_for_formula_leaks(
        _MATCHER_DIR / "score_with_vision.py"
    )


def test_detector_flags_weighted_sum_leak() -> None:
    hits = _scan_file_for_formula_leaks_from_source(
        "total = (phash_weight * p) + (desc_weight * d) + (vision_weight * v)\n"
    )
    assert len(hits) == 1
    assert hits[0].pattern == "weighted_sum"


def test_detector_flags_phash_normalize_leak() -> None:
    hits = _scan_file_for_formula_leaks_from_source(
        "score = max(0, 1 - (dist / 16))\n"
    )
    assert len(hits) == 1
    assert hits[0].pattern == "phash_normalize"


def test_detector_allows_formula_module() -> None:
    formula_path = _MATCHER_DIR / "score_formula.py"
    assert not _scan_file_for_formula_leaks(formula_path)


def _scan_file_for_formula_leaks_from_source(source: str) -> list[_FormulaLeakHit]:
    """Scan arbitrary source as if it were a matcher module (not score_formula.py)."""
    return _scan_source_for_formula_leaks(
        "lightroom_tagger/core/matcher/_synthetic_leak_probe.py", source
    )


def test_formula_module_is_pure() -> None:
    """score_formula.py must not import I/O, DB, or vision modules."""
    tree = ast.parse((_MATCHER_DIR / "score_formula.py").read_text(encoding="utf-8"))
    imports = {
        node.names[0].name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
    }
    import_froms = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module and node.module != "__future__"
    }
    assert not imports
    assert not import_froms
