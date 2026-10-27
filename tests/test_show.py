"""Tests that ``show`` prints every fact a target's entries state, with that fact's record (#70)."""

from __future__ import annotations

import contextlib
import copy

import pytest

from conftest import BASE_DOCUMENT, RECORD, SDK_SOURCE
from helia_platforms import _show
from helia_platforms.catalog import builtin, load_overlay

SDK = {**RECORD, "status": "sdk", "source": [SDK_SOURCE]}
#: Implementation keys merged into the realized Soc, whose rows print them.
MERGED = {"memories", "access", "clock_domains", "operating_points", "boot_configs", "default_boot"}
CHARACTERIZATION = {"read_latency_ns": 12.5, "max_outstanding": 4, "bandwidth_fraction": 0.5}


def full_document() -> dict:
    """The base document with nearly every optional fact set."""
    document = copy.deepcopy(BASE_DOCUMENT)
    del document["cores"]  # the built-in catalog under the overlay has them
    soc = document["socs"]["soc_a"]
    soc["revision"] = "B0"
    soc["npus"][0].update(axi_width_bits=64, base_address=0x40020000, irq=12)
    soc["accelerators"] = [
        {
            "id": "gpu_0",
            "kind": "gpu",
            "ip": "nema",
            "driven_by": "cm55_0",
            "clock_domain": "cpu",
            "base_address": 0x40030000,
            "irq": 13,
        }
    ]
    tcm = soc["memories"]["tcm"]
    tcm.update(alternate_bases=[0x30000000], executable=True, writeable=False, cacheable=True)
    tcm["characterization"] = CHARACTERIZATION
    soc["access"].append(
        {
            "master": "cm55_0",
            "target": "nvm",
            "access": "direct",
            "requires_awake": ["mcu"],
            "reason": "the cache path",
            "address": 0x00400000,
            "characterization": CHARACTERIZATION,
        }
    )
    soc["clock_domains"]["cpu"]["lp"]["hal_mode"] = "LOW_POWER"
    soc["operating_points"]["lp"]["hal_mode"] = "LP_MODE"
    soc["sdk"] = {
        "c_define": "AM_PART_A",
        "cmsis_header": "a.h",
        "trace_clock_mhz": 96,
        "hal_enums": {"sram": "AM_HAL_SRAM"},
        "build": {"abi": "thumbv8.1m", "float_abi": "hard"},
    }
    soc["derives_from"] = "soc_a"
    document["parts"]["PART-A"].update(
        package="BGA",
        radio="none",
        jlink_device="PART-A",
        image_slots={
            "app": {
                "core": "cm55_0",
                "region": "nvm",
                "offset": "64K",
                "size": "1M",
                "supplier": "customer",
            }
        },
    )
    board = document["boards"]["board_a"]
    board.update(revision="2.0", jlink_device="BOARD-A", trace_clock_mhz=48)
    board["interfaces"]["mspi0"]["modes"] = ["octal"]
    board["interfaces"]["iom0"] = {"controller": "iom0"}  # left unpopulated
    soc["peripherals"].append("mspi1")
    soc["memory_controllers"].append("mspi1")
    board["interfaces"]["mspi1"] = {
        "controller": "mspi1",
        "aperture_base": 0x70000000,
        "aperture_max": "256M",
    }
    document["memory_devices"]["psram_8m"].update(
        driver_family="aps", modes=["octal"], characterization=CHARACTERIZATION
    )
    document["addons"] = {
        "shield": {
            "fits_boards": ["board_a"],
            "occupies": ["mspi1"],
            "population": {"mspi1": "psram_8m"},
            "revision": "1",
        }
    }
    document["compositions"] = {"board_a_shield": {"board": "board_a", "addons": ["shield"]}}
    document["implementations"] = {
        "soc_a_fpga": {
            "soc": "soc_a",
            "kind": "fpga",
            "model": "vu19p",
            "subset": {"memories_removed": ["ssram"], "max_cpu_mhz": 96},
            "provisioning": "nbl",
            "jlink_device": "FPGA",
            "trace_clock_mhz": 24,
            "interfaces": {
                "mspi0": {"controller": "mspi0", "aperture_base": 0x60000000, "aperture_max": "8M"}
            },
            "population": {"mspi0": "psram_8m"},
        }
    }
    return document


@pytest.fixture
def catalog():
    return load_overlay(full_document(), base=builtin(include_plugins=False))


def row_texts(target, label: str) -> list[str]:
    """The text and status of each row with ``label``."""
    return [
        f"{r.text}  {_show._status(r.facts)}"
        for _, rows in _show.sections(target)
        for r in rows
        if r.label == label
    ]


def printed(target, **kwargs) -> set[_show.Where]:
    return {f.where for _, rows in _show.sections(target, **kwargs) for r in rows for f in r.facts}


@pytest.mark.parametrize("name", ["board_a", "board_a_shield", "PART-A", "soc_a", "soc_a_fpga"])
def test_every_stated_fact_is_printed(catalog, name):
    target = catalog.resolve(name)
    stated = {
        w
        for w in _show.stated_facts(target)
        if not (w[0] == "implementations" and w[2][0] in MERGED)
    }
    assert stated - printed(target) == set()


def test_the_built_in_targets_print_every_stated_fact():
    catalog = builtin(include_plugins=False)
    for name in ("apollo510_evb", "AP510NFA-IBR", "apollo510"):
        target = catalog.resolve(name)
        assert _show.stated_facts(target) - printed(target) == set(), name


def test_a_default_the_data_does_not_state_is_not_printed(catalog):
    target = catalog.resolve("board_a")
    (nvm,) = row_texts(target, "nvm")
    assert "executable" not in nvm  # the base document never sets it
    (tcm,) = row_texts(target, "tcm")
    assert "executable yes, writeable no, cacheable yes" in tcm


def test_each_fact_gets_its_own_record(catalog):
    document = full_document()
    soc = document["socs"]["soc_a"]
    soc["accelerators"][0]["ip"] = {"value": "nema", "provenance": SDK}
    document["implementations"]["soc_a_fpga"]["model"] = {"value": "vu19p", "provenance": SDK}
    document["boards"]["board_a"]["population"]["mspi0"] = {
        "value": "psram_8m",
        "provenance": SDK,
    }
    catalog = load_overlay(document, base=builtin(include_plugins=False))
    board = catalog.resolve("board_a")
    assert row_texts(board, "gpu_0")[0].endswith("ip: sdk]")
    assert row_texts(board, "psram0")[0].endswith("population.mspi0: sdk]")
    fpga = catalog.resolve("soc_a_fpga")
    assert row_texts(fpga, "implementation")[0].endswith("[unverified; model: sdk]")


@pytest.mark.parametrize(
    ("name", "boot", "selected"),
    [
        ("board_a", None, "sbl (by the board's provisioning)"),
        ("soc_a_fpga", None, "nbl (by the implementation's provisioning)"),
        ("soc_a", None, "sbl (by the soc's default_boot)"),
        ("board_a", "nbl", "nbl (by --boot)"),
    ],
)
def test_the_selected_boot_names_the_fact_that_selects_it(catalog, name, boot, selected):
    with pytest.warns() if boot else contextlib.nullcontext():
        target = catalog.resolve(name, boot=boot)
    rows = [r for _, rs in _show.sections(target, requested_boot=boot) for r in rs]
    (row,) = [r for r in rows if r.label == "selected boot"]
    assert row.text == selected
    assert bool(row.facts) == (boot is None)


def test_sources_list_the_composition(catalog):
    target = catalog.resolve("board_a_shield")
    labels = dict(_show._source_labels(target))
    assert labels["composition board_a_shield"].startswith("overlay:")
    assert "addon shield" in labels


def test_a_float_prints_in_full():
    document = full_document()
    tcm = document["socs"]["soc_a"]["memories"]["tcm"]
    tcm["characterization"] = {"bandwidth_fraction": 0.9999999, "read_latency_ns": 1.0}
    catalog = load_overlay(document, base=builtin(include_plugins=False))
    (row,) = row_texts(catalog.resolve("board_a"), "tcm")
    assert (
        "characterization.read_latency_ns 1, characterization.bandwidth_fraction 0.9999999" in row
    )


def test_a_record_on_a_removed_access_pair_covers_the_pair():
    document = full_document()
    subset = document["implementations"]["soc_a_fpga"]["subset"]
    subset["access_removed"] = [{"master": "npu_0", "target": "tcm"}]
    subset["provenance"] = SDK
    catalog = load_overlay(document, base=builtin(include_plugins=False))
    (row,) = row_texts(catalog.resolve("soc_a_fpga"), "subset")
    assert "subset.access_removed.npu_0@tcm.master npu_0" in row
    assert row.endswith("[sdk]"), row


def test_each_population_row_shows_its_own_device_and_region():
    """``show`` pairs each interface with the region resolution computed for it."""
    document = full_document()
    document["memory_devices"]["psram_2m"] = {"technology": "psram", "capacity": "2M"}
    board = document["boards"]["board_a"]
    board["interfaces"]["iom0"] = {
        "controller": "iom0",
        "aperture_base": 0x68000000,
        "aperture_max": "2M",
    }
    board["population"] = {  # not in name order
        "mspi0": "psram_8m",
        "iom0": {"value": "psram_2m", "provenance": SDK},
    }
    target = load_overlay(document, base=builtin(include_plugins=False)).resolve("board_a")
    (psram0,) = row_texts(target, "psram0")
    assert psram0.startswith("population.iom0 psram_2m, controller iom0,")
    assert "(2M at 0x68000000, computed)" in psram0 and psram0.endswith("population.iom0: sdk]")
    (psram1,) = row_texts(target, "psram1")
    assert psram1.startswith("population.mspi0 psram_8m, controller mspi0,")
    assert "(8M at 0x60000000, computed)" in psram1 and psram1.endswith("[unverified]")
