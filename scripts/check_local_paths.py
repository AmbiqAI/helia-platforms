#!/usr/bin/env python3
"""Reject local filesystem paths in committed text files.

The repository is meant to be public, so CONTRIBUTING.md asks contributors
to cite repositories by name and revision. Paths inside remote URLs (http,
https, ssh, ...) are exempt, and ``local-paths: ignore`` skips a line.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import NamedTuple

IGNORE_DIRECTIVE = "local-paths: ignore"

# A user name starts and ends with a word character or U+FFFD (an undecodable
# byte), so placeholders such as <name>, {user} or $USER never match.
_NAME = r"[\w\ufffd](?:[\w\ufffd.-]*[\w\ufffd])?"
_SEPARATOR = r"(?:\\\\|[\\/])"  # "/", "\" or a JSON-escaped "\\"

LOCAL_PATH_FORMS: tuple[tuple[str, str], ...] = (
    ("macos_home", rf"(?:/System/Volumes/Data)?/Users/{_NAME}/?"),
    ("linux_home", rf"(?:/var|/usr|/export)?/home/{_NAME}/?"),
    ("windows_home", rf"(?<![A-Za-z0-9])[A-Za-z]:{_SEPARATOR}(?i:users){_SEPARATOR}"),
    ("windows_shell_home", r"(?:/mnt|/cygdrive)?/[A-Za-z]/(?i:users)/"),
    ("macos_private_tmp", r"/private/tmp/"),  # local-paths: ignore
    ("macos_var_folders", r"/var/folders/"),  # local-paths: ignore
    ("cloud_storage", r"Library/CloudStorage/"),  # local-paths: ignore
    ("icloud_drive", r"com~apple~CloudDocs"),  # local-paths: ignore
    ("onedrive_hyphen", r"OneDrive-[^\s/\\:]{1,64}[/\\]"),  # local-paths: ignore
    ("onedrive_spaced", r"OneDrive - [^/\\:\n]{1,64}[/\\]"),  # local-paths: ignore
)
LOCAL_PATH_RE = re.compile("|".join(f"(?P<{name}>{regex})" for name, regex in LOCAL_PATH_FORMS))

# These forms must not follow a word character, "." or "-" (so api/Users/x is
# not a home); the check is in code because non-remote URLs waive it.
BOUNDED_FORMS = frozenset({"macos_home", "linux_home", "windows_shell_home"})
_BOUNDARY_CHAR_RE = re.compile(r"[\w.-]")

HINT = "Cite repositories by name and revision instead (see CONTRIBUTING.md)."

_URL_RE = re.compile(r"""(?<![A-Za-z0-9+.-])([A-Za-z][A-Za-z0-9+.-]*)://[^\s"'()<>\[\]{}|,`]*""")
_REMOTE_SCHEMES = frozenset({"http", "https", "ftp", "sftp", "ssh", "git", "s3"})


class _Url(NamedTuple):
    """Span of one URL in a line, and whether its scheme names a remote host."""

    start: int
    end: int
    is_remote: bool


def _find_urls(line: str) -> list[_Url]:
    """Find the URLs in one line.

    A scheme starts at the beginning of a run of scheme characters, so
    ``myhttps://`` is the scheme ``myhttps``, not ``https``. The remote schemes
    may also carry a ``git+`` prefix.

    Args:
        line: Line to scan.

    Returns:
        One span per URL, in line order.
    """
    return [
        _Url(
            match.start(),
            match.end(),
            match.group(1).lower().removeprefix("git+") in _REMOTE_SCHEMES,
        )
        for match in _URL_RE.finditer(line)
    ]


def _find_local_paths(line: str) -> list[str]:
    """Find the local paths in one line, leftmost first and never overlapping.

    A match lying entirely inside a remote URL is exempt.

    Args:
        line: Line to scan, without its line terminator.

    Returns:
        The matched text of each finding, in line order.
    """
    urls = _find_urls(line)
    url_index = 0
    findings: list[str] = []
    position = 0
    while match := LOCAL_PATH_RE.search(line, position):
        start, end = match.span()
        while url_index < len(urls) and urls[url_index].end <= start:
            url_index += 1
        in_url = url_index < len(urls) and urls[url_index].start <= start
        url = urls[url_index] if in_url else None
        if url is not None and url.is_remote and end <= url.end:
            position = end
            continue
        if (
            match.lastgroup in BOUNDED_FORMS
            and (url is None or url.is_remote)
            and start > 0
            and _BOUNDARY_CHAR_RE.match(line[start - 1])
        ):
            # No two forms can match at the same start, so skip just this one.
            position = start + 1
            continue
        findings.append(match.group())
        position = end
    return findings


def check_text(text: str, path: str) -> list[str]:
    """Scan text for local filesystem paths.

    Lines split on ``\\n`` only, and a trailing ``\\r`` is ignored.

    Args:
        text: File contents to scan.
        path: Path used in the returned messages.

    Returns:
        One message per local path, in line order; empty when the text is clean.
    """
    messages: list[str] = []
    for lineno, raw_line in enumerate(text.split("\n"), start=1):
        line = raw_line.removesuffix("\r")
        if IGNORE_DIRECTIVE in line:
            continue
        messages.extend(
            f"{path}:{lineno}: local filesystem path '{found}'. {HINT}"
            for found in _find_local_paths(line)
        )
    return messages


def check_file(path: Path) -> list[str]:
    """Scan one file, or a symlink's target string, reporting unreadable files.

    A symlink is never followed. Text that is not valid UTF-8 is still
    scanned, with each undecodable byte read as U+FFFD.

    Args:
        path: File or symlink to scan.

    Returns:
        One message per local path; empty for clean or unreadable files.
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


def main(argv: Sequence[str] | None = None) -> int:
    """Scan the given files and report local filesystem paths.

    Args:
        argv: Command-line arguments; defaults to ``sys.argv[1:]``.

    Returns:
        1 when any local path was found, 0 otherwise.
    """
    parser = argparse.ArgumentParser(description="Reject local filesystem paths.")
    parser.add_argument("filenames", nargs="*", help="files to scan")
    args = parser.parse_args(argv)

    messages = [message for name in args.filenames for message in check_file(Path(name))]
    for message in messages:
        print(message)
    return 1 if messages else 0


if __name__ == "__main__":
    sys.exit(main())
