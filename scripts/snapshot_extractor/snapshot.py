"""Serialise snapshots and summarise the values that changed between two of them."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from snapshot_extractor import EXTRACTOR_VERSION

FILES = {
    "nsx-ambiq-sdk": "nsx-ambiq-sdk.json",
    "neuralspotx": "neuralspotx.json",
    "zephyr": "zephyr.json",
}


def document(body: dict[str, Any], sources: list[dict[str, str]]) -> dict[str, Any]:
    """``body`` with the metadata ADR 0006 section 2 specifies."""
    return {"metadata": {"extractor_version": EXTRACTOR_VERSION, "sources": sources}, **body}


def dumps(snapshot: dict[str, Any]) -> bytes:
    """The normalised bytes: sorted keys, two-space indent, ASCII, final newline."""
    text = json.dumps(snapshot, sort_keys=True, indent=2, ensure_ascii=True)
    return (text + "\n").encode("ascii")


def _leaves(value: Any, path: tuple[str, ...] = ()) -> Iterator[tuple[tuple[str, ...], Any]]:
    if isinstance(value, dict) and value:
        for key in sorted(value):
            yield from _leaves(value[key], (*path, str(key)))
    else:
        yield path, value


def _show(value: Any) -> str:
    """Integers in hex, as the extractor's summary prints addresses; JSON otherwise."""
    if isinstance(value, int) and not isinstance(value, bool):
        return hex(value)
    return json.dumps(value, sort_keys=True)


def summary(old: dict[str, Any] | None, new: dict[str, Any]) -> list[str]:
    """One line per added, removed or changed value, keys joined with ``" > "``."""
    before = dict(_leaves(old or {}))
    after = dict(_leaves(new))
    lines: list[str] = []
    for path in sorted(before.keys() | after.keys()):
        where = " > ".join(path)
        if path not in after:
            lines.append(f"- {where}: {_show(before[path])}")
        elif path not in before:
            lines.append(f"+ {where}: {_show(after[path])}")
        elif before[path] != after[path]:
            lines.append(f"~ {where}: {_show(before[path])} -> {_show(after[path])}")
    return lines
