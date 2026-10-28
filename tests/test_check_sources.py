"""``check-sources``: the built-in catalog against the committed snapshots (ADR 0006, #72)."""

import copy
import dataclasses
import json
import shutil
import warnings
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from helia_platforms import _check_sources
from helia_platforms import catalog as catalog_module
from helia_platforms.catalog import builtin, load_overlay
from helia_platforms.cli import app

ROOT = Path(__file__).resolve().parents[1]
runner = CliRunner()


@pytest.fixture
def snapshots(tmp_path):
    """A copy of the committed snapshots, safe to edit."""
    directory = tmp_path / "snapshots"
    shutil.copytree(ROOT / "snapshots", directory)
    return directory


def edit(directory: Path, name: str, change) -> None:
    path = directory / name
    data = json.loads(path.read_text())
    change(data)
    path.write_text(json.dumps(data))


def findings(directory: Path) -> list[_check_sources.Finding]:
    return list(_check_sources.check(builtin(include_plugins=False), directory).findings)


def test_the_committed_snapshots_agree_with_the_built_in_catalog():
    result = _check_sources.check(builtin(include_plugins=False), ROOT / "snapshots")
    assert result.ok, _check_sources.render(result)


@pytest.mark.parametrize(
    ("key", "value", "rule"),
    [
        ("NSX_SOC_SERIES", ["apollo4"], "series"),
        ("NSX_SOC_CORE", ["cortex-m4"], "core"),
        ("NSX_SOC_ARCH_CLASS", ["armv7e_m"], "arch"),
        ("NSX_SOC_PMU_TIER", ["none"], "pmu"),
        ("NSX_SOC_HAS_MVE", ["FALSE"], "mve"),
        ("NSX_FPU", ["fpv4-sp-d16"], "fpu"),
        ("NSX_ABI_FLAGS", ["thumbv7em"], "abi"),
        ("NSX_SEGGER_CPUFREQ", ["48000000"], "trace clock"),
        ("NSX_SOC_COMPILE_DEFINITIONS", ["ARMCM55"], "c_define"),
        ("NSX_SOC_CAPABILITIES", ["npu"], "npu"),
    ],
)
def test_each_facts_value_is_compared(snapshots, key, value, rule):
    def change(data):
        data["socs"]["apollo510"]["facts"]["values"][key] = value

    edit(snapshots, _check_sources.SDK, change)
    assert [f.rule for f in findings(snapshots)].count(rule) >= 1


@pytest.mark.parametrize(
    ("value", "read"),
    [
        *((v, True) for v in ("TRUE", "on", "Yes", "y", "1", "2", "0.5", "-1")),
        *((v, False) for v in ("FALSE", "off", "No", "n", "0", "0.0", "IGNORE", "X-NOTFOUND", "")),
        *((v, True) for v in ("0x1", "0XFF", "-0x1p-3")),
        *((v, False) for v in ("0x0", "0x0.0")),
        *((v, v) for v in ("MAYBE", "0x", "1x")),  # no CMake boolean, so it equals neither
    ],
)
def test_a_flag_is_read_as_cmake_reads_it(value, read):
    assert _check_sources._flag({"NSX_SOC_HAS_MVE": [value]}, "NSX_SOC_HAS_MVE") == read


@pytest.mark.parametrize(
    ("value", "rules"),
    [("Y", []), ("0x1", []), ("N", ["mve"]), ("0x0", ["mve"]), ("MAYBE", ["mve"])],
)
def test_a_flag_is_compared_with_the_catalog(snapshots, value, rules):
    def change(data):
        data["socs"]["apollo510"]["facts"]["values"]["NSX_SOC_HAS_MVE"] = [value]  # catalog: true

    edit(snapshots, _check_sources.SDK, change)
    assert [f.rule for f in findings(snapshots)] == rules


def test_the_flash_load_address_follows_the_default_boot(snapshots):
    def change(data):
        data["socs"]["apollo510"]["facts"]["values"]["NSX_SEGGER_PF_ADDR"] = ["0x00400000"]

    edit(snapshots, _check_sources.SDK, change)
    (found,) = [f for f in findings(snapshots) if f.rule == "flash load address"]
    at = ("socs", "apollo510", "facts", "values", "NSX_SEGGER_PF_ADDR")  # where it comes from
    assert (found.snapshot, found.at) == (_check_sources.SDK, at)
    assert found.message == "catalog 0x410000, snapshot 0x400000"


def except_(directory: Path, snapshot: str, at: list[str], rule: str) -> None:
    path = directory / "exceptions.yaml"
    document = yaml.safe_load(path.read_text())
    entry = {"snapshot": snapshot, "at": at, "rule": rule, "reason": "x", "issue": "#1"}
    document["exceptions"].append(entry)
    path.write_text(yaml.safe_dump(document))


@pytest.mark.parametrize(
    ("snapshot", "change", "at"),
    [
        pytest.param(
            _check_sources.SDK,
            lambda d: d["socs"]["apollo510"]["facts"]["values"].update(
                NSX_SEGGER_CPUFREQ=["48000000"]
            ),
            ["socs", "apollo510", "facts", "values", "NSX_SEGGER_CPUFREQ"],
            id="sdk fallback",
        ),
    ],
)
def test_an_exception_at_the_supplying_path_covers_a_board_value(snapshots, snapshot, change, at):
    edit(snapshots, snapshot, change)
    except_(snapshots, snapshot, at, "trace clock")
    result = _check_sources.check(builtin(include_plugins=False), snapshots)
    assert result.ok, _check_sources.render(result)


def test_the_neuralspotx_snapshot_is_not_compared(snapshots):
    """neuralspotx is a consumer (#18): its frozen snapshot is parity data, not a source."""

    def change(data):
        board = data["boards"]["apollo510_evb"]
        board["board"]["values"].update(soc="apollo4p", toolchains=["armclang"])
        board["debug"]["values"]["NSX_SEGGER_CPUFREQ"] = ["48000000"]
        board["linker"]["defaults"].pop("gcc")
        data["boards"]["not_a_board"] = board

    edit(snapshots, _check_sources.NSX, change)
    assert findings(snapshots) == []


def test_a_missing_fpu_dp_define_reads_as_single_precision(snapshots):
    edit(
        snapshots,
        _check_sources.SDK,
        lambda d: d["socs"]["apollo510"]["cmsis"]["values"].pop("__FPU_DP"),
    )
    (found,) = findings(snapshots)
    assert (found.rule, found.message) == ("fpu_dp", "catalog True, snapshot False")


def test_overlapping_exceptions_are_all_in_use(snapshots):
    except_(snapshots, _check_sources.SDK, ["socs"], _check_sources.MISSING)
    result = _check_sources.check(builtin(include_plugins=False), snapshots)
    assert result.ok, _check_sources.render(result)


def test_register_defines_are_compared_with_region_bases_and_sizes(snapshots):
    def change(data):
        data["socs"]["apollo510"]["registers"]["values"]["DTCM_MAX_SIZE"] = 507904

    edit(snapshots, _check_sources.SDK, change)
    (found,) = [f for f in findings(snapshots) if f.rule == "register"]
    assert found.at[-1] == "DTCM_MAX_SIZE"


@pytest.mark.parametrize("soc", ["apollo510", "apollo510b"])
@pytest.mark.parametrize(
    "define",
    [
        f"{region}_{part}"
        for region in ("ITCM", "DTCM", "SSRAM", "MRAM")
        for part in ("BASEADDR", "MAX_SIZE")
    ],
)
def test_each_apollo5_soc_compares_its_register_defines(snapshots, soc, define):
    def change(data):
        data["socs"][soc]["registers"]["values"][define] += 0x400

    edit(snapshots, _check_sources.SDK, change)
    (found,) = [f for f in findings(snapshots) if f.rule == "register"]
    assert found.at[1:2] + found.at[-1:] == (soc, define)


@pytest.mark.parametrize("soc", ["apollo3", "apollo3p"])
@pytest.mark.parametrize("define", ["TCM_BASEADDR", "TCM_MAX_SIZE", "FLASH_BASEADDR"])
def test_apollo3_register_defines_are_compared(snapshots, soc, define):
    def change(data):
        data["socs"][soc]["registers"]["values"][define] = 0x8000

    edit(snapshots, _check_sources.SDK, change)
    (found,) = [f for f in findings(snapshots) if f.rule == "register"]
    assert found.at[1:2] + found.at[-1:] == (soc, define)


def renamed(soc: str, old: str, new: str):
    """The built-in catalog with one of ``soc``'s regions renamed."""
    documents = copy.deepcopy(catalog_module._data_documents(catalog_module._data_root()))
    for data, _ in documents:
        memories = data.get("socs", {}).get(soc, {}).get("memories", {})
        if old in memories:
            memories[new] = memories.pop(old)
    return catalog_module._load_documents(documents, builtin=True)


@pytest.mark.parametrize(
    ("old", "rules"),
    [
        ("sram", [("flash header", "AM_HAL_FLASH_SRAM_SIZE")]),
        ("tcm", [("register", "TCM_BASEADDR"), ("flash header", "AM_HAL_FLASH_SRAM_SIZE")]),
    ],
)
def test_a_configured_region_the_soc_lacks_is_reported(old, rules):
    result = _check_sources.check(renamed("apollo3", old, "renamed"), ROOT / "snapshots")
    found = [f for f in result.findings if f.rule in ("register", "flash header")]
    assert [(f.rule, f.at[-1]) for f in found] == rules
    assert all(f.message == f"the catalog's apollo3 has no region {old!r}" for f in found)


@pytest.mark.parametrize("soc", ["apollo3", "apollo3p"])
@pytest.mark.parametrize("define", ["AM_HAL_FLASH_TOTAL_SIZE", "AM_HAL_FLASH_SRAM_SIZE"])
def test_apollo3_flash_header_sizes_are_compared(snapshots, soc, define):
    def change(data):
        data["socs"][soc]["flash"]["values"][define] //= 2

    edit(snapshots, _check_sources.SDK, change)
    (found,) = [f for f in findings(snapshots) if f.rule == "flash header"]
    assert found.at[1:2] + found.at[-1:] == (soc, define)


@pytest.mark.parametrize("define", ["AM_HAL_FLASH_TOTAL_SIZE", "AM_HAL_FLASH_SRAM_SIZE"])
def test_a_flash_header_define_the_snapshot_lacks_is_reported(snapshots, define):
    edit(
        snapshots, _check_sources.SDK, lambda d: d["socs"]["apollo3"]["flash"]["values"].pop(define)
    )
    (found,) = [f for f in findings(snapshots) if f.rule == "flash header"]
    assert (found.at[-1], found.message) == (define, f"the snapshot has no {define}")


@pytest.mark.parametrize("soc", ["apollo510L", "apollo330P"])
@pytest.mark.parametrize(
    "define",
    [
        "DTCM_BASEADDR",
        "DTCM_MAX_SIZE",
        "SSRAM_BASEADDR",
        "SSRAM_MAX_SIZE",
        "MRAM_BASEADDR",
        "MRAM_MAX_SIZE",
    ],
)
def test_apollo510l_and_apollo330p_compare_every_register_define(snapshots, soc, define):
    def change(data):
        data["socs"][soc]["registers"]["values"][define] += 0x400

    edit(snapshots, _check_sources.SDK, change)
    (found,) = [f for f in findings(snapshots) if f.rule == "register"]
    assert found.at[1:2] + found.at[-1:] == (soc, define)


def test_a_register_define_missing_from_the_header_is_reported(snapshots):
    edit(
        snapshots,
        _check_sources.SDK,
        lambda d: d["socs"]["apollo510"]["registers"]["values"].pop("DTCM_MAX_SIZE"),
    )
    (found,) = findings(snapshots)
    assert (found.rule, found.at[-1], found.message) == (
        "register",
        "DTCM_MAX_SIZE",
        "DTCM_MAX_SIZE is not defined",
    )


def test_an_empty_register_define_is_skipped(snapshots, monkeypatch):
    """A region with a base define and no size define names the size ``""``."""
    registers = dict(_check_sources.REGISTERS["apollo510"], dtcm=("DTCM_BASEADDR", ""))
    monkeypatch.setitem(_check_sources.REGISTERS, "apollo510", registers)

    def change(data):
        values = data["socs"]["apollo510"]["registers"]["values"]
        values[""] = 0  # compared with the DTCM size unless the empty name is skipped
        values["DTCM_BASEADDR"] += 0x400  # the base define is still compared

    edit(snapshots, _check_sources.SDK, change)
    (found,) = findings(snapshots)
    assert (found.rule, found.at[-1]) == ("register", "DTCM_BASEADDR")


def test_a_linker_region_outside_every_run_of_regions_is_reported(snapshots):
    def change(data):
        scripts = data["socs"]["apollo510"]["linker"]["gcc"]["scripts"]
        scripts["linker_script_sbl.ld"]["MCU_MRAM"]["length"] = 0x400000  # past the MRAM

    edit(snapshots, _check_sources.SDK, change)
    (found,) = [f for f in findings(snapshots) if f.rule == "region containment"]
    assert found.at[-2:] == ("linker_script_sbl.ld", "MCU_MRAM")


def test_a_linker_region_with_a_negative_length_is_reported(snapshots):
    def change(data):
        scripts = data["socs"]["apollo510"]["linker"]["gcc"]["scripts"]
        scripts["linker_script_sbl.ld"]["MCU_MRAM"]["length"] = -1

    edit(snapshots, _check_sources.SDK, change)
    (found,) = findings(snapshots)
    assert (found.rule, found.at[-2:]) == (
        "region containment",
        ("linker_script_sbl.ld", "MCU_MRAM"),
    )
    assert found.message.endswith("has length -1")


def test_a_zero_length_region_is_checked_by_its_origin(snapshots):
    """An armclang ``EMPTY 0`` region, such as Apollo3's ARM_LIB_HEAP, occupies nothing."""

    def change(data, origin):
        scripts = data["socs"]["apollo510"]["linker"]["armclang"]["scripts"]
        scripts["linker_script_sbl.sct"]["ARM_LIB_HEAP"].update(origin=origin, length=0)

    edit(snapshots, _check_sources.SDK, lambda d: change(d, 0x2007B000))  # its own origin, in DTCM
    assert findings(snapshots) == []
    edit(snapshots, _check_sources.SDK, lambda d: change(d, 0x00800000))  # just past MRAM
    (found,) = findings(snapshots)
    assert found.rule == "region containment"


def test_an_unsized_scatter_region_is_checked_by_its_origin(snapshots):
    def change(data):
        soc = data["socs"]["apollo510"]
        soc["facts"]["values"]["NSX_SOC_SERIES"] = ["apollo4"]
        scripts = soc["linker"]["armclang"]["scripts"]["linker_script_sbl.sct"]
        del scripts["MCU_TCM"]["length"]  # inside the TCM
        scripts["MCU_MRAM"] = {"origin": 0x50000000}  # in no region and no aperture

    edit(snapshots, _check_sources.SDK, change)
    found = findings(snapshots)
    assert sorted(f.rule for f in found) == ["region containment", "series"]  # the rest still ran
    (outside,) = [f for f in found if f.rule == "region containment"]
    assert outside.at[-1] == "MCU_MRAM" and outside.message.startswith("0x50000000 (no length)")


def test_a_region_may_span_adjoining_regions(snapshots):
    def change(data):
        scripts = data["socs"]["apollo510"]["linker"]["gcc"]["scripts"]
        scripts["linker_script_sbl.ld"]["MCU_TCM"]["length"] = 0x80000 + 0x300000  # DTCM + SSRAM

    edit(snapshots, _check_sources.SDK, change)
    assert [f for f in findings(snapshots) if f.rule == "region containment"] == []


def test_an_aperture_end_is_exclusive(snapshots):
    def change(data):
        memory = data["boards"]["apollo510_evb"]["devicetree"]["memory"]
        memory["/memory@6ffff000"] = {"base": 0x6FFFF000, "size": 0x1000}  # MSPI0's last page
        memory["/memory@70000000"] = {"base": 0x70000000, "size": 1}  # at MSPI0_APERTURE_END_ADDR

    edit(snapshots, _check_sources.ZEPHYR, change)
    (found,) = findings(snapshots)
    assert (found.rule, found.at[-1]) == ("region containment", "/memory@70000000")


def test_a_zephyr_node_in_an_xip_aperture_is_external_memory(snapshots):
    def change(data):
        memory = data["boards"]["apollo510_evb"]["devicetree"]["memory"]
        memory["/memory@50000000"] = {"base": 0x50000000, "size": 0x1000}

    edit(snapshots, _check_sources.ZEPHYR, change)
    (found,) = findings(snapshots)
    assert (found.rule, found.at[-1]) == ("region containment", "/memory@50000000")


def test_an_xspi_aperture_and_its_secure_alias_are_external_memory():
    """atomiq110's spelling (#120): XSPI<n>'s apertures belong to controller xspimc<n>."""
    apollo510 = builtin(include_plugins=False).resolve("apollo510").soc
    soc = dataclasses.replace(apollo510, memory_controllers=("xspimc0",))
    block = {
        "registers": {
            "values": {
                "XSPI0_APERTURE_START_ADDR": 0x50000000,
                "XSPI0_APERTURE_END_ADDR": 0x50100000,
                "XSPI0_APERTURE_START_SECURE_ADDR": 0x50100000,
                "XSPI0_APERTURE_END_SECURE_ADDR": 0x50200000,
                "XSPI1_APERTURE_START_ADDR": 0x50200000,  # xspimc1, which soc lacks
                "XSPI1_APERTURE_END_ADDR": 0x50300000,
            }
        }
    }
    assert _check_sources._apertures(block, soc) == [
        (0x50000000, 0x50100000),
        (0x50100000, 0x50200000),
    ]


@pytest.mark.parametrize(("soc", "reported"), [("apollo510", False), ("apollo510b", True)])
def test_only_the_socs_own_controllers_have_external_memory(snapshots, soc, reported):
    """apollo510b reads apollo510's header, but its MSPI2 window is Reserved (DS-A510B p35)."""

    def change(data):
        scripts = data["socs"][soc]["linker"]["gcc"]["scripts"]
        scripts["linker_script_sbl.ld"]["PSRAM"] = {"origin": 0x84000000, "length": 0x1000}

    edit(snapshots, _check_sources.SDK, change)
    found = [(f.rule, f.at[1], f.at[-1]) for f in findings(snapshots)]
    assert found == ([("region containment", soc, "PSRAM")] if reported else [])


def test_an_sdk_record_must_cite_a_snapshotted_revision(snapshots):
    held = json.loads((snapshots / _check_sources.SDK).read_text())["metadata"]["sources"][0]

    def change(data):
        data["metadata"]["sources"][0]["revision"] = "v0.0.0"  # a revision no record cites

    edit(snapshots, _check_sources.SDK, change)
    revisions = [f for f in findings(snapshots) if f.rule == "sdk revision"]
    cited = f"nsx-ambiq-sdk@{held['revision']}"
    assert revisions and all(cited in f.message for f in revisions)


def test_an_overlay_record_must_cite_a_snapshotted_revision(snapshots):
    source = "repo:AmbiqAI/nsx-ambiq-sdk@v9.9.9:README.md:1"
    record = {"status": "sdk", "source": [source]}
    device = {"technology": "psram", "capacity": "8M", "provenance": record}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        document = {"schema_version": 1, "memory_devices": {"extra": device}}
        catalog = load_overlay(document, base=builtin(include_plugins=False))
    found = _check_sources.check(catalog, snapshots).findings
    assert [f.rule for f in found] == ["sdk revision"]
    assert found[0].message.startswith("memory_devices.extra cites AmbiqAI/nsx-ambiq-sdk@v9.9.9")


def test_an_id_the_catalog_lacks_needs_an_exception(snapshots):
    path = snapshots / "exceptions.yaml"
    document = yaml.safe_load(path.read_text())
    document["exceptions"] = [e for e in document["exceptions"] if e["at"] != ["socs", "apollo2"]]
    path.write_text(yaml.safe_dump(document))
    (found,) = findings(snapshots)
    assert (found.at, found.rule) == (("socs", "apollo2"), _check_sources.MISSING)


def test_an_exception_that_covers_nothing_is_stale(snapshots):
    path = snapshots / "exceptions.yaml"
    document = yaml.safe_load(path.read_text())
    stale = {"snapshot": "nsx-ambiq-sdk.json", "at": ["socs", "apollo510"], "rule": "series"}
    document["exceptions"].append({**stale, "reason": "x", "issue": "#1"})
    path.write_text(yaml.safe_dump(document))
    result = _check_sources.check(builtin(include_plugins=False), snapshots)
    assert [e.at for e in result.stale] == [("socs", "apollo510")]
    assert not result.ok


def test_an_exception_under_an_id_the_catalog_lacks_is_not_stale(snapshots):
    path = snapshots / "exceptions.yaml"
    entry = (
        "  - snapshot: nsx-ambiq-sdk.json\n"
        "    at: [socs, apollo2, linker, gcc, scripts, linker_script.ld]\n"
        "    rule: region containment\n"
        "    reason: apollo2 is left out of the catalog.\n"
        '    issue: "#79"\n'
    )
    path.write_text(path.read_text() + entry)
    result = _check_sources.check(builtin(include_plugins=False), snapshots)
    (added,) = [
        e for e in _check_sources.load_exceptions(path) if e.at[1] == "apollo2" and e.at[2:]
    ]
    assert added not in [e for _, e in result.excepted]
    assert result.stale == ()


def test_a_typo_under_an_id_the_catalog_lacks_is_stale(snapshots):
    path = snapshots / "exceptions.yaml"
    entry = (
        "  - snapshot: nsx-ambiq-sdk.json\n"
        "    at: [socs, apollo2, linker, gcc, scripts, no_such_script.ld]\n"
        "    rule: region containment\n"
        "    reason: a typo.\n"
        '    issue: "#79"\n'
    )
    path.write_text(path.read_text() + entry)
    result = _check_sources.check(builtin(include_plugins=False), snapshots)
    assert [e.at[-1] for e in result.stale] == ["no_such_script.ld"]
    assert "stale exception (covers no finding)" in _check_sources.render(result)


def test_the_cli_exits_1_on_a_disagreement(snapshots):
    assert runner.invoke(app, ["check-sources", "--snapshots", str(snapshots)]).exit_code == 0

    def change(data):
        data["socs"]["apollo510"]["facts"]["values"]["NSX_SOC_SERIES"] = ["apollo4"]

    edit(snapshots, _check_sources.SDK, change)
    result = runner.invoke(app, ["check-sources", "--snapshots", str(snapshots)])
    assert result.exit_code == 1
    assert "socs.apollo510.facts.values.NSX_SOC_SERIES: series" in result.output
