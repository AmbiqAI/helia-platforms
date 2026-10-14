import pytest

from helia_platforms import AmbiguousPlatform, Catalog, builtin, resolve_board


@pytest.fixture(scope="module")
def catalog() -> Catalog:
    return builtin(include_plugins=False)


def test_the_packaged_data_loads(catalog):
    assert [s.id for s in catalog.socs()] == ["apollo510"]
    assert {c.id for c in catalog.cores()} == {"cortex-m4", "cortex-m55"}
    assert {p.id for p in catalog.parts()} == {"AP510NFA-CBR", "AP510NFA-IBR", "AP510NFA-CCR"}
    assert [b.id for b in catalog.boards()] == ["apollo510_evb"]
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
