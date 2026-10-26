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


def test_the_app_start_offset_names_the_mram_base_it_is_derived_from(catalog):
    sbl = catalog.resolve("apollo510_evb").boot
    assert (
        "fact:soc:apollo510:memories.mram.base"
        in sbl.field_provenance["app_start.cm55_0.offset"].source
    )


@pytest.mark.parametrize(
    ("name", "board", "jlink"),
    [
        ("apollo510l_evb", "apollo510dL_evb", "AP510DLA-CBR"),
        ("apollo330mp_evb", "apollo330mP_evb", "Apollo330P_510L"),
    ],
)
def test_the_radio_core_evbs_answer_the_consumer_queries(catalog, name, board, jlink):
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
    assert (target.jlink_device, target.trace_clock_mhz) == (jlink, 48)
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


@pytest.mark.parametrize(
    ("part", "usable"),
    [
        ("AP510NLA-CBR", 2 * 1024 * 1024 - 64 * 1024 - 16 * 1024),
        ("AP330NPA-IBR", 2 * 1024 * 1024 - 64 * 1024 - 16 * 1024),
        ("AP510BLA-ICR", 2 * 1024 * 1024 - 64 * 1024 - 288 * 1024),
        ("AP330MPA-CCR", 2 * 1024 * 1024 - 64 * 1024 - 432 * 1024),
    ],
)
def test_nvm_m41_is_left_out_on_every_part(catalog, part, usable):
    """A no-radio part has no radio core; its 16 KB NVM-M41 is a boot reservation instead."""
    target = catalog.resolve(part)
    assert dict(target.usable_nvm()) == {"mram": usable}
    has_radio = target.part.radio != "none"
    assert bool(target.cores(role="radio")) == has_radio
    assert target.has_region("rs_tcm") == has_radio


def test_apollo330p_has_no_display_or_gpu(catalog):
    peripherals = set(catalog.resolve("apollo330P").soc.peripherals)
    assert not peripherals & {"dc", "dsi", "gpu", "i2s1"}
    assert {"dc", "dsi", "gpu"} <= set(catalog.resolve("apollo510L").soc.peripherals)
