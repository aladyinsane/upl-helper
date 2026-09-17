"""Tests for the CLI scaffolding itself.

Command behavior is tested alongside each command; this only covers the
registration mechanism and the bare entry point.
"""

from __future__ import annotations

import argparse

import pytest

from upl_helper import cli


def test_version_flag_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["--version"])
    assert excinfo.value.code == 0
    assert "upl-helper" in capsys.readouterr().out


def test_no_command_prints_help_and_exits_nonzero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli.main([]) == 1
    assert "COMMAND" in capsys.readouterr().out


def test_register_command_adds_a_subparser() -> None:
    sentinel_name = "_test_only_command"

    @cli.register_command(sentinel_name, "help text for the test command")
    def _add(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--flag", action="store_true")
        parser.set_defaults(func=lambda args: 7)

    try:
        parsed = cli.build_parser().parse_args([sentinel_name, "--flag"])
        assert parsed.flag is True
        assert parsed.func(parsed) == 7
    finally:
        del cli._COMMANDS[sentinel_name]
