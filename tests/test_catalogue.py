import dataclasses
import datetime
from types import MappingProxyType

import pytest
from typer.testing import CliRunner

from conftest import RECORD
from helia_platforms import model
from helia_platforms.catalogue import load_documents, load_overlay
from helia_platforms.cli import app
from helia_platforms.errors import FormatError


def soc(document):
    return document["socs"]["soc_a"]


def problems_of(document, **kwargs) -> str:
    with pytest.raises(FormatError) as exc:
        load_overlay(document, **kwargs)
    return "\n".join(exc.value.problems)


# ---- building the model -------------------------------------------------------------


def test_model_values(document):
    cat = load_overlay(document)
    a = cat.entry("socs", "soc_a")
    assert a.memories[0] == dataclasses.replace(a.memories[0], size=524288, base=0x20000000)
    assert [r.name for r in a.memories] == ["tcm", "ssram", "nvm"]
    assert a.cores[0].options.fpu_dp is False
    assert a.npus[0].npu.accelerator_config == "ethos-u85-256"
    assert a.boot_configs["sbl"].reserved[0].purpose == "sbl"
    assert a.boot_configs["sbl"].reserved[0].size == 64 * 1024
    assert a.release_status == "embargoed"  # the overlay default
    assert cat.boards("soc_a")[0].id == "board_a"
    assert cat.npus()[0].model == "u85"
    assert cat.sources["soc_a"] == "overlay:<mapping>"


def test_model_is_immutable(document):
    a = load_overlay(document).entry("socs", "soc_a")
    with pytest.raises(dataclasses.FrozenInstanceError):
        a.series = "x"  # type: ignore[misc]
    assert isinstance(a.boot_configs, MappingProxyType)
    assert isinstance(a.memories, tuple)


def test_shorthands_expand(document):
    a = load_overlay(document).entry("socs", "soc_a")
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
    a = load_overlay(document).entry("socs", "soc_a")
    assert a.provenance.status == "datasheet"
    assert a.provenance.verified_on == datetime.date(2026, 10, 5)
    tcm = a.memories[0]
    assert tcm.provenance == a.provenance
    assert tcm.field_provenance["size"].status == "measured"
    assert "memories.tcm.size" not in a.field_provenance  # held by the region
    assert dict(a.memories[1].field_provenance) == {}


def test_values_without_a_record_are_unverified_in_overlays(document):
    part = load_overlay(document).entry("parts", "PART-A")
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
    b = load_overlay(overlay, base=base).entry("socs", "soc_b")
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
    b = load_overlay({"socs": {"soc_b": {"based_on": "soc_a"}}}, base=base).entry("socs", "soc_b")
    assert b.aliases == ()
    assert b.release_status == "embargoed"


def test_based_on_merges_extensions_per_tool(document):
    document["boards"]["board_a"]["extensions"] = {"a": {"x": 1}, "b": {"y": 2}}
    base = load_overlay(document)
    overlay = {"boards": {"board_b": {"based_on": "board_a", "extensions": {"b": {"z": 3}}}}}
    board = load_overlay(overlay, base=base).entry("boards", "board_b")
    assert board.extensions == {"a": {"x": 1}, "b": {"z": 3}}


def test_based_on_within_one_overlay(document):
    document["socs"]["soc_b"] = {"based_on": "soc_a", "peripherals_removed": ["iom2"]}
    document["socs"]["soc_c"] = {"based_on": "soc_b", "peripherals_removed": ["iom1"]}
    c = load_overlay(document).entry("socs", "soc_c")
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


def test_removing_a_core_or_region_drops_its_access(document):
    document["socs"]["soc_b"] = {"based_on": "soc_a", "memories_removed": ["ssram"]}
    b = load_overlay(document).entry("socs", "soc_b")
    assert [(a.master, a.target) for a in b.access] == [("npu_0", "tcm")]


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
    impl = cat.entry("implementations", "soc_a_fpga")
    assert impl.subset.memories_resized == {"tcm": 256 * 1024}
    realized = cat.realized("soc_a_fpga")
    assert (realized.memories[0].name, realized.memories[0].size) == ("tcm", 256 * 1024)
    cpu = next(d for d in realized.clock_domains if d.id == "cpu")
    assert [(p.name, p.mhz) for p in cpu.points] == [("lp", 24.0), ("fpga", 25.0)]
    assert list(realized.boot_configs) == ["nbl"]
    assert realized.default_boot == "nbl"


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
        load_documents([(document, "builtin.yaml")], builtin=True)
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
    assert cat.entry("memory_devices", "dev").capacity == 8 * 1024 * 1024
    assert cat.sources["dev"] == f"overlay:{path}"


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


def test_cli_export_schema():
    result = runner.invoke(app, ["export", "--schema"])
    assert result.exit_code == 0
    assert '"$id": "tag:ambiq.com,2026:helia-platforms/schema/v1"' in result.output
