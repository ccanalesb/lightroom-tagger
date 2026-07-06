"""Tests for the CLI command-registry dispatch engine."""

from __future__ import annotations

import argparse
from unittest.mock import Mock

from lightroom_tagger.core.cli import run
from lightroom_tagger.core.cli_commands import Command
from lightroom_tagger.core.config import Config


def _fake_command(handler):
    def add_arguments(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--db", help="Path to SQLite database (overrides global)")
        parser.add_argument("--limit", type=int, help="Limit number of images to process")
        parser.add_argument("--cache-only", action="store_true")

    return Command(
        name="fake-cmd",
        help="Fake command for registry tests",
        add_arguments=add_arguments,
        handler=handler,
    )


def test_run_dispatches_known_command_with_parsed_flags():
    captured: dict[str, object] = {}

    def handler(args, config):
        captured["args"] = args
        captured["config"] = config
        return 42

    commands = [_fake_command(handler)]
    config = Config(catalog_path="/cfg/catalog.lrcat", db_path="/cfg/library.db")

    exit_code = run(
        ["fake-cmd", "--db", "/override/db.sqlite", "--limit", "7", "--cache-only"],
        config,
        commands,
    )

    assert exit_code == 42
    assert captured["config"] is config
    args = captured["args"]
    assert args.command == "fake-cmd"
    assert args.db == "/override/db.sqlite"
    assert args.limit == 7
    assert args.cache_only is True


def test_run_empty_command_prints_help_and_returns_exit_code(capsys):
    commands = [_fake_command(Mock(return_value=0))]
    config = Config()

    exit_code = run([], config, commands)

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "lightroom-tagger" in captured.out
    assert "Available commands" in captured.out


def test_run_unknown_command_prints_help_and_returns_exit_code(capsys):
    handler = Mock(return_value=0)
    commands = [_fake_command(handler)]
    config = Config()

    exit_code = run(["not-a-command"], config, commands)

    assert exit_code == 1
    handler.assert_not_called()
    captured = capsys.readouterr()
    assert "lightroom-tagger" in captured.out
