"""Tests for ``helia-platforms list`` and ``show`` (#70)."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from conftest import BASE_DOCUMENT, RECORD, SDK_SOURCE
from helia_platforms.cli import app

runner = CliRunner()


@pytest.fixture
def overlay(tmp_path: Path):
    """Write a fixture document as an overlay over the built-in catalog."""

    def write(document=None) -> Path:
        document = document or copy.deepcopy(BASE_DOCUMENT)
        del document["cores"]["cortex-m55"]  # the built-in catalog under the overlay has it
        path = tmp_path / "fixture.yaml"
        path.write_text(yaml.safe_dump(document))
        return path

    return write


def run(*args: str):
    return runner.invoke(app, [*args, "--builtin-only"])


def rows(output: str, label: str) -> list[str]:
    """Each row with ``label``, its wrapped lines joined and its spacing collapsed."""
    found: list[str] = []
    matching = False
    for line in output.splitlines():
        if line.startswith(" " * 29) and matching:
            found[-1] += " " + line.strip()
        elif line.startswith("  ") and not line.startswith("   "):
            matching = line[2:].startswith(f"{label} ")
            if matching:
                found.append(" ".join(line.split()))
        else:
            matching = False
    return found


def test_list_prints_every_kind_with_its_source(overlay, tmp_path):
    result = run("list", "--overlay", str(overlay()))
    assert result.exit_code == 0, result.output
    for title in ("socs", "implementations", "parts", "boards"):
        assert f"\n{title}\n" in f"\n{result.output}"
    path = str(tmp_path / "fixture.yaml")
    assert f"soc_a                      series test  (overlay:{path})" in result.output
    assert "board_a                    evaluation board, part PART-A" in result.output


def test_list_names_an_fpga_boards_implementation(overlay):
    document = copy.deepcopy(BASE_DOCUMENT)
    document["implementations"] = {"soc_a_fpga": {"soc": "soc_a", "kind": "fpga"}}
    document["boards"]["fpga_a"] = {"category": "fpga", "implementation": "soc_a_fpga"}
    path = str(overlay(document))
    result = run("list", "boards", "--overlay", path)
    assert result.exit_code == 0, result.output
    assert "fpga_a                     fpga board, implementation soc_a_fpga" in result.output
    show = run("show", "fpga_a", "--overlay", path)
    assert show.exit_code == 0, show.output
    assert "implementation soc_a_fpga" in " ".join(rows(show.output, "board")[0].split())


def test_list_one_kind(overlay):
    result = run("list", "boards", "--overlay", str(overlay()))
    assert result.exit_code == 0
    assert result.output.startswith("boards\n")
    assert "socs" not in result.output


def test_list_rejects_an_unknown_kind():
    result = run("list", "widgets")
    assert result.exit_code == 2
    assert "unknown kind 'widgets'" in result.output


def test_show_prints_a_status_beside_each_row(overlay):
    document = copy.deepcopy(BASE_DOCUMENT)
    tcm = document["socs"]["soc_a"]["memories"]["tcm"]
    tcm["size"] = {
        "value": "512K",
        "provenance": {**RECORD, "status": "sdk", "source": [SDK_SOURCE]},
    }
    result = run("show", "board_a", "--overlay", str(overlay(document)))
    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    (tcm,) = rows(result.output, "tcm")
    assert "technology sram, attachment tcm, base 0x20000000, size 512K" in tcm
    assert tcm.endswith("[datasheet; size: sdk]")
    # board_a carries no record, so an overlay value resolves to unverified.
    assert any(line.startswith("  board ") and line.endswith("[unverified]") for line in lines)
    assert "  usable nvm                 4032K (4128768 bytes; core 0, computed)" in lines
    assert "  flash load address         0x00410000 (core 0, computed)" in lines


def test_show_prints_records_and_sources_on_request(overlay):
    path = overlay()
    result = run("show", "board_a", "--provenance", "--sources", "--overlay", str(path))
    assert result.exit_code == 0, result.output
    assert "doc:DS-TEST@1.0:p1" in result.output
    assert "verified 2026-10-05 by tester" in result.output
    flat = " ".join(result.output.split())
    assert f"source of board board_a overlay:{path}" in flat


def test_show_resolves_aliases_and_compositions(overlay):
    document = copy.deepcopy(BASE_DOCUMENT)
    document["boards"]["board_a"]["aliases"] = ["evb_a"]
    document["compositions"] = {"board_a_plus": {"board": "board_a"}}
    path = overlay(document)
    for name in ("evb_a", "board_a_plus"):
        result = run("show", name, "--overlay", str(path))
        assert result.exit_code == 0, result.output
        assert "board_a (board, overlay, embargoed)" in result.output


def test_show_selects_a_boot_configuration(overlay):
    result = run("show", "board_a", "--boot", "nbl", "--overlay", str(overlay()))
    assert result.exit_code == 0
    assert (
        "  flash load address         0x00400000 (core 0, computed)" in result.output.splitlines()
    )


def test_show_an_implementation_target(overlay):
    document = copy.deepcopy(BASE_DOCUMENT)
    document["implementations"] = {
        "soc_a_fpga": {"soc": "soc_a", "kind": "fpga", "subset": {"memories_removed": ["ssram"]}}
    }
    result = run("show", "soc_a_fpga", "--overlay", str(overlay(document)))
    assert result.exit_code == 0, result.output
    assert "soc_a_fpga, soc soc_a, kind fpga" in result.output
    assert not any(line.strip().startswith("ssram ") for line in result.output.splitlines())


def test_show_suggests_close_names_for_an_unknown_one(overlay):
    result = run("show", "board_b", "--overlay", str(overlay()))
    assert result.exit_code == 1
    assert "unknown platform 'board_b'; did you mean board_a" in result.output


def test_show_lists_the_candidates_of_a_shorthand():
    result = run("show", "AP510")
    assert result.exit_code == 1
    assert "'AP510' is a family shorthand and names no single target; use one of apollo510" in (
        result.output
    )


def test_a_bad_overlay_prints_its_problems(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("schema_version: 1\nmemory_devices:\n  dev: {technology: psram, capacity: 8m}\n")
    result = run("show", "apollo510", "--overlay", str(bad))
    assert result.exit_code == 1
    assert "capacity" in result.output


def test_show_on_the_built_in_data():
    result = run("show", "apollo510_evb")
    assert result.exit_code == 0, result.output
    assert "psram0" in result.output and "capacity: measured" in result.output


def add_radio(document):
    document["socs"]["soc_a"]["cores"].append(
        {
            "id": "radio_m4",
            "role": "radio",
            "core": "cortex-m4",
            "clock_domain": "cpu",
            "options": {"fpu": "fpv4-sp-d16", "mve": "none"},
            "programmable_by": "vendor",
        }
    )


def test_show_computes_the_flash_address_of_each_core_with_a_start(overlay):
    document = copy.deepcopy(BASE_DOCUMENT)
    add_radio(document)
    nbl = document["socs"]["soc_a"]["boot_configs"]["nbl"]
    nbl["app_start"] = {"radio_m4": {"region": "nvm", "offset": "2M"}}
    result = run("show", "board_a", "--boot", "nbl", "--overlay", str(overlay(document)))
    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    assert "  flash load address         0x00600000 (core 1, computed)" in lines
    assert "(core 0, computed)" not in result.output.replace("usable nvm", "")


def test_show_reports_a_start_region_with_no_base(overlay):
    document = copy.deepcopy(BASE_DOCUMENT)
    del document["socs"]["soc_a"]["memories"]["nvm"]["base"]
    result = run("show", "board_a", "--overlay", str(overlay(document)))
    assert result.exit_code == 0, result.output
    assert "flash load address" in result.output
    assert "region 'nvm' has no base" in result.output


def test_show_gives_each_access_field_its_own_status(overlay):
    document = copy.deepcopy(BASE_DOCUMENT)
    sdk = {**RECORD, "status": "sdk", "source": [SDK_SOURCE]}
    access = document["socs"]["soc_a"]["access"]
    access[0]["port"] = {"value": 0, "provenance": sdk}
    access[1]["guidance"] = {"value": "discouraged", "provenance": sdk}
    access.append(
        {
            "master": "cm55_0",
            "target": "nvm",
            "access": "direct",
            "address": {"value": 0x00400000, "provenance": sdk},
        }
    )
    result = run("show", "board_a", "--overlay", str(overlay(document)))
    assert result.exit_code == 0, result.output
    entries = rows(result.output, "entry")
    for start, end in (
        ("entry master npu_0, target ssram", "[datasheet; port: sdk]"),
        ("entry master npu_0, target tcm", "[datasheet; guidance: sdk]"),
        ("entry master cm55_0, target nvm", "[datasheet; address: sdk]"),
    ):
        line = next(line for line in entries if line.startswith(start))
        assert line.endswith(end), line


def test_show_gives_each_operating_point_domain_its_own_status(overlay):
    document = copy.deepcopy(BASE_DOCUMENT)
    sdk = {**RECORD, "status": "sdk", "source": [SDK_SOURCE]}
    lp = document["socs"]["soc_a"]["operating_points"]["lp"]
    lp["domains"]["cpu"] = {"value": "lp", "provenance": sdk}
    result = run("show", "board_a", "--overlay", str(overlay(document)))
    assert result.exit_code == 0, result.output
    line = next(line for line in result.output.splitlines() if "point lp" in line)
    assert line.endswith("[sdk; domains.npu: datasheet]"), line


def test_show_sources_include_the_core_ip_blocks(overlay, tmp_path):
    document = copy.deepcopy(BASE_DOCUMENT)
    path = overlay(document)
    raw = yaml.safe_load(path.read_text())
    raw["cores"] = {"cortex-m33": {"arch": "armv8-m", "pmu": "dwt", "has_dsp_extension": True}}
    raw["socs"]["soc_a"]["cores"][0]["core"] = "cortex-m33"
    path.write_text(yaml.safe_dump(raw))
    result = run("show", "board_a", "--sources", "--overlay", str(path))
    assert result.exit_code == 0, result.output
    flat = " ".join(result.output.split())
    assert f"source of core cortex-m33 overlay:{tmp_path / 'fixture.yaml'}" in flat


def test_show_an_external_region_whose_interface_has_no_base(overlay):
    document = copy.deepcopy(BASE_DOCUMENT)
    del document["boards"]["board_a"]["interfaces"]["mspi0"]["aperture_base"]
    result = run("show", "board_a", "--overlay", str(overlay(document)))
    assert result.exit_code == 0, result.output
    (psram,) = rows(result.output, "psram0")
    assert "(8M no base, computed)" in psram


def test_show_prints_usable_nvm_for_each_core(overlay):
    document = copy.deepcopy(BASE_DOCUMENT)
    add_radio(document)
    soc = document["socs"]["soc_a"]
    for master in ("cm55_0", "radio_m4"):
        soc["access"].append({"master": master, "target": "nvm", "access": "direct"})
    document["parts"]["PART-A"]["image_slots"] = {
        "radio": {
            "core": "radio_m4",
            "region": "nvm",
            "offset": "3M",
            "size": "1M",
            "supplier": "vendor",
        }
    }
    result = run("show", "board_a", "--overlay", str(overlay(document)))
    assert result.exit_code == 0, result.output
    # Each core loses the SBL's 64K; core 0 also loses the radio's 1M image slot.
    assert rows(result.output, "usable") == [
        "usable nvm 3008K (3080192 bytes; core 0, computed)",
        "usable nvm 4032K (4128768 bytes; core 1, computed)",
    ]
