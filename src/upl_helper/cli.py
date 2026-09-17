"""Command line entry point.

Subcommands are registered by the modules that implement them, so that adding
a command does not mean editing a central dispatch table.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence

from upl_helper import __version__

# Populated by register_command(). Maps command name -> (help text, adder).
_COMMANDS: dict[str, tuple[str, Callable[[argparse.ArgumentParser], None]]] = {}


def register_command(
    name: str, help_text: str
) -> Callable[
    [Callable[[argparse.ArgumentParser], None]],
    Callable[[argparse.ArgumentParser], None],
]:
    """Register a subcommand.

    The decorated function receives the subparser for its command and is
    responsible for adding its own arguments and setting ``func`` as the
    handler via ``parser.set_defaults(func=...)``.
    """

    def decorator(
        adder: Callable[[argparse.ArgumentParser], None],
    ) -> Callable[[argparse.ArgumentParser], None]:
        _COMMANDS[name] = (help_text, adder)
        return adder

    return decorator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="upl",
        description="Checks for Medicaid Upper Payment Limit demonstrations.",
    )
    parser.add_argument(
        "--version", action="version", version=f"upl-helper {__version__}"
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    for name, (help_text, adder) in sorted(_COMMANDS.items()):
        sub = subparsers.add_parser(name, help=help_text, description=help_text)
        adder(sub)

    return parser


def _load_commands() -> None:
    """Import command modules for their registration side effects.

    Each module calls ``register_command`` at import time. Modules are added
    here as they are implemented.
    """
    # Nothing registered yet. SPEC-0002 adds `profile` and `unprotect`.


def main(argv: Sequence[str] | None = None) -> int:
    _load_commands()
    parser = build_parser()
    args = parser.parse_args(argv)

    if not getattr(args, "func", None):
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
