"""Command line of the snapshot extractor (ADR 0006 sections 1, 2 and 4)."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from snapshot_extractor import ExtractError, git, neuralspotx, reading, references, sdk, zephyr
from snapshot_extractor import snapshot as snapshots
from snapshot_extractor.git import Checkout

REPO_ROOT = Path(__file__).resolve().parents[2]
_DESCRIPTION = """\
Regenerate or check snapshots/*.json from nsx-ambiq-sdk, neuralspotx and Zephyr
with hal_ambiq. The pins are the SDK tag of each Soc and the Zephyr revision the
committed snapshots record; the hal_ambiq commit follows from Zephyr. neuralspotx
is a consumer, so its snapshot stays at its recorded revision (#18).
"""


def _default_cache() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "helia-platforms" / "upstream"


def _load(directory: Path) -> dict[str, dict[str, Any] | None]:
    loaded: dict[str, dict[str, Any] | None] = {}
    for name, file in snapshots.FILES.items():
        path = directory / file
        loaded[name] = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
    return loaded


def _recorded(docs: dict[str, dict[str, Any] | None]) -> dict[tuple[str, str], str]:
    """(repository, revision) to commit, over every committed snapshot's sources."""
    recorded: dict[tuple[str, str], str] = {}
    for doc in docs.values():
        for source in (doc or {}).get("metadata", {}).get("sources", []):
            recorded[(source["repository"], source["revision"])] = source["commit"]
    return recorded


def _pin(doc: dict[str, Any] | None, repository: str) -> str | None:
    for source in (doc or {}).get("metadata", {}).get("sources", []):
        if source["repository"] == repository:
            return source["revision"]
    return None


def _version_key(revision: str) -> list[Any]:
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", revision)]


class _Sources:
    """Fetch each (repository, revision) once, at the recorded or the resolved commit."""

    def __init__(self, cache: Path, recorded: dict[tuple[str, str], str], at: str) -> None:
        self.cache = cache
        self.recorded = recorded
        self.at = at
        self.moved: list[str] = []

    def commit(self, repository: str, revision: str) -> str:
        key = (repository, revision)
        if self.at == "commit" and key in self.recorded:
            return self.recorded[key]
        commit = git.resolve(repository, revision)
        if key in self.recorded and self.recorded[key] != commit:
            self.moved.append(
                f"{repository} {revision} resolves to {commit}; "
                f"the snapshots record {self.recorded[key]}"
            )
        return commit

    def checkout(self, repository: str, revision: str, paths: Sequence[str]) -> Checkout:
        commit = self.commit(repository, revision)
        return git.checkout(self.cache, repository, revision, commit, paths)


def extract_all(
    sources: _Sources, nsx_revision: str, sdk_pins: dict[str, str], zephyr_revision: str
) -> dict[str, Any]:
    """The three snapshot documents, keyed as ``snapshot.FILES``; ``sdk_pins`` maps Soc to tag."""
    nsx = sources.checkout(neuralspotx.REPOSITORY, nsx_revision, neuralspotx.PATHS)
    with reading(f"{neuralspotx.REPOSITORY}@{nsx_revision}"):
        nsx_body = neuralspotx.extract(nsx)
    by_revision: dict[str, list[str]] = {}
    for soc, revision in sdk_pins.items():
        by_revision.setdefault(revision, []).append(soc)
    socs: dict[str, Any] = {}
    sdk_sources: list[dict[str, str]] = []
    for revision in sorted(by_revision, key=_version_key):
        checkout = sources.checkout(sdk.REPOSITORY, revision, sdk.paths(by_revision[revision]))
        sdk_sources.append(checkout.source())
        for soc in sorted(by_revision[revision]):
            with reading(f"{sdk.REPOSITORY}@{revision} {soc}"):
                socs[soc] = sdk.extract_soc(checkout, soc)
    zep = sources.checkout(zephyr.REPOSITORY, zephyr_revision, zephyr.PATHS)
    hal = sources.checkout(zephyr.HAL_REPOSITORY, zephyr.hal_revision(zep), zephyr.HAL_PATHS)
    with reading(f"{zephyr.REPOSITORY}@{zephyr_revision}"):
        zephyr_body = zephyr.extract(zep, hal)
    return {
        "nsx-ambiq-sdk": snapshots.document({"socs": socs}, sdk_sources),
        "neuralspotx": snapshots.document(nsx_body, [nsx.source()]),
        "zephyr": snapshots.document(zephyr_body, [zep.source(), hal.source()]),
    }


def _sdk_pins(committed: dict[str, Any] | None, sdk_revision: str | None) -> dict[str, str]:
    """Each Soc's SDK tag: ``--sdk`` for every Soc the extractor knows, else the recorded tags."""
    if sdk_revision is not None:
        return dict.fromkeys(sorted(sdk.HEADERS), sdk_revision)
    return {soc: block["revision"] for soc, block in (committed or {}).get("socs", {}).items()}


def _extract(args: argparse.Namespace) -> int:
    committed = _load(args.snapshots)
    nsx_revision = _pin(committed["neuralspotx"], neuralspotx.REPOSITORY)
    sdk_pins = _sdk_pins(committed["nsx-ambiq-sdk"], args.sdk)
    zephyr_revision = args.zephyr or _pin(committed["zephyr"], zephyr.REPOSITORY)
    if nsx_revision is None or not sdk_pins or zephyr_revision is None:
        print("no committed snapshots: pass --sdk and --zephyr", file=sys.stderr)
        return 2
    sources = _Sources(args.cache, _recorded(committed), args.at)
    regenerated = extract_all(sources, nsx_revision, sdk_pins, zephyr_revision)
    status = 0
    for message in sources.moved:
        print(f"moved: {message}")
        status = 1
    output: Path = args.output or args.snapshots
    for name, file in snapshots.FILES.items():
        data = snapshots.dumps(regenerated[name])
        changes = snapshots.summary(committed[name], regenerated[name])
        if args.check:
            path = args.snapshots / file
            if not path.is_file() or path.read_bytes() != data:
                status = 1
                print(f"{file}: differs from the regenerated output")
                for line in changes or ["  (same values; the file is not in normalised form)"]:
                    print(f"  {line}")
            continue
        output.mkdir(parents=True, exist_ok=True)
        (output / file).write_bytes(data)
        print(f"{file}: {len(changes)} values changed")
        for line in changes:
            print(f"  {line}")
    return status


def _references(args: argparse.Namespace) -> int:
    recorded = _recorded(_load(args.snapshots))
    found = references.find(args.data) if args.data.is_dir() else []

    def open_source(repository: str, revision: str) -> Checkout | None:
        commit = recorded.get((repository, revision))
        return None if commit is None else git.fetch(args.cache, repository, revision, commit)

    problems = references.check(found, open_source)
    for problem in problems:
        print(problem)
    print(f"{len(found)} symbol references checked, {len(problems)} problems")
    return 1 if problems else 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line; return the process exit status."""
    parser = argparse.ArgumentParser(description=_DESCRIPTION)
    parser.add_argument("--snapshots", type=Path, default=REPO_ROOT / "snapshots")
    parser.add_argument(
        "--cache", type=Path, default=_default_cache(), help="where upstream commits are fetched"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    extract = commands.add_parser("extract", help="regenerate the snapshots")
    extract.add_argument(
        "--check", action="store_true", help="compare with the committed files, write nothing"
    )
    extract.add_argument(
        "--at",
        choices=("commit", "revision"),
        default="commit",
        help="fetch each recorded revision at its recorded commit, or resolve it again",
    )
    extract.add_argument("--sdk", help="nsx-ambiq-sdk tag for every Soc (a refresh's new pin)")
    extract.add_argument("--zephyr", help="Zephyr revision (a refresh's new pin, a full SHA)")
    extract.add_argument("--output", type=Path, help="write here instead of --snapshots")
    refs = commands.add_parser("references", help="check #<symbol> references in the data")
    refs.add_argument("--data", type=Path, default=REPO_ROOT / "src" / "helia_platforms" / "data")
    args = parser.parse_args(argv)
    try:
        return _extract(args) if args.command == "extract" else _references(args)
    except ExtractError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
