"""Insights landing-page aggregate reads (tile counts + perspective coverage)."""

from __future__ import annotations

import sqlite3
from typing import TypedDict

from .stack_suggestions import count_pending_stack_suggestions
from .frame_substance import (
    count_frame_substance_by_unknown_reason,
    count_frame_substance_flagged_net_of_overrides,
    count_frame_substance_never_judged,
    get_latest_finished_frame_substance_run,
)


class PerspectiveCoverageRow(TypedDict):
    slug: str
    display_name: str
    active: bool
    scored_images: int


class FrameSubstanceRunSummary(TypedDict):
    detector_version: str
    finished_at: str
    breached: bool
    breach_reason: str


class InsightsSummary(TypedDict):
    catalog_images: int
    scoring_9_plus: int
    burst_stacks: int
    pending_stack_suggestions: int
    unscored_on_active_perspectives: int
    no_current_score: int
    perspective_coverage: list[PerspectiveCoverageRow]
    frame_substance_flagged: int
    frame_substance_unknown: dict[str, int]
    frame_substance_run: FrameSubstanceRunSummary | None


def get_insights_summary(conn: sqlite3.Connection) -> InsightsSummary:
    """Return tile counts and per-perspective coverage for the Insights landing page."""
    catalog_images = int(
        conn.execute("SELECT COUNT(*) AS c FROM images").fetchone()["c"]
    )

    scoring_9_plus = int(
        conn.execute(
            """
            SELECT COUNT(DISTINCT s.image_key) AS c
            FROM image_scores s
            INNER JOIN perspectives p
                ON p.slug = s.perspective_slug AND p.active = 1
            WHERE s.is_current = 1
              AND s.image_type = 'catalog'
              AND s.score >= 9
            """
        ).fetchone()["c"]
    )

    burst_stacks = int(
        conn.execute("SELECT COUNT(*) AS c FROM image_stacks").fetchone()["c"]
    )

    pending_stack_suggestions = count_pending_stack_suggestions(conn)

    frame_substance_flagged = count_frame_substance_flagged_net_of_overrides(conn)
    frame_substance_unknown = dict(count_frame_substance_by_unknown_reason(conn))
    never_judged = count_frame_substance_never_judged(conn)
    if never_judged:
        frame_substance_unknown["never_judged"] = never_judged

    latest_run = get_latest_finished_frame_substance_run(conn)
    frame_substance_run: FrameSubstanceRunSummary | None = None
    if latest_run is not None:
        frame_substance_run = {
            "detector_version": str(latest_run["detector_version"]),
            "finished_at": str(latest_run["finished_at"]),
            "breached": bool(int(latest_run.get("breached") or 0)),
            "breach_reason": str(latest_run.get("breach_reason") or ""),
        }

    unscored_on_active_perspectives = int(
        conn.execute(
            """
            SELECT COUNT(DISTINCT i.key) AS c
            FROM images i
            INNER JOIN perspectives p ON p.active = 1
            WHERE NOT EXISTS (
                SELECT 1 FROM image_scores s
                WHERE s.image_key = i.key
                  AND s.perspective_slug = p.slug
                  AND s.is_current = 1
                  AND s.image_type = 'catalog'
            )
            """
        ).fetchone()["c"]
    )

    no_current_score = int(
        conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM images i
            WHERE NOT EXISTS (
                SELECT 1 FROM image_scores s
                WHERE s.image_key = i.key
                  AND s.is_current = 1
                  AND s.image_type = 'catalog'
            )
            """
        ).fetchone()["c"]
    )

    coverage_rows = conn.execute(
        """
        SELECT
            p.slug AS slug,
            p.display_name AS display_name,
            p.active AS active,
            COUNT(DISTINCT s.image_key) AS scored_images
        FROM perspectives p
        LEFT JOIN image_scores s
            ON s.perspective_slug = p.slug
           AND s.is_current = 1
           AND s.image_type = 'catalog'
        GROUP BY p.slug
        ORDER BY p.slug ASC
        """
    ).fetchall()

    perspective_coverage: list[PerspectiveCoverageRow] = []
    for row in coverage_rows:
        perspective_coverage.append(
            {
                "slug": str(row["slug"]),
                "display_name": str(row["display_name"]),
                "active": bool(row["active"]),
                "scored_images": int(row["scored_images"]),
            }
        )

    return {
        "catalog_images": catalog_images,
        "scoring_9_plus": scoring_9_plus,
        "burst_stacks": burst_stacks,
        "pending_stack_suggestions": pending_stack_suggestions,
        "unscored_on_active_perspectives": unscored_on_active_perspectives,
        "no_current_score": no_current_score,
        "perspective_coverage": perspective_coverage,
        "frame_substance_flagged": frame_substance_flagged,
        "frame_substance_unknown": frame_substance_unknown,
        "frame_substance_run": frame_substance_run,
    }
