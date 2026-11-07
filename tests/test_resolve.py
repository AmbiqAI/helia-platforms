import copy
import warnings

import pytest

import helia_platforms
from conftest import RECORD, as_builtin
from helia_platforms import (
    AmbiguousPlatform,
    PlatformError,
    PlatformWarning,
    UnknownPlatform,
    _provenance,
    load_overlay,
    resolve,
    resolve_board,
    resolve_soc,
)
from helia_platforms.catalog import _load_documents, builtin

KB = 1024


def quiet(document):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", PlatformWarning)
        return load_overlay(document)


@pytest.fixture
def catalog(document):
    return quiet(document)


def with_fpga(document, **subset):
    document["implementations"] = {"soc_a_fpga": {"soc": "soc_a", "kind": "fpga", "subset": subset}}
    return document


# ---- resolution ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "kind", "target_id"),
    [
        ("board_a", "board", "board_a"),
        ("BOARD_A", "board", "board_a"),
        ("part-a", "part", "PART-A"),
        ("soc_a", "soc", "soc_a"),
    ],
)
def test_each_kind_of_id_resolves_case_insensitively(catalog, name, kind, target_id):
    target = resolve(name, catalog=catalog)
    assert (target.kind, target.id) == (kind, target_id)


def test_an_fpga_board_takes_its_implementations_facts(document):
    with_fpga(document, memories_removed=["ssram"])
    document["implementations"]["soc_a_fpga"]["trace_clock_mhz"] = 48
    document["boards"]["fpga_a"] = {"category": "fpga", "implementation": "soc_a_fpga"}
    target = resolve("fpga_a", catalog=quiet(document))
    assert (target.kind, target.part) == ("board", None)
    assert target.implementation is not None and target.implementation.id == "soc_a_fpga"
    assert (target.trace_clock_mhz, target.jlink_device) == (48, None)
    assert "ssram" not in {r.name for r in target.memories()}


def test_an_implementation_id_resolves_to_its_target(document):
    target = resolve("soc_a_fpga", catalog=quiet(with_fpga(document)))
    assert target.kind == "implementation"
    assert target.implementation is not None and target.part is None


def test_a_soc_id_never_resolves_to_a_board_however_many_boards_carry_it(document):
    assert resolve("soc_a", catalog=quiet(document)).kind == "soc"
    document["boards"]["board_b"] = copy.deepcopy(document["boards"]["board_a"])
    assert resolve("soc_a", catalog=quiet(document)).kind == "soc"
    document["socs"]["soc_a"]["default_board"] = "board_a"
    assert resolve("soc_a", catalog=quiet(document)).kind == "soc"


def test_an_alias_resolves_to_its_entry(document):
    document["boards"]["board_a"]["aliases"] = ["evb_a"]
    target = resolve("EVB_A", catalog=quiet(document))
    assert (target.id, target.aliases) == ("board_a", ("evb_a",))


def test_a_composition_resolves_to_its_board_with_its_add_ons(document):
    document["boards"]["board_a"]["interfaces"]["mspi1"] = {
        "controller": "iom0",
        "aperture_base": 0x70000000,
        "aperture_max": "64M",
    }
    document["addons"] = {
        "shield": {
            "fits_boards": ["board_a"],
            "occupies": ["mspi1"],
            "population": {"mspi1": "psram_8m"},
        }
    }
    document["compositions"] = {"Board_A_Shield": {"board": "board_a", "addons": ["shield"]}}
    catalog = quiet(document)
    target = resolve("board_a_shield", catalog=catalog)
    assert (target.id, [a.id for a in target.addons]) == ("board_a", ["shield"])
    assert target.aliases == ("Board_A_Shield",)  # as the catalog writes it
    assert resolve("BOARD_A_SHIELD", catalog=catalog) == target
    assert [r.name for r in target.external_memories()] == ["psram0", "psram1"]


def test_a_shorthand_is_ambiguous(document):
    document["boards"]["board_b"] = copy.deepcopy(document["boards"]["board_a"])
    document["shorthands"] = {"AB": ["board_a", "board_b"]}
    catalog = _load_documents([(as_builtin(document), "builtin.yaml")], builtin=True)
    with pytest.raises(AmbiguousPlatform) as exc:
        resolve("ab", catalog=catalog)
    assert exc.value.candidates == ("board_a", "board_b")


def test_an_unknown_name_suggests_close_names(catalog):
    with pytest.raises(UnknownPlatform) as exc:
        resolve("board_aa", catalog=catalog)
    assert exc.value.suggestions[0] == "board_a"
    assert catalog.suggest("soc-a") == ("soc_a",)


def test_resolve_board_uses_default_board_only_for_a_soc(document):
    with pytest.raises(PlatformError, match="names no default_board"):
        resolve_board("soc_a", catalog=quiet(document))
    document["socs"]["soc_a"]["default_board"] = "board_a"
    catalog = quiet(document)
    assert resolve_board("soc_a", catalog=catalog).id == "board_a"
    assert resolve_board("board_a", catalog=catalog).id == "board_a"
    with pytest.raises(UnknownPlatform):
        resolve_board("PART-A", catalog=catalog)
    assert resolve_soc("board_a", catalog=catalog).id == "soc_a"


def test_add_ons_apply_only_to_a_board(catalog):
    with pytest.raises(PlatformError, match="only to a board"):
        resolve("soc_a", addons=["shield"], catalog=catalog)


def test_find_filters_every_kind_of_target(catalog):
    assert [t.id for t in catalog.find(core="cortex-m55")] == ["board_a", "PART-A", "soc_a"]
    assert [t.id for t in catalog.find(npu_model="u85", kind="soc")] == ["soc_a"]
    assert [t.id for t in catalog.find(has_region="psram0")] == ["board_a"]
    with pytest.raises(TypeError, match="unknown predicates"):
        catalog.find(colour="red")


def test_the_package_exports_the_public_names():
    assert {"resolve", "resolve_board", "resolve_soc", "Target", "UnknownPlatform"} <= set(
        helia_platforms.__all__
    )
    assert all(hasattr(helia_platforms, name) for name in helia_platforms.__all__)


# ---- the resolved target -----------------------------------------------------------


def test_structure_and_isa(catalog):
    target = resolve("board_a", catalog=catalog)
    assert (target.core.id, target.core_options.mve) == ("cortex-m55", "fp")
    assert target.npu is not None and target.npu.npu.accelerator_config == "ethos-u85-256"
    assert [c.id for c in target.cores(role="application")] == ["cm55_0"]
    isa = target.isa()
    assert (isa.has_dsp, isa.has_mve, isa.supports_fp16, isa.supports_fp64) == (
        True,
        True,
        True,
        False,
    )
    assert target.capabilities == {"dsp", "mve", "mve_fp", "fp16", "fp32", "pmu", "npu", "psram"}
    assert target.category == "evaluation"


def test_memories_are_what_the_core_reaches_plus_populated_devices(catalog):
    target = resolve("board_a", catalog=catalog)
    assert [(r.name, r.size) for r in target.memories()] == [
        ("tcm", 512 * KB),
        ("ssram", 3 * KB * KB),
        ("nvm", 4 * KB * KB),
        ("psram0", 8 * KB * KB),
    ]
    assert target.placement_ranges()["psram0"] == (0x60000000, 8 * KB * KB)
    npu_entry, psram_entry = (
        target.reachable("npu_0", "ssram"),
        target.reachable("cm55_0", "psram0"),
    )
    assert npu_entry is not None and npu_entry.port == 0
    assert psram_entry is not None and psram_entry.target == "mspi0"
    assert target.has_external_memory("psram") and not target.has_external_memory("flash")
    assert target.has_region(technology="mram") and not target.has_region("itcm")
    assert resolve("soc_a", catalog=catalog).external_memories() == ()


def test_an_interface_alias_is_the_device_regions_alternate_base(document):
    document["boards"]["board_a"]["interfaces"]["mspi0"]["alternate_bases"] = [0x80000000]
    target = resolve("board_a", catalog=quiet(document))
    (psram,) = target.external_memories()
    assert (psram.base, psram.alternate_bases) == (0x60000000, (0x80000000,))
    assert target.placement_ranges()["psram0"] == (0x60000000, 8 * KB * KB)
    assert target.classify_address(0x80000010) == "psram0"


def test_an_interface_window_carries_the_boards_record_not_the_devices(document):
    alias = {**RECORD, "source": ["doc:DS-OTHER@2.0:p2"]}
    document["boards"]["board_a"]["provenance"] = RECORD
    mspi0 = document["boards"]["board_a"]["interfaces"]["mspi0"]
    mspi0["alternate_bases"] = {"value": [0x80000000], "provenance": alias}
    (psram,) = resolve("board_a", catalog=quiet(document)).external_memories()
    assert psram.provenance.status == "unverified"  # the device's record
    assert psram.field_provenance["base"].source == tuple(RECORD["source"])
    assert psram.field_provenance["alternate_bases.0x80000000"].source == tuple(alias["source"])


def test_an_external_region_keys_the_devices_records_by_its_own_fields(document):
    measured = {**RECORD, "status": "measured", "source": ["meas:board_a/psram/2026-10-01"]}
    psram = document["memory_devices"]["psram_8m"]
    psram["capacity"] = {"value": psram["capacity"], "provenance": measured}
    psram["driver_family"] = {"value": "aps", "provenance": measured}
    (region,) = resolve("board_a", catalog=quiet(document)).external_memories()
    assert region.field_provenance["size"].status == "measured"
    assert {"capacity", "driver_family"}.isdisjoint(region.field_provenance)


def test_a_discouraged_entry_stays_out_of_memories_and_placement(document):
    soc = document["socs"]["soc_a"]
    soc["access"].append(
        {"master": "cm55_0", "target": "tcm", "access": "direct", "guidance": "discouraged"}
    )
    target = resolve("board_a", catalog=quiet(document))
    assert [r.name for r in target.memories()] == ["ssram", "nvm", "psram0"]
    assert "tcm" not in target.placement_ranges()
    entry = target.reachable("cm55_0", "tcm")
    assert entry is not None and entry.guidance == "discouraged"
    assert target.classify_address(0x20000000) == "tcm"


def test_include_discouraged_puts_a_discouraged_region_back(document):
    soc = document["socs"]["soc_a"]
    soc["access"].append(
        {"master": "cm55_0", "target": "tcm", "access": "direct", "guidance": "discouraged"}
    )
    target = resolve("board_a", catalog=quiet(document))
    names = [r.name for r in target.memories(include_discouraged=True)]
    assert names == ["tcm", "ssram", "nvm", "psram0"]
    assert "tcm" in target.placement_ranges(include_discouraged=True)


def test_usable_nvm_leaves_out_a_discouraged_nvm_region_unless_asked(document):
    soc = document["socs"]["soc_a"]
    soc["access"].append(
        {"master": "cm55_0", "target": "nvm", "access": "direct", "guidance": "discouraged"}
    )
    target = resolve("board_a", catalog=quiet(document))
    assert "nvm" not in target.usable_nvm()
    assert "nvm" in target.usable_nvm(include_discouraged=True)


def test_placement_leaves_out_an_external_device_with_no_base(document):
    del document["boards"]["board_a"]["interfaces"]["mspi0"]["aperture_base"]
    target = resolve("board_a", catalog=quiet(document))
    assert [(r.name, r.base) for r in target.external_memories()] == [("psram0", None)]
    assert set(target.placement_ranges()) == {"tcm", "ssram", "nvm"}


def test_placement_raises_for_an_on_chip_region_with_no_base(document):
    del document["socs"]["soc_a"]["memories"]["nvm"]["base"]
    target = resolve("board_a", catalog=quiet(document))
    with pytest.raises(PlatformError, match="region 'nvm' has no base"):
        target.placement_ranges()


def test_placement_raises_for_a_soc_external_region_with_no_base(document):
    soc = document["socs"]["soc_a"]
    soc["memories"]["hbl"] = {"technology": "dram", "attachment": "external", "size": "8M"}
    soc["access"].append({"master": "cm55_0", "target": "hbl", "access": "direct"})
    target = resolve("board_a", catalog=quiet(document))
    assert "hbl" in {r.name for r in target.memories()}
    with pytest.raises(PlatformError, match="region 'hbl' has no base"):
        target.placement_ranges()


def test_an_implementation_subset_removes_memories(document):
    target = resolve("soc_a_fpga", catalog=quiet(with_fpga(document, memories_removed=["ssram"])))
    assert [r.name for r in target.memories()] == ["tcm", "nvm"]


def test_classify_address(catalog):
    target = resolve("board_a", catalog=catalog)
    assert target.classify_address(0x20000010) == "tcm"
    assert target.classify_address(0x60000000) == "psram0"
    assert target.classify_address(0x10000000) is None


def test_clocks(catalog):
    target = resolve("board_a", catalog=catalog)
    default = target.default_operating_point
    assert default is not None and default.name == "lp"
    assert [p.name for p in target.operating_points()] == ["lp", "hp"]
    assert (target.cpu_mhz(), target.cpu_mhz("hp"), target.npu_mhz()) == (96, 192, 96)
    assert dict(target.npu_clocks()) == {"lp": 96, "hp": 192}
    assert target.operating_point(domain="cpu").name == "lp"
    with pytest.raises(PlatformError, match="no operating point 'turbo'"):
        target.cpu_mhz("turbo")


def test_names_inside_an_entry_fold_case(catalog):
    """ADR 0002 section 2.3: the estimator's ``npu_mhz("HP")`` finds point ``hp``."""
    target = resolve("board_a", boot="SBL", catalog=catalog)
    assert target.boot is not None and target.boot.name == "sbl"
    assert (target.cpu_mhz("HP", core="CM55_0"), target.npu_mhz("Hp", npu="NPU_0")) == (192, 192)
    assert target.operating_point("LP", domain="CPU").name == "lp"
    assert target.region("TCM").name == "tcm" and target.region("PSRAM0").name == "psram0"
    assert target.has_region("NVM")
    assert target.reachable("CM55_0", "TCM") is not None
    assert target.memories("CM55_0") == target.memories(0)


def test_the_trace_clock_is_whole_mhz(document):
    document["boards"]["board_a"]["trace_clock_mhz"] = 48
    target = resolve("board_a", catalog=quiet(document))
    assert target.trace_clock_mhz == 48 and type(target.trace_clock_mhz) is int
    document["boards"]["board_a"]["trace_clock_mhz"] = 24.576
    assert resolve("board_a", catalog=quiet(document)).trace_clock_mhz == 24.576


def test_npu_clocks_skip_a_point_that_leaves_the_npu_domain_unset(document):
    document["socs"]["soc_a"]["operating_points"]["sleep"] = {"domains": {"cpu": "lp"}}
    target = resolve("board_a", catalog=quiet(document))
    assert dict(target.npu_clocks()) == {"lp": 96, "hp": 192}


def test_the_boot_warning_points_at_the_caller_from_either_entry_point(catalog):
    for call in (
        lambda: resolve("board_a", boot="nbl", catalog=catalog),
        lambda: catalog.resolve("board_a", boot="nbl"),
    ):
        with pytest.warns(PlatformWarning) as record:
            call()
        assert record[0].filename == __file__


def test_boot_follows_the_board_provisioning(catalog):
    target = resolve("board_a", catalog=catalog)
    assert target.boot is not None and target.boot.name == "sbl"
    assert target.flash_load_address() == 0x00400000 + 64 * KB
    assert dict(target.usable_nvm()) == {"nvm": 4 * KB * KB - 64 * KB}


def test_an_explicit_boot_wins_and_warns_when_it_differs(catalog):
    with pytest.warns(PlatformWarning, match="differs from the board's provisioning"):
        target = resolve("board_a", boot="nbl", catalog=catalog)
    assert (target.flash_load_address(), dict(target.usable_nvm())) == (
        0x00400000,
        {"nvm": 4 * KB * KB},
    )
    with pytest.raises(PlatformError, match="no boot configuration 'xbl'"):
        resolve("board_a", boot="xbl", catalog=catalog)


def add_vendor_radio(document):
    """A vendor-programmed radio core; both cores get the nvm entries its slots need."""
    soc = document["socs"]["soc_a"]
    soc["cores"].append(
        {
            "id": "radio_m4",
            "role": "radio",
            "core": "cortex-m4",
            "clock_domain": "cpu",
            "options": {"fpu": "fpv4-sp-d16", "mve": "none"},
            "programmable_by": "vendor",
        }
    )
    for master in ("cm55_0", "radio_m4"):
        soc["access"].append({"master": master, "target": "nvm", "access": "direct"})


def radio_slot(offset, size):
    return {
        "core": "radio_m4",
        "region": "nvm",
        "offset": offset,
        "size": size,
        "supplier": "vendor",
    }


def test_usable_nvm_leaves_out_other_cores_image_slots(document):
    add_vendor_radio(document)
    document["parts"]["PART-A"]["image_slots"] = {"radio": radio_slot("3M", "432K")}
    target = resolve("board_a", catalog=quiet(document))
    assert dict(target.usable_nvm()) == {"nvm": 4 * KB * KB - 64 * KB - 432 * KB}
    assert dict(target.usable_nvm("radio_m4")) == {}  # only the vendor programs it


def test_a_soc_image_slot_applies_to_the_bare_soc_unless_the_part_replaces_it(document):
    add_vendor_radio(document)
    document["socs"]["soc_a"]["image_slots"] = {"radio": radio_slot("4080K", "16K")}
    catalog = quiet(document)
    soc_nvm = dict(resolve("soc_a", catalog=catalog).usable_nvm())
    assert soc_nvm == {"nvm": 4 * KB * KB - 64 * KB - 16 * KB}
    document["parts"]["PART-A"]["image_slots"] = {"radio": radio_slot("3M", "432K")}
    target = resolve("board_a", catalog=quiet(document))
    assert dict(target.usable_nvm()) == {"nvm": 4 * KB * KB - 64 * KB - 432 * KB}


@pytest.mark.parametrize("pmu", ["dwt", "none"])
def test_a_core_with_no_pmu_tier_reports_no_pmu(document, pmu):
    document["cores"]["cortex-m4"]["pmu"] = pmu
    document["socs"]["soc_a"]["cores"][0]["core"] = "cortex-m4"
    document["socs"]["soc_a"]["cores"][0]["options"] = {"fpu": "fpv4-sp-d16", "mve": "none"}
    target = resolve("board_a", catalog=quiet(document))
    assert (target.isa().has_pmu, target.isa().pmu_kind) == (False, pmu)
    assert "pmu" not in target.capabilities


@pytest.mark.parametrize(
    ("programmable_by", "free"), [("either", 4032), ("vendor", None), (None, None)]
)
def test_usable_nvm_is_empty_for_a_core_no_customer_programs(document, programmable_by, free):
    """RFC 0002 multicore: an unset programmable_by is a core with no loadable image."""
    add_vendor_radio(document)
    radio = document["socs"]["soc_a"]["cores"][1]
    del radio["programmable_by"]
    if programmable_by is not None:
        radio["programmable_by"] = programmable_by
    target = resolve("board_a", catalog=quiet(document))
    expected = {} if free is None else {"nvm": free * KB}
    assert dict(target.usable_nvm("radio_m4")) == expected


def test_debug_facts_fall_back_from_board_to_part(document):
    document["parts"]["PART-A"]["jlink_device"] = "PART-A-JLINK"
    assert resolve("board_a", catalog=quiet(document)).jlink_device == "PART-A-JLINK"
    document["boards"]["board_a"]["jlink_device"] = "BOARD-JLINK"
    assert resolve("board_a", catalog=quiet(document)).jlink_device == "BOARD-JLINK"


def test_release_status_and_origin(document):
    for kind in ("socs", "parts", "boards", "memory_devices"):
        for entry in document[kind].values():
            entry["release_status"] = "public"
    catalog = quiet(document)
    assert resolve("board_a", catalog=catalog).release_status == "public"
    assert resolve("board_a", catalog=catalog).origin == "overlay"
    document["memory_devices"]["psram_8m"]["release_status"] = "embargoed"
    assert resolve("board_a", catalog=quiet(document)).release_status == "embargoed"
    assert resolve("soc_a", catalog=quiet(document)).release_status == "public"
    builtin = _load_documents([(as_builtin(document), "builtin.yaml")], builtin=True)
    assert resolve("board_a", catalog=builtin).origin == "builtin"


def test_external_region_names_skip_the_socs_own_names(document):
    document["socs"]["soc_a"]["memories"]["psram0"] = {
        "technology": "psram",
        "attachment": "external",
        "base": 0x70000000,
        "size": "8M",
    }
    target = resolve("board_a", catalog=quiet(document))
    assert [r.name for r in target.external_memories()] == ["psram1"]
    assert target.region("psram1").base == 0x60000000
    assert target.region("psram0").base == 0x70000000


# ---- application_ranges (#73) -----------------------------------------------------------


def test_application_ranges_subtract_reservations_and_other_cores_slots(document):
    """The region less the selected boot's reservations and other cores' slots, in order."""
    soc = document["socs"]["soc_a"]
    soc["cores"].append({**soc["cores"][0], "id": "radio_0", "role": "radio"})
    soc["access"] += [
        {"master": "radio_0", "target": "nvm", "access": "direct"},
        {"master": "cm55_0", "target": "nvm", "access": "direct"},
    ]
    soc["image_slots"] = {
        "radio": {
            "core": "radio_0",
            "region": "nvm",
            "offset": "3M",
            "size": "512K",
            "supplier": "vendor",
        },
        "app": {
            "core": "cm55_0",
            "region": "nvm",
            "offset": "64K",
            "size": "1M",
            "supplier": "customer",
        },
    }
    target = quiet(document).resolve("board_a")
    ranges = target.application_ranges()
    nvm = [(r.start, r.end) for r in ranges["nvm"]]
    base = 0x00400000
    assert nvm == [
        (base + 64 * KB, base + 3 * KB * KB),
        (base + 3 * KB * KB + 512 * KB, base + 4 * KB * KB),
    ]
    first = ranges["nvm"][0]
    assert (first.region, first.core, first.boot, first.size) == (
        "nvm",
        "cm55_0",
        "sbl",
        3 * KB * KB - 64 * KB,
    )
    assert first.access is not None and first.access.master == "cm55_0"
    assert first.provenance.status == "derived"
    assert "fact:soc:soc_a:boot_configs.sbl.reserved.sbl.size" in first.provenance.source
    assert "fact:soc:soc_a:image_slots.radio.offset" in first.provenance.source
    assert [(r.start, r.end) for r in ranges["ssram"]] == [(0x20080000, 0x20080000 + 3 * KB * KB)]
    # The radio core keeps its own slot and loses the application's.
    radio = target.application_ranges("radio_0")["nvm"]
    assert [(r.start, r.end) for r in radio] == [(base + 64 * KB + KB * KB, base + 4 * KB * KB)]


def test_application_ranges_follow_the_selected_boot_and_the_discouraged_filter(document):
    soc = document["socs"]["soc_a"]
    soc["access"].append(
        {"master": "cm55_0", "target": "tcm", "access": "direct", "guidance": "discouraged"}
    )
    catalog = quiet(document)
    sbl = catalog.resolve("board_a").application_ranges()
    with pytest.warns(PlatformWarning):  # an explicit boot that is not the provisioning
        nbl = catalog.resolve("board_a", boot="nbl").application_ranges()
    assert sbl["nvm"][0].start == 0x00410000 and nbl["nvm"][0].start == 0x00400000
    assert nbl["nvm"][0].boot == "nbl"
    assert "tcm" not in sbl and "tcm" in catalog.resolve("board_a").application_ranges(
        include_discouraged=True
    )


def test_application_ranges_tell_an_unknown_region_from_an_empty_one(document):
    soc = document["socs"]["soc_a"]
    soc["boot_configs"]["sbl"]["reserved"] = {"all": {"region": "nvm", "offset": 0, "size": "4M"}}
    soc["memories"]["extra"] = {"technology": "sram", "attachment": "system", "size": "1M"}
    soc["access"].append({"master": "cm55_0", "target": "extra", "access": "direct"})
    ranges = quiet(document).resolve("board_a").application_ranges()
    assert ranges["nvm"] == ()  # every byte reserved: empty
    assert "extra" not in ranges  # no base: unknown, not empty


def test_application_ranges_stay_in_the_regions_address_space_and_skip_zero_sizes(document):
    soc = document["socs"]["soc_a"]
    soc["access"].append(
        {"master": "cm55_0", "target": "nvm", "access": "direct", "address": 0x08000000}
    )
    soc["boot_configs"]["sbl"]["reserved"]["nothing"] = {"region": "nvm", "offset": "1M", "size": 0}
    soc["memories"]["empty"] = {
        "technology": "sram",
        "attachment": "system",
        "size": 0,
        "base": 0x30000000,
    }
    soc["access"].append({"master": "cm55_0", "target": "empty", "access": "direct"})
    target = quiet(document).resolve("board_a")
    ranges = target.application_ranges()
    # The region's base, as flash_load_address() uses it, not the core's own address.
    assert [(r.start, r.end) for r in ranges["nvm"]] == [(0x00410000, 0x00800000)]
    assert ranges["nvm"][0].start == target.flash_load_address()
    assert ranges["nvm"][0].provenance.source == (
        "fact:soc:soc_a:memories.nvm.base",
        "fact:soc:soc_a:memories.nvm.size",
        "fact:soc:soc_a:boot_configs.sbl.reserved.sbl.offset",
        "fact:soc:soc_a:boot_configs.sbl.reserved.sbl.size",
    )
    assert ranges["empty"] == ()


def test_application_ranges_name_facts_that_exist(document):
    """Every source a derived record names is a fact path the catalog holds, on an FPGA with
    a rebased region and its own boot configuration, and on a board with external memory."""
    document["implementations"] = {
        "soc_a_fpga": {
            "soc": "soc_a",
            "kind": "fpga",
            "subset": {"memories_rebased": {"nvm": 0x10000000}, "memories_resized": {"nvm": "2M"}},
            "boot_configs": {
                "fpga": {
                    "reserved": {"rom": {"region": "nvm", "offset": 0, "size": "32K"}},
                    "app_start": {"region": "nvm", "offset": "32K"},
                    "requires": "none",
                }
            },
            "default_boot": "fpga",
        }
    }
    catalog = quiet(document)
    facts = _provenance.Facts(catalog._trees, lambda _: True)
    for target in (catalog.resolve("soc_a_fpga"), catalog.resolve("board_a")):
        for name, ranges in target.application_ranges().items():
            assert ranges, name
            for r in ranges:
                assert r.provenance.status == "derived" and r.provenance.source
                for source in r.provenance.source:
                    key = facts.parse(source)
                    assert key is not None and facts.exists(key), (name, source)


def test_application_ranges_are_unknown_without_a_boot_configuration(document):
    soc = document["socs"]["soc_a"]
    del soc["boot_configs"], soc["default_boot"]
    document["boards"]["board_a"].pop("provisioning", None)
    target = quiet(document).resolve("board_a")
    assert target.boot is None and target.application_ranges() == {}


def test_application_ranges_credit_each_input_to_the_entry_that_states_it(document):
    """A wrong owner in a record passes a mere existence check; these pin the exact owners."""
    soc = document["socs"]["soc_a"]
    soc["cores"].append(
        {**soc["cores"][0], "id": "radio_0", "role": "radio", "programmable_by": "vendor"}
    )
    soc["access"].append({"master": "radio_0", "target": "nvm", "access": "direct"})
    soc["access"].append({"master": "cm55_0", "target": "nvm", "access": "direct"})
    soc["image_slots"] = {
        "radio": {
            "core": "radio_0",
            "region": "nvm",
            "offset": "1M",
            "size": "256K",
            "supplier": "vendor",
        }
    }
    document["parts"]["PART-A"]["image_slots"] = {
        "radio": {
            "core": "radio_0",
            "region": "nvm",
            "offset": "1M",
            "size": "512K",
            "supplier": "vendor",
        }
    }
    document["implementations"] = {
        "soc_a_fpga": {
            "soc": "soc_a",
            "kind": "fpga",
            "subset": {"memories_rebased": {"nvm": 0x10000000}, "memories_resized": {"nvm": "2M"}},
            "boot_configs": {
                "fpga": {
                    "reserved": {"rom": {"region": "nvm", "offset": 0, "size": "32K"}},
                    "app_start": {"region": "nvm", "offset": "32K"},
                    "requires": "none",
                }
            },
            "default_boot": "fpga",
        }
    }
    catalog = quiet(document)
    board = catalog.resolve("board_a").application_ranges()["nvm"][0]
    assert board.target == "board_a" and board.boot == "sbl"
    assert (
        "fact:part:PART-A:image_slots.radio.size" in board.provenance.source
    )  # the part's slot, not the Soc's
    assert "fact:soc:soc_a:image_slots.radio.size" not in board.provenance.source
    assert board.end == 0x00400000 + KB * KB  # up to the part's slot at 1M
    second = catalog.resolve("board_a").application_ranges()["nvm"][1]
    assert second.start == 0x00400000 + KB * KB + 512 * KB  # the part's 512K, not the Soc's 256K
    fpga = catalog.resolve("soc_a_fpga").application_ranges()["nvm"][0]
    assert fpga.target == "soc_a_fpga" and fpga.boot == "fpga"
    assert {
        "fact:implementation:soc_a_fpga:subset.memories_rebased.nvm",
        "fact:implementation:soc_a_fpga:subset.memories_resized.nvm",
        "fact:implementation:soc_a_fpga:boot_configs.fpga.reserved.rom.size",
    } <= set(fpga.provenance.source)
    assert (
        "fact:soc:soc_a:memories.nvm.base" not in fpga.provenance.source
    )  # the rebase supplies it
    assert not any(s.startswith("fact:soc:soc_a:boot_configs") for s in fpga.provenance.source)
    # programmable_by is not applied: the vendor-only radio core still gets its ranges.
    radio = catalog.resolve("board_a").application_ranges("radio_0")["nvm"]
    assert radio and catalog.resolve("board_a").usable_nvm("radio_0") == {}


def test_application_ranges_total_what_usable_nvm_gives():
    catalog = builtin(include_plugins=False)
    for board in catalog.boards():
        target = catalog.resolve(board.id)
        for core in target.soc.cores:
            ranges = target.application_ranges(core.id)
            for region, size in target.usable_nvm(core.id).items():
                assert sum(r.size for r in ranges[region]) == size, (board.id, core.id, region)


def test_a_rebase_that_gives_a_baseless_region_its_base_is_the_cited_source(document):
    soc = document["socs"]["soc_a"]
    del soc["memories"]["ssram"]["base"]
    document["implementations"] = {
        "soc_a_fpga": {
            "soc": "soc_a",
            "kind": "fpga",
            "subset": {"memories_rebased": {"ssram": 0x30000000}},
        }
    }
    catalog = quiet(document)
    assert "ssram" not in catalog.resolve("soc_a").application_ranges()  # no base: unknown
    rng = catalog.resolve("soc_a_fpga").application_ranges()["ssram"][0]
    assert rng.start == 0x30000000
    assert "fact:implementation:soc_a_fpga:subset.memories_rebased.ssram" in rng.provenance.source
    assert "fact:soc:soc_a:memories.ssram.base" not in rng.provenance.source
    facts = _provenance.Facts(catalog._trees, lambda _: True)
    assert all(facts.exists(k) for s in rng.provenance.source if (k := facts.parse(s)))
