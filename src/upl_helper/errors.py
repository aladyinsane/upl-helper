"""Exception types shared across the package."""

from __future__ import annotations


class UplHelperError(Exception):
    """Base class for errors this package raises deliberately.

    The CLI catches these and prints the message without a traceback. Anything
    not derived from this is a bug and should surface with its traceback.
    """


class UnsupportedWorkbookError(UplHelperError):
    """The input is not a workbook this package can read."""
