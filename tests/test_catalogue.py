import copy
import dataclasses
import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from typing import Any

import pytest
from typer.testing import CliRunner

from conftest import BASE_DOCUMENT, RECORD
from helia_platforms import catalogue, cli, model
from helia_platforms._build import freeze
from helia_platforms._tree import MergeError
from helia_platforms.catalogue import _EMPTY, _load_documents, builtin, load_overlay
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


# ---- builtin() and side-loaded catalogues (RFC 0002 private silicon) ---------------


def write(path: Path, data: dict[str, Any]) -> Path:
    """Write ``data`` as a catalogue file (JSON is YAML 1.2) and return its path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema_version": 1, **data}))
    return path


@dataclasses.dataclass
class FakeEntryPoint:
    name: str
    distribution: str
    result: Any

    @property
    def dist(self) -> SimpleNamespace:
        return SimpleNamespace(name=self.distribution)

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
    write(data / "socs" / "soc_a.yaml", {"socs": {"soc_a": soc_a}})
    write(
        data / "memory_devices.yaml",
        {"memory_devices": {"psram_8m": device | {"provenance": RECORD}}},
    )
    found: list[FakeEntryPoint] = []
    monkeypatch.setattr(catalogue, "_CACHE", {})
    monkeypatch.setattr(catalogue, "_data_root", lambda: data)
    monkeypatch.setattr(catalogue, "entry_points", lambda *, group: list(found))
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
    with pytest.raises(error):  # the failure is not cached as a partial catalogue
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


def test_a_source_that_calls_builtin_while_loading_is_refused(plugins, monkeypatch):
    reentrant = FakeEntryPoint("a", "a-private", None)
    monkeypatch.setattr(reentrant, "load", lambda: builtin)  # its callable is builtin itself
    plugins.append(reentrant)
    with pytest.raises(PlatformError, match="called while the catalogue was being loaded"):
        builtin()
    assert set(builtin(include_plugins=False).sources.values()) == {"builtin"}


def test_builtin_is_cached_and_discovers_once(plugins, tmp_path, monkeypatch):
    calls: list[str] = []

    def found(*, group: str) -> list[FakeEntryPoint]:
        calls.append(group)
        return []

    monkeypatch.setattr(catalogue, "entry_points", found)
    cat = builtin()
    monkeypatch.setenv("HELIA_PLATFORMS_PATH", str(tmp_path / "missing.yaml"))
    assert builtin() is cat
    assert builtin(include_plugins=True) is cat
    assert builtin(include_plugins=False) is builtin(include_plugins=False)
    assert calls == ["helia_platforms.catalogues"]


def test_the_packaged_data_loads(monkeypatch):
    monkeypatch.setattr(catalogue, "_CACHE", {})
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
import helia_platforms, helia_platforms.catalogue, helia_platforms.cli
assert not seen and "yaml" not in sys.modules, seen
helia_platforms.catalogue.builtin()
assert all(any(w in event for event in seen) for w in ["entry_points", *sys.argv[1:]]), seen
"""


def test_importing_the_package_reads_no_catalogue_or_entry_points(tmp_path):
    data = Path(catalogue.__file__).parent / "data"
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
