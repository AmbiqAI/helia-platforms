#!/usr/bin/env python3
"""Reject deferred-work markers that name no tracking issue or reserved tag.

CONTRIBUTING.md requires ``TODO(#123)`` for tracked work and ``TODO(verify)``
for unverified claims, so a marker can never outlive the context that
explains it.

A line carrying ``todo-markers: ignore`` (in whatever comment syntax the file
uses) silences the whole line, not just the marker on it, for the rare case
where the word is the subject rather than a marker.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Sequence
from pathlib import Path

import hook_common

ALLOWED_TAGS: tuple[str, ...] = ("verify",)
MARKERS: tuple[str, ...] = ("TODO", "FIXME", "HACK", "XXX")  # todo-markers: ignore

IGNORE_DIRECTIVE = "todo-markers: ignore"

_TAGS = "|".join((r"#\d+", *(re.escape(tag) for tag in ALLOWED_TAGS)))
MARKER_RE = re.compile(rf"\b({'|'.join(MARKERS)})\b(?!\((?:{_TAGS})\))")

HINT = (
    "Use TODO(#123) for tracked work or TODO(verify) for unverified claims (see CONTRIBUTING.md)."
)

_EXTENSION_RE = re.compile(r"^\.[A-Za-z0-9]+")


def _is_path_segment(line: str, start: int, end: int) -> bool:
    """Report whether the match at ``[start:end)`` names a path, URL, or file.

    A marker is exempt only when it is not standing alone as deferred-work
    prose: inside a URL (``://`` earlier in the same token), as a bare path
    segment (``/foo``, ``./foo``, ``../foo``, but not a ``//`` comment
    opener, which is glued to no path at all), or immediately followed by a
    file extension (``TODO.md``). A marker after a plain ``word/`` prefix is
    none of these and must still be caught.

    Args:
        line: Line containing the match.
        start: Index of the first character of the match.
        end: Index one past the last character of the match.

    Returns:
        True when the match names a location rather than marking work.
    """
    token_start = start
    while token_start > 0 and not line[token_start - 1].isspace():
        token_start -= 1
    token_end = end
    while token_end < len(line) and not line[token_end].isspace():
        token_end += 1
    token = line[token_start:token_end]
    local_start = start - token_start
    local_end = end - token_start

    if "://" in token[:local_start]:
        return True
    if token.startswith(("../", "./")):
        return True
    if token.startswith("/") and not token.startswith("//"):
        return True
    return _EXTENSION_RE.match(token[local_end:]) is not None


def check_text(text: str, path: str) -> list[str]:
    """Scan text for untagged markers.

    Args:
        text: File contents to scan.
        path: Path used in the returned messages.

    Returns:
        One message per untagged marker; empty when the text is clean.
    """
    messages: list[str] = []
    for lineno, line in hook_common.split_lines(text):
        if IGNORE_DIRECTIVE in line:
            continue
        for match in MARKER_RE.finditer(line):
            if _is_path_segment(line, match.start(), match.end()):
                continue
            messages.append(f"{path}:{lineno}: bare {match.group(1)} marker. {HINT}")
    return messages


def check_file(path: Path) -> list[str]:
    """Scan one file, or a symlink's target string; see ``hook_common.check_file``."""
    return hook_common.check_file(path, check_text)


def main(argv: Sequence[str] | None = None) -> int:
    """Scan the given files; return 1 when any untagged marker was found, 0 otherwise."""
    return hook_common.main(argv, check_text, "Reject untagged deferred-work markers.")


if __name__ == "__main__":
    sys.exit(main())
