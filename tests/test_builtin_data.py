import pytest

from helia_platforms import AmbiguousPlatform, Catalog, builtin, resolve_board


@pytest.fixture(scope="module")
def catalog() -> Catalog:
    return builtin(include_plugins=False)


def test_the_packaged_data_loads(catalog):
    assert [s.id for s in catalog.socs()] == ["apollo510", "atomiq110"]
    assert [i.id for i in catalog.implementations()] == ["atomiq110_fpga"]
    assert [c.id for c in catalog.cores()] == ["cortex-m55"]
    assert {p.id for p in catalog.parts()} == {"AP510NFA-CBR", "AP510NFA-IBR", "AP510NFA-CCR"}
    assert [b.id for b in catalog.boards()] == ["apollo510_evb", "atomiq110_fpga_turbo"]
    assert [d.id for d in catalog.memory_devices()] == ["APS512XX"]


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
    rram = npu["rram"]
    assert rram is not None and (rram.read_latency_ns, rram.max_outstanding_reads) == (240, 2)
    timing = npu["ssram"]
    assert timing is not None and timing.write_latency_ns == 64
    assert (timing.max_outstanding_reads, timing.max_outstanding_writes) == (8, 4)
    assert (timing.read_latency_ns, timing.burst_bytes, timing.axi_clock_hz) == (
        64,
        128,
        250_000_000,
    )


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
    assert (timing["ssram"].burst_bytes, timing["ssram"].axi_clock_hz) == (128, 250_000_000)
    assert timing["rram"] is None  # helia-npu's rram timing is fitted, not a hardware fact
    assert target.soc.npus[0].sram_port_hash == 0x80


def test_the_soc_and_part_names_resolve(catalog):
    assert resolve_board("apollo510", catalog=catalog).id == "apollo510_evb"
    assert catalog.resolve("AP510NFA-CBR").part.id == "AP510NFA-CBR"


@pytest.mark.parametrize("shorthand", ["AP5", "AP510"])
def test_a_shorthand_names_its_socs(catalog, shorthand):
    with pytest.raises(AmbiguousPlatform) as exc:
        catalog.resolve(shorthand)
    assert exc.value.candidates == ("apollo510",)


def test_records_cite_the_best_available_source(catalog):
    """Datasheet where a page states the value; the SDK only for what only it sets."""
    soc = catalog.resolve("apollo510_evb").soc
    peripherals = {name: soc.field_provenance[f"peripherals.{name}"] for name in soc.peripherals}
    assert {name for name, record in peripherals.items() if record.status != "datasheet"} == {
        "fpio"
    }
    m55 = next(c for c in catalog.cores() if c.id == "cortex-m55")
    assert (m55.provenance.status, m55.field_provenance["pmu"].status) == ("datasheet", "sdk")
    board = catalog.resolve("apollo510_evb").board
    assert board.field_provenance["interfaces.mspi0.controller"].source == ("doc:QS-A510@2.1:p10",)


def test_the_app_start_offset_names_the_mram_base_it_is_derived_from(catalog):
    sbl = catalog.resolve("apollo510_evb").boot
    assert (
        "fact:soc:apollo510:memories.mram.base"
        in sbl.field_provenance["app_start.cm55_0.offset"].source
    )
