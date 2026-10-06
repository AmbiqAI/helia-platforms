"""Exceptions the package raises."""

from __future__ import annotations


class PlatformError(Exception):
    """Base class for every error this package raises."""


class FormatError(PlatformError):
    """A catalogue file or mapping breaks the file format of ADR 0002.

    ``problems`` lists every problem found, each prefixed with the location
    (``<origin>: <path>``) it was found at.
    """

    def __init__(self, message: str, problems: tuple[str, ...] = ()) -> None:
        self.problems = problems or (message,)
        super().__init__(message if not problems else "\n".join(problems))
