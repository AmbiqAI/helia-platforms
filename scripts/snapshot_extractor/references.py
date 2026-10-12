"""Check that each ``#<symbol>`` reference into a snapshotted repository names one definition.

ADR 0003 section 2 lets a ``repo:`` reference end in ``#<symbol>``, the single
CMake ``set``, C ``#define`` or enumerator of that name in the file. ADR 0006
section 1 has the extract jobs check it, since only they hold the source trees.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from snapshot_extractor import ExtractError, cdefines, cmake
from snapshot_extractor.git import Checkout

SNAPSHOTTED = frozenset(
    {
        "AmbiqAI/nsx-ambiq-sdk",
        "AmbiqAI/neuralspotx",
        "zephyrproject-rtos/hal_ambiq",
        "zephyrproject-rtos/zephyr",
    }
)
_REFERENCE = re.compile(
    r"repo:(?P<repository>[^@\s]+)@(?P<revision>[^:\s]+):(?P<path>[^:#\s]+)"
    r"(?::\d+(?:-\d+)?)?(?:#(?P<symbol>\S+))?"
)
_ENUM = re.compile(r"\benum\b[^{;]*\{([^}]*)\}")
_ENUMERATOR = re.compile(r"\s*([A-Za-z_]\w*)")


@dataclass(frozen=True)
class Reference:
    """One ``repo:...#<symbol>`` reference and the data file that holds it."""

    repository: str
    revision: str
    path: str
    symbol: str
    origin: str


def _strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _strings(key)
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def find(data_dir: Path) -> list[Reference]:
    """Every symbol reference into a snapshotted repository in the YAML under ``data_dir``."""
    found: list[Reference] = []
    files = sorted([*data_dir.rglob("*.yaml"), *data_dir.rglob("*.yml")])
    for file in files:
        for text in _strings(yaml.safe_load(file.read_text(encoding="utf-8"))):
            match = _REFERENCE.fullmatch(text)
            if match and match["symbol"] and match["repository"] in SNAPSHOTTED:
                found.append(
                    Reference(
                        match["repository"],
                        match["revision"],
                        match["path"],
                        match["symbol"],
                        file.as_posix(),
                    )
                )
    return found


def count_definitions(text: str, path: str, symbol: str) -> int:
    """How many CMake ``set``, C ``#define`` or enumerator definitions ``symbol`` has."""
    name = PurePosixPath(path).name
    if name.endswith(".cmake") or name == "CMakeLists.txt":
        return sum(
            1
            for command in cmake.commands(text)
            if command.name == "set" and command.args[:1] == (symbol,)
        )
    stripped = cdefines.strip_comments(text)
    defines = len(re.findall(rf"^\s*#\s*define\s+{re.escape(symbol)}\b", stripped, re.MULTILINE))
    enumerators = sum(
        1
        for body in _ENUM.findall(stripped)
        for item in body.split(",")
        if (match := _ENUMERATOR.match(item)) and match.group(1) == symbol
    )
    return defines + enumerators


def check(refs: list[Reference], open_source: Callable[[str, str], Checkout | None]) -> list[str]:
    """One message per reference that does not name exactly one definition.

    ``open_source`` returns the checkout of a (repository, revision) the
    snapshots hold, or ``None`` when they hold no such revision.
    """
    problems: list[str] = []
    for ref in refs:
        cited = f"repo:{ref.repository}@{ref.revision}:{ref.path}#{ref.symbol}"
        source = open_source(ref.repository, ref.revision)
        if source is None:
            problems.append(f"{ref.origin}: {cited}: the snapshots hold no such revision")
            continue
        text = source.blob(ref.path)
        if text is None:
            problems.append(f"{ref.origin}: {cited}: no such file at {source.commit}")
            continue
        try:
            count = count_definitions(text, ref.path, ref.symbol)
        except ExtractError as exc:
            problems.append(f"{ref.origin}: {cited}: {exc}")
            continue
        if count != 1:
            problems.append(f"{ref.origin}: {cited}: {count} definitions, expected one")
    return problems
