"""File reading, line splitting and command-line handling shared by the hook scripts.

Each hook script supplies a ``check_text(text, path)`` function that returns
one message per finding; this module reads the files and runs that function.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path

CheckText = Callable[[str, str], list[str]]


def split_lines(text: str) -> Iterator[tuple[int, str]]:
    """Yield ``(line number, line)`` pairs, numbering from 1.

    Lines split on ``\\n`` only, so a form feed or U+2028 cannot make the line
    numbers disagree with editors. A trailing ``\\r`` is dropped from each line.
    """
    for lineno, line in enumerate(text.split("\n"), start=1):
        yield lineno, line.removesuffix("\r")


def split_segments(text: str, ignore_directive: str) -> Iterator[tuple[int, str]]:
    """Yield ``(line number, segment)`` for each segment without ``ignore_directive``.

    Numbering follows ``split_lines``; each line is then cut at every break
    ``str.splitlines`` knows (``\\r``, ``\\f``, U+2028, ...), which some
    editors render as a new line, so a directive silences only its own segment.
    """
    for lineno, line in split_lines(text):
        for segment in line.splitlines():
            if ignore_directive not in segment:
                yield lineno, segment


def check_file(path: Path, check_text: CheckText) -> list[str]:
    """Run ``check_text`` on one file, or on a symlink's target string.

    A symlink is never followed. Text that is not valid UTF-8 is still scanned,
    with each undecodable byte read as U+FFFD. An unreadable file is reported
    on stderr and yields no messages.
    """
    try:
        if path.is_symlink():
            text = os.readlink(path)
        else:
            text = path.read_bytes().decode("utf-8", errors="replace")
    except OSError as exc:
        print(f"{path}: skipped ({exc.strerror})", file=sys.stderr)
        return []
    return check_text(text, str(path))


def main(argv: Sequence[str] | None, check_text: CheckText, description: str) -> int:
    """Run ``check_text`` on each file named in ``argv`` and print every message.

    ``argv`` of ``None`` means ``sys.argv[1:]``. Returns 1 when any message was
    printed and 0 otherwise.
    """
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("filenames", nargs="*", help="files to scan")
    args = parser.parse_args(argv)

    messages = [
        message for name in args.filenames for message in check_file(Path(name), check_text)
    ]
    for message in messages:
        print(message)
    return 1 if messages else 0
