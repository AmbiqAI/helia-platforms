"""Parity with each consumer's current data, except an allow-list with reasons (#13)."""

import dataclasses
import json
import sys
from pathlib import Path
from typing import cast

import pytest
import yaml

from helia_platforms import PlatformError, Target, UnknownPlatform, model
from helia_platforms.catalog import builtin

PARITY = Path(__file__).resolve().parent / "parity"
SNAPSHOTS = Path(__file__).resolve().parents[1] / "snapshots"
#: neuralspotx-v0.9.0's effective board facts, frozen while both snapshots pinned v5.2.26 (#18).
NSX_FIXTURE = PARITY / "neuralspotx" / "boards.json"
ALLOW = yaml.safe_load((PARITY / "allow.yaml").read_text())
#: The heliaAOT capabilities a target's derived capabilities map onto; MCU is its policy tag.
_AOT_CAPABILITIES = {"dsp": "DSP", "mve": "MVE", "fp16": "FP16", "npu": "NPU"}


def helia_aot(target: Target) -> dict:
    """The ``targets.json`` facts heliaAOT's adapter derives (RFC 0003 "How consumers migrate").

    ``min_alignment`` and ``preferred_memory_order`` are heliaAOT policy and are not compared.
    heliaAOT 0.33.0 has no PSRAM capability; PSRAM is only a memory there.
    """
    memories: dict[str, int] = {}
    for region in target.memories():
        if region.attachment == "external" or region.technology != "sram":
            continue
        if region.name == "hblram":  # out of the budget until its placement is confirmed (#19)
            continue
        kind = region.name.upper() if region.attachment == "tcm" else "SRAM"
        # heliaAOT's name for Apollo3's and Apollo4's one data TCM.
        kind = "DTCM" if kind == "TCM" else kind
        memories[kind] = memories.get(kind, 0) + region.size
    psram = [r.size for r in target.external_memories() if r.technology == "psram"]
    if psram:
        memories["PSRAM"] = sum(psram)
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


def neuralspotx(target: Target) -> dict:
    """The board facts neuralspotx's build uses, from the catalog (#18)."""
    try:
        load: int | str = target.flash_load_address()
    except PlatformError as exc:
        load = str(exc)
    build = (target.soc.sdk.build if target.soc.sdk else None) or model.BuildFacts()
    return {
        "soc": target.soc.id.casefold(),
        "cpu.core": target.core.id,
        "cpu.abi": build.abi,
        "cpu.float_abi": build.float_abi,
        "jlink_device": target.jlink_device,
        "trace_clock_mhz": target.trace_clock_mhz,
        "flash_load_address": load,
    }


def neuralspotx_record(block: dict, sdk: dict) -> dict:
    """The same facts from neuralspotx: its board's ``debug.cmake``, else its Soc's SDK facts."""
    soc = block["board"]["values"]["soc"]
    facts = next(b for k, b in sdk.items() if k.casefold() == soc.casefold())["facts"]["values"]
    debug = block.get("debug", {}).get("values", {})

    def value(key: str) -> str | None:
        found = debug[key] if key in debug else facts.get(key)  # an empty set() still overrides
        return found[0] if found else None

    hz, address = value("NSX_SEGGER_CPUFREQ"), value("NSX_SEGGER_PF_ADDR")
    cpu = block["board"]["values"]["cpu"]
    return {
        "soc": soc.casefold(),
        "cpu.core": cpu["core"],
        "cpu.abi": cpu["abi"],
        "cpu.float_abi": cpu["float_abi"],
        "jlink_device": value("NSX_SEGGER_DEVICE"),
        "trace_clock_mhz": None if hz is None else int(hz) / 1e6,
        "flash_load_address": None if address is None else int(address, 16),
    }


def _records(consumer: str) -> list[tuple[str, dict]]:
    """``(target name, the consumer's facts)`` for each target ``consumer`` records."""
    if consumer == "helia-aot":
        targets = json.loads((PARITY / "helia-aot" / "targets.json").read_text())["targets"]
        return [(t["name"], helia_aot_record(t)) for t in targets]
    assert consumer == "neuralspotx"
    return list(json.loads(NSX_FIXTURE.read_text()).items())


def neuralspotx_from_snapshots() -> dict[str, dict]:
    """Each neuralspotx board's effective facts, from its snapshot and the SDK snapshot."""
    boards = json.loads((SNAPSHOTS / "neuralspotx.json").read_text())["boards"]
    sdk = json.loads((SNAPSHOTS / "nsx-ambiq-sdk.json").read_text())["socs"]
    return {name: neuralspotx_record(block, sdk) for name, block in sorted(boards.items())}


_PROJECTIONS = {"helia-aot": helia_aot, "neuralspotx": neuralspotx}


def compare(consumer: str) -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
    """``(target, field)`` for each value compared with ``consumer``, and for each that differs."""
    records = _records(consumer)
    assert records, "the fixture holds no targets"
    catalog = builtin(include_plugins=False)
    compared, found = set(), set()
    for name, theirs in records:
        try:
            ours = _PROJECTIONS[consumer](catalog.resolve(name))
        except UnknownPlatform:
            found.add((name, "target"))
            continue
        keys = {(name, key) for key in ours.keys() | theirs.keys()}
        compared |= keys
        found |= {(n, key) for n, key in keys if ours.get(key) != theirs.get(key)}
    return compared, found


def differences(consumer: str) -> set[tuple[str, str]]:
    """``(target, field)`` for each value the catalog gives differently from ``consumer``."""
    return compare(consumer)[1]


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


_EXPECTED_KEYS = {
    "helia-aot": {"cpu", "speeds_mhz", "memories.SRAM", "memories.MRAM"},
    "neuralspotx": {
        "soc",
        "cpu.core",
        "cpu.abi",
        "cpu.float_abi",
        "jlink_device",
        "trace_clock_mhz",
        "flash_load_address",
    },
}


@pytest.mark.parametrize(
    ("field", "value"),
    [("cpu.core", "cortex-m4"), ("cpu.abi", "thumbv7em"), ("cpu.float_abi", "soft")],
)
def test_neuralspotx_parity_compares_the_cpu_block(tmp_path, monkeypatch, field, value):
    boards = json.loads(NSX_FIXTURE.read_text())
    boards["apollo510_evb"][field] = value
    fixture = tmp_path / "boards.json"
    fixture.write_text(json.dumps(boards))
    monkeypatch.setattr(sys.modules[__name__], "NSX_FIXTURE", fixture)
    assert ("apollo510_evb", field) in differences("neuralspotx")


def test_an_empty_debug_setting_overrides_the_sdk_fact():
    sdk = json.loads((SNAPSHOTS / "nsx-ambiq-sdk.json").read_text())["socs"]
    block = json.loads((SNAPSHOTS / "neuralspotx.json").read_text())["boards"]["apollo510_evb"]
    block["debug"]["values"]["NSX_SEGGER_DEVICE"] = []
    assert neuralspotx_record(block, sdk)["jlink_device"] is None


def test_the_neuralspotx_fixture_matches_its_snapshots_while_the_pins_agree():
    """The fixture freezes neuralspotx's view; an SDK refresh must not move it (#18)."""
    nsx = json.loads((SNAPSHOTS / "neuralspotx.json").read_text())["soc_families"]["values"]
    sdk = json.loads((SNAPSHOTS / "nsx-ambiq-sdk.json").read_text())["socs"]
    if any(sdk[soc]["revision"] != tag for soc, tag in nsx.items() if soc in sdk):
        pytest.skip("the SDK snapshot has moved past neuralspotx's pins; the fixture stays")
    assert json.loads(NSX_FIXTURE.read_text()) == neuralspotx_from_snapshots()


@pytest.mark.parametrize("consumer", sorted(ALLOW["consumers"]))
def test_values_are_compared(consumer):
    compared, found = compare(consumer)
    assert _EXPECTED_KEYS[consumer] <= {key for _, key in compared}
    assert compared - found  # some values agree, so the projection lines up


def test_hblram_is_left_out_and_psram_counted_whatever_core_0_reaches():
    """RFC 0002 0002-migration.md, heliaAOT budgets: HBLRAM waits on #19."""
    target = builtin(include_plugins=False).resolve("apollo510_evb")
    ssram = target.region("ssram")
    hblram = dataclasses.replace(ssram, name="hblram", size=13312 << 10)
    on_chip = tuple(r for r in target.memories() if r.attachment != "external")

    class Reduced:  # core 0 reaches HBLRAM but no external memory
        def __getattr__(self, name):
            return getattr(target, name)

        def memories(self):
            return (*on_chip, hblram)

    ours = helia_aot(cast(Target, Reduced()))
    assert ours["memories.SRAM"] == ssram.size
    assert ours["memories.PSRAM"] == 64 << 20
