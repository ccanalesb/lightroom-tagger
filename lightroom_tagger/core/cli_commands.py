"""Explicit command registry for the lightroom-tagger CLI."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass

from lightroom_tagger.core.cli import cmd_scan, cmd_search, cmd_sync
from lightroom_tagger.core.cli_cmds_extra import (
    cmd_enrich_catalog,
    cmd_export,
    cmd_init,
    cmd_stats,
)

# Registry handlers expose ``(args, config) -> int``. Library-DB commands are
# wrapped by ``@with_library_db`` (or ``@map_cli_errors`` + manual DB open for
# ``scan``) so dispatch stays ADR-0006-compatible while bodies take ``db``.


@dataclass(frozen=True)
class Command:
    name: str
    help: str
    add_arguments: Callable[[argparse.ArgumentParser], None]
    handler: Callable[..., int]


def _add_scan_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--catalog",
        help="Path to .lrcat file (overrides global)"
    )
    parser.add_argument(
        "--db",
        help="Path to SQLite database (overrides global)"
    )
    parser.add_argument(
        "--workers",
        type=int,
        help="Parallel workers"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of images to process"
    )


def _add_sync_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--catalog",
        help="Path to .lrcat file (overrides global)",
    )
    parser.add_argument(
        "--db",
        help="Path to SQLite database (overrides global)",
    )


def _add_search_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--db",
        help="Path to SQLite database (overrides global)"
    )
    parser.add_argument(
        "--keyword",
        help="Search by keyword"
    )
    parser.add_argument(
        "--rating",
        type=int,
        help="Minimum rating (0-5)"
    )
    parser.add_argument(
        "--color-label",
        help="Filter by color label"
    )
    parser.add_argument(
        "--date-start",
        help="Start date (ISO format)"
    )
    parser.add_argument(
        "--date-end",
        help="End date (ISO format)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit results"
    )


def _add_export_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--db",
        help="Path to SQLite database (overrides global)"
    )
    parser.add_argument(
        "--output", "-o",
        required=True,
        help="Output file path"
    )
    parser.add_argument(
        "--format",
        choices=["json", "csv"],
        default="json",
        help="Export format (default: json)"
    )
    parser.add_argument(
        "--keyword",
        help="Export only images matching keyword"
    )
    parser.add_argument(
        "--rating",
        type=int,
        help="Export only images with minimum rating"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit results"
    )


def _add_init_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--db",
        help="Path to SQLite database (overrides global)"
    )


def _add_stats_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--db",
        help="Path to SQLite database (overrides global)"
    )


def _add_enrich_catalog_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--db",
        help="Path to SQLite database (overrides global)",
    )
    parser.add_argument(
        "--catalog",
        help="Path to .lrcat file (overrides global; full enrichment only)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of images to process",
    )
    parser.add_argument(
        "--cache-only",
        action="store_true",
        help="Warm vision cache only (skip full enrichment)",
    )


COMMANDS: list[Command] = [
    Command("scan", "Scan catalog, index all images", _add_scan_arguments, cmd_scan),
    Command(
        "sync",
        "Incremental catalog sync — add missing images to library.db",
        _add_sync_arguments,
        cmd_sync,
    ),
    Command("search", "Search indexed images", _add_search_arguments, cmd_search),
    Command("export", "Export to JSON/CSV", _add_export_arguments, cmd_export),
    Command("init", "Initialize database", _add_init_arguments, cmd_init),
    Command("stats", "Show database statistics", _add_stats_arguments, cmd_stats),
    Command(
        "enrich-catalog",
        "Analyze catalog images or warm the vision cache",
        _add_enrich_catalog_arguments,
        cmd_enrich_catalog,
    ),
]
