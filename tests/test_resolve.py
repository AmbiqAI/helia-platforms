import copy
import warnings

import pytest

import helia_platforms
from conftest import as_builtin
from helia_platforms import (
    AmbiguousPlatform,
    PlatformError,
    PlatformWarning,
    UnknownPlatform,
    load_overlay,
    resolve,
    resolve_board,
    resolve_soc,
)
from helia_platforms.catalog import _load_documents

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


def test_a_dwt_core_reports_no_pmu(document):
    document["socs"]["soc_a"]["cores"][0]["core"] = "cortex-m4"
    document["socs"]["soc_a"]["cores"][0]["options"] = {"fpu": "fpv4-sp-d16", "mve": "none"}
    target = resolve("board_a", catalog=quiet(document))
    assert (target.isa().has_pmu, target.isa().pmu_kind) == (False, "dwt")
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
