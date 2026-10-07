import copy
import dataclasses
import datetime
import re
import warnings
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest
from typer.testing import CliRunner

from conftest import RECORD
from helia_platforms import cli, model
from helia_platforms._build import freeze
from helia_platforms._tree import MergeError
from helia_platforms.catalogue import _EMPTY, _expanded_access, _load_documents, load_overlay
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


def test_the_catalogue_and_the_empty_base_are_read_only(document):
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

_ENTITY_TABLES = ("cores", "socs", "implementations", "parts", "boards", "addons", "memory_devices")


def as_builtin(document):
    """The document made fit for a built-in load: every entity public and recorded."""
    for kind in _ENTITY_TABLES:
        for entry in document.get(kind, {}).values():
            entry.setdefault("provenance", RECORD)
            if kind != "cores":
                entry["release_status"] = "public"
    return document


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
    load_quietly(document)
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


def shield(population, fits=("board_a",)):
    return {"fits_boards": list(fits), "occupies": list(population), "population": population}


def with_mspi1(document, aperture_max="256M"):
    soc(document)["peripherals"].append("mspi1")
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
        ("cm55_0", "iom1", "direct"),
        ("cm55_0", "iom2", "direct"),
    ]  # not radio_tcm (another core's), hbl (external) or iom0 (core 0's own entry)
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


def test_an_overlay_interface_without_access_draws_a_warning(document):
    del soc(document)["default_access"]
    with pytest.warns(PlatformWarning, match="controller 'mspi0' has no access entry"):
        load_overlay(document)
    soc(document)["access"].append({"master": "npu_0", "target": "mspi0", "access": "none"})
    load_quietly(document)


def test_an_interface_needs_a_controller_of_the_soc(document):
    document["boards"]["board_a"]["interfaces"]["mspi0"]["controller"] = "mspi7"
    assert "boards.board_a.interfaces.mspi0: no controller 'mspi7'" in problems_of(document)


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


@pytest.mark.parametrize(("programmable_by", "ok"), [("either", True), (None, False)])
def test_an_image_slot_owner_is_a_programmable_core(document, programmable_by, ok):
    add_radio(document, programmable_by)
    document["parts"]["PART-A"]["image_slots"] = {"radio": slot("1M", "64K")}
    if ok:
        load_quietly(document)
    else:
        assert (
            "parts.PART-A.image_slots.radio: core 'radio_m4' is not programmable"
        ) in problems_of(document)


def test_image_slots_overlap_neither_each_other_nor_boot_reservations(document):
    add_radio(document, "vendor")
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


# ---- RFC 0002's example overlays --------------------------------------------------

RFC_0002 = Path(__file__).parents[1] / "docs" / "rfcs" / "0002-model-and-api.md"


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
    overlays = re.findall(r"^```yaml\n(.*?)^```", RFC_0002.read_text(), re.MULTILINE | re.DOTALL)
    assert len(overlays) == 5
    path = tmp_path / "overlay.yaml"
    path.write_text(overlays[index])
    if not expected:
        load_overlay(path)
        return
    with pytest.raises(FormatError) as exc:
        load_overlay(path)
    assert [p.removeprefix(f"{path}: ") for p in exc.value.problems] == expected


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
    def fail(path):
        raise PlatformError("cannot load")

    monkeypatch.setattr(cli, "load_overlay", fail)
    path = tmp_path / "x.yaml"
    path.write_text("schema_version: 1\n")
    result = runner.invoke(app, ["validate", str(path)])
    assert result.exit_code == 1
    assert f"{path}: cannot load" in result.output


def test_cli_validate_rejects_a_directory(tmp_path):
    result = runner.invoke(app, ["validate", str(tmp_path)])
    assert result.exit_code == 2
    assert result.exception is None or isinstance(result.exception, SystemExit)


def test_cli_export_schema():
    result = runner.invoke(app, ["export", "--schema"])
    assert result.exit_code == 0
    assert '"$id": "tag:ambiq.com,2026:helia-platforms/schema/v1"' in result.output
