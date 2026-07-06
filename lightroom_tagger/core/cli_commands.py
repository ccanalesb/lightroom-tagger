"""CLI command registry — each command's name, flags, and handler in one place."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Command:
    name: str
    help: str
    add_arguments: Callable[[argparse.ArgumentParser], None]
    handler: Callable[..., int]


def add_scan_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--catalog",
        help="Path to .lrcat file (overrides global)",
    )
    parser.add_argument(
        "--db",
        help="Path to SQLite database (overrides global)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        help="Parallel workers",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of images to process",
    )


def add_sync_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--catalog",
        help="Path to .lrcat file (overrides global)",
    )
    parser.add_argument(
        "--db",
        help="Path to SQLite database (overrides global)",
    )


def add_search_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--db",
        help="Path to SQLite database (overrides global)",
    )
    parser.add_argument(
        "--keyword",
        help="Search by keyword",
    )
    parser.add_argument(
        "--rating",
        type=int,
        help="Minimum rating (0-5)",
    )
    parser.add_argument(
        "--color-label",
        help="Filter by color label",
    )
    parser.add_argument(
        "--date-start",
        help="Start date (ISO format)",
    )
    parser.add_argument(
        "--date-end",
        help="End date (ISO format)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit results",
    )


def add_export_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--db",
        help="Path to SQLite database (overrides global)",
    )
    parser.add_argument(
        "--output", "-o",
        required=True,
        help="Output file path",
    )
    parser.add_argument(
        "--format",
        choices=["json", "csv"],
        default="json",
        help="Export format (default: json)",
    )
    parser.add_argument(
        "--keyword",
        help="Export only images matching keyword",
    )
    parser.add_argument(
        "--rating",
        type=int,
        help="Export only images with minimum rating",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit results",
    )


def add_init_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--db",
        help="Path to SQLite database (overrides global)",
    )


def add_stats_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--db",
        help="Path to SQLite database (overrides global)",
    )


def _build_commands() -> list[Command]:
    from lightroom_tagger.core.cli import cmd_scan, cmd_search, cmd_sync
    from lightroom_tagger.core.cli_cmds_extra import cmd_export, cmd_init, cmd_stats

    return [
        Command("scan", "Scan catalog, index all images", add_scan_arguments, cmd_scan),
        Command(
            "sync",
            "Incremental catalog sync — add missing images to library.db",
            add_sync_arguments,
            cmd_sync,
        ),
        Command("search", "Search indexed images", add_search_arguments, cmd_search),
        Command("export", "Export to JSON/CSV", add_export_arguments, cmd_export),
        Command("init", "Initialize database", add_init_arguments, cmd_init),
        Command("stats", "Show database statistics", add_stats_arguments, cmd_stats),
    ]


COMMANDS: list[Command] = _build_commands()
