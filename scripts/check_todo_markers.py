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

import argparse
import re
import sys
from collections.abc import Sequence
from pathlib import Path

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
    for lineno, line in enumerate(text.splitlines(), start=1):
        if IGNORE_DIRECTIVE in line:
            continue
        for match in MARKER_RE.finditer(line):
            if _is_path_segment(line, match.start(), match.end()):
                continue
            messages.append(f"{path}:{lineno}: bare {match.group(1)} marker. {HINT}")
    return messages


def check_file(path: Path) -> list[str]:
    """Scan one file, reporting rather than hiding files it cannot read.

    Args:
        path: File to scan.

    Returns:
        One message per untagged marker; empty for clean or unscannable files.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        print(f"{path}: skipped (not UTF-8)", file=sys.stderr)
        return []
    except OSError as exc:
        print(f"{path}: skipped ({exc.strerror})", file=sys.stderr)
        return []
    return check_text(text, str(path))


def main(argv: Sequence[str] | None = None) -> int:
    """Scan the given files and report untagged markers.

    Args:
        argv: Command-line arguments; defaults to ``sys.argv[1:]``.

    Returns:
        1 when any untagged marker was found, 0 otherwise.
    """
    parser = argparse.ArgumentParser(description="Reject untagged deferred-work markers.")
    parser.add_argument("filenames", nargs="*", help="files to scan")
    args = parser.parse_args(argv)

    messages = [message for name in args.filenames for message in check_file(Path(name))]
    for message in messages:
        print(message)
    return 1 if messages else 0


if __name__ == "__main__":
    sys.exit(main())
