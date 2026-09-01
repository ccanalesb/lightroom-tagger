"""Batch frame substance detection over the local vision cache (#295)."""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from lightroom_tagger.core import cancel_scope
from lightroom_tagger.core.database.frame_substance import (
    FLAGGED_VERDICTS,
    finish_frame_substance_run,
    insert_frame_substance_run,
    list_catalog_images_with_vision_cache,
    load_frame_substance_verdict_map,
    upsert_frame_substance_verdicts,
)
from lightroom_tagger.core.database.vision_cache import VISION_CACHE_OVERSIZED_SENTINEL
from lightroom_tagger.core.frame_substance_detector import (
    classify_verdict,
    compute_statistics_from_path,
    detector_version,
)

ABSOLUTE_FLAGGED_BOUND = 250
RATIO_FLAGGED_MULTIPLIER = 3.0
_PROGRESS_EVERY = 500


def _resolve_unknown_reason(compressed_path: object) -> tuple[str, str] | None:
    """Return ``(verdict, unknown_reason)`` when the cache cannot be decoded."""
    cp = str(compressed_path or "").strip()
    if not cp:
        return "unknown", "no_cache_row"
    if cp == VISION_CACHE_OVERSIZED_SENTINEL:
        return "unknown", "oversized_sentinel"
    if not os.path.isfile(cp):
        return "unknown", "cache_file_missing"
    return None


def _empty_verdict_row(
    *,
    image_key: str,
    verdict: str,
    unknown_reason: str,
    version: str,
    run_id: int,
) -> dict[str, Any]:
    return {
        "image_key": image_key,
        "verdict": verdict,
        "unknown_reason": unknown_reason,
        "black_frac_25": None,
        "blown_frac_235": None,
        "lap_var": None,
        "tile_max": None,
        "entropy": None,
        "detector_version": version,
        "run_id": run_id,
    }


def _judge_image(
    image_key: str,
    compressed_path: object,
    *,
    version: str,
    run_id: int,
) -> dict[str, Any]:
    unknown = _resolve_unknown_reason(compressed_path)
    if unknown is not None:
        verdict, reason = unknown
        return _empty_verdict_row(
            image_key=image_key,
            verdict=verdict,
            unknown_reason=reason,
            version=version,
            run_id=run_id,
        )

    stats = compute_statistics_from_path(str(compressed_path))
    if stats is None:
        return _empty_verdict_row(
            image_key=image_key,
            verdict="unknown",
            unknown_reason="decode_failed",
            version=version,
            run_id=run_id,
        )

    verdict = classify_verdict(stats)
    return {
        "image_key": image_key,
        "verdict": verdict,
        "unknown_reason": "",
        "black_frac_25": stats["black_frac_25"],
        "blown_frac_235": stats["blown_frac_235"],
        "lap_var": stats["lap_var"],
        "tile_max": stats["tile_max"],
        "entropy": stats["entropy"],
        "detector_version": version,
        "run_id": run_id,
    }


def _count_verdicts(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts = {"void": 0, "illegible": 0, "ok": 0, "unknown": 0}
    for row in rows:
        verdict = str(row["verdict"])
        counts[verdict] = counts.get(verdict, 0) + 1
    return counts


def _flagged_count(counts: Mapping[str, int]) -> int:
    return int(counts.get("void", 0)) + int(counts.get("illegible", 0))


def evaluate_breach(
    *,
    new_rows: Mapping[str, dict[str, Any]],
    previous_rows: Mapping[str, dict[str, Any]],
) -> tuple[bool, str]:
    """Return ``(breached, reason)`` for a completed detection run."""
    new_counts = _count_verdicts(new_rows.values())
    flagged = _flagged_count(new_counts)
    if flagged > ABSOLUTE_FLAGGED_BOUND:
        return True, f"absolute bound: {flagged} flagged > {ABSOLUTE_FLAGGED_BOUND}"

    if not previous_rows:
        return False, ""

    intersection_keys = [
        key
        for key in new_rows
        if key in previous_rows
        and str(previous_rows[key]["verdict"]) != "unknown"
        and str(new_rows[key]["verdict"]) != "unknown"
    ]
    if not intersection_keys:
        return False, ""

    prev_flagged = sum(
        1
        for key in intersection_keys
        if str(previous_rows[key]["verdict"]) in FLAGGED_VERDICTS
    )
    new_flagged = sum(
        1
        for key in intersection_keys
        if str(new_rows[key]["verdict"]) in FLAGGED_VERDICTS
    )
    if prev_flagged > 0 and new_flagged > RATIO_FLAGGED_MULTIPLIER * prev_flagged:
        return (
            True,
            f"ratio bound: intersection flagged {new_flagged} > "
            f"{RATIO_FLAGGED_MULTIPLIER:g}x previous {prev_flagged}",
        )
    return False, ""


def run_frame_substance_detection(
    db: sqlite3.Connection,
    *,
    progress: Callable[[int, str | None], None] | None = None,
) -> dict[str, Any]:
    """Scan the catalog, overwrite verdict rows, and finalize the run record."""
    version = detector_version()
    previous_rows = load_frame_substance_verdict_map(db)
    run_id = insert_frame_substance_run(db, detector_version=version)

    catalog_rows = list_catalog_images_with_vision_cache(db)
    total = len(catalog_rows)
    new_rows: dict[str, dict[str, Any]] = {}
    batch: list[dict[str, Any]] = []

    for idx, row in enumerate(catalog_rows, start=1):
        if cancel_scope.is_cancelled():
            raise RuntimeError("cancelled")

        image_key = str(row["image_key"])
        verdict_row = _judge_image(
            image_key,
            row.get("compressed_path"),
            version=version,
            run_id=run_id,
        )
        new_rows[image_key] = verdict_row
        batch.append(verdict_row)

        if len(batch) >= _PROGRESS_EVERY:
            upsert_frame_substance_verdicts(db, batch)
            batch.clear()

        if progress is not None and (idx % _PROGRESS_EVERY == 0 or idx == total):
            pct = 5 + int(95 * idx / max(total, 1))
            progress(pct, f"Judged {idx}/{total} images")

    if batch:
        upsert_frame_substance_verdicts(db, batch)

    counts = _count_verdicts(new_rows.values())
    breached, breach_reason = evaluate_breach(
        new_rows=new_rows,
        previous_rows=previous_rows,
    )
    finish_frame_substance_run(
        db,
        run_id,
        count_void=counts["void"],
        count_illegible=counts["illegible"],
        count_ok=counts["ok"],
        count_unknown=counts["unknown"],
        breached=breached,
        breach_reason=breach_reason,
    )

    return {
        "run_id": run_id,
        "detector_version": version,
        "total": total,
        "count_void": counts["void"],
        "count_illegible": counts["illegible"],
        "count_ok": counts["ok"],
        "count_unknown": counts["unknown"],
        "flagged": _flagged_count(counts),
        "breached": breached,
        "breach_reason": breach_reason,
    }
