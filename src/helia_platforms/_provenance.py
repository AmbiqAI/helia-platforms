"""ADR 0003's provenance validator: record rules, reference spellings, the register and the gate.

Built-in entries get every check, as errors. Other sources cannot extend the register
and may cite private documents, so their references are checked for form only.
"""

from __future__ import annotations

import datetime
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from helia_platforms._tree import Path, Tree

_DOC = re.compile(
    r"^doc:(?P<key>[^@:]+)@(?P<rev>[^:]+):p(?P<lo>[1-9][0-9]*)(?:-(?P<hi>[1-9][0-9]*))?$"
)
_REPO = re.compile(
    r"^repo:(?P<repo>[^@]+)@(?P<rev>[^:]+):(?P<path>[^:#/][^:#]*)"
    r"(?::(?P<lo>[1-9][0-9]*)(?:-(?P<hi>[1-9][0-9]*))?)?(?:#(?P<symbol>[A-Za-z_][A-Za-z0-9_]*))?$"
)
_MEAS = re.compile(
    r"^meas:(?P<target>[^/]+)/(?P<method>[a-z0-9]+(?:-[a-z0-9]+)*)/(?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2})$"
)
_FACT = re.compile(r"^fact:(?P<kind>[a-z_]+):(?P<id>[^:]+):(?P<path>[^:]+)$")
_SHA = re.compile(r"^[0-9a-f]{40}$")
_SHORT_SHA = re.compile(r"^[0-9a-f]{7,39}$")
_LOGIN = re.compile(r"^(@[A-Za-z0-9-]+/[A-Za-z0-9_.-]+|[A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))$")
#: ``fact:`` entity kinds (ADR 0003 section 2), by the table that holds them.
TABLE_OF = {
    "core": "cores",
    "soc": "socs",
    "implementation": "implementations",
    "part": "parts",
    "board": "boards",
    "addon": "addons",
    "memory_device": "memory_devices",
}
#: The reference kinds each status needs, as alternatives per requirement (section 2).
_NEEDS: dict[str, tuple[frozenset[str], ...]] = {
    "datasheet": (frozenset({"doc"}),),
    "sdk": (frozenset({"repo"}),),
    "measured": (frozenset({"meas"}), frozenset({"repo", "url"})),
    "fitted": (frozenset({"meas"}), frozenset({"repo", "url"}), frozenset({"repo", "doc"})),
    "derived": (frozenset({"doc", "repo", "meas", "url", "fact"}),),
}

FactKey = tuple[str, str, Path]  # (table, entry id, path)


@dataclass(frozen=True)
class Register:
    """The source register and the release allow-list, as the built-in files declare them."""

    documents: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    repositories: Mapping[str, Any] = field(default_factory=dict)
    allowed: tuple[Mapping[str, Any], ...] = ()


@dataclass
class Facts:
    """Fact lookups over the catalog's trees, with addresses compared as integers."""

    trees: Mapping[tuple[str, str], Tree]
    resolvable: Callable[[str], bool]
    _paths: dict[tuple[str, str], set[Path]] = field(default_factory=dict)

    def parse(self, reference: str) -> FactKey | None:
        match = _FACT.match(reference)
        if match is None or match["kind"] not in TABLE_OF:
            return None
        return TABLE_OF[match["kind"]], match["id"], _canonical(match["path"].split("."))

    def exists(self, key: FactKey) -> bool:
        table, entry_id, path = key
        return any(p[: len(path)] == path for p in self.paths(table, entry_id))

    def paths(self, table: str, entry_id: str) -> set[Path]:
        if (table, entry_id) not in self._paths:
            tree = self.trees.get((table, entry_id))
            records = tree.records if tree else {}
            self._paths[(table, entry_id)] = {_canonical(p) for p in records}
        return self._paths[(table, entry_id)]

    def record(self, key: FactKey) -> Any:
        table, entry_id, path = key
        tree = self.trees.get((table, entry_id))
        if tree is None:
            return None
        return next((r for p, r in tree.records.items() if _canonical(p) == path), None)

    def leaves(self, table: str, entry_id: str, under: Path = ()) -> list[tuple[Path, Any]]:
        """Each value (a path no other path extends) under ``under``, with its record."""
        tree = self.trees.get((table, entry_id))
        if tree is None:
            return []
        paths = {_canonical(p): r for p, r in tree.records.items()}
        inner = {p[:i] for p in paths for i in range(len(p))}
        return [(p, r) for p, r in paths.items() if p not in inner and p[: len(under)] == under]


def record_problems(
    record: Mapping[str, Any], register: Register | None, facts: Facts
) -> list[str]:
    """What is wrong with one record. ``register`` is None to check the form only."""
    status = record.get("status")
    sources = list(record.get("source") or [])
    problems: list[str] = []
    if status == "unverified":
        problems += [
            f"an unverified record may not carry {k}"
            for k in ("verified_on", "verified_by")
            if k in record
        ]
    else:
        if not sources:
            problems.append(f"a {status} record needs a source")
        problems += [
            f"a {status} record needs {k}"
            for k in ("verified_on", "verified_by")
            if k not in record
        ]
    if "verified_by" in record and not _LOGIN.match(str(record["verified_by"])):
        problems.append(f"verified_by {record['verified_by']!r} is not a GitHub login or @org/team")
    kinds: set[str] = set()
    for reference in sources:
        kind = str(reference).split(":", 1)[0]
        found = reference_problems(str(reference), record, register, facts)
        problems += found
        if not found:
            kinds.add(kind)
    for alternatives in _NEEDS.get(str(status), ()):
        if not kinds & alternatives and sources:
            needed = " or ".join(f"{k}:" for k in sorted(alternatives))
            problems.append(f"a {status} record needs a {needed} reference")
    return problems


def reference_problems(  # noqa: PLR0911, PLR0912 (one branch per reference kind)
    reference: str, record: Mapping[str, Any], register: Register | None, facts: Facts
) -> list[str]:
    at = f"{reference!r}"
    kind = reference.split(":", 1)[0]
    if kind == "doc":
        match = _DOC.match(reference)
        if match is None:
            return [f"{at} is not doc:<key>@<revision>:p<page>[-<page>]"]
        lo, hi = int(match["lo"]), int(match["hi"] or match["lo"])
        if hi < lo:
            return [f"{at}: the page range runs backwards"]
        if register is None:
            return []
        revision = register.documents.get(match["key"], {}).get(match["rev"])
        if revision is None:
            return [f"{at}: {match['key']}@{match['rev']} is not in the source register"]
        if hi > revision["pages"]:
            return [f"{at}: the document has {revision['pages']} pages"]
        return []
    if kind == "repo":
        match = _REPO.match(reference)
        if match is None:
            return [f"{at} is not repo:<repository>@<revision>:<path>[:<line>[-<line>]][#<symbol>]"]
        if match["hi"] and int(match["hi"]) < int(match["lo"]):
            return [f"{at}: the line range runs backwards"]
        rev = match["rev"]
        if _SHORT_SHA.match(rev) and not _SHA.match(rev):
            return [f"{at}: {rev!r} is an abbreviated SHA; cite the full 40-hex SHA or a tag"]
        if register is None:
            return []
        repository = register.repositories.get(match["repo"])
        if repository is None:
            return [f"{at}: repository {match['repo']!r} is not in the source register"]
        if not _SHA.match(rev) and rev not in (repository.get("tags") or {}):
            return [f"{at}: {rev!r} is neither a full SHA nor a registered tag of {match['repo']}"]
        return []
    if kind == "meas":
        match = _MEAS.match(reference)
        if match is None:
            return [f"{at} is not meas:<target id>/<method slug>/<YYYY-MM-DD>"]
        problems = []
        try:
            day = datetime.date.fromisoformat(match["date"])
        except ValueError:
            return [f"{at}: {match['date']} is not a date"]
        verified = record.get("verified_on")
        if verified is not None and day > datetime.date.fromisoformat(str(verified)):
            problems.append(f"{at}: measured after verified_on {verified}")
        if not facts.resolvable(match["target"]):
            problems.append(f"{at}: target {match['target']!r} does not resolve")
        return problems
    if kind == "url":
        parts = urlsplit(reference[len("url:") :])
        if parts.scheme != "https" or not parts.hostname or "@" in parts.netloc or not parts.path:
            return [f"{at} is not url:https://<host>/<path> without credentials"]
        return []
    if kind == "fact":
        key = facts.parse(reference)
        if key is None:
            return [f"{at} is not fact:<entity kind>:<id>:<field path>"]
        if not facts.exists(key):
            return [f"{at}: no such fact"]
        return []
    return [f"{at}: unknown reference kind; use doc:, repo:, meas:, url: or fact:"]


def gate_problems(
    entries: Iterable[tuple[str, str]], register: Register, facts: Facts
) -> list[tuple[str, str]]:
    """``(where, message)`` for the unverified gate, stale allow-list entries and cycles."""
    entries = list(entries)
    problems: list[tuple[str, str]] = []
    allowed: list[FactKey] = []
    for index, entry in enumerate(register.allowed):
        key = facts.parse(str(entry["fact"]))
        where = f"unverified_allowed[{index}]"
        if key is None or not facts.exists(key):
            problems.append((where, f"{entry['fact']} names no fact"))
        elif not any(_status(r) == "unverified" for _, r in facts.leaves(*key)):
            problems.append((where, f"{entry['fact']} is no longer unverified; remove the entry"))
        else:
            allowed.append(key)

    def is_allowed(table: str, entry_id: str, path: Path) -> bool:
        return any((t, i) == (table, entry_id) and path[: len(p)] == p for t, i, p in allowed)

    for table, entry_id in entries:
        uncovered: dict[int, tuple[Path, int]] = {}
        for path, record in facts.leaves(table, entry_id):
            if _status(record) == "unverified" and not is_allowed(table, entry_id, path):
                first, count = uncovered.get(id(record), (path, 0))
                uncovered[id(record)] = (first, count + 1)
        for path, count in uncovered.values():
            more = f" and {count - 1} other values under the same record" if count > 1 else ""
            problems.append(
                (
                    _where(table, entry_id, path),
                    f"resolves to unverified{more}; add a source or an unverified_allowed entry",
                )
            )
        for path, record in facts.leaves(table, entry_id):
            if _status(record) != "derived" or is_allowed(table, entry_id, path):
                continue
            for reference in record.get("source") or []:
                key = facts.parse(str(reference))
                if key and any(_status(r) == "unverified" for _, r in facts.leaves(*key)):
                    problems.append(
                        (_where(table, entry_id, path), f"derived from unverified {reference}")
                    )
    problems += _cycles(entries, facts)
    return list(dict.fromkeys(problems))


def _cycles(entries: Iterable[tuple[str, str]], facts: Facts) -> list[tuple[str, str]]:
    """A cycle in the graph of ``fact:`` inputs between derived records (ADR 0003 section 4)."""
    owners: dict[int, FactKey] = {}
    edges: dict[int, set[int]] = {}
    records: dict[int, Any] = {}
    for table, entry_id in {(t, i) for t, i in entries}:
        tree = facts.trees[(table, entry_id)]
        for path, record in sorted(tree.records.items(), key=lambda item: len(item[0])):
            owners.setdefault(id(record), (table, entry_id, _canonical(path)))
            records[id(record)] = record
    for rid, record in records.items():
        if _status(record) != "derived":
            continue
        for reference in record.get("source") or []:
            key = facts.parse(str(reference))
            target = facts.record(key) if key else None
            if target is not None and _status(target) == "derived":
                edges.setdefault(rid, set()).add(id(target))
    problems, done, active = [], set(), set()

    def visit(node: int) -> None:
        active.add(node)
        for nxt in edges.get(node, ()):
            if nxt in active:
                table, entry_id, path = owners.get(node, ("?", "?", ()))
                problems.append((_where(table, entry_id, path), "its derived inputs form a cycle"))
            elif nxt not in done:
                visit(nxt)
        active.discard(node)
        done.add(node)

    for node in list(edges):
        if node not in done:
            visit(node)
    return problems


def _status(record: Any) -> str | None:
    return record.get("status") if isinstance(record, Mapping) else None


def _canonical(path: Iterable[str]) -> Path:
    """A path with each integer segment (an address) in one spelling."""
    out = []
    for segment in path:
        try:
            out.append(hex(int(segment, 0)))
        except ValueError:
            out.append(segment)
    return tuple(out)


def _where(table: str, entry_id: str, path: Path) -> str:
    return ".".join((table, entry_id, *path))
