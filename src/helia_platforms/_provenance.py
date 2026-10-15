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

from helia_platforms._tree import Address, Path, Tree

# Keys, revisions and repository names use the register's own grammar (_format).
_KEY = r"[A-Za-z][A-Za-z0-9_-]{0,63}"
_REV = r"[0-9A-Za-z][0-9A-Za-z._-]*"
_DOC = re.compile(
    rf"^doc:(?P<key>{_KEY})@(?P<rev>{_REV}):p(?P<lo>[1-9][0-9]*)(?:-(?P<hi>[1-9][0-9]*))?$"
)
_REPO = re.compile(
    rf"^repo:(?P<repo>[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)?)@(?P<rev>{_REV}):(?P<path>[^:#/\s][^:#\s]*)"
    r"(?::(?P<lo>[1-9][0-9]*)(?:-(?P<hi>[1-9][0-9]*))?)?(?:#(?P<symbol>[A-Za-z_][A-Za-z0-9_]*))?$"
)
_MEAS = re.compile(
    r"^meas:(?P<target>[^/]+)/(?P<method>[a-z0-9]+(?:-[a-z0-9]+)*)/(?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2})$"
)
_FACT = re.compile(r"^fact:(?P<kind>[a-z_]+):(?P<id>[^:]+):(?P<path>[^:]+)$")
_SHA = re.compile(r"^[0-9a-f]{40}$")
_SHORT_SHA = re.compile(r"^[0-9a-f]{7,39}$")
# GitHub: up to 39 characters, alphanumerics and single inner hyphens.
_LOGIN = re.compile(
    r"^(@[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*/[A-Za-z0-9_.-]+"
    r"|(?=[A-Za-z0-9-]{1,39}$)[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*)$"
)
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
    """Fact lookups over the catalog's trees; a reference may spell an address in any base."""

    trees: Mapping[tuple[str, str], Tree]
    resolvable: Callable[[str], bool]

    def parse(self, reference: str) -> FactKey | None:
        match = _FACT.match(reference)
        if match is None or match["kind"] not in TABLE_OF:
            return None
        return TABLE_OF[match["kind"]], match["id"], tuple(match["path"].split("."))

    def exists(self, key: FactKey) -> bool:
        table, entry_id, path = key
        tree = self.trees.get((table, entry_id))
        return tree is not None and any(under(p, path) for p in tree.records)

    def leaves(self, table: str, entry_id: str, prefix: Path = ()) -> list[tuple[Path, Any]]:
        """Each value (a path no other path extends) under ``prefix``, with its record."""
        tree = self.trees.get((table, entry_id))
        return [] if tree is None else leaves(tree, prefix)

    def unverified_inputs(self, record: Any) -> list[str]:
        """The ``fact:`` inputs of a derived record that reach an unverified value."""
        if _status(record) != "derived":
            return []
        found = []
        for reference in record.get("source") or []:
            key = self.parse(str(reference))
            if key and any(_status(r) == "unverified" for _, r in self.leaves(*key)):
                found.append(str(reference))
        return found


def leaves(tree: Tree, prefix: Path = ()) -> list[tuple[Path, Any]]:
    """Each value in ``tree`` (a path no other path extends) under ``prefix``, with its record."""
    inner = {p[:i] for p in tree.records for i in range(len(p))}
    return [(p, r) for p, r in tree.records.items() if p not in inner and under(p, prefix)]


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
        url = reference[len("url:") :]
        try:
            parts = urlsplit(url)
            hostname = parts.hostname
        except ValueError:
            hostname = None
        if (
            hostname is None
            or parts.scheme != "https"
            or "@" in parts.netloc
            or not parts.path
            or any(c.isspace() or not c.isprintable() for c in url)
        ):
            return [f"{at} is not url:https://<host>/<path> without credentials or spaces"]
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
        elif not any(
            _status(r) == "unverified" or facts.unverified_inputs(r) for _, r in facts.leaves(*key)
        ):
            problems.append((where, f"{entry['fact']} is no longer unverified; remove the entry"))
        else:
            allowed.append(key)

    def is_allowed(table: str, entry_id: str, path: Path) -> bool:
        return any((t, i) == (table, entry_id) and under(path, p) for t, i, p in allowed)

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
            if not is_allowed(table, entry_id, path):
                problems += [
                    (_where(table, entry_id, path), f"derived from unverified {reference}")
                    for reference in facts.unverified_inputs(record)
                ]
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
            owners.setdefault(id(record), (table, entry_id, path))
            records[id(record)] = record
    for rid, record in records.items():
        if _status(record) != "derived":
            continue
        # A reference to a group reaches every value under it.
        for reference in record.get("source") or []:
            key = facts.parse(str(reference))
            for _, target in facts.leaves(*key) if key else ():
                if _status(target) == "derived":
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


#: ADR 0003 section 1's report order, worst first. ``derived`` ranks as its worst input.
RANKS = ("unverified", "fitted", "sdk", "measured", "datasheet")
_RANK_OF_KIND = {"doc": "datasheet", "meas": "measured", "repo": "sdk", "url": "sdk"}


def rank(record: Any, facts: Facts, seen: frozenset[int] = frozenset()) -> str:
    """The report rank of a record; a ``fact:`` input that is missing or cyclic is unverified."""
    status = _status(record)
    if status != "derived":
        return status if status in RANKS else "unverified"
    if id(record) in seen:
        return "unverified"
    ranks = []
    for reference in record.get("source") or []:
        kind = str(reference).split(":", 1)[0]
        if kind != "fact":
            ranks.append(_RANK_OF_KIND.get(kind, "unverified"))
            continue
        key = facts.parse(str(reference))
        inputs = facts.leaves(*key) if key else []
        ranks += [rank(r, facts, seen | {id(record)}) for _, r in inputs] or ["unverified"]
    return worst(ranks)


def worst(ranks: Iterable[str]) -> str:
    """The worst of ``ranks`` in ``RANKS`` order; none at all is unverified."""
    return min(ranks, key=RANKS.index, default="unverified")


def _status(record: Any) -> str | None:
    return record.get("status") if isinstance(record, Mapping) else None


def under(path: Path, prefix: Path) -> bool:
    """Whether ``path`` starts with ``prefix``; only an address segment matches in any base."""
    return len(path) >= len(prefix) and all(
        a == b or (isinstance(a, Address) and _integer(b) == int(a, 16))
        for a, b in zip(path, prefix, strict=False)
    )


def _integer(text: str) -> int | None:
    try:
        return int(text, 0)
    except ValueError:
        return None


def _where(table: str, entry_id: str, path: Path) -> str:
    return ".".join((table, entry_id, *path))
