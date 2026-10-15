#!/usr/bin/env python3
"""Check a pull request's fact changes against ADR 0003 section 4.

The built-in data is read from git at the merge base and at the head, loaded with
this checkout's loader and compared by fact path. A changed value needs a changed
record, and a changed ``fact:`` input needs a changed record on each ``derived``
value that names it. A new fact path is exempt.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from helia_platforms import _format as fmt
from helia_platforms import _parse, _provenance
from helia_platforms._tree import Path as FactPath
from helia_platforms._tree import iter_values
from helia_platforms.catalog import _KINDS, Catalog, _load_documents
from helia_platforms.errors import FormatError

DATA = "src/helia_platforms/data"
FactKey = tuple[str, str, FactPath]  # (table, entry id, path)
RULE = "change its status, source or verified_on, or give the value a record of its own"


def facts(catalog: Catalog) -> dict[FactKey, tuple[Any, Any]]:
    """Each value of each entry, keyed by fact path, with the record it resolves to."""
    found: dict[FactKey, tuple[Any, Any]] = {}
    for (table, entry_id), tree in catalog._trees.items():
        pairs = iter_values(tree.values, getattr(fmt, _KINDS[table].__name__))
        inner = {p[:i] for p, _ in pairs for i in range(len(p))}
        for path, value in pairs:
            if path not in inner:
                found[(table, entry_id, path)] = (value, tree.records.get(path))
    return found


def record_changed(old: Any, new: Any) -> bool:
    """Whether ``new`` differs from ``old`` in a way that counts (ADR 0003 section 4)."""
    old, new = old or {}, new or {}
    if old.get("status") != new.get("status") or old.get("verified_on") != new.get("verified_on"):
        return True
    if {str(s) for s in old.get("source") or []} != {str(s) for s in new.get("source") or []}:
        return True
    both_unverified = old.get("status") == new.get("status") == "unverified"
    return both_unverified and old.get("notes") != new.get("notes")


def problems(base: Catalog, head: Catalog) -> list[str]:
    """Each changed value whose record did not change, then each stale derived record."""
    old, new = facts(base), facts(head)
    found: dict[FactKey, str] = {}
    for key, (value, record) in new.items():
        if key in old and old[key][0] != value and not record_changed(old[key][1], record):
            was = old[key][0]
            found[key] = f"{_where(key)}: changed from {was!r} to {value!r}; {RULE}"
    lookup = _provenance.Facts(head._trees, lambda _: True)
    for key, (_, record) in new.items():
        if key in found or key not in old or not isinstance(record, dict):
            continue
        if record.get("status") != "derived" or record_changed(old[key][1], record):
            continue
        for reference in record.get("source") or []:
            named = lookup.parse(str(reference))
            if named is not None and _values_under(old, named) != _values_under(new, named):
                found[key] = f"{_where(key)}: its derived input {reference} changed; {RULE}"
                break
    return list(found.values())


def _values_under(found: dict[FactKey, tuple[Any, Any]], named: FactKey) -> dict[FactPath, Any]:
    table, entry_id, prefix = named
    return {
        path: value
        for (t, i, path), (value, _) in found.items()
        if (t, i) == (table, entry_id) and _provenance.under(path, prefix)
    }


def _where(key: FactKey) -> str:
    table, entry_id, path = key
    return ".".join((table, entry_id, *path))


def load_at(revision: str, repo: Path) -> Catalog:
    """The built-in catalog as the data files at ``revision`` declare it."""
    names = _git(repo, "ls-tree", "-r", "--name-only", revision, "--", DATA).splitlines()
    documents = []
    for name in sorted(n for n in names if n.endswith(".yaml")):
        origin = "helia_platforms/data/" + name.removeprefix(f"{DATA}/")
        text = _git(repo, "show", f"{revision}:{name}")
        documents.append((_parse.parse_yaml(text, origin), origin))
    return _load_documents(documents, builtin=True)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check fact changes against ADR 0003 section 4.")
    parser.add_argument("--base", required=True, help="the target branch; its merge base is used")
    parser.add_argument("--head", default="HEAD", help="the pull request's head (default HEAD)")
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="the git checkout")
    args = parser.parse_args(argv)
    merge_base = _git(args.repo, "merge-base", args.base, args.head).strip()
    catalogs = []
    for label, revision in (("merge base", merge_base), ("head", args.head)):
        try:
            catalogs.append(load_at(revision, args.repo))
        except FormatError as exc:
            print(f"the built-in data at the {label} ({revision}) does not load:", file=sys.stderr)
            print(*(f"  {p}" for p in exc.problems), sep="\n", file=sys.stderr)
            return 2
    found = problems(*catalogs)
    if found:
        print(*found, sep="\n")
        return 1
    print(f"no unrecorded fact changes since {merge_base}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
