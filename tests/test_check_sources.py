"""``check-sources``: the built-in catalog against the committed snapshots (ADR 0006, #72)."""

import json
import shutil
import warnings
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from helia_platforms import _check_sources
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
        *((v, v) for v in ("MAYBE", "0x1")),  # no CMake boolean, so it equals neither
    ],
)
def test_a_flag_is_read_as_cmake_reads_it(value, read):
    assert _check_sources._flag({"NSX_SOC_HAS_MVE": [value]}, "NSX_SOC_HAS_MVE") == read


@pytest.mark.parametrize(("value", "rules"), [("Y", []), ("N", ["mve"]), ("MAYBE", ["mve"])])
def test_a_flag_is_compared_with_the_catalog(snapshots, value, rules):
    def change(data):
        data["socs"]["apollo510"]["facts"]["values"]["NSX_SOC_HAS_MVE"] = [value]  # catalog: true

    edit(snapshots, _check_sources.SDK, change)
    assert [f.rule for f in findings(snapshots)] == rules


def test_the_flash_load_address_follows_the_board_provisioning(snapshots):
    def change(data):
        data["socs"]["apollo510"]["facts"]["values"]["NSX_SEGGER_PF_ADDR"] = ["0x00400000"]

    edit(snapshots, _check_sources.SDK, change)
    (found,) = [f for f in findings(snapshots) if f.rule == "flash load address"]
    at = ("socs", "apollo510", "facts", "values", "NSX_SEGGER_PF_ADDR")  # where it comes from
    assert (found.snapshot, found.at) == (_check_sources.SDK, at)
    assert found.message == "catalog 0x410000, snapshot 0x400000"


def test_a_board_debug_override_wins_over_the_soc_facts(snapshots):
    def change(data):
        data["boards"]["apollo510_evb"]["debug"]["values"]["NSX_SEGGER_CPUFREQ"] = ["48000000"]

    edit(snapshots, _check_sources.NSX, change)
    (found,) = [f for f in findings(snapshots) if f.rule == "trace clock"]
    at = ("boards", "apollo510_evb", "debug", "values", "NSX_SEGGER_CPUFREQ")
    assert (found.snapshot, found.at) == (_check_sources.NSX, at)


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
            _check_sources.NSX,
            lambda d: d["boards"]["apollo510_evb"]["debug"]["values"].update(
                NSX_SEGGER_CPUFREQ=["48000000"]
            ),
            ["boards", "apollo510_evb", "debug", "values", "NSX_SEGGER_CPUFREQ"],
            id="board override",
        ),
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


@pytest.mark.parametrize(
    "change",
    [
        pytest.param(lambda b, s: b.pop("debug"), id="no debug.cmake"),
        pytest.param(lambda b, s: b.pop("linker"), id="no memory.cmake"),
        pytest.param(lambda b, s: s["linker"]["gcc"].pop("default"), id="no sdk default"),
    ],
)
def test_a_snapshot_may_omit_its_optional_sections(snapshots, change):
    nsx = json.loads((snapshots / _check_sources.NSX).read_text())
    sdk = json.loads((snapshots / _check_sources.SDK).read_text())
    change(nsx["boards"]["apollo510_evb"], sdk["socs"]["apollo510"])
    (snapshots / _check_sources.NSX).write_text(json.dumps(nsx))
    (snapshots / _check_sources.SDK).write_text(json.dumps(sdk))
    assert {f.rule for f in findings(snapshots)} <= {"default scripts"}


def test_a_default_script_the_board_drops_is_reported(snapshots):
    edit(
        snapshots,
        _check_sources.NSX,
        lambda d: d["boards"]["apollo510_evb"]["linker"]["defaults"].pop("gcc"),
    )
    (found,) = findings(snapshots)
    assert (found.rule, found.at[-1]) == ("default scripts", "gcc")


def test_the_board_soc_is_matched_to_the_sdk_ignoring_case(snapshots):
    edit(
        snapshots,
        _check_sources.NSX,
        lambda d: d["boards"]["apollo510_evb"]["board"]["values"].update(soc="Apollo510"),
    )

    def change(data):
        data["socs"]["apollo510"]["facts"]["values"]["NSX_SEGGER_PF_ADDR"] = ["0x00400000"]

    edit(snapshots, _check_sources.SDK, change)
    assert [f.rule for f in findings(snapshots)] == ["flash load address"]


def test_board_toolchains_are_compared_ignoring_the_soc_case(snapshots):
    def change(data):
        values = data["boards"]["apollo510_evb"]["board"]["values"]
        values.update(soc="Apollo510", toolchains=["armclang"])

    edit(snapshots, _check_sources.NSX, change)
    assert [f.rule for f in findings(snapshots)] == ["toolchains"]


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


def test_a_linker_region_outside_every_run_of_regions_is_reported(snapshots):
    def change(data):
        scripts = data["socs"]["apollo510"]["linker"]["gcc"]["scripts"]
        scripts["linker_script_sbl.ld"]["MCU_MRAM"]["length"] = 0x400000  # past the MRAM

    edit(snapshots, _check_sources.SDK, change)
    (found,) = [f for f in findings(snapshots) if f.rule == "region containment"]
    assert found.at[-2:] == ("linker_script_sbl.ld", "MCU_MRAM")


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


def test_board_toolchains_and_default_scripts_are_compared(snapshots):
    def change(data):
        board = data["boards"]["apollo510_evb"]
        board["board"]["values"]["toolchains"] = ["armclang"]
        board["linker"]["defaults"]["gcc"] = (
            "modules/nsx-core/src/apollo510/gcc/linker_script_nbl.ld"
        )

    edit(snapshots, _check_sources.NSX, change)
    assert sorted(f.rule for f in findings(snapshots)) == ["default scripts", "toolchains"]


def test_an_sdk_record_must_cite_a_snapshotted_revision(snapshots):
    def change(data):
        data["metadata"]["sources"][0]["revision"] = "v5.2.26"

    edit(snapshots, _check_sources.SDK, change)
    revisions = [f for f in findings(snapshots) if f.rule == "sdk revision"]
    assert revisions and all("nsx-ambiq-sdk@v5.2.24" in f.message for f in revisions)


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


def test_an_exception_under_an_id_the_catalog_lacks_is_not_stale():
    result = _check_sources.check(builtin(include_plugins=False), ROOT / "snapshots")
    held = [e for _, e in result.excepted]
    containment = [
        e
        for e in _check_sources.load_exceptions(ROOT / "snapshots/exceptions.yaml")
        if e.rule == "region containment"
    ]
    assert containment and not any(e in held for e in containment)
    assert result.stale == ()


def test_the_cli_exits_1_on_a_disagreement(snapshots):
    assert runner.invoke(app, ["check-sources", "--snapshots", str(snapshots)]).exit_code == 0

    def change(data):
        data["socs"]["apollo510"]["facts"]["values"]["NSX_SOC_SERIES"] = ["apollo4"]

    edit(snapshots, _check_sources.SDK, change)
    result = runner.invoke(app, ["check-sources", "--snapshots", str(snapshots)])
    assert result.exit_code == 1
    assert "socs.apollo510.facts.values.NSX_SOC_SERIES: series" in result.output
