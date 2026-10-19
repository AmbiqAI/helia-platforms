"""``check-sources``: the built-in catalog against the committed snapshots (ADR 0006, #72)."""

import json
import shutil
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from helia_platforms import _check_sources
from helia_platforms.catalog import builtin
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


def test_the_flash_load_address_follows_the_board_provisioning(snapshots):
    def change(data):
        data["socs"]["apollo510"]["facts"]["values"]["NSX_SEGGER_PF_ADDR"] = ["0x00400000"]

    edit(snapshots, _check_sources.SDK, change)
    (found,) = [f for f in findings(snapshots) if f.rule == "flash load address"]
    assert found.at == ("boards", "apollo510_evb", "NSX_SEGGER_PF_ADDR")
    assert found.message == "catalog 0x410000, snapshot 0x400000"


def test_a_board_debug_override_wins_over_the_soc_facts(snapshots):
    def change(data):
        data["boards"]["apollo510_evb"]["debug"]["values"]["NSX_SEGGER_CPUFREQ"] = ["48000000"]

    edit(snapshots, _check_sources.NSX, change)
    (found,) = [f for f in findings(snapshots) if f.rule == "trace clock"]
    assert found.at == ("boards", "apollo510_evb", "debug", "NSX_SEGGER_CPUFREQ")


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


def test_a_region_may_span_adjoining_regions(snapshots):
    def change(data):
        scripts = data["socs"]["apollo510"]["linker"]["gcc"]["scripts"]
        scripts["linker_script_sbl.ld"]["MCU_TCM"]["length"] = 0x80000 + 0x300000  # DTCM + SSRAM

    edit(snapshots, _check_sources.SDK, change)
    assert [f for f in findings(snapshots) if f.rule == "region containment"] == []


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
