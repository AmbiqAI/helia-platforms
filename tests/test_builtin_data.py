import pytest

from helia_platforms import AmbiguousPlatform, Catalog, builtin, resolve_board


@pytest.fixture(scope="module")
def catalog() -> Catalog:
    return builtin(include_plugins=False)


def test_the_packaged_data_loads(catalog):
    assert {s.id for s in catalog.socs()} == {
        "apollo510",
        "apollo510b",
        "apollo510L",
        "apollo330P",
    }
    assert [c.id for c in catalog.cores()] == ["cortex-m55", "cortex-m4"]
    assert {p.id for p in catalog.parts(soc="apollo510")} == {
        "AP510NFA-CBR",
        "AP510NFA-IBR",
        "AP510NFA-CCR",
    }
    assert {p.id for p in catalog.parts(soc="apollo510b")} == {"AP510BFA-CBR"}
    assert {b.id for b in catalog.boards()} == {
        "apollo510_evb",
        "apollo510b_evb",
        "apollo510dL_evb",
        "apollo330mP_evb",
    }
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
    assert {(s.name, s.core, s.size // 1024) for s in target.image_slots.values()} == {
        ("nvm_m41", "radio_m4", slot_kb)
    }
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
