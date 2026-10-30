"""Link environments: the dataset, ``Target.budget`` and the ``windows`` command (#73)."""

import pytest
import yaml
from typer.testing import CliRunner

import generate_link_environments as generator
from helia_platforms import FormatError, PlatformError, load_overlay
from helia_platforms.catalog import builtin
from helia_platforms.cli import app
from helia_platforms.link_environments import (
    environment_to_dict,
    find_link_environment,
    link_environments,
    load_link_environment,
)

K = 1024


def env(regions, applies_to=("soc_a",), family="gnu"):
    return load_link_environment(
        {
            "owner": "test",
            "link_family": family,
            "profile": "default",
            "applies_to": list(applies_to),
            "regions": regions,
            "source": "linker.ld",
            "revision": "a" * 40,
        }
    )


@pytest.fixture
def catalog(document):
    return load_overlay(document)


# ---- the dataset ----------------------------------------------------------------------


def test_the_dataset_regenerates_byte_for_byte():
    assert generator.render(generator.generate()) == generator.OUTPUT.read_text(), (
        "the link-environment dataset is stale; run "
        "`uv run python scripts/generate_link_environments.py`"
    )


def test_the_check_mode_fails_on_a_stale_dataset(tmp_path, monkeypatch):
    stale = tmp_path / "link_environments.json"
    stale.write_text("{}\n")
    monkeypatch.setattr(generator, "OUTPUT", stale)
    monkeypatch.setattr(generator, "ROOT", tmp_path)
    assert generator.main(["--check"]) == 1
    assert generator.main([]) == 0
    assert generator.main(["--check"]) == 0


def test_every_shipped_environment_is_public_and_names_public_entries():
    catalog = builtin(include_plugins=False)
    environments = link_environments()
    assert {e.owner for e in environments} == {"nsx-ambiq-sdk", "zephyr"}
    for environment in environments:
        assert environment.release_status == "public"
        for entry in environment.applies_to:
            assert catalog.resolve(entry).release_status == "public"


def test_the_sdk_environments_cover_every_catalog_soc_the_snapshot_holds():
    catalog = builtin(include_plugins=False)
    for family in ("gnu", "armlink"):
        covered = {e.applies_to[0] for e in link_environments(link_family=family)}
        assert covered == {s.id for s in catalog.socs()}


def test_every_sdk_window_lies_inside_the_physical_regions():
    catalog = builtin(include_plugins=False)
    for environment in link_environments(owner="nsx-ambiq-sdk"):
        target = catalog.resolve(environment.applies_to[0])
        master = target.cores()[0].id
        for name, window in environment.regions.items():
            end = window.start + window.length
            inside = sum(
                max(0, min(end, base + region.size) - max(window.start, base))
                for region in target.memories()
                for base in target._bases(region, master)
            )
            assert inside == window.length, (environment.source, name)


def test_the_generator_applies_carve_outs_and_the_zephyr_load_offset():
    (apollo3p,) = [e for e in link_environments(link_family="gnu") if "apollo3p" in e.applies_to]
    assert apollo3p.regions["STACKMEM"].reserved
    assert not apollo3p.regions["RWMEM"].reserved
    (armlink,) = [
        e for e in link_environments(link_family="armlink") if "apollo510" in e.applies_to
    ]
    assert armlink.regions["ARM_LIB_STACK"].reserved
    (apollo3_evb,) = [e for e in link_environments(owner="zephyr") if "apollo3_evb" in e.applies_to]
    flash = apollo3_evb.regions["FLASH"]
    assert (flash.start, flash.length, flash.chosen) == (0xC000, 976 * K, ("zephyr,flash",))
    assert apollo3_evb.regions["ITCM"].chosen == ("zephyr,itcm",)


# ---- budget ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "family", "expected"),
    [
        # gcc's MCU_TCM stops at 496K of the 512K DTCM.
        (
            "apollo510",
            "gnu",
            {"itcm": 256 * K, "dtcm": 496 * K, "ssram": 3 * K * K, "mram": 4032 * K},
        ),
        # armlink's fixed heap and stack sit above MCU_TCM and are carved out.
        ("apollo510", "armlink", {"dtcm": 492 * K}),
        # The fitted part's 432K radio slot (NVM-M41) leaves 1552K of the 1984K window.
        ("apollo510dL_evb", "gnu", {"dtcm": 240 * K, "mram": 1552 * K}),
        ("apollo330mP_evb", "armlink", {"dtcm": 236 * K, "mram": 1552 * K}),
        # apollo3's RWMEM runs from TCM into SRAM; each region gets its share.
        ("apollo3", "gnu", {"tcm": 64 * K, "sram": 320 * K, "flash": 976 * K}),
        # Zephyr's RAM runs across the rest of TCM and every SRAM bank.
        (
            "apollo4p_evb",
            "zephyr",
            {"tcm": 384 * K, "ssram0": K * K, "extram": 384 * K, "ssram1": K * K},
        ),
        ("apollo510_evb", "zephyr", {"ssram": 3 * K * K, "psram0": 64 * K * K}),
    ],
)
def test_budget(name, family, expected):
    target = builtin(include_plugins=False).resolve(name)
    environment = find_link_environment(target, family)
    assert environment is not None
    budget = target.budget(environment)
    assert {region: budget[region] for region in expected} == expected


def test_budget_raises_for_a_target_the_environment_does_not_cover():
    catalog = builtin(include_plugins=False)
    (zephyr,) = [e for e in link_environments(owner="zephyr") if "apollo510_evb" in e.applies_to]
    with pytest.raises(PlatformError, match="does not apply"):
        catalog.resolve("apollo510L").budget(zephyr)


def test_budget_clips_to_the_region_and_takes_out_reservations_and_carve_outs(catalog):
    target = catalog.resolve("board_a")
    budget = target.budget(
        env(
            {
                "FLASH": {"start": 0x00400000, "length": 8 * K * K},  # past the 4M region
                "RAM": {"start": 0x20000000, "length": 512 * K},
                "STACK": {"start": 0x2007C000, "length": 16 * K, "reserved": True},
                "SRAM": {"start": 0x20080000, "length": 1024 * K},
            }
        )
    )
    assert dict(budget) == {"tcm": 496 * K, "ssram": 1024 * K, "nvm": 4 * K * K - 64 * K}


def test_a_region_seen_at_two_bases_counts_once(document):
    document["socs"]["soc_a"]["memories"]["tcm"]["alternate_bases"] = [0x30000000]
    target = load_overlay(document).resolve("soc_a")
    budget = target.budget(
        env(
            {
                "A": {"start": 0x20000000, "length": 256 * K},
                "B": {"start": 0x30000000, "length": 512 * K},
            }
        )
    )
    assert budget["tcm"] == 512 * K


def test_budget_leaves_out_regions_no_window_overlaps(catalog):
    budget = catalog.resolve("soc_a").budget(env({"RAM": {"start": 0x20000000, "length": 4 * K}}))
    assert dict(budget) == {"tcm": 4 * K}


def test_the_reference_chain_stops_at_a_rebasing_implementation(document):
    document["implementations"] = {
        "cut": {"soc": "soc_a", "kind": "fpga", "subset": {"memories_rebased": {"nvm": 0}}}
    }
    catalog = load_overlay(document)
    silicon = env({"RAM": {"start": 0x20000000, "length": 4 * K}})
    assert catalog.resolve("board_a").covered_by(silicon)
    assert catalog.resolve("PART-A").covered_by(silicon)
    assert not catalog.resolve("cut").covered_by(silicon)
    fpga = env({"RAM": {"start": 0x20000000, "length": 4 * K}}, applies_to=("cut",))
    assert catalog.resolve("cut").budget(fpga) == {"tcm": 4 * K}


def test_find_returns_none_where_no_environment_covers_the_target(catalog):
    assert find_link_environment(catalog.resolve("board_a"), "gnu") is None


# ---- environment files ------------------------------------------------------------------


def test_an_environment_file_round_trips(tmp_path):
    (shipped,) = [e for e in link_environments(link_family="gnu") if "apollo510" in e.applies_to]
    path = tmp_path / "env.yaml"
    path.write_text(yaml.safe_dump(environment_to_dict(shipped)))
    assert load_link_environment(path) == shipped


def test_an_environment_file_lists_every_problem():
    with pytest.raises(FormatError) as raised:
        load_link_environment(
            {
                "owner": "x",
                "link_family": "iar",
                "applies_to": [],
                "regions": {
                    "A": {"start": -1, "length": 4},
                    "B": {"start": 0, "length": 4, "x": 1},
                },
                "colour": "red",
            }
        )
    problems = "\n".join(raised.value.problems)
    for fragment in (
        "unknown key 'colour'",
        "profile must be",
        "link_family must be one of",
        "applies_to must be",
        "regions.A: start and length",
        "regions.B: unknown key 'x'",
    ):
        assert fragment in problems


# ---- the windows command ----------------------------------------------------------------


def test_windows_prints_each_environment_and_the_budget():
    result = CliRunner().invoke(app, ["windows", "apollo510dL_evb", "--family", "gnu"])
    assert result.exit_code == 0, result.output
    assert "nsx-ambiq-sdk gnu default" in result.output
    assert "MCU_MRAM                   0x00410000, 1984K, in mram" in result.output
    assert "budget                     dtcm 240K, ssram 1792K, mram 1552K" in result.output


def test_windows_reads_an_environment_file(tmp_path):
    path = tmp_path / "env.yaml"
    path.write_text(
        yaml.safe_dump(
            environment_to_dict(
                env({"RAM": {"start": 0x20000000, "length": 4 * K}}, ("apollo510",))
            )
        )
    )
    runner = CliRunner()
    result = runner.invoke(app, ["windows", "apollo510_evb", "--environment", str(path)])
    assert result.exit_code == 0, result.output
    assert "budget                     dtcm 4K" in result.output
    result = runner.invoke(app, ["windows", "apollo4p_evb", "--environment", str(path)])
    assert result.exit_code == 1
    assert "does not apply to apollo4p_evb" in result.output


def test_windows_says_when_nothing_covers_the_target():
    result = CliRunner().invoke(app, ["windows", "apollo510L", "--family", "zephyr"])
    assert result.exit_code == 0
    assert "no link environment covers apollo510L" in result.output


def test_identity_records_the_dataset_sources():
    sources = builtin(include_plugins=False).identity().link_environment_sources
    assert {s["repository"] for s in sources} >= {"AmbiqAI/nsx-ambiq-sdk"}
    assert all(set(s) == {"repository", "revision", "commit"} for s in sources)
