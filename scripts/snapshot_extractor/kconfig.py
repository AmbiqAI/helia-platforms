"""Find a Kconfig symbol's default for one SoC in Zephyr's ``Kconfig.defconfig`` files.

Only ``default`` lines are read. A condition is a ``&&`` of symbols, each
optionally negated: the SoC's family, series and SoC symbols are set and every
other symbol, ``BOOTLOADER_MCUBOOT`` included, is unset (a build without MCUboot).
"""

from __future__ import annotations

import re
from pathlib import Path

from snapshot_extractor import ExtractError, cexpr

_STATEMENT = re.compile(r"(\w+)\s*(.*)")
_TERM = re.compile(r"(!?)\s*([A-Z0-9_]+)")
_DEFAULT = re.compile(r"(.+?)(?:\s+if\s+(.+))?")


def _truth(expression: str, enabled: frozenset[str]) -> bool | None:
    """Evaluate a ``&&`` of plain or negated symbols; ``None`` for anything else."""
    result = True
    for term in expression.split("&&"):
        match = _TERM.fullmatch(term.strip())
        if match is None:
            return None
        result = result and ((match.group(2) in enabled) != bool(match.group(1)))
    return result


def _strip_comment(line: str) -> str:
    in_quote = False
    for index, char in enumerate(line):
        if char == '"':
            in_quote = not in_quote
        elif char == "#" and not in_quote:
            return line[:index]
    return line


def soc_default(
    root: Path, entry: str, symbol: str, enabled: frozenset[str]
) -> tuple[str, int] | None:
    """The first default of ``symbol`` that applies, as (repo-relative path, value).

    Reading starts at ``entry`` and follows ``rsource``. A default of ``symbol``
    under a condition this module cannot evaluate raises ``ExtractError``.
    """
    for path, conditions, value in _defaults(root, root / entry, symbol, []):
        truths = [_truth(condition, enabled) for condition in conditions]
        if None in truths:
            raise ExtractError(f"{path}: cannot evaluate the conditions {conditions}")
        if all(truths):
            return path, cexpr.evaluate(value)
    return None


def _defaults(  # noqa: PLR0912 (one branch per Kconfig keyword)
    root: Path, path: Path, symbol: str, outer: list[str]
) -> list[tuple[str, list[str], str]]:
    """Every default of ``symbol`` with the conditions around it, in source order."""
    found: list[tuple[str, list[str], str]] = []
    conditions = list(outer)
    depth_at_entry = len(conditions)
    current: str | None = None
    help_indent: int | None = None
    relative = path.relative_to(root).as_posix()
    for raw in path.read_text(encoding="utf-8").splitlines():
        indent = len(raw) - len(raw.lstrip())
        if help_indent is not None:
            if not raw.strip() or indent > help_indent:
                continue
            help_indent = None
        line = _strip_comment(raw).strip()
        statement = _STATEMENT.match(line)
        if statement is None:
            continue
        keyword, rest = statement.groups()
        if keyword == "if":
            conditions.append(rest)
        elif keyword == "endif":
            if len(conditions) <= depth_at_entry:
                raise ExtractError(f"{relative}: endif without if")
            conditions.pop()
        elif keyword in ("config", "menuconfig", "configdefault"):
            current = rest
        elif keyword in ("choice", "endchoice", "menu", "endmenu", "comment"):
            current = None
        elif keyword == "help":
            help_indent = indent
        elif keyword in ("rsource", "orsource"):
            pattern = rest.strip().strip('"')
            for included in sorted(path.parent.glob(pattern)):
                found.extend(_defaults(root, included, symbol, conditions))
        elif keyword in ("source", "osource"):
            raise ExtractError(f"{relative}: {keyword} is outside the Kconfig reader's scope")
        elif keyword == "default" and current == symbol:
            match = _DEFAULT.fullmatch(rest)
            if match is None:
                raise ExtractError(f"{relative}: cannot read default {rest!r}")
            value, condition = match.groups()
            found.append((relative, conditions + ([condition] if condition else []), value))
    if len(conditions) != depth_at_entry:
        raise ExtractError(f"{relative}: unterminated if")
    return found
