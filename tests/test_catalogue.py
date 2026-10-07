import copy
import dataclasses
import datetime
import re
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest
from typer.testing import CliRunner

from conftest import RECORD
from helia_platforms import cli, model
from helia_platforms._build import freeze
from helia_platforms._tree import MergeError
from helia_platforms.catalogue import _EMPTY, _load_documents, load_overlay
from helia_platforms.cli import app
from helia_platforms.errors import FormatError, PlatformError


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


def test_fvp_substitutions_replace_regions_many_to_one(document):
    substitution = {"replaces": ["tcm", "ssram"], "size": "8M", "base": 0x30000000}
    realized = implementation(document, "fvp", subset={"substitutions": {"sram": substitution}})
    assert [r.name for r in realized.memories] == ["nvm", "sram"]
    sram = realized.memories[1]
    assert (sram.technology, sram.attachment) == ("sram", "tcm")  # from tcm, the first replaced
    assert (sram.size, sram.base) == (8 * 1024 * 1024, 0x30000000)
    assert sram.provenance == model.UNVERIFIED  # the overlay's record for the substitution
    assert sram.field_provenance["technology"].status == "datasheet"  # the Soc's, for tcm
    assert realized.access == ()  # the replaced regions' access entries go with them


def test_a_substitute_may_take_the_name_of_a_region_it_replaces(document):
    subset = {"substitutions": {"ssram": {"replaces": ["ssram"], "size": "1M"}}}
    ssram = implementation(document, "fvp", subset=subset).memories[-1]
    assert (ssram.name, ssram.size, ssram.base) == ("ssram", 1024 * 1024, None)


def test_substitutions_are_allowed_only_on_kind_fvp(document):
    subset = {"substitutions": {"sram": {"replaces": ["ssram"], "size": "1M"}}}
    found = problems_of(with_cut(document, subset=subset))
    assert "implementations.cut.subset: substitutions are allowed only for kind fvp" in found


def test_substitutions_must_replace_regions_the_soc_has_once(document):
    subset = {
        "substitutions": {
            "a": {"replaces": ["tcm", "hblram"], "size": "1M"},
            "b": {"replaces": ["tcm"], "size": "1M"},
            "c": {"replaces": [], "size": "1M"},
            "nvm": {"replaces": ["ssram"], "size": "1M"},
        }
    }
    found = problems_of(with_cut(document, "fvp", subset=subset))
    assert "region 'tcm' is replaced by more than one substitution" in found
    assert "substitutions.a replaces region 'hblram', which the base lacks" in found
    assert "substitutions.c replaces no region" in found
    assert "substitutions.nvm is named after a region it does not replace" in found


def test_an_implementation_cannot_add_a_memory(document):
    region = {"technology": "sram", "attachment": "system", "size": "1M"}
    found = problems_of(with_cut(document, memories={"extra": region}))
    assert "implementations.cut.memories: unknown key 'memories'" in found


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
    stand_in["peripherals"] = ["iom0", "iom1", "iom2", "iom3"]
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
