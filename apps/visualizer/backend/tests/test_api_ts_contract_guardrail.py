"""Guardrail (ADR-0013): no hand-written API response types remain in frontend api.ts."""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[4]
_API_TS = _REPO_ROOT / "apps/visualizer/frontend/src/services/api.ts"

_ALLOWED_EXPORT_TYPE_OBJECT_LITERALS = frozenset(
    {
        "CatalogListQueryParams",
        "DescriptionListResult",
    }
)


def _export_interface_names(source: str) -> list[str]:
    return re.findall(r"^export interface (\w+)", source, flags=re.MULTILINE)


def _export_type_object_literal_names(source: str) -> list[str]:
    names: list[str] = []
    for match in re.finditer(r"^export type (\w+)\s*=\s*\{", source, flags=re.MULTILINE):
        names.append(match.group(1))
    return names


def _forbidden_hand_written_response_types(source: str) -> list[str]:
    violations: list[str] = []
    violations.extend(f"interface:{name}" for name in _export_interface_names(source))
    for name in _export_type_object_literal_names(source):
        if name not in _ALLOWED_EXPORT_TYPE_OBJECT_LITERALS:
            violations.append(f"type:{name}")
    return violations


def test_api_ts_has_no_hand_written_response_types() -> None:
    source = _API_TS.read_text(encoding="utf-8")
    violations = _forbidden_hand_written_response_types(source)
    assert violations == [], (
        "Hand-written response types remain in api.ts; migrate to api.gen.ts "
        f"(allowed object-literal exports: {sorted(_ALLOWED_EXPORT_TYPE_OBJECT_LITERALS)}). "
        f"Violations: {violations}"
    )


def test_guardrail_detects_re_added_hand_written_interface() -> None:
    sample = "export interface RogueResponse { items: string[] }\n"
    assert _forbidden_hand_written_response_types(sample) == ["interface:RogueResponse"]


def test_guardrail_detects_re_added_hand_written_response_type_literal() -> None:
    sample = "export type RogueResponse = { ok: boolean }\n"
    assert _forbidden_hand_written_response_types(sample) == ["type:RogueResponse"]


def test_guardrail_allows_catalog_list_query_params() -> None:
    sample = "export type CatalogListQueryParams = { limit?: number }\n"
    assert _forbidden_hand_written_response_types(sample) == []


def test_guardrail_allows_description_list_result() -> None:
    sample = "export type DescriptionListResult = Awaited<ReturnType<typeof DescriptionsAPI.list>>\n"
    assert _forbidden_hand_written_response_types(sample) == []
