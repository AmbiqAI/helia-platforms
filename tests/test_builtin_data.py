import pytest

from helia_platforms import AmbiguousPlatform, Catalog, builtin, resolve_board
from helia_platforms.catalog import load_overlay
from helia_platforms.errors import FormatError


@pytest.fixture(scope="module")
def catalog() -> Catalog:
    return builtin(include_plugins=False)


def test_the_packaged_data_loads(catalog):
    assert {s.id for s in catalog.socs()} == {"apollo510", "apollo4p", "apollo4l"}
    assert {c.id for c in catalog.cores()} == {"cortex-m55", "cortex-m4", "cortex-m0"}
    assert {p.id for p in catalog.parts()} == {
        "AP510NFA-CBR",
        "AP510NFA-IBR",
        "AP510NFA-CCR",
        "AMAP42KP-KBR",
        "AMA4B2KP-KBR",
        "AMA4B2KP-KXR",
        "AMAP42KL-KBR",
        "AMA4B2KL-KXR",
    }
    assert {b.id for b in catalog.boards()} == {
        "apollo510_evb",
        "apollo4p_evb",
        "apollo4p_blue_kbr_evb",
        "apollo4p_blue_kxr_evb",
        "apollo4l_evb",
        "apollo4l_blue_evb",
    }
    assert [a.id for a in catalog.addons()] == ["apollo4p_disp_shield"]
    assert {d.id for d in catalog.memory_devices()} == {"APS512XX", "APS256XXN", "IS25WX064"}


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
    assert (target.jlink_device, target.trace_clock_mhz) == (jlink, 96)


def test_the_display_shield_composition_adds_psram_and_flash(catalog):
    target = catalog.resolve("apollo4p_evb_disp_shield_rev2")
    assert (target.id, target.aliases) == ("apollo4p_evb", ("apollo4p_evb_disp_shield_rev2",))
    assert [a.id for a in target.addons] == ["apollo4p_disp_shield"]
    modes = {name: i.modes for name, i in target.board.interfaces.items()}
    assert modes == {"mspi0": ("hex-ddr", "octal-ddr"), "mspi1": ("octal-ddr",), "mspi2": ()}
    external = {(r.technology, r.base, r.size) for r in target.external_memories()}
    assert external == {("psram", 0x14000000, 32 * 1024 * 1024), ("flash", 0x18000000, 8 << 20)}
    assert target.has_external_memory("psram")
    assert catalog.resolve("apollo4p_evb").addons == ()


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
