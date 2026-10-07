"""Read GNU ld ``MEMORY`` regions and armlink scatter-file execution regions."""

from __future__ import annotations

import re
from typing import Any

from snapshot_extractor import ExtractError, cdefines, cexpr

_MEMORY = re.compile(r"\bMEMORY\s*\{(.*?)\}", re.DOTALL)
_GNU_REGION = re.compile(
    r"([A-Za-z_.][\w.]*)\s*(?:\(\s*([^)]*?)\s*\))?\s*:\s*"
    r"(?:ORIGIN|org|o)\s*=\s*(.+?)\s*,\s*(?:LENGTH|len|l)\s*=\s*(.+?)\s*,?"
)
_SCATTER_TOKEN = re.compile(r"0[xX][0-9a-fA-F]+|\d+|[A-Za-z_][\w.$]*|[-+{}]|\S")
# Execution-region attributes that take no operand; only EMPTY changes the range.
_SCATTER_ATTRIBUTES = frozenset(
    {"EMPTY", "UNINIT", "ZEROPAD", "ABSOLUTE", "PI", "NOCOMPRESS", "FIXED", "OVERLAY"}
)


def gnu_memory(text: str) -> dict[str, dict[str, Any]]:
    """Each region of the script's one ``MEMORY`` block, commented-out ones excluded."""
    blocks = _MEMORY.findall(cdefines.strip_comments(text))
    if len(blocks) != 1:
        raise ExtractError(f"expected one MEMORY block, found {len(blocks)}")
    regions: dict[str, dict[str, Any]] = {}
    for line in blocks[0].splitlines():
        if not line.strip():
            continue
        match = _GNU_REGION.fullmatch(line.strip())
        if match is None:
            raise ExtractError(f"cannot read MEMORY line {line.strip()!r}")
        name, attributes, origin, length = match.groups()
        if name in regions:
            raise ExtractError(f"region {name} declared twice")
        region: dict[str, Any] = {
            "length": cexpr.evaluate(length, size_suffixes=True),
            "origin": cexpr.evaluate(origin, size_suffixes=True),
        }
        if attributes is not None:
            region["attributes"] = attributes
        regions[name] = region
    return regions


def _strip_scatter_comments(text: str) -> str:
    return cdefines.strip_comments(re.sub(r";[^\n]*", "", text))


def scatter_regions(text: str) -> dict[str, dict[str, Any]]:
    """Each execution region of every load region.

    An ``EMPTY`` region is recorded as the range it occupies, ``base - length``
    to ``base`` for a negative length, with ``empty: true``.
    """
    tokens = _SCATTER_TOKEN.findall(_strip_scatter_comments(text))
    regions: dict[str, dict[str, Any]] = {}
    pos = 0
    while pos < len(tokens):
        _, pos = _region_header(tokens, pos)  # a load region
        while tokens[pos] != "}":
            name, pos = _region_header(tokens, pos, regions)
            depth = 1
            while depth:  # skip the input section selectors
                if pos >= len(tokens):
                    raise ExtractError(f"unterminated execution region {name}")
                depth += {"{": 1, "}": -1}.get(tokens[pos], 0)
                pos += 1
            if pos >= len(tokens):
                raise ExtractError("unterminated load region")
        pos += 1
    return regions


def _region_header(
    tokens: list[str], pos: int, regions: dict[str, dict[str, Any]] | None = None
) -> tuple[str, int]:
    """Read ``name base [attributes] [length] {``; record it in ``regions`` if given."""
    name = tokens[pos]
    try:
        brace = tokens.index("{", pos)
    except ValueError:
        raise ExtractError(f"region {name} has no body") from None
    header = tokens[pos + 1 : brace]
    if not header or not header[0][0].isdigit():
        raise ExtractError(f"region {name} has no absolute base address: {header}")
    base = cexpr.evaluate(header[0])
    attributes: list[str] = []
    length: int | None = None
    rest = header[1:]
    while rest:
        token = rest.pop(0)
        if token in _SCATTER_ATTRIBUTES:
            attributes.append(token)
        elif token in ("-", "+") and rest and rest[0][0].isdigit() and length is None:
            length = cexpr.evaluate(token + rest.pop(0))
        elif token[0].isdigit() and length is None:
            length = cexpr.evaluate(token)
        else:
            raise ExtractError(f"cannot read {token!r} in the header of region {name}")
    if regions is not None:
        if name in regions:
            raise ExtractError(f"execution region {name} declared twice")
        regions[name] = _region(base, attributes, length)
    return name, brace + 1


def _region(base: int, attributes: list[str], length: int | None) -> dict[str, Any]:
    region: dict[str, Any] = {"origin": base}
    if length is not None:
        if length < 0 and "EMPTY" not in attributes:
            raise ExtractError("a negative length is valid only for an EMPTY region")
        region["origin"] = base + min(length, 0)
        region["length"] = abs(length)
    if "EMPTY" in attributes:
        region["empty"] = True
    others = [attribute for attribute in attributes if attribute != "EMPTY"]
    if others:
        region["attributes"] = others
    return region
