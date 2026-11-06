import pytest

from helia_platforms import AmbiguousPlatform, Catalog, builtin, resolve_board
from helia_platforms.catalog import load_overlay
from helia_platforms.errors import FormatError


@pytest.fixture(scope="module")
def catalog() -> Catalog:
    return builtin(include_plugins=False)


def test_the_packaged_data_loads(catalog):
    assert {s.id for s in catalog.socs()} == {
        "apollo510",
        "apollo510b",
        "apollo510L",
        "apollo330P",
        "apollo4p",
        "apollo4l",
        "apollo3",
        "apollo3p",
        "atomiq110",
    }
    assert [i.id for i in catalog.implementations() if i.kind == "fpga"] == ["atomiq110_fpga"]
    assert {c.id for c in catalog.cores()} == {"cortex-m55", "cortex-m4", "cortex-m0"}
    assert {
        p.id
        for p in catalog.parts()
        if p.soc in {"apollo510", "apollo510b", "apollo4p", "apollo4l", "apollo3", "apollo3p"}
    } == {
        "AP510NFA-CBR",
        "AP510NFA-IBR",
        "AP510NFA-CCR",
        "AP510BFA-CBR",
        "AMAP42KP-KBR",
        "AMA4B2KP-KBR",
        "AMA4B2KP-KXR",
        "AMAP42KL-KBR",
        "AMA4B2KL-KXR",
        *("AMA3B1KK-KBR-B0", "AMA3B1KK-KCR-B0", "AMA3B1KK-KCR-TB", "AMA3B1KK-KQR"),
        *("AMAP31KK-KBR", "AMAP31KK-KCR", "AMA3B2KK-KBR"),
    }
    assert {b.id for b in catalog.boards()} == {
        "apollo510_evb",
        "apollo510b_evb",
        "apollo510dL_evb",
        "apollo330mP_evb",
        "apollo4p_evb",
        "apollo4p_blue_kbr_evb",
        "apollo4p_blue_kxr_evb",
        "apollo4l_evb",
        "apollo4l_blue_evb",
        "apollo3_evb",
        "apollo3p_evb",
        "atomiq110_fpga_turbo",
    }
    assert {a.id for a in catalog.addons()} == {"apollo4p_disp_shield", "cygnus"}
    assert {d.id for d in catalog.memory_devices()} == {
        "APS512XX",
        "APS256XXN",
        "IS25WX064",
        "APS6404L",
    }


def test_apollo510_evb_answers_the_consumer_queries(catalog):
    """RFC 0002's heliaAOT and profiler questions, against #63's proposal section 1.6."""
    target = catalog.resolve("apollo510_evb")
    assert target.capabilities == {"dsp", "fp16", "fp32", "fp64", "mve", "mve_fp", "pmu", "psram"}
    assert {m.name: (m.base, m.size) for m in target.memories()} == {
        "itcm": (0x00000000, 256 * 1024),
        "dtcm": (0x20000000, 512 * 1024),
        "ssram": (0x20080000, 3 * 1024 * 1024),
        "mram": (0x00400000, 4 * 1024 * 1024),
        "psram0": (0x60000000, 64 * 1024 * 1024),
    }
    assert dict(target.usable_nvm()) == {"mram": 4 * 1024 * 1024 - 64 * 1024}
    assert target.flash_load_address() == 0x00410000
    assert (target.cpu_mhz(), target.cpu_mhz("hp")) == (96, 250)
    assert target.default_operating_point.name == "lp"
    assert target.jlink_device == "AP510NFA-CBR"
    assert target.trace_clock_mhz == 96


_ATOMIQ110_ON_DIE = {
    "itcm": (0x00000000, 256 * 1024),
    "dtcm": (0x20000000, 512 * 1024),
    "ssram": (0x21000000, 3 * 1024 * 1024),
    "rram": (0x22000000, 4 * 1024 * 1024),
}


def test_the_atomiq110_fpga_board_answers_the_consumer_queries(catalog):
    """#68 and #104's decisions: the board carries atomiq110_fpga, with no HBLRAM or J-Link."""
    target = catalog.resolve("atomiq110_fpga_turbo")
    assert (target.kind, target.part) == ("board", None)
    assert target.implementation is not None and target.implementation.kind == "fpga"
    assert target.capabilities == {"dsp", "fp16", "fp32", "fp64", "mve", "mve_fp", "npu", "pmu"}
    assert {m.name: (m.base, m.size) for m in target.memories()} == _ATOMIQ110_ON_DIE
    assert dict(target.usable_nvm()) == {"rram": 4 * 1024 * 1024}
    assert target.flash_load_address() == 0x22000000
    assert [
        (p.name, target.cpu_mhz(p.name), target.npu_mhz(p.name)) for p in target.operating_points()
    ] == [
        ("ulp_ulp", 10, 10),
        ("ulp_hp", 10, 50),
        ("lp_ulp", 25, 10),
        ("lp_hp", 25, 50),
        ("hp_ulp", 50, 10),
        ("hp_hp", 50, 50),
    ]
    assert target.default_operating_point is not None
    assert target.default_operating_point.name == "lp_ulp"
    assert (target.jlink_device, target.trace_clock_mhz) == (None, 50)
    assert target.board is not None and target.board.provisioning == "nbl"
    modes = {(d.id, p.name): p.hal_mode for d in target.soc.clock_domains for p in d.points}
    assert modes == {
        ("cpu", "ulp"): "AM_HAL_PWRCTRL_MCU_MODE_ULTRA_LOW_POWER",
        ("cpu", "lp"): "AM_HAL_PWRCTRL_MCU_MODE_LOW_POWER",
        ("cpu", "hp"): "AM_HAL_PWRCTRL_MCU_MODE_HIGH_PERFORMANCE",
        ("npu", "ulp"): "AM_HAL_PWRCTRL_NPU_MODE_ULTRA_LOW_POWER",
        ("npu", "hp"): "AM_HAL_PWRCTRL_NPU_MODE_HIGH_PERFORMANCE",
    }
    assert {"iom2", "iom11", "hblram"} & set(target.soc.peripherals) == {"hblram"}
    npu = {a.target: a.characterization for a in target.soc.access if a.master == "npu_0"}
    assert npu["rram"] is None  # block RAM on the FPGA, so not the Soc's RRAM timing
    timing = npu["ssram"]  # the FPGA gives cycle counts, so it states no latency
    assert timing is not None and (timing.read_latency_ns, timing.write_latency_ns) == (None, None)
    assert (timing.max_outstanding_reads, timing.max_outstanding_writes) == (8, 4)
    assert (timing.max_beats, timing.axi_clock_hz) == (128, 25_000_000)


def test_the_atomiq110_soc_answers_the_consumer_queries(catalog):
    target = catalog.resolve("atomiq110")
    assert target.kind == "soc" and catalog.resolve("at110").id == "atomiq110"
    assert resolve_board("atomiq110", catalog=catalog).id == "atomiq110_fpga_turbo"
    assert target.npu is not None and target.npu.npu.accelerator_config == "ethos-u85-256"
    assert {m.name: (m.base, m.size) for m in target.memories()} == {
        **_ATOMIQ110_ON_DIE,
        "hblram": (0x60000000, 13312 * 1024),
    }
    assert sorted({target.cpu_mhz(p.name) for p in target.operating_points()}) == [100, 250, 500]
    assert target.default_operating_point is not None
    assert target.default_operating_point.name == "lp_ulp"
    assert (target.cpu_mhz(), target.npu_mhz()) == (250, 100)
    assert (target.jlink_device, target.trace_clock_mhz) == (None, None)
    npu_reach = [(a.target, a.port) for a in target.soc.access if a.master == "npu_0"]
    assert npu_reach == [("ssram", 0), ("hblram", 1), ("rram", 1)]
    timing = {a.target: a.characterization for a in target.soc.access if a.master == "npu_0"}
    ssram = timing["ssram"]
    assert (ssram.read_latency_ns, ssram.max_outstanding_reads, ssram.max_outstanding_writes) == (
        64,
        12,
        16,
    )
    assert (timing["ssram"].max_beats, timing["ssram"].axi_clock_hz) == (128, 250_000_000)
    rram = timing["rram"]  # silicon's latency only; helia-npu's outstanding limit is fitted
    assert rram is not None and (rram.read_latency_ns, rram.max_outstanding_reads) == (240, None)
    assert target.soc.npus[0].sram_port_hash == 0x80


def test_apollo510b_evb_answers_the_consumer_queries(catalog):
    """The same questions on #64's data: apollo510's memory map, its own part and J-Link."""
    target = catalog.resolve("apollo510b_evb")
    assert target.capabilities == {"dsp", "fp16", "fp32", "fp64", "mve", "mve_fp", "pmu", "psram"}
    assert {m.name: (m.base, m.size) for m in target.memories()} == {
        "itcm": (0x00000000, 256 * 1024),
        "dtcm": (0x20000000, 512 * 1024),
        "ssram": (0x20080000, 3 * 1024 * 1024),
        "mram": (0x00400000, 4 * 1024 * 1024),
        "psram0": (0x60000000, 64 * 1024 * 1024),
    }
    assert dict(target.usable_nvm()) == {"mram": 4 * 1024 * 1024 - 64 * 1024}
    assert target.flash_load_address() == 0x00410000
    assert (target.cpu_mhz(), target.cpu_mhz("hp")) == (96, 250)
    assert target.default_operating_point.name == "lp"
    assert target.jlink_device == "AP510BFA-CBR"
    assert target.trace_clock_mhz == 96


def test_apollo510b_derives_from_apollo510_with_its_own_peripherals(catalog):
    """Equal physical regions; MSPI2, MSPI3 and the IOS are absent (DS-A510B p94, p19, p91).

    IOM6 is not pinned out (p94), but the BSP drives the BLE controller through it.
    """
    soc = catalog.resolve("apollo510b").soc
    apollo510 = catalog.resolve("apollo510").soc
    assert soc.derives_from == "apollo510"

    def physical(s):
        return [(r.name, r.technology, r.attachment, r.base, r.size) for r in s.memories]

    assert physical(soc) == physical(apollo510)
    assert set(apollo510.peripherals) - set(soc.peripherals) == {"ioslave", "mspi2", "mspi3"}
    assert "iom6" in soc.peripherals
    assert set(soc.peripherals) <= set(apollo510.peripherals)
    assert soc.memory_controllers == ("mspi0", "mspi1")


def test_the_soc_and_part_names_resolve(catalog):
    assert resolve_board("apollo510", catalog=catalog).id == "apollo510_evb"
    assert catalog.resolve("AP510NFA-CBR").part.id == "AP510NFA-CBR"
    assert resolve_board("apollo510b", catalog=catalog).id == "apollo510b_evb"
    assert catalog.resolve("AP510BFA-CBR").soc.id == "apollo510b"


@pytest.mark.parametrize("shorthand", ["AP5", "AP510"])
def test_a_shorthand_names_its_socs(catalog, shorthand):
    with pytest.raises(AmbiguousPlatform) as exc:
        catalog.resolve(shorthand)
    assert exc.value.candidates == ("apollo510", "apollo510b", "apollo510L")


@pytest.mark.parametrize(
    ("board", "sdk_only", "guide"),
    [
        ("apollo510_evb", {"fpio"}, "doc:QS-A510@2.1:p10"),
        ("apollo510b_evb", {"fpio", "iom6"}, "doc:QS-A510B@1.1:p10"),
    ],
)
def test_records_cite_the_best_available_source(catalog, board, sdk_only, guide):
    """Datasheet where a page states the value; the SDK only for what only it sets."""
    target = catalog.resolve(board)
    soc = target.soc
    peripherals = {name: soc.field_provenance[f"peripherals.{name}"] for name in soc.peripherals}
    assert {n for n, record in peripherals.items() if record.status != "datasheet"} == sdk_only
    m55 = next(c for c in catalog.cores() if c.id == "cortex-m55")
    assert (m55.provenance.status, m55.field_provenance["pmu"].status) == ("datasheet", "sdk")
    assert target.board.field_provenance["interfaces.mspi0.controller"].source == (guide,)


@pytest.mark.parametrize(
    "board", ["apollo510_evb", "apollo510b_evb", "apollo510dL_evb", "apollo330mP_evb"]
)
def test_the_app_start_offset_names_the_mram_base_it_is_derived_from(catalog, board):
    target = catalog.resolve(board)
    assert (
        f"fact:soc:{target.soc.id}:memories.mram.base"
        in target.boot.field_provenance["app_start.cm55_0.offset"].source
    )


@pytest.mark.parametrize(
    ("name", "sram", "flash"),
    [("apollo3_evb", 320 * 1024, 1024 * 1024), ("apollo3p_evb", 704 * 1024, 2048 * 1024)],
)
def test_apollo3_boards_answer_the_consumer_queries(catalog, name, sram, flash):
    """RFC 0002's heliaAOT and profiler questions, against #67's proposal section 1.6."""
    target = catalog.resolve(name)
    assert target.core.id == "cortex-m4"
    assert target.capabilities == {"dsp", "fp32"}
    assert {m.name: (m.base, m.size) for m in target.memories()} == {
        "tcm": (0x10000000, 64 * 1024),
        "sram": (0x10010000, sram),
        "flash": (0x00000000, flash),
    }
    assert dict(target.usable_nvm()) == {"flash": flash - 48 * 1024}
    assert target.flash_load_address() == 0xC000
    assert (target.cpu_mhz(), target.cpu_mhz("hp")) == (48, 96)
    assert target.default_operating_point.name == "lp"
    assert target.trace_clock_mhz == 6
    assert target.external_memories() == ()


@pytest.mark.parametrize(
    ("alias", "board"),
    [
        ("apollo3_blue_evb", "apollo3_evb"),
        ("apollo3_blue_thin_evb", "AMA3B1KK-KCR-TB"),
        ("apollo3_blue_plus_evb", "apollo3p_evb"),
    ],
)
def test_heliaaot_apollo3_names_are_aliases(catalog, alias, board):
    assert catalog.resolve(alias).id == board


def test_the_cygnus_composition_adds_its_psram_on_mspi1(catalog):
    target = catalog.resolve("apollo3p_evb_cygnus")
    assert (target.id, [a.id for a in target.addons]) == ("apollo3p_evb", ["cygnus"])
    (psram,) = target.external_memories()
    # Placement uses the read/write XIPMM window; the cached XIP window is read-only.
    assert (psram.name, psram.base, psram.size) == ("psram0", 0x54000000, 8 * 1024 * 1024)
    assert psram.alternate_bases == (0x04000000,)
    assert target.placement_ranges()["psram0"] == (0x54000000, 8 * 1024 * 1024)
    assert target.classify_address(0x04000010) == "psram0"
    window = ("doc:DS-A3P@1.3.0:p82", "doc:DS-A3P@1.3.0:p244", "doc:DS-A3P@1.3.0:p249")
    for key in ("base", "alternate_bases.0x4000000"):
        assert psram.field_provenance[key].source[:3] == window  # the board's, not the device's
    assert target.board.interfaces["mspi1"].controller == "mspi1"
    assert "psram" in target.capabilities


def test_apollo3_parts_carry_their_radio_and_jlink_device(catalog):
    assert catalog.resolve("apollo3_evb").jlink_device == "AMA3B1KK-KBR"
    assert catalog.resolve("apollo3p_evb").jlink_device == "AMA3B2KK-KBR"
    assert catalog.resolve("AMA3B1KK-KCR-B0").jlink_device == "AMA3B1KK-KCR"
    assert catalog.resolve("AMA3B1KK-KQR").jlink_device == "AMA3B1KK-KQR"
    thin = catalog.resolve("apollo3_blue_thin_evb")
    assert (thin.kind, thin.part.package, thin.jlink_device) == (
        "part",
        "66-pin WLCSP",
        "AMA3B1KK-KCR",
    )
    radios = {p.id: p.radio for p in catalog.parts(soc="apollo3")}
    assert {part for part, radio in radios.items() if radio == "none"} == {
        "AMAP31KK-KBR",
        "AMAP31KK-KCR",
    }


def test_the_apollo3_reservation_is_derived_from_the_app_start(catalog):
    (reservation,) = catalog.resolve("apollo3p_evb").boot.reserved
    assert reservation.provenance.source == (
        "fact:soc:apollo3p:boot_configs.sbl.app_start.cm4_0.offset",
        "fact:soc:apollo3p:memories.flash.base",
    )


APOLLO4P = {
    "tcm": (0x10000000, 384 * 1024),
    "ssram0": (0x10060000, 1024 * 1024),
    "extram": (0x10160000, 384 * 1024),
    "ssram1": (0x101C0000, 1024 * 1024),
    "mram": (0x00000000, 2 * 1024 * 1024),
}
APOLLO4L = {
    "tcm": (0x10000000, 384 * 1024),
    "ssram0": (0x10060000, 1024 * 1024),
    "mram": (0x00000000, 2 * 1024 * 1024),
}


@pytest.mark.parametrize(
    ("board", "regions", "jlink"),
    [
        ("apollo4p_evb", APOLLO4P, "AMAP42KP-KBR"),
        ("apollo4p_blue_kbr_evb", APOLLO4P, "AMA4B2KP-KBR"),
        ("apollo4p_blue_kxr_evb", APOLLO4P, "AMA4B2KP-KXR"),
        ("apollo4l_evb", APOLLO4L, "AMAP42KL-KBR"),
        ("apollo4l_blue_evb", APOLLO4L, "AMA4B2KL-KXR"),
    ],
)
def test_the_apollo4_evbs_answer_the_consumer_queries(catalog, board, regions, jlink):
    """#66's proposal section 1.7, with no PSRAM on any of the five EVBs."""
    target = catalog.resolve(board)
    assert target.capabilities == {"dsp", "fp32"}
    assert {m.name: (m.base, m.size) for m in target.memories()} == regions
    assert target.external_memories() == ()
    assert dict(target.usable_nvm()) == {"mram": 2 * 1024 * 1024 - 96 * 1024}
    assert target.flash_load_address() == 0x18000
    assert (target.cpu_mhz(), target.cpu_mhz("hp")) == (96, 192)
    assert target.default_operating_point.name == "lp"
    assert (target.jlink_device, target.trace_clock_mhz) == (jlink, 48)


@pytest.mark.parametrize("name", ["apollo4p_evb_disp_shield_rev2", "AMAP4PDISP"])
def test_the_display_kit_compositions_add_psram_and_flash(catalog, name):
    target = catalog.resolve(name)
    assert (target.id, target.aliases) == ("apollo4p_evb", (name,))
    assert [a.id for a in target.addons] == ["apollo4p_disp_shield"]
    fitted = {name: i.modes for name, i in target.interfaces.items()}
    octal = ("serial-sdr", "dual-sdr", "quad-sdr", "octal-sdr", "octal-ddr")
    assert fitted == {"mspi0": ("octal-ddr",), "mspi1": ("octal-ddr",), "mspi2": octal}
    evb_modes = ("serial-sdr", "dual-sdr", "quad-sdr", "octal-sdr", "octal-ddr", "hex-ddr")
    assert target.board.interfaces["mspi0"].modes == evb_modes
    assert catalog.resolve("apollo4p_evb").interfaces["mspi0"].modes == evb_modes
    assert catalog.resolve("apollo4p_evb").interfaces["mspi2"].modes == octal
    external = {(r.technology, r.base, r.size) for r in target.external_memories()}
    assert external == {("psram", 0x14000000, 32 * 1024 * 1024), ("flash", 0x18000000, 8 << 20)}
    assert target.has_external_memory("psram")
    assert catalog.resolve("apollo4p_evb").addons == ()


def test_the_display_kit_uses_the_display_s_mspi2_without_a_device_there(catalog):
    """QS-A4PDK p10-11 wire the display to MSPI2, so no other add-on may use it."""
    overlay = {
        "schema_version": 1,
        "addons": {
            "my_display": {"fits_boards": ["apollo4p_evb"], "occupies": ["mspi2"], "population": {}}
        },
        "compositions": {
            "both": {"board": "apollo4p_evb", "addons": ["apollo4p_disp_shield", "my_display"]}
        },
    }
    with pytest.raises(FormatError) as exc:
        load_overlay(overlay, base=catalog)
    assert (
        "compositions.both: add-on 'my_display' and add-on 'apollo4p_disp_shield' both use 'mspi2'"
    ) in "\n".join(exc.value.problems)


def test_the_blue_parts_record_their_radio(catalog):
    radios = {p.id: p.radio for p in catalog.parts() if p.soc in {"apollo4p", "apollo4l"}}
    assert radios == {
        "AMAP42KP-KBR": "none",
        "AMA4B2KP-KBR": "ble-5.4",
        "AMA4B2KP-KXR": "ble-5.4",
        "AMAP42KL-KBR": "none",
        "AMA4B2KL-KXR": "ble-5.1",
    }


@pytest.mark.parametrize(
    ("board", "cores", "removed", "controllers"),
    [
        ("apollo4p_evb", ["cm4_0"], set(), ["mspi0", "mspi1", "mspi2"]),
        ("apollo4p_blue_kbr_evb", ["cm4_0", "ble_m0"], set(), ["mspi0", "mspi2"]),
        ("apollo4p_blue_kxr_evb", ["cm4_0", "ble_m0"], {"pdm1", "pdm2"}, None),
        ("apollo4l_evb", ["cm4_0"], set(), ["mspi0", "mspi1", "mspi2"]),
        ("apollo4l_blue_evb", ["cm4_0", "ble_m0"], set(), ["mspi0", "mspi1", "mspi2"]),
    ],
)
def test_each_apollo4_part_keeps_what_its_datasheet_gives(
    catalog, board, cores, removed, controllers
):
    target = catalog.resolve(board)
    soc = catalog._entry("socs", target.soc.id)
    assert [c.id for c in target.soc.cores] == cores
    # The radio domain goes with ble_m0 (clock_domains_removed on the plain parts).
    assert [d.id for d in target.soc.clock_domains] == ["cpu", "radio"][: len(cores)]
    assert set(soc.peripherals) - set(target.soc.peripherals) == removed
    assert list(target.soc.memory_controllers) == (controllers or ["mspi0", "mspi1", "mspi2"])
    ble = [c for c in target.soc.cores if c.id == "ble_m0"]
    assert [(c.core, c.programmable_by, c.clock_domain) for c in ble] == [
        ("cortex-m0", "vendor", "radio")
    ] * len(ble)


def test_a_blue_plus_kbr_board_cannot_put_memory_on_mspi1(catalog):
    """DS-A4BP p118: "MSPI1 is not pinned out on the Apollo4 Blue Plus KBR package"."""
    board = {
        "category": "custom",
        "part": "AMA4B2KP-KBR",
        "interfaces": {
            "mspi1": {"controller": "mspi1", "aperture_base": 0x18000000, "aperture_max": "64M"}
        },
        "population": {"mspi1": "IS25WX064"},
    }
    with pytest.raises(FormatError) as exc:
        load_overlay({"schema_version": 1, "boards": {"my_kbr": board}}, base=catalog)
    removed = "interfaces.mspi1: controller 'mspi1' is removed by the implementation"
    assert f"boards.my_kbr.{removed}" in "\n".join(exc.value.problems)


@pytest.mark.parametrize(
    ("name", "board"),
    [("apollo510l_evb", "apollo510dL_evb"), ("apollo330mp_evb", "apollo330mP_evb")],
)
def test_the_radio_core_evbs_answer_the_consumer_queries(catalog, name, board):
    """#65's decisions: core-0 answers are those of a single-core part; NVM-M41 is the radio's."""
    target = catalog.resolve(name)
    assert target.board.id == board
    assert target.capabilities == {"dsp", "fp16", "fp32", "fp64", "mve", "mve_fp", "pmu"}
    assert {m.name: (m.base, m.size) for m in target.memories()} == {
        "dtcm": (0x20000000, 256 * 1024),
        "ssram": (0x20080000, 1792 * 1024),
        "mram": (0x00400000, 2 * 1024 * 1024),
    }
    assert dict(target.usable_nvm()) == {"mram": 1589248}
    assert target.flash_load_address() == 0x00410000
    assert [(p.name, target.cpu_mhz(p.name)) for p in target.operating_points()] == [
        ("lp", 96),
        ("hp1", 192),
        ("hp2", 250),
    ]
    assert target.default_operating_point.name == "lp"
    assert (target.jlink_device, target.trace_clock_mhz) == (None, 48)
    assert not target.external_memories()


def test_the_radio_core_reaches_its_tcm_nvm_and_system_sram(catalog):
    target = catalog.resolve("apollo510dL_evb")
    radio = target.cores(role="radio")
    assert [(c.id, c.core, c.programmable_by) for c in radio] == [
        ("radio_m4", "cortex-m4", "vendor")
    ]
    assert [m.name for m in target.memories("radio_m4")] == ["ssram", "mram", "rs_tcm"]
    assert [(p.name, p.mhz) for p in target.operating_points(domain="radio")] == [
        ("lp", 48),
        ("hp", 96),
    ]
    assert not target.isa("radio_m4").has_mve
    assert not target.isa("radio_m4").has_pmu  # a Cortex-M4 has DWT, not a PMU
    assert dict(target.usable_nvm("radio_m4")) == {}  # only the vendor programs it


@pytest.mark.parametrize(
    ("name", "slot_kb"),
    [
        ("apollo510L", 16),
        ("AP510NLA-CBR", 16),
        ("AP330NPA-IBR", 16),
        ("AP510BLA-ICR", 288),
        ("AP330MPA-CCR", 432),
        ("apollo330P", 16),
    ],
)
def test_nvm_m41_is_the_radio_core_s_slot_on_every_part_and_the_soc(catalog, name, slot_kb):
    """The #127 review: every part keeps the Cortex-M4, whose factory firmware is in NVM-M41."""
    target = catalog.resolve(name)
    assert [
        (s.name, s.core, s.region, s.offset, s.size, s.supplier)
        for s in target.image_slots.values()
    ] == [("nvm_m41", "radio_m4", "mram", (2048 - slot_kb) * 1024, slot_kb * 1024, "vendor")]
    assert dict(target.usable_nvm()) == {"mram": (2048 - 64 - slot_kb) * 1024}
    assert [c.id for c in target.cores(role="radio")] == ["radio_m4"]
    assert target.has_region("rs_tcm")


@pytest.mark.parametrize("soc", ["apollo510L", "apollo330P"])
def test_the_m55_reaches_the_radio_tcm_but_no_budget_counts_it(catalog, soc):
    """The #127 review: DS p33 maps RS TCM for the M55, recorded as discouraged."""
    target = catalog.resolve(soc)
    entry = target.reachable("cm55_0", "rs_tcm")
    assert entry is not None and (entry.access, entry.guidance) == ("direct", "discouraged")
    assert "rs_tcm" not in {m.name for m in target.memories()}
    assert "rs_tcm" not in target.placement_ranges()
    assert target.classify_address(0x003C0000) == "rs_tcm"


@pytest.mark.parametrize("soc", ["apollo510L", "apollo330P"])
def test_the_radio_core_on_every_part_is_derived(catalog, soc):
    """The #127 review: the datasheet puts the RSS on the radio parts only."""
    record = catalog.resolve(soc).soc.field_provenance["cores.radio_m4.role"]
    assert record.status == "derived"
    assert {s.rsplit(":", 1)[-1] for s in record.source} == {"p2", "p33", "p55", "p67"}


def test_apollo330p_has_no_display_or_gpu(catalog):
    peripherals = set(catalog.resolve("apollo330P").soc.peripherals)
    assert not peripherals & {"dc", "dsi", "gpu", "i2s1"}
    assert {"dc", "dsi", "gpu"} <= set(catalog.resolve("apollo510L").soc.peripherals)


@pytest.mark.parametrize(
    ("soc", "controllers", "boundaries"),
    [
        (
            "apollo510",
            ["mspi0", "mspi1", "mspi2", "mspi3"],
            {"dtcm": 4096, "ssram": 1 << 20, "mram": 2 << 20},
        ),
        ("apollo510b", ["mspi0", "mspi1"], {"dtcm": 4096, "ssram": 1 << 20, "mram": 2 << 20}),
        ("apollo510L", ["mspi0", "mspi1", "mspi2"], {"dtcm": 4096}),
        ("apollo330P", ["mspi0", "mspi1", "mspi2"], {"dtcm": 4096}),
    ],
)
def test_apollo5_records_its_dma_reach_and_boundaries(catalog, soc, controllers, boundaries):
    """ADR 0011: every MSPI DMA engine reaches dtcm, ssram and mram; the datasheet's boundaries."""
    target = catalog.resolve(soc)
    assert {r.name: r.dma_boundary for r in target.memories() if r.dma_boundary} == boundaries
    for controller in controllers:
        for region in ("dtcm", "ssram", "mram"):
            entry = target.reachable(controller, region)
            assert entry is not None and entry.access == "direct", (controller, region)
            assert entry.provenance is not None and entry.provenance.status == "datasheet"
    assert target.reachable("mspi0", "itcm") is None  # no source states it
    assert {r.name for r in target.memories()} >= set(boundaries)  # core 0's view is unchanged


def test_the_psram_devices_record_the_driver_s_dma_break(catalog):
    """ADR 0011: the SDK's PSRAM drivers split a DMA at 1 kB of device address; flash does not."""
    breaks = {d.id: d.dma_boundary for d in catalog.memory_devices()}
    assert breaks == {"APS512XX": 1024, "APS256XXN": 1024, "APS6404L": 1024, "IS25WX064": None}
