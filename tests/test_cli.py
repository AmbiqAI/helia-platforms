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
        del document["cores"]  # the built-in catalog under the overlay has them
        path = tmp_path / "fixture.yaml"
        path.write_text(yaml.safe_dump(document))
        return path

    return write


def run(*args: str):
    return runner.invoke(app, [*args, "--builtin-only"])


def test_list_prints_every_kind_with_its_source(overlay, tmp_path):
    result = run("list", "--overlay", str(overlay()))
    assert result.exit_code == 0, result.output
    for title in ("socs", "implementations", "parts", "boards"):
        assert f"\n{title}\n" in f"\n{result.output}"
    path = str(tmp_path / "fixture.yaml")
    assert f"soc_a                      series test  (overlay:{path})" in result.output
    assert "board_a                    evaluation board, part PART-A" in result.output


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
    tcm_line = next(line for line in lines if line.strip().startswith("tcm "))
    assert "sram tcm, 0x20000000, 512K" in tcm_line
    assert tcm_line.endswith("[datasheet; size: sdk]")
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
    assert "soc_a_fpga (fpga)" in result.output
    assert not any(line.strip().startswith("ssram ") for line in result.output.splitlines())


def test_show_suggests_close_names_for_an_unknown_one(overlay):
    result = run("show", "board_b", "--overlay", str(overlay()))
    assert result.exit_code == 1
    assert "unknown platform 'board_b'; did you mean board_a" in result.output


def test_show_lists_the_candidates_of_a_shorthand():
    result = run("show", "AP510")
    assert result.exit_code == 1
    assert "names several targets" in result.output


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
