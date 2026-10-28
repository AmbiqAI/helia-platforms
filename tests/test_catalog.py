import copy
import dataclasses
import datetime
import json
import os
import re
import subprocess
import sys
import threading
import warnings
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from typing import Any, get_args

import pytest
from typer.testing import CliRunner

from conftest import BASE_DOCUMENT, RECORD, REGISTER, SDK_SOURCE, as_builtin
from helia_platforms import _digest, _walk, catalog, cli, model
from helia_platforms import _format as fmt
from helia_platforms._build import freeze
from helia_platforms._tree import MergeError
from helia_platforms.catalog import (
    _EMPTY,
    _expanded_access,
    _load_documents,
    builtin,
    load_overlay,
)
from helia_platforms.cli import app
from helia_platforms.errors import FormatError, PlatformError, PlatformWarning


def soc(document):
    return document["socs"]["soc_a"]


def problems_of(document, **kwargs) -> str:
    with pytest.raises(FormatError) as exc:
        load_overlay(document, **kwargs)
    return "\n".join(exc.value.problems)


# ---- building the model -------------------------------------------------------------


def test_model_values(document):
    cat = load_overlay(document)
    a = cat._entry("socs", "soc_a")
    assert a.memories[0] == dataclasses.replace(a.memories[0], size=524288, base=0x20000000)
    assert [r.name for r in a.memories] == ["tcm", "ssram", "nvm"]
    assert a.cores[0].options.fpu_dp is False
    assert a.npus[0].npu.accelerator_config == "ethos-u85-256"
    assert a.boot_configs["sbl"].reserved[0].purpose == "sbl"
    assert a.boot_configs["sbl"].reserved[0].size == 64 * 1024
    assert a.release_status == "embargoed"  # the overlay default
    assert cat.boards("soc_a")[0].id == "board_a"
    assert cat.npus()[0].model == "u85"
    assert cat.sources[("socs", "soc_a")] == "overlay:<mapping>"


def test_model_is_immutable(document):
    a = load_overlay(document)._entry("socs", "soc_a")
    with pytest.raises(dataclasses.FrozenInstanceError):
        a.series = "x"  # type: ignore[misc]
    assert isinstance(a.boot_configs, MappingProxyType)
    assert isinstance(a.memories, tuple)


def test_the_catalog_and_the_empty_base_are_read_only(document):
    cat = load_overlay(document)
    mappings: tuple[Any, ...] = (cat._tables, cat._tables["socs"], cat.sources, _EMPTY._tables)
    for mapping in mappings:
        with pytest.raises(TypeError):
            mapping["ghost"] = None


def test_shorthands_expand(document):
    a = load_overlay(document)._entry("socs", "soc_a")
    hp = next(p for p in a.operating_points if p.name == "hp")
    assert dict(hp.domains) == {"cpu": "hp", "npu": "hp"}
    npu = next(d for d in a.clock_domains if d.id == "npu")
    assert [(p.name, p.mhz) for p in npu.points] == [("lp", 96.0), ("hp", 192.0)]
    assert dict(a.boot_configs["nbl"].app_start) == {
        "cm55_0": model.AppStart(region="nvm", offset=0)
    }


def test_shorthand_needs_the_core_0_domain(document):
    soc(document)["cores"][0]["clock_domain"] = "nope"
    assert "operating_points.hp.cpu_mhz: no clock domain 'nope'" in problems_of(document)


def test_shorthand_conflicting_with_a_point_is_rejected(document):
    soc(document)["operating_points"]["hp"] = {"cpu_mhz": 200}
    assert "is 200 MHz but clock_domains.cpu.hp is 192 MHz" in problems_of(document)


def test_provenance_records(document):
    soc(document)["memories"]["tcm"]["size"] = {
        "value": "512K",
        "provenance": {"status": "measured", "source": ["meas:board_a/x/2026-10-01"]},
    }
    a = load_overlay(document)._entry("socs", "soc_a")
    assert a.provenance.status == "datasheet"
    assert a.provenance.verified_on == datetime.date(2026, 10, 5)
    tcm = a.memories[0]
    assert tcm.provenance == a.provenance
    assert tcm.field_provenance["size"].status == "measured"
    assert "memories.tcm.size" not in a.field_provenance  # held by the region
    assert dict(a.memories[1].field_provenance) == {}


def test_a_value_list_item_may_carry_its_own_record(document):
    record = {"status": "sdk", "source": ["repo:x@v1:a.h"]}
    soc(document)["peripherals"] = ["mspi0", {"value": "iom0", "provenance": record}]
    a = load_overlay(document)._entry("socs", "soc_a")
    assert a.peripherals == ("mspi0", "iom0")
    assert a.field_provenance["peripherals.iom0"].status == "sdk"
    assert "peripherals.mspi0" not in a.field_provenance


def test_a_keyed_item_whose_key_carries_a_record(document):
    soc(document)["access"][0]["master"] = {"value": "npu_0", "provenance": {"status": "sdk"}}
    first = load_overlay(document)._entry("socs", "soc_a").access[0]
    assert first.master == "npu_0"
    assert first.field_provenance["master"].status == "sdk"


def test_a_subset_record_reaches_its_removed_access_pairs(document):
    subset = {
        "access_removed": [{"master": "npu_0", "target": "tcm"}],
        "provenance": {"status": "sdk", "source": [SDK_SOURCE]},
    }
    document["implementations"] = {"cut": {"soc": "soc_a", "kind": "fpga", "subset": subset}}
    held = load_overlay(document)._entry("implementations", "cut").field_provenance
    for key in ("master", "target"):
        assert held[f"subset.access_removed.npu_0@tcm.{key}"].status == "sdk"


def _objects_holding_facts(tp: Any, seen: set) -> set:
    """Each declared object that ``iter_values`` descends into below ``tp`` (#106)."""
    bare, markers = _walk.unwrap(tp)
    if fmt.NOT_FACT in markers or fmt.OPAQUE in markers:
        return set()
    if _walk.is_object(bare):
        if bare in seen:
            return set()
        seen.add(bare)
        found = {bare}
        for field in _walk.fields(bare).values():
            found |= _objects_holding_facts(field.type, seen)
        return found
    return set().union(*(_objects_holding_facts(arg, seen) for arg in get_args(bare)))


def test_every_object_iter_values_reads_facts_from_may_carry_a_record():
    """Otherwise the loader gives its values no record while ``iter_values`` lists them."""
    seen: set = set()
    found = set().union(*(_objects_holding_facts(t, seen) for t in fmt.ENTITY_TABLES.values()))
    assert {o.__name__ for o in found if not _walk.carries_facts(o)} == set()


def test_integer_valued_floats_in_address_lists_become_integers(document):
    soc(document)["memories"]["tcm"]["alternate_bases"] = [4096.0]
    (base,) = load_overlay(document)._entry("socs", "soc_a").memories[0].alternate_bases
    assert type(base) is int


def test_freeze_keeps_shared_sub_objects_shared():
    shared = [1]
    frozen = freeze([shared, shared])
    assert frozen[0] is frozen[1]


def test_values_without_a_record_are_unverified_in_overlays(document):
    part = load_overlay(document)._entry("parts", "PART-A")
    assert part.provenance == model.UNVERIFIED


def test_bad_calendar_date_is_rejected(document):
    soc(document)["provenance"] = {**RECORD, "verified_on": "2026-13-40"}
    assert "is not a calendar date" in problems_of(document)


# ---- based_on (ADR 0002 section 2.5; RFC 0002 "Inheritance and derivation") ---------


def test_based_on_merges_and_keeps_base_records(document):
    base = load_overlay(document)
    overlay = {
        "socs": {
            "soc_b": {
                "based_on": "soc_a",
                "memories_resized": {"ssram": "2M"},
                "memories": {"extra": {"technology": "sram", "attachment": "system", "size": "1M"}},
                "clock_domains": {"cpu": {"turbo": {"mhz": 250}}},
            }
        }
    }
    b = load_overlay(overlay, base=base)._entry("socs", "soc_b")
    assert [(r.name, r.size) for r in b.memories] == [
        ("tcm", 512 * 1024),
        ("ssram", 2 * 1024 * 1024),
        ("nvm", 4 * 1024 * 1024),
        ("extra", 1024 * 1024),
    ]
    cpu = next(d for d in b.clock_domains if d.id == "cpu")
    assert [p.name for p in cpu.points] == ["lp", "hp", "turbo"]
    assert b.provenance == model.UNVERIFIED  # the overlay's own record
    assert b.field_provenance["series"].status == "datasheet"  # inherited unchanged
    ssram = b.memories[1]
    assert ssram.provenance.status == "datasheet"
    assert ssram.field_provenance["size"] == model.UNVERIFIED  # changed by the overlay


def test_based_on_does_not_copy_aliases_or_status(document):
    soc(document)["aliases"] = ["SOC-A"]
    soc(document)["release_status"] = "public"
    base = load_overlay(document)
    b = load_overlay({"socs": {"soc_b": {"based_on": "soc_a"}}}, base=base)._entry("socs", "soc_b")
    assert b.aliases == ()
    assert b.release_status == "embargoed"


def test_based_on_merges_extensions_per_tool(document):
    document["boards"]["board_a"]["extensions"] = {"a": {"x": 1}, "b": {"y": 2}}
    base = load_overlay(document)
    overlay = {"boards": {"board_b": {"based_on": "board_a", "extensions": {"b": {"z": 3}}}}}
    board = load_overlay(overlay, base=base)._entry("boards", "board_b")
    assert board.extensions == {"a": {"x": 1}, "b": {"z": 3}}


def test_based_on_within_one_overlay(document):
    document["socs"]["soc_b"] = {"based_on": "soc_a", "peripherals_removed": ["iom2"]}
    document["socs"]["soc_c"] = {"based_on": "soc_b", "peripherals_removed": ["iom1"]}
    c = load_overlay(document)._entry("socs", "soc_c")
    assert c.peripherals == ("mspi0", "iom0")


def test_a_delta_naming_a_missing_key_is_an_error(document):
    document["socs"]["soc_b"] = {"based_on": "soc_a", "memories_resized": {"hblram": "1M"}}
    assert "memories_resized names region 'hblram', which the base lacks" in problems_of(document)


def test_a_delta_without_based_on_is_an_error(document):
    soc(document)["memories_removed"] = ["tcm"]
    assert "a delta needs a based_on entry" in problems_of(document)


def test_based_on_must_resolve_and_not_cycle(document):
    document["socs"]["x"] = {"based_on": "nowhere"}
    document["socs"]["y"] = {"based_on": "z"}
    document["socs"]["z"] = {"based_on": "y"}
    found = problems_of(document)
    assert "no socs entry 'nowhere'" in found
    assert "cycle" in found


def test_a_cycle_is_reported_once(document):
    document["socs"]["y"] = {"based_on": "z"}
    document["socs"]["z"] = {"based_on": "y"}
    document["socs"]["w"] = {"based_on": "y"}
    with pytest.raises(FormatError) as exc:
        load_overlay(document)
    assert exc.value.problems == ("<mapping>: socs.y.based_on: based_on forms a cycle at 'z'",)


def test_shorthands_expand_the_same_with_the_base_in_either_place(document):
    del soc(document)["clock_domains"]["cpu"]["hp"]  # hp comes only from the shorthand
    child = {"based_on": "soc_a", "operating_points": {"hp": {"cpu_mhz": 250, "npu_mhz": 250}}}
    together = copy.deepcopy(document)
    together["socs"]["soc_b"] = copy.deepcopy(child)
    same_load = load_overlay(together)._entry("socs", "soc_b")
    over_base = load_overlay({"socs": {"soc_b": child}}, base=load_overlay(document))
    assert over_base._entry("socs", "soc_b") == same_load
    cpu = next(d for d in same_load.clock_domains if d.id == "cpu")
    assert [(p.name, p.mhz) for p in cpu.points] == [("lp", 96.0), ("hp", 250.0)]


def test_removing_a_core_or_region_drops_its_access(document):
    document["socs"]["soc_b"] = {"based_on": "soc_a", "memories_removed": ["ssram"]}
    b = load_overlay(document)._entry("socs", "soc_b")
    assert [(a.master, a.target) for a in b.access] == [("npu_0", "tcm")]


def test_access_written_to_a_removed_region_is_an_error(document):
    document["socs"]["soc_b"] = {
        "based_on": "soc_a",
        "memories_removed": ["ssram"],
        "access": [{"master": "npu_0", "target": "ssram", "access": "direct"}],
    }
    assert "access npu_0@ssram: no target 'ssram'" in problems_of(document)


def test_a_single_app_start_without_a_core_0_is_reported(document):
    soc(document)["cores"] = []
    del soc(document)["npus"]
    del soc(document)["access"]
    del soc(document)["operating_points"]["hp"]
    found = problems_of(document)
    assert "boot_configs.sbl.app_start needs a core 0" in found
    assert "boot_configs.nbl.app_start needs a core 0" in found


# ---- an Implementation over its Soc ------------------------------------------------


def test_implementation_realizes_the_soc(document):
    document["implementations"] = {
        "soc_a_fpga": {
            "soc": "soc_a",
            "kind": "fpga",
            "clock_domains": {"cpu": {"lp": {"mhz": 24}, "fpga": {"mhz": 25}}},
            "default_boot": "nbl",
            "provisioning": "nbl",
            "subset": {
                "memories_resized": {"tcm": "256K"},
                "clock_domains_removed": ["cpu.hp"],
                "boot_configs_removed": ["sbl"],
                "operating_points_removed": ["hp"],
            },
        }
    }
    cat = load_overlay(document)
    impl = cat._entry("implementations", "soc_a_fpga")
    assert impl.subset.memories_resized == {"tcm": 256 * 1024}
    realized = cat._realized("soc_a_fpga")
    assert (realized.memories[0].name, realized.memories[0].size) == ("tcm", 256 * 1024)
    cpu = next(d for d in realized.clock_domains if d.id == "cpu")
    assert [(p.name, p.mhz) for p in cpu.points] == [("lp", 24.0), ("fpga", 25.0)]
    assert list(realized.boot_configs) == ["nbl"]
    assert realized.default_boot == "nbl"


def test_realizing_does_not_change_the_stored_trees(document):
    document["implementations"] = {
        "impl": {
            "soc": "soc_a",
            "kind": "fpga",
            "clock_domains": {"x": {"p": {"mhz": 10}, "q": {"mhz": 20}}},
            "subset": {"clock_domains_removed": ["x.p"]},
        }
    }
    cat = load_overlay(document)
    stored = copy.deepcopy(cat._trees[("implementations", "impl")].values)
    assert cat._realized("impl") == cat._realized("impl")
    assert cat._trees[("implementations", "impl")].values == stored
    assert issubclass(MergeError, PlatformError)


def test_an_implementation_of_an_unknown_soc_is_reported(document):
    document["implementations"] = {
        "cut": {
            "soc": "nope",
            "kind": "fpga",
            "boot_configs": {
                "nbl": {
                    "reserved": {},
                    "app_start": {"region": "nvm", "offset": 0},
                    "requires": "none",
                }
            },
        }
    }
    with pytest.raises(FormatError) as exc:
        load_overlay(document)
    assert exc.value.problems == ("<mapping>: implementations.cut: no soc 'nope'",)


def test_image_slots_are_checked_against_the_realized_soc(document):
    document["implementations"] = {
        "cut": {"soc": "soc_a", "kind": "fpga", "subset": {"memories_removed": ["ssram"]}}
    }
    document["parts"]["PART-A"]["implementation"] = "cut"
    document["parts"]["PART-A"]["image_slots"] = {
        "app": {
            "core": "cm55_0",
            "region": "ssram",
            "offset": 0,
            "size": "64K",
            "supplier": "vendor",
        }
    }
    assert "parts.PART-A.image_slots.app: no region 'ssram'" in problems_of(document)


def test_implementation_references_are_checked_after_the_merge(document):
    document["implementations"] = {
        "cut": {"soc": "soc_a", "kind": "fpga", "subset": {"clock_domains_removed": ["cpu.hp"]}}
    }
    found = problems_of(document)
    assert "as realized: operating_points.hp: no point cpu.hp" in found


def with_cut(document, kind="fpga", **keys) -> dict[str, Any]:
    """``document`` with one Implementation, ``cut``, of soc_a."""
    document["implementations"] = {"cut": {"soc": "soc_a", "kind": kind, **keys}}
    return document


def implementation(document, kind="fpga", **keys) -> model.Soc:
    """Implementation ``cut`` of soc_a, realized."""
    return load_overlay(with_cut(document, kind, **keys))._realized("cut")


@pytest.mark.parametrize(
    "subset",
    [
        pytest.param({"max_cpu_mhz": 100}, id="core 0"),
        pytest.param({"max_npu_mhz": 100}, id="npu 0"),
        pytest.param({"max_domain_mhz": {"npu": 100}}, id="any domain"),
    ],
)
def test_clock_caps_drop_the_points_they_exceed(document, subset):
    realized = implementation(document, subset=subset)
    assert [p.name for p in realized.operating_points] == ["lp"]
    assert realized.default_operating_point == "lp"
    cpu = next(d for d in realized.clock_domains if d.id == "cpu")
    assert [p.name for p in cpu.points] == ["lp", "hp"]  # caps act on operating points only


def test_a_cap_equal_to_a_clock_keeps_the_point(document):
    realized = implementation(document, subset={"max_cpu_mhz": 192})
    assert [p.name for p in realized.operating_points] == ["lp", "hp"]


def test_a_dropped_default_point_becomes_none(document):
    soc(document)["default_operating_point"] = "hp"
    realized = implementation(document, subset={"max_cpu_mhz": 100})
    assert realized.default_operating_point is None
    assert "default_operating_point" not in realized.field_provenance


def test_caps_that_drop_every_point_need_the_implementations_own(document):
    found = problems_of(with_cut(copy.deepcopy(document), subset={"max_cpu_mhz": 50}))
    assert "clock caps drop every operating point" in found
    realized = implementation(
        document,
        subset={"max_cpu_mhz": 50},
        operating_points={"fpga": {"cpu_mhz": 25, "npu_mhz": 25}},
    )
    assert [p.name for p in realized.operating_points] == ["fpga"]
    assert realized.default_operating_point is None


def test_caps_name_units_and_domains_the_soc_has(document):
    del soc(document)["npus"]
    del soc(document)["access"]
    del soc(document)["operating_points"]["hp"]["npu_mhz"]
    subset = {"max_npu_mhz": 100, "max_domain_mhz": {"dsp": 100}}
    found = problems_of(with_cut(document, subset=subset))
    assert "implementations.cut.subset: max_npu_mhz needs an NPU 0" in found
    assert "max_domain_mhz names domain 'dsp', which the base lacks" in found


def fvp_memories() -> dict[str, Any]:
    """An FVP memory map over soc_a: tcm and nvm by name, and ram standing in for ssram."""
    return {
        "tcm": {"technology": "sram", "attachment": "tcm", "size": "256K"},
        "ram": {
            "technology": "sram",
            "attachment": "system",
            "size": "8M",
            "stands_in_for": ["ssram"],
        },
        "nvm": {"technology": "mram", "attachment": "system", "size": "4M"},
    }


def test_an_fvp_realizes_to_exactly_its_own_memories(document):
    soc(document)["memories"]["hblram"] = {
        "technology": "psram",
        "attachment": "external",
        "base": 0x60000000,
        "size": "8M",
    }
    memories = fvp_memories()
    memories["ram"]["stands_in_for"] = ["ssram", {"value": "hblram", "provenance": RECORD}]
    cat = load_overlay(with_cut(document, "fvp", model="corstone", memories=memories))
    assert [r.name for r in cat._entry("implementations", "cut").memories] == ["tcm", "ram", "nvm"]
    realized = cat._realized("cut")
    assert [r.name for r in realized.memories] == ["tcm", "ram", "nvm"]
    tcm, ram, nvm = realized.memories
    assert (tcm.size, tcm.base) == (256 * 1024, None)  # nothing of the Soc's tcm is inherited
    assert tcm.provenance == model.UNVERIFIED  # the overlay's record, not the Soc's
    assert dict(tcm.field_provenance) == {}
    assert ram.stands_in_for == ("ssram", "hblram")
    assert ram.field_provenance["stands_in_for.hblram"].status == "datasheet"
    assert nvm.stands_in_for == ()


def test_an_fvp_without_memories_inherits_the_socs(document):
    realized = implementation(document, "fvp", model="corstone")
    assert [r.name for r in realized.memories] == ["tcm", "ssram", "nvm"]


def test_fvp_access_keeps_drops_adds_and_overrides_soc_entries(document):
    soc(document)["default_access"] = {"master": "cm55_0", "access": "direct", "scope": "on_die"}
    realized = implementation(copy.deepcopy(document), "fvp", memories=fvp_memories())
    assert [(a.target, a.guidance) for a in realized.access] == [("tcm", "discouraged")]
    assert realized.default_access is not None
    access = [
        {"master": "npu_0", "target": "ram", "access": "direct", "port": 1},
        {"master": "npu_0", "target": "tcm", "access": "direct", "guidance": "preferred"},
    ]
    realized = implementation(document, "fvp", memories=fvp_memories(), access=access)
    assert [(a.target, a.guidance, a.port) for a in realized.access] == [
        ("tcm", "preferred", None),  # the Soc's entry, overridden in place
        ("ram", None, 1),
    ]
    assert realized.access[1].provenance == model.UNVERIFIED


def test_fvp_access_to_a_soc_region_it_does_not_list_is_an_error(document):
    access = [{"master": "npu_0", "target": "ssram", "access": "direct"}]
    found = problems_of(with_cut(document, "fvp", memories=fvp_memories(), access=access))
    assert "implementations.cut: as realized: access npu_0@ssram: no target 'ssram'" in found


def test_stands_in_for_names_soc_regions_the_fvp_does_not_list_once(document):
    region = {"technology": "sram", "attachment": "system", "size": "1M"}
    memories = {
        "tcm": region,
        "a": {**region, "stands_in_for": ["hblram"]},
        "b": {**region, "stands_in_for": ["tcm", "ssram"]},
        "c": {**region, "stands_in_for": ["ssram"]},
    }
    found = problems_of(with_cut(document, "fvp", memories=memories))
    assert (
        "implementations.cut: memories.a.stands_in_for names 'hblram', which the Soc lacks" in found
    )
    assert "memories.b.stands_in_for names 'tcm', which the implementation also lists" in found
    assert "Soc region 'ssram' is in the stands_in_for of more than one region (b, c)" in found


def test_only_an_fvp_declares_memories_access_and_stands_in_for(document):
    soc(document)["memories"]["tcm"]["stands_in_for"] = ["ssram"]
    access = [{"master": "npu_0", "target": "tcm", "access": "direct"}]
    found = problems_of(with_cut(document, "rtl", memories=fvp_memories(), access=access))
    assert (
        "socs.soc_a.memories.tcm.stands_in_for: "
        "only a region of an fvp Implementation may stand in for others"
    ) in found
    assert "implementations.cut: memories is allowed only for kind fvp, not 'rtl'" in found
    assert "implementations.cut: access is allowed only for kind fvp, not 'rtl'" in found


def test_fvp_memories_cannot_be_combined_with_region_deltas(document):
    subset = {
        "memories_removed": ["nvm"],
        "memories_resized": {"tcm": "128K"},
        "memories_rebased": {"tcm": 0},
    }
    found = problems_of(with_cut(document, "fvp", memories=fvp_memories(), subset=subset))
    for key in subset:
        assert f"implementations.cut: memories cannot be combined with subset.{key}" in found


def test_an_implementation_cannot_grow_a_region_or_a_clock(document):
    with_cut(
        document,
        clock_domains={"cpu": {"turbo": {"mhz": 250}}, "dsp": {"x": {"mhz": 500}}},
        subset={"memories_resized": {"tcm": "1M", "ssram": "1M"}},
    )
    found = problems_of(document)
    assert "memories_resized.tcm is 1048576 bytes, more than the Soc's 524288" in found
    assert "memories_resized.ssram" not in found
    assert "clock_domains.cpu.turbo is 250 MHz, above the Soc's highest cpu point (192" in found
    assert "dsp" not in found  # a domain the Soc lacks has no clock to exceed


# ---- names, references and origins --------------------------------------------------


def test_ids_and_aliases_share_one_namespace(document):
    document["boards"]["board_a"]["aliases"] = ["SOC_A"]
    assert "'SOC_A' is already used by socs.soc_a" in problems_of(document)


def test_overlays_cannot_shadow_the_base(document):
    base = load_overlay(document)
    overlay = {"parts": {"part-a": {"soc": "soc_a"}}}
    assert "would shadow parts.PART-A" in problems_of(overlay, base=base)


def test_cores_have_their_own_namespace(document):
    document["parts"]["cortex-m4"] = {"soc": "soc_a"}
    load_overlay(document)


def test_references_must_resolve(document):
    del soc(document)["operating_points"]["hp"]  # its shorthand would report the domain first
    soc(document)["cores"][0]["clock_domain"] = "nope"
    soc(document)["default_boot"] = "missing"
    document["boards"]["board_a"]["population"] = {"mspi1": "no_device"}
    found = problems_of(document)
    assert "cores.cm55_0.clock_domain: no domain 'nope'" in found
    assert "default_boot: no boot config 'missing'" in found
    assert "no interface 'mspi1'" in found
    assert "no memory device 'no_device'" in found


def test_core_0_must_be_an_application_core(document):
    soc(document)["cores"][0]["role"] = "dsp"
    assert "core 0 (cm55_0) must have role application" in problems_of(document)


def test_overlays_may_not_carry_shorthands(document):
    document["shorthands"] = {"AP": ["soc_a"]}
    assert "only built-in files may carry 'shorthands'" in problems_of(document)


def test_compositions_resolve(document):
    with_mspi1(document)
    document["addons"] = {
        "shield": {
            "fits_boards": ["board_a"],
            "occupies": ["mspi1"],
            "population": {"mspi1": "psram_8m"},
        }
    }
    document["compositions"] = {"board_a_shield": {"board": "board_a", "addons": ["shield"]}}
    cat = load_overlay(document)
    assert cat.compositions["board_a_shield"].addons == ("shield",)


def test_builtin_rules(document):
    soc(document)["release_status"] = "public"
    del soc(document)["memories"]["nvm"]["base"]
    document["boards"]["board_a"]["extensions"] = {"tool": {}}
    document["socs"]["soc_b"] = {"based_on": "soc_a"}
    with pytest.raises(FormatError) as exc:
        _load_documents([(document, "builtin.yaml")], builtin=True)
    found = "\n".join(exc.value.problems)
    assert "memories.nvm: a built-in region needs a base" in found
    assert "built-in entries may not carry extensions" in found
    assert "built-in entries may not use based_on" in found
    assert "parts.PART-A: a built-in entry must write release_status: public" in found
    assert "this fact has no provenance record" in found  # parts.PART-A has none


def test_load_overlay_reads_files(tmp_path, document):
    path = tmp_path / "overlay.yaml"
    path.write_text(
        "schema_version: 1\nmemory_devices:\n  dev: {technology: psram, capacity: 8M}\n"
    )
    cat = load_overlay(path)
    assert cat._entry("memory_devices", "dev").capacity == 8 * 1024 * 1024
    assert cat.sources[("memory_devices", "dev")] == f"overlay:{path}"


def test_sources_are_keyed_by_table(tmp_path, document):
    path = tmp_path / "addon.yaml"
    path.write_text(
        "schema_version: 1\naddons:\n"
        "  psram_8m: {fits_boards: [board_a], occupies: [], population: {}}\n"
    )
    cat = load_overlay(path, base=load_overlay(document))
    assert cat.sources[("memory_devices", "psram_8m")] == "overlay:<mapping>"
    assert cat.sources[("addons", "psram_8m")] == f"overlay:{path}"


# ---- semantic rules (RFC 0002 "Overlays, validation, export, CLI") ------------------


def builtin_problems(document) -> str:
    with pytest.raises(FormatError) as exc:
        _load_documents([(as_builtin(document), "builtin.yaml")], builtin=True)
    return "\n".join(exc.value.problems)


def add_radio(document, programmable_by=None):
    core = {
        "id": "radio_m4",
        "role": "radio",
        "core": "cortex-m4",
        "clock_domain": "cpu",
        "options": {"fpu": "fpv4-sp-d16", "mve": "none"},
    }
    if programmable_by is not None:
        core["programmable_by"] = programmable_by
    soc(document)["cores"].append(core)


def load_quietly(document, **kwargs):
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        return load_overlay(document, **kwargs)


def test_regions_may_touch_but_not_overlap(document):
    load_quietly(document)  # tcm ends where ssram begins
    soc(document)["memories"]["ssram"]["base"] = 0x2007F000
    assert (
        "socs.soc_a: memories.tcm (0x20000000, 524288 bytes) overlaps "
        "memories.ssram (0x2007f000, 3145728 bytes)"
    ) in problems_of(document)


def test_alternate_bases_may_not_overlap_another_region(document):
    soc(document)["memories"]["tcm"]["alternate_bases"] = [0x10000000]
    load_quietly(document)
    soc(document)["memories"]["tcm"]["alternate_bases"] = [0x00500000]
    assert (
        "memories.tcm at alternate base 0x500000 (0x500000, 524288 bytes) overlaps memories.nvm"
        in (problems_of(document))
    )


def test_a_region_without_a_base_is_not_checked_for_overlap(document):
    soc(document)["memories"]["extra"] = {
        "technology": "sram",
        "attachment": "system",
        "size": "1M",
    }
    load_quietly(document)


def test_a_region_without_a_base_is_checked_at_its_alternate_bases(document):
    soc(document)["memories"]["extra"] = {
        "technology": "sram",
        "attachment": "system",
        "size": "4K",
        "alternate_bases": [0x20000000],
    }
    assert (
        "socs.soc_a: memories.tcm (0x20000000, 524288 bytes) overlaps "
        "memories.extra at alternate base 0x20000000 (0x20000000, 4096 bytes)"
    ) in problems_of(document)


def test_an_implementation_rebase_is_checked_for_overlap(document):
    document["implementations"] = {
        "cut": {
            "soc": "soc_a",
            "kind": "fpga",
            "subset": {"memories_rebased": {"ssram": 0x20000000}},
        }
    }
    assert "implementations.cut: as realized: memories.tcm (0x20000000" in problems_of(document)


def test_derives_from_requires_equal_physical_regions(document):
    document["socs"]["soc_b"] = {**copy.deepcopy(soc(document)), "derives_from": "soc_a"}
    document["socs"]["soc_b"]["memories"]["tcm"]["cacheable"] = True  # not a physical fact
    soc(document)["memories"]["tcm"]["alternate_bases"] = [0x10000000, 0x30000000]
    document["socs"]["soc_b"]["memories"]["tcm"]["alternate_bases"] = [0x30000000, 0x10000000]
    load_quietly(document)  # alternate_bases is keyed by value, so its order is not a fact
    document["socs"]["soc_b"]["memories"]["ssram"]["size"] = "2M"
    document["socs"]["soc_b"]["memories"]["nvm"]["base"] = 0x00800000
    found = problems_of(document)
    assert (
        "socs.soc_b: derives_from 'soc_a': memories.ssram is not the same physical region" in found
    )
    assert "socs.soc_b: derives_from 'soc_a': memories.nvm is not the same physical region" in found
    assert "memories.tcm" not in found


def test_a_device_may_not_exceed_its_aperture(document):
    document["boards"]["board_a"]["interfaces"]["mspi0"]["aperture_max"] = "8M"
    load_quietly(document)  # exactly the device's capacity
    document["boards"]["board_a"]["interfaces"]["mspi0"]["aperture_max"] = "4M"
    assert (
        "boards.board_a.population.mspi0: 'psram_8m' (8388608 bytes) exceeds the 'mspi0' "
        "aperture (4194304 bytes)"
    ) in problems_of(document)


def test_an_interface_without_an_aperture_is_skipped_with_a_warning(document):
    del document["boards"]["board_a"]["interfaces"]["mspi0"]["aperture_max"]
    with pytest.warns(PlatformWarning, match="interface 'mspi0' has no aperture_max"):
        load_overlay(document)


def test_an_escalated_warning_does_not_hide_the_problems(document):
    del document["boards"]["board_a"]["interfaces"]["mspi0"]["aperture_max"]
    document["parts"]["PART-B"] = {"soc": "nope"}
    with pytest.raises(FormatError, match="no soc 'nope'"):
        load_quietly(document)


def shield(population, fits=("board_a",)):
    return {"fits_boards": list(fits), "occupies": list(population), "population": population}


def with_mspi1(document, aperture_max="256M"):
    soc(document)["peripherals"].append("mspi1")
    soc(document)["memory_controllers"].append("mspi1")
    document["boards"]["board_a"]["interfaces"]["mspi1"] = {
        "controller": "mspi1",
        "aperture_base": 0x70000000,
        "aperture_max": aperture_max,
    }


def test_an_add_on_may_not_put_a_second_device_on_a_board_interface(document):
    with_mspi1(document)
    document["addons"] = {"shield": shield({"mspi1": "psram_8m"})}
    load_quietly(document)
    document["addons"] = {"shield": shield({"mspi0": "psram_8m"})}
    assert (
        "addons.shield: add-on 'shield' and board 'board_a' both put a device on 'mspi0'"
    ) in problems_of(document)


def test_an_add_on_uses_only_interfaces_its_boards_have(document):
    document["addons"] = {"shield": shield({"mspi1": "psram_8m"})}
    document["compositions"] = {"c": {"board": "board_a", "addons": ["shield"]}}
    assert "addons.shield: board 'board_a' has no interface 'mspi1'" in problems_of(document)
    document["addons"]["shield"] = {**shield({}), "occupies": ["mspi1"]}
    assert "addons.shield: board 'board_a' has no interface 'mspi1'" in problems_of(document)


def test_an_add_on_device_may_not_exceed_the_board_aperture(document):
    with_mspi1(document, aperture_max="4M")
    document["addons"] = {"shield": shield({"mspi1": "psram_8m"})}
    assert (
        "addons.shield.population.mspi1 on board_a: 'psram_8m' (8388608 bytes) exceeds"
    ) in problems_of(document)


def test_a_composition_puts_add_ons_only_on_boards_they_fit(document):
    with_mspi1(document)
    document["boards"]["board_b"] = {"category": "custom", "part": "PART-A"}
    document["addons"] = {"shield": shield({"mspi1": "psram_8m"})}
    document["compositions"] = {"ok": {"board": "board_a", "addons": ["shield"]}}
    load_quietly(document)
    document["compositions"]["bad"] = {"board": "board_b", "addons": ["shield"]}
    assert "compositions.bad: add-on 'shield' does not fit board 'board_b'" in problems_of(document)


def test_a_composition_puts_one_device_on_each_interface(document):
    with_mspi1(document)
    document["addons"] = {
        "first": shield({"mspi1": "psram_8m"}),
        "second": shield({"mspi1": "psram_8m"}),
    }
    document["compositions"] = {"one": {"board": "board_a", "addons": ["first"]}}
    load_quietly(document)
    document["compositions"]["two"] = {"board": "board_a", "addons": ["first", "second"]}
    assert (
        "compositions.two: add-on 'second' and add-on 'first' both put a device on 'mspi1'"
    ) in problems_of(document)


def test_default_access_grants_core_0_what_no_core_has_an_entry_for(document):
    add_radio(document)
    memories = soc(document)["memories"]
    memories["radio_tcm"] = {
        "technology": "sram",
        "attachment": "tcm",
        "base": 0x10000000,
        "size": "64K",
    }
    memories["hbl"] = {
        "technology": "psram",
        "attachment": "external",
        "base": 0x60000000,
        "size": "1M",
    }
    soc(document)["access"] += [
        {"master": "radio_m4", "target": "radio_tcm", "access": "direct"},
        {"master": "cm55_0", "target": "iom0", "access": "none"},
    ]
    a = load_quietly(document)._entry("socs", "soc_a")
    expanded = _expanded_access(a)
    granted = [(e.master, e.target, e.access) for e in expanded if e not in a.access]
    assert granted == [
        ("cm55_0", "tcm", "direct"),  # an NPU's entry does not exclude core 0
        ("cm55_0", "ssram", "direct"),
        ("cm55_0", "nvm", "direct"),
        ("cm55_0", "mspi0", "direct"),
    ]  # not radio_tcm (another core's), hbl (external), iom0 (core 0's own entry),
    # or iom1 and iom2 (peripherals that are not memory controllers)
    assert {e.provenance for e in expanded if e not in a.access} == {a.default_access.provenance}


def test_default_access_names_core_0(document):
    add_radio(document)
    soc(document)["default_access"]["master"] = "radio_m4"
    assert "socs.soc_a: default_access.master: 'radio_m4' is not core 0" in problems_of(document)


def test_built_in_regions_and_interface_controllers_need_an_access_entry(document):
    _load_documents([(as_builtin(copy.deepcopy(document)), "builtin.yaml")], builtin=True)
    del soc(document)["default_access"]
    found = builtin_problems(document)
    assert "socs.soc_a.memories.nvm: no access entry after default_access expansion" in found
    assert "memories.tcm:" not in found  # npu_0 has an entry
    assert (
        "boards.board_a.interfaces.mspi0: controller 'mspi0' has no access entry; "
        "its devices are unreachable"
    ) in found


def test_a_built_in_implementation_keeps_an_access_entry_for_each_region(document):
    del soc(document)["default_access"]
    soc(document)["access"] += [
        {"master": "cm55_0", "target": target, "access": "direct"}
        for target in ("nvm", "mspi0", "iom0")
    ]
    document["implementations"] = {
        "cut": {
            "soc": "soc_a",
            "kind": "fpga",
            "subset": {"access_removed": [{"master": "npu_0", "target": "tcm"}]},
        }
    }
    found = builtin_problems(copy.deepcopy(document))
    assert (
        "implementations.cut.memories.tcm: as realized: no access entry after "
        "default_access expansion"
    ) in found
    assert "socs.soc_a.memories" not in found
    soc(document)["access"].append({"master": "cm55_0", "target": "tcm", "access": "none"})
    _load_documents([(as_builtin(document), "builtin.yaml")], builtin=True)


def test_a_built_in_fvp_keeps_an_access_entry_for_each_of_its_own_regions(document):
    del soc(document)["default_access"]
    soc(document)["access"] += [
        {"master": "cm55_0", "target": target, "access": "direct"}
        for target in ("ssram", "nvm", "mspi0", "iom0")
    ]
    memories = fvp_memories()
    for name, base in (("tcm", 0x0), ("ram", 0x20000000), ("nvm", 0x10000000)):
        memories[name]["base"] = base  # built-in regions need one
    with_cut(document, "fvp", model="corstone", memories=memories)
    found = builtin_problems(copy.deepcopy(document))
    assert (
        "implementations.cut.memories.ram: as realized: no access entry after "
        "default_access expansion"
    ) in found
    access = [{"master": "cm55_0", "target": "ram", "access": "direct"}]
    document["implementations"]["cut"]["access"] = access
    _load_documents([(as_builtin(document), "builtin.yaml")], builtin=True)


def test_an_overlay_interface_without_access_draws_a_warning(document):
    del soc(document)["default_access"]
    with pytest.warns(PlatformWarning, match="controller 'mspi0' has no access entry"):
        load_overlay(document)
    soc(document)["access"].append({"master": "npu_0", "target": "mspi0", "access": "none"})
    load_quietly(document)


def test_an_interface_needs_a_controller_of_the_soc(document):
    document["boards"]["board_a"]["interfaces"]["mspi0"]["controller"] = "mspi7"
    assert "boards.board_a.interfaces.mspi0: no controller 'mspi7'" in problems_of(document)


def test_an_interface_on_a_peripheral_that_is_not_a_memory_controller_is_an_error(document):
    document["boards"]["board_a"]["interfaces"]["mspi0"]["controller"] = "iom1"
    assert (
        "boards.board_a.interfaces.mspi0: 'iom1' is not a memory controller of the Soc"
    ) in problems_of(document)


def test_memory_controllers_are_peripherals(document):
    soc(document)["memory_controllers"].append("mspi1")
    assert "socs.soc_a: memory_controllers: 'mspi1' is not in peripherals" in problems_of(document)


def test_access_to_a_peripheral_that_is_not_a_memory_controller_is_an_error(document):
    soc(document)["access"].append({"master": "npu_0", "target": "iom1", "access": "direct"})
    assert (
        "socs.soc_a: access npu_0@iom1: peripheral 'iom1' is not a memory controller"
    ) in problems_of(document)


def test_removing_a_peripheral_removes_the_memory_controller_and_its_access(document):
    soc(document)["access"].append({"master": "npu_0", "target": "mspi0", "access": "direct"})
    soc(document)["memory_controllers"] = [
        {"value": "mspi0", "provenance": {**RECORD, "status": "sdk", "source": [SDK_SOURCE]}},
        "iom0",
    ]
    document["socs"]["soc_b"] = {"based_on": "soc_a", "peripherals_removed": ["mspi0"]}
    cat = load_quietly(document)
    a, b = cat._entry("socs", "soc_a"), cat._entry("socs", "soc_b")
    assert a.field_provenance["memory_controllers.mspi0"].status == "sdk"
    assert b.memory_controllers == ("iom0",)
    assert "memory_controllers.mspi0" not in b.field_provenance
    assert ("npu_0", "mspi0") not in [(e.master, e.target) for e in b.access]
    assert "mspi0" not in [e.target for e in _expanded_access(b)]


def test_an_implementation_subset_removes_the_memory_controller(document):
    document["implementations"] = {
        "cut": {"soc": "soc_a", "kind": "fpga", "subset": {"peripherals_removed": ["iom0"]}}
    }
    cat = load_quietly(document)
    assert cat._realized("cut").memory_controllers == ("mspi0",)


def test_a_delta_that_keeps_a_removed_peripheral_as_a_memory_controller_is_an_error(document):
    document["socs"]["soc_b"] = {
        "based_on": "soc_a",
        "peripherals_removed": ["iom0"],
        "memory_controllers": ["iom0"],
    }
    assert "socs.soc_b: memory_controllers: 'iom0' is not in peripherals" in problems_of(document)


def test_an_interface_on_a_controller_the_implementation_removed_is_an_error(document):
    interfaces = copy.deepcopy(document["boards"]["board_a"]["interfaces"])
    document["implementations"] = {
        "cut": {
            "soc": "soc_a",
            "kind": "fpga",
            "interfaces": interfaces,
            "subset": {"peripherals_removed": ["iom2"]},
        }
    }
    document["parts"]["PART-A"]["implementation"] = "cut"
    load_quietly(document)
    document["implementations"]["cut"]["subset"]["peripherals_removed"] = ["mspi0"]
    found = problems_of(document)
    removed = "interfaces.mspi0: controller 'mspi0' is removed by the implementation"
    assert f"implementations.cut.{removed}" in found
    assert f"boards.board_a.{removed}" in found


@pytest.mark.parametrize(("programmable_by", "ok"), [("vendor", True), (None, False)])
def test_app_start_keys_name_programmable_cores(document, programmable_by, ok):
    add_radio(document, programmable_by)
    soc(document)["boot_configs"]["nbl"]["app_start"] = {
        "cm55_0": {"region": "nvm", "offset": 0},
        "radio_m4": {"region": "nvm", "offset": "2M"},
    }
    if ok:
        load_quietly(document)
    else:
        assert "boot_configs.nbl.app_start: core 'radio_m4' is not programmable" in problems_of(
            document
        )


def slot(offset, size, core="radio_m4"):
    return {"core": core, "region": "nvm", "offset": offset, "size": size, "supplier": "vendor"}


def add_reaching_radio(document, programmable_by="vendor"):
    """A radio core with an nvm entry; core 0 then needs its own, which default_access skips."""
    add_radio(document, programmable_by)
    for master in ("cm55_0", "radio_m4"):
        soc(document)["access"].append({"master": master, "target": "nvm", "access": "direct"})


@pytest.mark.parametrize(("programmable_by", "ok"), [("either", True), (None, False)])
def test_an_image_slot_owner_is_a_programmable_core(document, programmable_by, ok):
    add_reaching_radio(document, programmable_by)
    document["parts"]["PART-A"]["image_slots"] = {"radio": slot("1M", "64K")}
    if ok:
        load_quietly(document)
    else:
        assert (
            "parts.PART-A.image_slots.radio: core 'radio_m4' is not programmable"
        ) in problems_of(document)


def test_image_slots_overlap_neither_each_other_nor_boot_reservations(document):
    add_reaching_radio(document)
    slots = document["parts"]["PART-A"]["image_slots"] = {
        "a": slot(0x100000, 0x10000),
        "b": slot(0x110000, 0x10000),  # touches a
    }
    load_quietly(document)
    slots["b"]["offset"] = 0x108000
    slots["c"] = slot(0x8000, 0x1000)  # inside the 64K SBL reservation
    found = problems_of(document)
    assert "parts.PART-A: image_slots.a overlaps image_slots.b in region 'nvm'" in found
    assert "parts.PART-A: image_slots.c overlaps boot_configs.sbl.reserved.sbl" in found


def test_an_image_slot_ends_inside_its_region(document):
    add_reaching_radio(document)
    document["parts"]["PART-A"]["image_slots"] = {"radio": slot("3M", "1M")}  # ends at 4M
    load_quietly(document)
    document["parts"]["PART-A"]["image_slots"]["radio"]["size"] = "2M"
    assert "parts.PART-A.image_slots.radio: runs past the end of region 'nvm'" in problems_of(
        document
    )


def test_a_slot_past_the_end_of_mram_is_rejected_before_usable_nvm_goes_negative():
    """A 4M slot on apollo510L's 2M of MRAM once loaded, and usable_nvm() gave -2162688."""
    part = {"soc": "apollo510L", "image_slots": {"nvm_m41": slot("1M", "4M")}}
    part["image_slots"]["nvm_m41"]["region"] = "mram"
    found = problems_of({"parts": {"MY-PART": part}}, base=builtin(include_plugins=False))
    assert "parts.MY-PART.image_slots.nvm_m41: runs past the end of region 'mram'" in found


def test_an_image_slot_sits_in_memory_its_core_reaches(document):
    add_radio(document, "vendor")
    document["parts"]["PART-A"]["image_slots"] = {"radio": slot("3M", "64K")}
    assert (
        "parts.PART-A.image_slots.radio: core 'radio_m4' has no direct access to 'nvm'"
    ) in problems_of(document)


def test_an_image_slot_holds_no_other_core_s_application_start(document):
    add_reaching_radio(document)
    document["parts"]["PART-A"]["image_slots"] = {"radio": slot("64K", "64K")}
    assert (
        "parts.PART-A.image_slots.radio: holds another core's start, "
        "boot_configs.sbl.app_start.cm55_0"
    ) in problems_of(document)


def test_a_soc_image_slot_is_checked_and_a_part_slot_replaces_it_by_name(document):
    add_reaching_radio(document)
    soc(document)["image_slots"] = {"radio": slot("3M", "2M")}
    assert "socs.soc_a: image_slots.radio: runs past the end of region 'nvm'" in problems_of(
        document
    )
    soc(document)["image_slots"]["radio"]["size"] = "16K"
    document["parts"]["PART-A"]["image_slots"] = {"radio": slot("2M", "1M")}
    part = load_quietly(document).resolve("PART-A")
    assert {n: (s.offset, s.size) for n, s in part.image_slots.items()} == {
        "radio": (2 * 1024 * 1024, 1024 * 1024)
    }


def test_removing_a_slot_s_core_removes_the_soc_slot(document):
    add_reaching_radio(document)
    soc(document)["image_slots"] = {"radio": slot("3M", "16K")}
    document["implementations"] = {
        "no_radio": {"soc": "soc_a", "kind": "silicon", "subset": {"cores_removed": ["radio_m4"]}}
    }
    target = load_quietly(document).resolve("no_radio")
    assert dict(target.image_slots) == {}


# ---- builtin() and side-loaded catalogs (RFC 0002 private silicon) ---------------


def write(path: Path, data: dict[str, Any]) -> Path:
    """Write ``data`` as a catalog file (JSON is YAML 1.2) and return its path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema_version": 1, **data}))
    return path


@dataclasses.dataclass
class FakeEntryPoint:
    name: str
    distribution: str
    result: Any
    version: str = "1.2.0"

    @property
    def dist(self) -> SimpleNamespace:
        return SimpleNamespace(name=self.distribution, version=self.version)

    def load(self) -> Any:
        if isinstance(self.result, Exception):
            raise self.result
        return lambda: self.result


@pytest.fixture
def plugins(tmp_path, monkeypatch) -> list[FakeEntryPoint]:
    """Point builtin() at a test data directory; returns the entry points it will find."""
    cores = {k: {**v, "provenance": RECORD} for k, v in BASE_DOCUMENT["cores"].items()}
    soc_a = {**BASE_DOCUMENT["socs"]["soc_a"], "release_status": "public"}
    device = {"technology": "psram", "capacity": "8M", "release_status": "public"}
    data = tmp_path / "data"
    write(data / "ip.yaml", {"cores": cores})
    write(data / "sources.yaml", REGISTER)
    write(data / "socs" / "soc_a.yaml", {"socs": {"soc_a": soc_a}})
    write(
        data / "memory_devices.yaml",
        {"memory_devices": {"psram_8m": device | {"provenance": RECORD}}},
    )
    found: list[FakeEntryPoint] = []
    monkeypatch.setattr(catalog, "_CACHE", {})
    monkeypatch.setattr(catalog, "_data_root", lambda: data)
    monkeypatch.setattr(catalog, "entry_points", lambda *, group: list(found))
    monkeypatch.delenv("HELIA_PLATFORMS_PATH", raising=False)
    return found


def test_builtin_merges_the_data_files_into_one_source(plugins):
    cat = builtin(include_plugins=False)
    assert cat.socs()[0].cores[0].core == "cortex-m55"  # a reference across data files
    assert set(cat.sources) == {
        ("cores", "cortex-m55"),
        ("cores", "cortex-m4"),
        ("socs", "soc_a"),
        ("memory_devices", "psram_8m"),
    }
    assert set(cat.sources.values()) == {"builtin"}


def test_builtin_data_rejects_an_id_defined_twice(plugins, tmp_path):
    core = {**BASE_DOCUMENT["cores"]["cortex-m4"], "provenance": RECORD}
    write(tmp_path / "data" / "more.yaml", {"cores": {"cortex-m4": core}})
    with pytest.raises(FormatError) as exc:
        builtin(include_plugins=False)
    assert "helia_platforms/data/more.yaml: cores.cortex-m4: defined twice" in exc.value.problems


def test_builtin_data_follows_the_built_in_rules(plugins, tmp_path):
    write(tmp_path / "data" / "parts.yaml", {"parts": {"PART-A": {"soc": "soc_a"}}})
    with pytest.raises(FormatError, match="a built-in entry must write release_status"):
        builtin(include_plugins=False)


def test_without_plugins_nothing_is_side_loaded(plugins, tmp_path, monkeypatch):
    plugins.append(FakeEntryPoint("a", "private", RuntimeError("must not load")))
    monkeypatch.setenv("HELIA_PLATFORMS_PATH", str(tmp_path / "missing.yaml"))
    assert set(builtin(include_plugins=False).sources.values()) == {"builtin"}


def test_side_loaded_sources_load_in_order_over_the_earlier_ones(plugins, tmp_path, monkeypatch):
    board_a = {**BASE_DOCUMENT["boards"]["board_a"], "part": "PART-B"}
    part_b = {"PART-B": {"based_on": "PART-A", "silicon_revision": "C0"}}
    part_b_file = str(write(tmp_path / "ep" / "part_b.yaml", {"parts": part_b}))
    plugins += [  # listed out of order: distribution name, then entry name, decides
        FakeEntryPoint("a", "b-private", {"schema_version": 1, "boards": {"board_a": board_a}}),
        FakeEntryPoint("b", "a-private", part_b_file),
        FakeEntryPoint(
            "a", "a-private", {"schema_version": 1, "parts": {"PART-A": {"soc": "soc_a"}}}
        ),
    ]
    env = tmp_path / "env"
    board_b = write(env / "a.yaml", {"boards": {"board_b": {"based_on": "board_a"}}})
    shield = {"fits_boards": ["board_b"], "occupies": [], "population": {}}
    addon = write(env / "b.yaml", {"addons": {"shield": shield}})
    composition = {"board": "board_b", "addons": ["shield"]}
    last = write(tmp_path / "last.yaml", {"compositions": {"b_shield": composition}})
    monkeypatch.setenv("HELIA_PLATFORMS_PATH", os.pathsep.join([str(env), "", str(last)]))
    cat = builtin()
    assert cat.sources[("socs", "soc_a")] == "builtin"
    assert cat.sources[("parts", "PART-A")] == "entry_point:a-private"
    assert cat.sources[("parts", "PART-B")] == "entry_point:a-private"
    assert cat.sources[("boards", "board_a")] == "entry_point:b-private"
    assert cat.sources[("boards", "board_b")] == f"env:{board_b}"
    assert cat.sources[("addons", "shield")] == f"env:{addon}"
    assert cat.sources[("compositions", "b_shield")] == f"env:{last}"
    assert cat._entry("parts", "PART-B").soc == "soc_a"


@pytest.mark.parametrize(
    ("overlay", "shadowed"),
    [
        pytest.param(
            {"cores": {"CORTEX-M4": {"based_on": "cortex-m4"}}},
            "cores.cortex-m4 from builtin",
            id="built-in",
        ),
        pytest.param(
            {"memory_devices": {"dev": {"technology": "sram", "capacity": "1K"}}},
            "memory_devices.dev from entry_point:a-private",
            id="earlier source",
        ),
    ],
)
def test_side_loaded_entries_may_not_shadow(plugins, tmp_path, monkeypatch, overlay, shadowed):
    device = {"technology": "psram", "capacity": "8M"}
    found = {"schema_version": 1, "memory_devices": {"dev": device}}
    plugins.append(FakeEntryPoint("a", "a-private", found))
    path = write(tmp_path / "late.yaml", overlay)
    monkeypatch.setenv("HELIA_PLATFORMS_PATH", str(path))
    with pytest.raises(FormatError) as exc:
        builtin()
    [problem] = exc.value.problems
    assert problem.startswith(f"env:{path}: ")
    assert problem.endswith(f"would shadow {shadowed}")


EP = "entry_point:a-private"


@pytest.mark.parametrize(
    ("result", "error", "message"),
    [
        (RuntimeError("boom"), PlatformError, f"{EP}: entry point 'a' raised RuntimeError('boom')"),
        (42, PlatformError, f"{EP}: entry point 'a' returned int, not a mapping or a path"),
        (
            {"schema_version": 1, "parts": {"P": {"soc": "nope"}}},
            FormatError,
            f"{EP} (a): parts.P: no soc 'nope'",
        ),
        ({"parts": {}}, FormatError, f"{EP} (a): missing required key 'schema_version'"),
        (Path("missing.yaml"), FormatError, f"{EP} (missing.yaml): cannot be read"),
    ],
    ids=["raises", "bad return", "invalid overlay", "no schema_version", "unreadable path"],
)
def test_a_failing_entry_point_names_its_source(plugins, result, error, message):
    plugins.append(FakeEntryPoint("a", "a-private", result))
    with pytest.raises(error) as exc:
        builtin()
    assert str(exc.value).startswith(message)
    with pytest.raises(error):  # the failure is not cached as a partial catalog
        builtin()
    assert set(builtin(include_plugins=False).sources.values()) == {"builtin"}


def test_an_unreadable_environment_path_names_its_source(plugins, tmp_path, monkeypatch):
    path = tmp_path / "missing.yaml"
    monkeypatch.setenv("HELIA_PLATFORMS_PATH", str(path))
    with pytest.raises(FormatError, match=re.escape(f"env:{path}: cannot be read")):
        builtin()


@pytest.mark.skipif(not hasattr(os, "geteuid") or os.geteuid() == 0, reason="root reads anything")
def test_an_unreadable_environment_directory_names_its_source(plugins, tmp_path, monkeypatch):
    env = tmp_path / "env"
    write(env / "a.yaml", {})
    env.chmod(0)
    monkeypatch.setenv("HELIA_PLATFORMS_PATH", str(env))
    try:
        with pytest.raises(FormatError, match=re.escape(f"env:{env}: cannot be read")):
            builtin()
    finally:
        env.chmod(0o700)


def test_an_unreadable_data_file_names_its_resource(plugins, tmp_path):
    (tmp_path / "data" / "bad.yaml").write_bytes(b"\xff\xfe")
    with pytest.raises(
        FormatError, match=re.escape("helia_platforms/data/bad.yaml: cannot be read")
    ):
        builtin(include_plugins=False)


def test_a_source_that_calls_builtin_while_loading_is_refused(plugins, monkeypatch):
    reentrant = FakeEntryPoint("a", "a-private", None)
    monkeypatch.setattr(reentrant, "load", lambda: builtin)  # its callable is builtin itself
    plugins.append(reentrant)
    with pytest.raises(PlatformError, match="called while the catalog was being loaded"):
        builtin()
    assert set(builtin(include_plugins=False).sources.values()) == {"builtin"}


def test_a_concurrent_first_call_waits_for_the_loading_one(plugins, monkeypatch):
    started, release = threading.Event(), threading.Event()
    calls: list[Any] = []
    read = catalog._data_documents

    def slow(root):
        calls.append(root)
        started.set()
        release.wait(5)
        return read(root)

    monkeypatch.setattr(catalog, "_data_documents", slow)
    results: dict[str, Any] = {}

    def call(name: str) -> None:
        try:
            results[name] = builtin(include_plugins=False)
        except PlatformError as exc:
            results[name] = exc

    first, second = (threading.Thread(target=call, args=(n,)) for n in ("first", "second"))
    first.start()
    try:
        assert started.wait(5)
        second.start()
        second.join(0.2)
        waiting = second.is_alive()
    finally:
        release.set()
        first.join()
    second.join()
    assert waiting, results  # the second call waited instead of being refused as recursion
    assert results["second"] is results["first"]
    assert len(calls) == 1


def test_identity_records_each_side_loaded_source_without_its_directory(
    plugins, tmp_path, monkeypatch
):
    board = {"boards": {"board_a": {**BASE_DOCUMENT["boards"]["board_a"], "part": "PART-A"}}}
    part = {"parts": {"PART-A": BASE_DOCUMENT["parts"]["PART-A"]}}
    plugins.append(FakeEntryPoint("a", "a-private", {"schema_version": 1, **part}, "2.0.1"))
    env_file = write(tmp_path / "private" / "board.yaml", board)
    monkeypatch.setenv("HELIA_PLATFORMS_PATH", str(env_file.parent))
    identity = builtin().identity()
    assert identity.catalog_digest == builtin(include_plugins=False).catalog_digest
    assert [(s.label, s.distribution_version) for s in identity.sources] == [
        ("entry_point:a-private", "2.0.1"),
        ("env:board.yaml", None),
    ]
    assert identity.sources[1].sha256 == _digest.source_sha256(json.loads(env_file.read_text()))
    assert builtin(include_plugins=False).identity().sources == ()


def test_builtin_is_cached_and_discovers_once(plugins, tmp_path, monkeypatch):
    calls: list[str] = []

    def found(*, group: str) -> list[FakeEntryPoint]:
        calls.append(group)
        return []

    monkeypatch.setattr(catalog, "entry_points", found)
    cat = builtin()
    monkeypatch.setenv("HELIA_PLATFORMS_PATH", str(tmp_path / "missing.yaml"))
    assert builtin() is cat
    assert builtin(include_plugins=True) is cat
    assert builtin(include_plugins=False) is builtin(include_plugins=False)
    assert calls == ["helia_platforms.catalogs"]


def test_the_packaged_data_loads(monkeypatch):
    monkeypatch.setattr(catalog, "_CACHE", {})
    assert set(builtin(include_plugins=False).sources.values()) <= {"builtin"}


IMPORT_CHECK = """
import importlib.metadata, sys
seen = []
entry_points = importlib.metadata.entry_points
def recording(*args, **kwargs):
    seen.append("entry_points")
    return entry_points(*args, **kwargs)
def hook(event, args):
    if event in ("open", "os.listdir", "os.scandir") and args:
        if any(watched in str(args[0]) for watched in sys.argv[1:]):
            seen.append(f"{event} {args[0]}")
importlib.metadata.entry_points = recording
sys.addaudithook(hook)
import helia_platforms, helia_platforms.catalog, helia_platforms.cli
assert not seen and "yaml" not in sys.modules, seen
helia_platforms.catalog.builtin()
assert all(any(w in event for event in seen) for w in ["entry_points", *sys.argv[1:]]), seen
"""


def test_importing_the_package_reads_no_catalog_or_entry_points(tmp_path):
    data = Path(catalog.__file__).parent / "data"
    write(
        tmp_path / "env" / "x.yaml",
        {"memory_devices": {"dev": {"technology": "sram", "capacity": "1K"}}},
    )
    env = {**os.environ, "HELIA_PLATFORMS_PATH": str(tmp_path / "env")}
    subprocess.run(
        [sys.executable, "-c", IMPORT_CHECK, str(data), str(tmp_path / "env")], env=env, check=True
    )


# ---- RFC 0002's example overlays --------------------------------------------------

RFC_0002 = Path(__file__).parents[1] / "docs" / "rfcs" / "0002-model-and-api.md"


def rfc_0002_overlays() -> list[str]:
    return re.findall(r"^```yaml\n(.*?)^```", RFC_0002.read_text(), re.MULTILINE | re.DOTALL)


@pytest.mark.parametrize(
    ("index", "expected"),
    [
        pytest.param(0, ["socs.my_soc.based_on: no socs entry 'apollo510'"], id="soc delta"),
        pytest.param(
            1, ["implementations.atomiq110_fpga_rev3: no soc 'atomiq110'"], id="implementation"
        ),
        pytest.param(2, [], id="memory device"),
        pytest.param(3, ["boards.my_product_v1: no part 'AP510NFA-CBR'"], id="board"),
        pytest.param(
            4,
            [
                "addons.my_psram_daughter.fits_boards: no board 'apollo4p_evb'",
                "addons.my_psram_daughter.population: no memory device 'acme_psram_8m'",
            ],
            id="addon",
        ),
    ],
)
def test_rfc_0002_overlays_load_or_name_the_built_in_entries_they_need(tmp_path, index, expected):
    overlays = rfc_0002_overlays()
    assert len(overlays) == 5
    path = tmp_path / "overlay.yaml"
    path.write_text(overlays[index])
    if not expected:
        load_overlay(path)
        return
    with pytest.raises(FormatError) as exc:
        load_overlay(path)
    assert [p.removeprefix(f"{path}: ") for p in exc.value.problems] == expected


def test_rfc_0002_fpga_example_realizes_over_a_stand_in_soc(tmp_path, document):
    stand_in = soc(document)
    tcm, ssram, nvm = (stand_in["memories"][k] for k in ("tcm", "ssram", "nvm"))
    stand_in["memories"] = {"dtcm": tcm, "hblram": ssram, "rram": {**nvm, "technology": "rram"}}
    stand_in["peripherals"] = ["iom0", "iom1", "iom2", "iom3", "mspi0"]  # mspi0: a controller
    del stand_in["access"]
    stand_in["boot_configs"] = {
        "sbl": {"reserved": {}, "app_start": {"region": "rram", "offset": "64K"}, "requires": "sbl"}
    }
    base = {"cores": document["cores"], "socs": {"atomiq110": stand_in}}
    path = tmp_path / "overlay.yaml"
    path.write_text(rfc_0002_overlays()[1])
    realized = load_overlay(path, base=load_overlay(base))._realized("atomiq110_fpga_rev3")
    assert [p.name for p in realized.operating_points] == ["fpga"]  # max_cpu_mhz: 25
    assert realized.default_operating_point is None
    assert [(r.name, r.size) for r in realized.memories] == [
        ("dtcm", 256 * 1024),
        ("rram", 4 * 1024 * 1024),
    ]


# ---- CLI --------------------------------------------------------------------------


runner = CliRunner()


def test_cli_validate(tmp_path):
    good = tmp_path / "good.yaml"
    good.write_text(
        "schema_version: 1\nmemory_devices:\n  dev: {technology: psram, capacity: 8M}\n"
    )
    bad = tmp_path / "bad.yaml"
    bad.write_text("schema_version: 1\nmemory_devices:\n  dev: {technology: psram, capacity: 8m}\n")
    assert runner.invoke(app, ["validate", str(good)]).exit_code == 0
    result = runner.invoke(app, ["validate", str(bad)])
    assert result.exit_code == 1
    assert "capacity" in result.output


def test_cli_validate_reports_each_unreadable_file_and_continues(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_bytes(b"v: caf\xe9\n")
    good = tmp_path / "good.yaml"
    good.write_text("schema_version: 1\n")
    result = runner.invoke(app, ["validate", str(bad), str(good)])
    assert result.exit_code == 1
    assert "bad.yaml: cannot be read" in result.output
    assert f"{good}: ok" in result.output


def test_cli_validate_reports_an_unbuildable_entry_and_continues(tmp_path):
    fpga = tmp_path / "fpga.yaml"
    fpga.write_text(
        "schema_version: 1\nimplementations:\n  cut:\n    soc: nope\n    kind: fpga\n"
        "    boot_configs:\n"
        "      nbl: {reserved: {}, app_start: {region: nvm, offset: 0}, requires: none}\n"
    )
    good = tmp_path / "good.yaml"
    good.write_text("schema_version: 1\n")
    result = runner.invoke(app, ["validate", str(fpga), str(good)])
    assert result.exit_code == 1
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert "implementations.cut: no soc 'nope'" in result.output
    assert f"{good}: ok" in result.output


def test_cli_validate_reports_any_platform_error(tmp_path, monkeypatch):
    def fail(path, base):
        raise PlatformError("cannot load")

    monkeypatch.setattr(cli, "load_overlay", fail)
    path = tmp_path / "x.yaml"
    path.write_text("schema_version: 1\n")
    result = runner.invoke(app, ["validate", str(path)])
    assert result.exit_code == 1
    assert f"{path}: cannot load" in result.output


def test_cli_validate_loads_each_file_over_the_built_in_catalog(tmp_path):
    board = tmp_path / "board.yaml"
    board.write_text("schema_version: 1\nboards:\n  b: {category: custom, part: AP510NFA-IBR}\n")
    result = runner.invoke(app, ["validate", "--builtin-only", str(board)])
    assert result.exit_code == 0, result.output
    assert f"{board}: ok" in result.output
    clash = tmp_path / "clash.yaml"
    clash.write_text(
        "schema_version: 1\nboards:\n  apollo510_evb: {category: custom, part: AP510NFA-IBR}\n"
    )
    result = runner.invoke(app, ["validate", "--builtin-only", str(clash)])
    assert result.exit_code == 1
    assert "would shadow boards.apollo510_evb from builtin" in result.output


def test_cli_validate_rejects_a_directory(tmp_path):
    result = runner.invoke(app, ["validate", str(tmp_path)])
    assert result.exit_code == 2
    assert result.exception is None or isinstance(result.exception, SystemExit)


def test_cli_export_schema():
    result = runner.invoke(app, ["export", "--schema"])
    assert result.exit_code == 0
    assert '"$id": "tag:ambiq.com,2026:helia-platforms/schema/v1"' in result.output


# ---- rules the resolver relies on (#98 review) ----------------------------------------


def test_a_soc_needs_a_core(document):
    soc(document)["cores"] = []
    for key in ("operating_points", "default_operating_point", "boot_configs", "default_boot"):
        del soc(document)[key]
    del soc(document)["default_access"]
    soc(document)["npus"] = []
    assert "socs.soc_a: cores: a Soc needs at least one core" in problems_of(document)


@pytest.mark.parametrize(
    ("offset", "size", "message"),
    [
        ("32K", "64K", "boot_configs.sbl.reserved.sbl overlaps reserved.extra in region 'nvm'"),
        ("4M", "64K", "boot_configs.sbl.reserved.extra: runs past the end of region 'nvm'"),
    ],
)
def test_reservations_stay_inside_their_region_and_apart(document, offset, size, message):
    reserved = soc(document)["boot_configs"]["sbl"]["reserved"]
    reserved["extra"] = {"region": "nvm", "offset": offset, "size": size}
    assert message in problems_of(document)


def test_adjacent_reservations_are_allowed(document):
    reserved = soc(document)["boot_configs"]["sbl"]["reserved"]
    reserved["extra"] = {"region": "nvm", "offset": "64K", "size": "64K"}
    load_quietly(document)


def test_default_board_must_carry_the_soc(document):
    document["socs"]["soc_b"] = copy.deepcopy(soc(document))
    document["parts"]["PART-B"] = {"soc": "soc_b"}
    document["boards"]["board_b"] = {
        **copy.deepcopy(document["boards"]["board_a"]),
        "part": "PART-B",
    }
    soc(document)["default_board"] = "board_b"
    assert (
        "socs.soc_a: default_board: board 'board_b' carries Soc 'soc_b', not 'soc_a'"
        in problems_of(document)
    )
    soc(document)["default_board"] = "board_a"
    load_quietly(document)
