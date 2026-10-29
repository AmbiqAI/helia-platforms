import pytest

from helia_platforms import AmbiguousPlatform, Catalog, builtin, resolve_board


@pytest.fixture(scope="module")
def catalog() -> Catalog:
    return builtin(include_plugins=False)


def test_the_packaged_data_loads(catalog):
    assert [s.id for s in catalog.socs()] == ["apollo510", "apollo510b"]
    assert [c.id for c in catalog.cores()] == ["cortex-m55"]
    assert {p.id for p in catalog.parts()} == {
        "AP510NFA-CBR",
        "AP510NFA-IBR",
        "AP510NFA-CCR",
        "AP510BFA-CBR",
    }
    assert [b.id for b in catalog.boards()] == ["apollo510_evb", "apollo510b_evb"]
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
    assert exc.value.candidates == ("apollo510", "apollo510b")


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


@pytest.mark.parametrize("board", ["apollo510_evb", "apollo510b_evb"])
def test_the_app_start_offset_names_the_mram_base_it_is_derived_from(catalog, board):
    target = catalog.resolve(board)
    assert (
        f"fact:soc:{target.soc.id}:memories.mram.base"
        in target.boot.field_provenance["app_start.cm55_0.offset"].source
    )
