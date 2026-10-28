import pytest

from helia_platforms import AmbiguousPlatform, Catalog, builtin, resolve_board


@pytest.fixture(scope="module")
def catalog() -> Catalog:
    return builtin(include_plugins=False)


def test_the_packaged_data_loads(catalog):
    assert {s.id for s in catalog.socs()} == {"apollo510", "apollo510L", "apollo330P"}
    assert [c.id for c in catalog.cores()] == ["cortex-m55", "cortex-m4"]
    assert {p.id for p in catalog.parts(soc="apollo510")} == {
        "AP510NFA-CBR",
        "AP510NFA-IBR",
        "AP510NFA-CCR",
    }
    assert {b.id for b in catalog.boards()} == {
        "apollo510_evb",
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


def test_the_soc_and_part_names_resolve(catalog):
    assert resolve_board("apollo510", catalog=catalog).id == "apollo510_evb"
    assert catalog.resolve("AP510NFA-CBR").part.id == "AP510NFA-CBR"


@pytest.mark.parametrize("shorthand", ["AP5", "AP510"])
def test_a_shorthand_names_its_socs(catalog, shorthand):
    with pytest.raises(AmbiguousPlatform) as exc:
        catalog.resolve(shorthand)
    assert exc.value.candidates == ("apollo510", "apollo510L")


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


@pytest.mark.parametrize(
    ("board", "soc"),
    [
        ("apollo510_evb", "apollo510"),
        ("apollo510dL_evb", "apollo510L"),
        ("apollo330mP_evb", "apollo330P"),
    ],
)
def test_the_app_start_offset_names_the_mram_base_it_is_derived_from(catalog, board, soc):
    sbl = catalog.resolve(board).boot
    assert (
        f"fact:soc:{soc}:memories.mram.base"
        in sbl.field_provenance["app_start.cm55_0.offset"].source
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


def test_apollo330p_has_no_display_or_gpu(catalog):
    peripherals = set(catalog.resolve("apollo330P").soc.peripherals)
    assert not peripherals & {"dc", "dsi", "gpu", "i2s1"}
    assert {"dc", "dsi", "gpu"} <= set(catalog.resolve("apollo510L").soc.peripherals)
