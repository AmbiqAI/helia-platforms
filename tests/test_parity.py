"""Parity with each consumer's current data, except an allow-list with reasons (#13)."""

import json
from pathlib import Path

import pytest
import yaml

from helia_platforms import Target, UnknownPlatform
from helia_platforms.catalog import builtin

PARITY = Path(__file__).resolve().parent / "parity"
ALLOW = yaml.safe_load((PARITY / "allow.yaml").read_text())
#: The heliaAOT capabilities a target's derived capabilities map onto; MCU is its policy tag.
_AOT_CAPABILITIES = {"dsp": "DSP", "mve": "MVE", "fp16": "FP16", "npu": "NPU"}


def helia_aot(target: Target) -> dict:
    """The ``targets.json`` facts heliaAOT's adapter derives (RFC 0003 "How consumers migrate").

    ``min_alignment`` and ``preferred_memory_order`` are heliaAOT policy and are not compared.
    """
    memories: dict[str, int] = {}
    for region in target.memories():
        if region.attachment == "external":
            kind = "PSRAM" if region.technology == "psram" else None
        else:
            kind = region.name.upper() if region.attachment == "tcm" else "SRAM"
            kind = kind if region.technology == "sram" else None
        if kind:
            memories[kind] = memories.get(kind, 0) + region.size
    memories["MRAM"] = sum(target.usable_nvm().values())
    return {
        "cpu": target.core.id,
        "speeds_mhz": sorted({target.cpu_mhz(p.name) for p in target.operating_points()}),
        "capabilities": sorted(
            {"MCU"} | {_AOT_CAPABILITIES[c] for c in target.capabilities if c in _AOT_CAPABILITIES}
        ),
        "supports_fp16": target.isa().supports_fp16,
        **{f"memories.{name}": size for name, size in memories.items()},
    }


def helia_aot_record(record: dict) -> dict:
    return {
        "cpu": record["cpu"],
        "speeds_mhz": sorted(record["speeds_mhz"]),
        "capabilities": sorted(record["capabilities"]),
        "supports_fp16": record["supports_fp16"],
        **{f"memories.{m['name']}": m["bytes"] for m in record["memories"]},
    }


def differences(consumer: str) -> set[tuple[str, str]]:
    """``(target, field)`` for each value the catalog gives differently from ``consumer``."""
    assert consumer == "helia-aot"
    records = json.loads((PARITY / "helia-aot" / "targets.json").read_text())["targets"]
    catalog = builtin(include_plugins=False)
    found = set()
    for record in records:
        try:
            ours = helia_aot(catalog.resolve(record["name"]))
        except UnknownPlatform:
            found.add((record["name"], "target"))
            continue
        theirs = helia_aot_record(record)
        found |= {
            (record["name"], key)
            for key in ours.keys() | theirs.keys()
            if ours.get(key) != theirs.get(key)
        }
    return found


def allowed(consumer: str) -> set[tuple[str, str]]:
    return {(a["target"], a["field"]) for a in ALLOW["allowed"] if a["consumer"] == consumer}


@pytest.mark.parametrize("consumer", sorted(ALLOW["consumers"]))
def test_every_difference_is_allowed_with_a_reason(consumer):
    assert differences(consumer) - allowed(consumer) == set()


@pytest.mark.parametrize("consumer", sorted(ALLOW["consumers"]))
def test_every_allowed_difference_still_differs(consumer):
    assert allowed(consumer) - differences(consumer) == set()


def test_every_allow_list_entry_has_a_reason_and_an_issue():
    for entry in ALLOW["allowed"]:
        assert entry["reason"].strip() and entry["issue"].strip(), entry
        assert entry["consumer"] in ALLOW["consumers"], entry
