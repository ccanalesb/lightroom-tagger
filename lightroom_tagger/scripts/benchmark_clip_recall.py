#!/usr/bin/env python3
"""Read-only recall benchmark: validated match pairs vs. CLIP top_k=50 shortlist."""

from __future__ import annotations

import argparse
import csv
import os
import sqlite3
import sys
from pathlib import Path
from typing import cast

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lightroom_tagger.core.clip_similarity import (
    get_clip_embedding_blob_for_key,
    shortlist_catalog_candidates_by_clip,
)
from lightroom_tagger.core.database import (
    catalog_key_is_primary_grid_row,
    get_instagram_dump_media,
    get_rejected_pairs,
    init_database,
)
from lightroom_tagger.core.matcher import find_candidates_by_date

_MATCH_TRUTH_SQL = (
    "SELECT catalog_key, insta_key FROM matches WHERE validated_at IS NOT NULL"
)
_CSV_COLUMNS = (
    "insta_key,validated_catalog_key,date_window_size,candidates_after_filters,shortlist_size,shortlist_includes_validated,status"
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark CLIP shortlist recall on validated instagram↔catalog pairs.",
    )
    parser.add_argument(
        "--db",
        default="library.db",
        help="Path to Lightroom tagger SQLite library (default: library.db)",
    )
    parser.add_argument(
        "--out-dir",
        default="artifacts/clip-recall-benchmark",
        help=(
            "Directory for 10-recall-data.csv and 10-RECALL.md "
            "(default: artifacts/clip-recall-benchmark)"
        ),
    )
    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f"error: database not found: {args.db}", file=sys.stderr)
        sys.exit(1)

    db = cast(sqlite3.Connection, init_database(args.db))
    try:
        truth_rows = list(db.execute(_MATCH_TRUTH_SQL).fetchall())
        total_validated = len(truth_rows)

        rejected = get_rejected_pairs(db)

        missing_dump_media = 0
        skipped_no_embedding = 0
        filtered_out = 0
        hits = 0
        misses = 0
        embedded = 0

        csv_rows: list[dict[str, str | int]] = []
        miss_details: list[dict[str, str | int]] = []

        for row in truth_rows:
            validated_catalog_key = row["catalog_key"]
            insta_key = row["insta_key"]
            dump_media = get_instagram_dump_media(db, insta_key)
            if dump_media is None:
                missing_dump_media += 1
                continue

            media_key = insta_key
            raw = find_candidates_by_date(db, dump_media, days_before=90)
            date_window_size = len(raw)
            candidates = [
                c for c in raw if (c.get("key"), media_key) not in rejected
            ]
            candidates = [
                c
                for c in candidates
                if c.get("key") and catalog_key_is_primary_grid_row(db, c["key"])
            ]
            cand_keys = [c["key"] for c in candidates if c.get("key")]
            candidates_after_filters = len(cand_keys)

            ig_blob = get_clip_embedding_blob_for_key(db, insta_key)
            # D-05: skip shortlist when get_clip_embedding_blob_for_key(db, insta_key) is None.
            if ig_blob is None:
                skipped_no_embedding += 1
                csv_rows.append(
                    {
                        "insta_key": insta_key,
                        "validated_catalog_key": validated_catalog_key,
                        "date_window_size": date_window_size,
                        "candidates_after_filters": candidates_after_filters,
                        "shortlist_size": 0,
                        "shortlist_includes_validated": "false",
                        "status": "skipped_no_embedding",
                    }
                )
                continue

            embedded += 1

            if validated_catalog_key not in cand_keys:
                filtered_out += 1
                csv_rows.append(
                    {
                        "insta_key": insta_key,
                        "validated_catalog_key": validated_catalog_key,
                        "date_window_size": date_window_size,
                        "candidates_after_filters": candidates_after_filters,
                        "shortlist_size": 0,
                        "shortlist_includes_validated": "false",
                        "status": "filtered_out",
                    }
                )
                continue

            short_keys = shortlist_catalog_candidates_by_clip(db, insta_key, cand_keys, top_k=50)
            shortlist_size = len(short_keys)
            in_shortlist = validated_catalog_key in short_keys
            includes = "true" if in_shortlist else "false"

            if in_shortlist:
                status = "hit"
                hits += 1
            else:
                status = "miss"
                misses += 1
                miss_details.append(
                    {
                        "insta_key": insta_key,
                        "validated_catalog_key": validated_catalog_key,
                        "shortlist_size": shortlist_size,
                        "date_window_size": date_window_size,
                        "candidates_after_filters": candidates_after_filters,
                    }
                )

            csv_rows.append(
                {
                    "insta_key": insta_key,
                    "validated_catalog_key": validated_catalog_key,
                    "date_window_size": date_window_size,
                    "candidates_after_filters": candidates_after_filters,
                    "shortlist_size": shortlist_size,
                    "shortlist_includes_validated": includes,
                    "status": status,
                }
            )

        out_base = Path(args.out_dir)
        out_base.mkdir(parents=True, exist_ok=True)
        csv_path = out_base / "10-recall-data.csv"
        md_path = out_base / "10-RECALL.md"

        csv_fieldnames = _CSV_COLUMNS.split(",")
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=csv_fieldnames)
            writer.writeheader()
            writer.writerows(csv_rows)

        denom = hits + misses
        if denom > 0:
            recall_pct = 100.0 * hits / denom
            recall_block = (
                f"**{recall_pct:.4f}%** (`100.0 * hits / (hits + misses)`, "
                f"hits={hits}, misses={misses})."
            )
        else:
            recall_block = (
                "CLIP shortlist recall: **undefined** — denominator "
                "`hits + misses` is 0 (no pairs reached hit/miss)."
            )

        funnel_lines = [
            "# Phase 10 — CLIP shortlist recall (validated pairs)",
            "",
            "## Funnel",
            "",
            f"- **total_validated:** {total_validated}",
            f"- **missing_dump_media:** {missing_dump_media}",
            f"- **embedded** (Instagram row had CLIP blob): {embedded}",
            f"- **skipped_no_embedding:** {skipped_no_embedding}",
            f"- **filtered_out:** {filtered_out}",
            f"- **hits:** {hits}",
            f"- **misses:** {misses}",
            "",
            "## Recall",
            "",
            recall_block,
            "",
            "## Miss table",
            "",
        ]

        if miss_details:
            funnel_lines.extend(
                [
                    "| insta_key | validated_catalog_key | shortlist_size | "
                    "date_window_size | candidates_after_filters |",
                    "| --- | --- | --- | --- | --- |",
                ]
            )
            for m in miss_details:
                funnel_lines.append(
                    f"| {m['insta_key']} | {m['validated_catalog_key']} | "
                    f"{m['shortlist_size']} | {m['date_window_size']} | "
                    f"{m['candidates_after_filters']} |"
                )
        else:
            funnel_lines.append("*No misses.*")

        md_path.write_text("\n".join(funnel_lines) + "\n", encoding="utf-8")
    finally:
        db.close()


if __name__ == "__main__":
    main()
