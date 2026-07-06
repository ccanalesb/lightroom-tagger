"""Tests for CLI dispatch via the run(argv, config, commands) seam."""

from __future__ import annotations

import argparse
import unittest
from unittest.mock import patch

from lightroom_tagger.core.cli import run
from lightroom_tagger.core.cli_commands import Command
from lightroom_tagger.core.config import Config


class TestCliRun(unittest.TestCase):
    """Exercise routing and parsed-arg delivery through run()."""

    def setUp(self):
        self.config = Config(catalog_path="/cat.lrcat", db_path="/db.sqlite")
        self.received: list[tuple[str, object, Config]] = []

    def _record_handler(self, name: str):
        def handler(args, config):
            self.received.append((name, args, config))
            return 0

        return handler

    def _fake_commands(self) -> list[Command]:
        def add_alpha_args(parser: argparse.ArgumentParser) -> None:
            parser.add_argument("--foo", default="bar")

        def add_beta_args(parser: argparse.ArgumentParser) -> None:
            parser.add_argument("--count", type=int, default=3)

        return [
            Command("alpha", "Alpha command", add_alpha_args, self._record_handler("alpha")),
            Command("beta", "Beta command", add_beta_args, self._record_handler("beta")),
        ]

    def test_known_command_routes_to_its_handler(self):
        commands = self._fake_commands()
        code = run(["alpha"], self.config, commands)
        self.assertEqual(code, 0)
        self.assertEqual(len(self.received), 1)
        self.assertEqual(self.received[0][0], "alpha")

    def test_handler_receives_correctly_parsed_flags(self):
        commands = self._fake_commands()
        run(["beta", "--count", "7"], self.config, commands)
        self.assertEqual(len(self.received), 1)
        _name, args, config = self.received[0]
        self.assertEqual(args.count, 7)
        self.assertIs(config, self.config)

    def test_empty_command_prints_help_and_returns_one(self):
        commands = self._fake_commands()
        with patch("sys.stdout"):
            code = run([], self.config, commands)
        self.assertEqual(code, 1)
        self.assertEqual(self.received, [])

    def test_unknown_command_exits_via_argparse(self):
        commands = self._fake_commands()
        with self.assertRaises(SystemExit) as ctx:
            run(["nope"], self.config, commands)
        self.assertEqual(ctx.exception.code, 2)
        self.assertEqual(self.received, [])


if __name__ == "__main__":
    unittest.main()
