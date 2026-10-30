#!/usr/bin/env python3
"""Regenerate or check the link-environment dataset from the committed snapshots.

ADR 0006 section 4, amended for #73: ``snapshots/link-environments.yaml`` says what
becomes an environment, and the catalog says which Socs and boards are public.
``--check`` fails when the committed dataset differs from a fresh run.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from helia_platforms import _parse
from helia_platforms.catalog import Catalog, builtin
from helia_platforms.link_environments import DATASET, DATASET_FORMAT

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOTS = ROOT / "snapshots"
OUTPUT = ROOT / "src" / "helia_platforms" / "data" / DATASET
#: Zephyr's Cortex-M linker script names these regions; every other one is the
#: node's ``zephyr,memory-region``.
_ZEPHYR_CHOSEN_REGIONS = {"zephyr,flash": "FLASH", "zephyr,sram": "RAM"}
_ZEPHYR_REPOSITORY = "zephyrproject-rtos/zephyr"


def generate(catalog: Catalog | None = None, snapshots: Path = SNAPSHOTS) -> dict[str, Any]:
    """The dataset document, from the snapshots and the catalog's public Socs and boards."""
    catalog = catalog if catalog is not None else builtin(include_plugins=False)
    mapping = _parse.parse_file(snapshots / "link-environments.yaml")
    sdk = json.loads((snapshots / "nsx-ambiq-sdk.json").read_text(encoding="utf-8"))
    zephyr = json.loads((snapshots / "zephyr.json").read_text(encoding="utf-8"))
    public = {
        t.id
        for t in (catalog.resolve(e.id) for e in (*catalog.socs(), *catalog.boards()))
        if t.release_status == "public"
    }
    environments = [
        *_sdk_environments(sdk, mapping["nsx-ambiq-sdk"], public),
        *_zephyr_environments(zephyr, public),
    ]
    environments.sort(key=lambda e: (e["owner"], e["link_family"], e["profile"], e["applies_to"]))
    return {
        "format": DATASET_FORMAT,
        "sources": sorted(
            [*sdk["metadata"]["sources"], *zephyr["metadata"]["sources"]],
            key=lambda s: s["repository"],
        ),
        "environments": environments,
    }


def _sdk_environments(
    snapshot: dict[str, Any], mapping: dict[str, Any], public: set[str]
) -> list[dict[str, Any]]:
    (source,) = snapshot["metadata"]["sources"]
    found = []
    for soc, facts in snapshot["socs"].items():
        if soc not in public:
            continue
        for toolchain, family in mapping["link_families"].items():
            group = facts["linker"].get(toolchain)
            if group is None or "default" not in group:
                continue
            reserved = set(mapping.get("reserved", {}).get(soc, {}).get(toolchain, ()))
            script = group["scripts"][group["default"]]
            regions = {}
            for name, region in sorted(script.items()):
                entry: dict[str, Any] = {"start": region["origin"], "length": region["length"]}
                if region.get("empty") or name in reserved:
                    entry["reserved"] = True
                regions[name] = entry
            found.append(
                {
                    "owner": "nsx-ambiq-sdk",
                    "link_family": family,
                    "profile": "default",
                    "applies_to": [soc],
                    "regions": regions,
                    "source": f"{group['path']}/{group['default']}",
                    "revision": source["commit"],
                    "release_status": "public",
                }
            )
    return found


def _zephyr_environments(snapshot: dict[str, Any], public: set[str]) -> list[dict[str, Any]]:
    commit = next(
        s["commit"]
        for s in snapshot["metadata"]["sources"]
        if s["repository"] == _ZEPHYR_REPOSITORY
    )
    found = []
    for board, facts in snapshot["boards"].items():
        if board not in public:
            continue
        tree = facts["devicetree"]
        chosen_by_node: dict[str, list[str]] = {}
        for prop, node in sorted(tree["chosen"].items()):
            chosen_by_node.setdefault(node, []).append(prop)
        offset = facts["kconfig"].get("FLASH_LOAD_OFFSET", {}).get("value", 0)
        regions = {}
        for node, memory in sorted(tree["memory"].items()):
            chosen = chosen_by_node.get(node, [])
            names = {_ZEPHYR_CHOSEN_REGIONS[c] for c in chosen if c in _ZEPHYR_CHOSEN_REGIONS}
            if "zephyr,memory-region" in memory:
                names.add(memory["zephyr,memory-region"])
            if not names:
                continue
            if len(names) > 1:
                raise SystemExit(f"{board}: {node} is in more than one linker region: {names}")
            (name,) = names
            start, length = memory["base"], memory["size"]
            if name == "FLASH":
                start, length = start + offset, length - offset
            entry: dict[str, Any] = {"start": start, "length": length}
            if chosen:
                entry["chosen"] = chosen
            regions[name] = entry
        found.append(
            {
                "owner": "zephyr",
                "link_family": "zephyr",
                "profile": "default",
                "applies_to": [board],
                "regions": dict(sorted(regions.items())),
                "source": tree["path"],
                "revision": commit,
                "release_status": "public",
            }
        )
    return found


def render(document: dict[str, Any]) -> str:
    return json.dumps(document, indent=2, sort_keys=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if the dataset is stale")
    args = parser.parse_args(argv)
    text = render(generate())
    if args.check:
        if OUTPUT.read_text(encoding="utf-8") != text:
            print(
                f"{OUTPUT.relative_to(ROOT)} is stale; run "
                "`uv run python scripts/generate_link_environments.py`",
                file=sys.stderr,
            )
            return 1
        return 0
    OUTPUT.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
