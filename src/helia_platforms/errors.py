"""Exceptions and warnings the package raises.

Validation findings that do not make a catalog invalid (an interface whose
devices no master can reach, a device on an interface without an aperture)
are issued with ``warnings.warn`` as ``PlatformWarning``, so callers can
filter them or turn them into errors with the ``warnings`` module.
"""

from __future__ import annotations


class PlatformError(Exception):
    """Base class for every error this package raises."""


class FormatError(PlatformError):
    """A catalog file or mapping breaks the file format of ADR 0002.

    ``problems`` lists every problem found, each prefixed with the location
    (``<origin>: <path>``) it was found at.
    """

    def __init__(self, message: str, problems: tuple[str, ...] = ()) -> None:
        self.problems = problems or (message,)
        super().__init__(message if not problems else "\n".join(problems))


class UnknownPlatform(PlatformError):
    """No board, part, implementation, Soc, alias or composition has this name."""

    def __init__(
        self, name: str, suggestions: tuple[str, ...] = (), *, what: str = "platform"
    ) -> None:
        self.name = name
        self.suggestions = suggestions
        hint = f"; did you mean {', '.join(suggestions)}?" if suggestions else ""
        super().__init__(f"unknown {what} {name!r}{hint}")


class AmbiguousPlatform(PlatformError):
    """A shorthand names several targets; ``candidates`` lists them."""

    def __init__(self, name: str, candidates: tuple[str, ...]) -> None:
        self.name = name
        self.candidates = candidates
        super().__init__(f"{name!r} names several targets: {', '.join(candidates)}")


class PlatformWarning(UserWarning):
    """A validation finding that does not make the catalog invalid."""
