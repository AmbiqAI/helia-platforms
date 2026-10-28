import pytest

from helia_platforms import AmbiguousPlatform, Catalog, builtin, resolve_board


@pytest.fixture(scope="module")
def catalog() -> Catalog:
    return builtin(include_plugins=False)


def test_the_packaged_data_loads(catalog):
    assert {s.id for s in catalog.socs()} == {"apollo3", "apollo3p", "apollo510"}
    assert {c.id for c in catalog.cores()} == {"cortex-m4", "cortex-m55"}
    assert {p.id for p in catalog.parts()} == {
        *("AMA3B1KK-KBR-B0", "AMA3B1KK-KCR-B0", "AMA3B1KK-KCR-TB", "AMA3B1KK-KQR"),
        *("AMAP31KK-KBR", "AMAP31KK-KCR", "AMA3B2KK-KBR"),
        *("AP510NFA-CBR", "AP510NFA-IBR", "AP510NFA-CCR"),
    }
    assert {b.id for b in catalog.boards()} == {"apollo3_evb", "apollo3p_evb", "apollo510_evb"}
    assert [a.id for a in catalog.addons()] == ["cygnus"]
    assert {d.id for d in catalog.memory_devices()} == {"APS512XX", "APS6404L"}


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
    assert (psram.name, psram.base, psram.size) == ("psram0", 0x04000000, 8 * 1024 * 1024)
    assert target.board.interfaces["mspi1"].controller == "mspi1"
    assert "psram" in target.capabilities


def test_apollo3_parts_carry_their_radio_and_jlink_device(catalog):
    assert catalog.resolve("apollo3_evb").jlink_device == "AMA3B1KK-KBR"
    assert catalog.resolve("apollo3p_evb").jlink_device == "AMA3B2KK-KBR"
    assert catalog.resolve("AMA3B1KK-KCR-B0").jlink_device == "AMA3B1KK-KCR"
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
