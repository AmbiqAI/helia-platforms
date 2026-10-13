import copy
import warnings

import pytest

import helia_platforms
from conftest import RECORD
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
    document["compositions"] = {"board_a_shield": {"board": "board_a", "addons": ["shield"]}}
    target = resolve("board_a_shield", catalog=quiet(document))
    assert (target.id, [a.id for a in target.addons]) == ("board_a", ["shield"])
    assert "board_a_shield" in target.aliases
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


def test_usable_nvm_leaves_out_other_cores_image_slots(document):
    document["socs"]["soc_a"]["cores"].append(
        {
            "id": "radio_m4",
            "role": "radio",
            "core": "cortex-m4",
            "clock_domain": "cpu",
            "options": {"fpu": "fpv4-sp-d16", "mve": "none"},
            "programmable_by": "vendor",
        }
    )
    slot = {
        "core": "radio_m4",
        "region": "nvm",
        "offset": "3M",
        "size": "432K",
        "supplier": "vendor",
    }
    document["parts"]["PART-A"]["image_slots"] = {"radio": slot}
    target = resolve("board_a", catalog=quiet(document))
    assert dict(target.usable_nvm()) == {"nvm": 4 * KB * KB - 64 * KB - 432 * KB}


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


def as_builtin(document):
    for kind in ("cores", "socs", "implementations", "parts", "boards", "addons", "memory_devices"):
        for entry in document.get(kind, {}).values():
            entry.setdefault("provenance", RECORD)
            if kind != "cores":
                entry["release_status"] = "public"
    return document
