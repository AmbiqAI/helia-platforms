"""The JSON export, its filter and its schema (RFC 0003, #74)."""

import copy
import dataclasses
import json
import warnings

import jsonschema
import pytest
from typer.testing import CliRunner

from conftest import RECORD, SDK_SOURCE
from helia_platforms import _digest, export, schema
from helia_platforms.catalog import (
    _data_documents,
    _data_root,
    _load_documents,
    builtin,
    load_overlay,
)
from helia_platforms.cli import app

runner = CliRunner()
FILE_FORMAT = jsonschema.Draft202012Validator(json.loads(schema.committed()))
EXPORT = jsonschema.Draft202012Validator(json.loads(schema.committed(export=True)))
_REGISTER = ("schema_version", "documents", "repositories", "unverified_allowed")
_TABLES = ("socs", "implementations", "parts", "boards", "addons", "memory_devices")


def public(document):
    """Every entry of ``document`` public, as a built-in entry must be."""
    for kind in _TABLES:
        for entry in document.get(kind, {}).values():
            entry["release_status"] = "public"
    return document


def overlay(document):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return load_overlay(document, base=None)


def test_the_committed_export_schema_is_current():
    assert schema.committed(export=True) == schema.render(export=True), (
        "the committed export schema is stale; run "
        f"`uv run helia-platforms export --export-schema > "
        f"src/helia_platforms/schema/{schema.EXPORT_SCHEMA_FILE}`"
    )


@pytest.mark.parametrize("provenance", [False, True])
def test_the_built_in_export_validates_against_both_schemas(provenance):
    document = export.document(builtin(include_plugins=False), provenance=provenance)
    assert list(EXPORT.iter_errors(document)) == []
    assert list(FILE_FORMAT.iter_errors(document["catalog"])) == []
    assert document["identity"]["sources"] == []


@pytest.mark.parametrize(
    "where", [(), ("identity",), ("catalog",)], ids=["top", "identity", "catalog"]
)
def test_the_export_schema_rejects_a_second_schema_version(where):
    document = export.document(builtin(include_plugins=False))
    member = document
    for key in where:
        member = member[key]
    member["schema_version"] = 2
    assert not EXPORT.is_valid(document)


def test_the_export_has_no_records_by_default():
    text = export.render(builtin(include_plugins=False).to_dict())
    assert '"provenance"' not in text
    assert text.endswith("}\n")
    assert text == export.render(json.loads(text))  # sorted keys, two-space indentation


def test_records_survive_a_round_trip():
    catalog = builtin(include_plugins=False)
    member = export.document(catalog, provenance=True)["catalog"]
    register = [
        ({k: v for k, v in data.items() if k in _REGISTER}, origin)
        for data, origin in _data_documents(_data_root())
    ]
    back = _load_documents([(member, "export.json"), *register], builtin=True)
    for kind, entries in back._tables.items():
        for entry_id, entry in entries.items():
            assert entry == catalog._entry(kind, entry_id), (kind, entry_id)


def test_exported_records_are_copies():
    catalog = builtin(include_plugins=False)
    before = export.render(export.document(catalog, provenance=True))
    written = export.document(catalog, provenance=True)["catalog"]["socs"]["apollo510"]
    written["provenance"]["source"].append("doc:changed@1:p1")
    written["provenance"]["notes"] = "changed"
    assert export.render(export.document(catalog, provenance=True)) == before


def test_external_memory_names_survive_the_json_form(document):
    """Sorted keys reorder a population; the ``<technology><n>`` names must not follow."""
    board = document["boards"]["board_a"]
    board["interfaces"]["iom0"] = {"controller": "iom0", "aperture_base": 0x70000000}
    document["memory_devices"]["psram_2m"] = {"technology": "psram", "capacity": "2M"}
    board["population"] = {"mspi0": "psram_8m", "iom0": "psram_2m"}  # not in name order
    catalog = overlay(public(document))
    back = overlay(json.loads(export.render(catalog.to_dict()))["catalog"])

    def answers(target):
        return [
            (r.name, r.base, r.size, target.reachable("cm55_0", r.name).target)
            for r in target.external_memories()
        ]

    assert answers(catalog.resolve("board_a")) == answers(back.resolve("board_a"))
    assert answers(back.resolve("board_a"))[0] == ("psram0", 0x70000000, 2 << 20, "iom0")


def test_values_survive_a_round_trip_without_records(document):
    catalog = overlay(public(document))
    back = overlay(catalog.to_dict()["catalog"])
    for kind, entries in back._tables.items():
        for entry_id, entry in entries.items():
            assert _digest.project(entry) == _digest.project(catalog._entry(kind, entry_id))


def test_an_entry_is_written_after_its_based_on_merge(document):
    public(document)
    document["socs"]["soc_b"] = {
        "based_on": "soc_a",
        "release_status": "public",
        "memories_removed": ["ssram"],
        "series": "other",
    }
    written = overlay(document).to_dict()["catalog"]["socs"]["soc_b"]
    assert "based_on" not in written and "memories_removed" not in written
    assert set(written["memories"]) == {"tcm", "nvm"} and written["series"] == "other"


def test_a_derived_entry_round_trips_without_a_second_merge(document):
    """The loaded entry keeps based_on (#134); the export must not, or a reader of the
    export merges the already-merged entry over its base again and the removals return."""
    public(document)
    document["socs"]["soc_b"] = {
        "based_on": "soc_a",
        "release_status": "public",
        "memories_removed": ["ssram"],
        "peripherals_removed": ["iom2"],
    }
    document["socs"]["soc_c"] = {
        "based_on": "soc_b",
        "release_status": "public",
        "peripherals_removed": ["iom1"],
    }
    document["boards"]["board_b"] = {"based_on": "board_a", "release_status": "public"}
    catalog = overlay(document)
    assert catalog._entry("socs", "soc_c").based_on == "soc_b"
    exports = [
        catalog.to_dict()["catalog"],
        export._document(catalog, filtered=False, provenance=False)["catalog"],
        export._document(catalog, filtered=False, provenance=True)["catalog"],
    ]
    for written in exports:
        back = overlay(written)
        for kind, entry_id in (("socs", "soc_b"), ("socs", "soc_c"), ("boards", "board_b")):
            assert "based_on" not in written[kind][entry_id]
            assert _digest.project(back._entry(kind, entry_id)) == _digest.project(
                catalog._entry(kind, entry_id)
            )
            assert back._entry(kind, entry_id).based_on is None
        assert [m.name for m in back._entry("socs", "soc_c").memories] == ["tcm", "nvm"]
        assert back._entry("socs", "soc_c").peripherals == ("mspi0", "iom0")


def test_an_implementation_keeps_its_subset(document):
    public(document)
    document["implementations"] = {
        "soc_a_fpga": {
            "soc": "soc_a",
            "kind": "fpga",
            "release_status": "public",
            "subset": {"memories_removed": ["ssram"], "max_cpu_mhz": 96},
        }
    }
    written = overlay(document).to_dict()["catalog"]["implementations"]["soc_a_fpga"]
    assert written["subset"] == {"memories_removed": ["ssram"], "max_cpu_mhz": 96}
    assert "memories" not in written


def test_a_value_list_item_keeps_its_own_record(document):
    record = {**RECORD, "status": "sdk", "source": [SDK_SOURCE]}
    document["socs"]["soc_a"]["peripherals"][1] = {"value": "iom0", "provenance": record}
    catalog = overlay(public(document))
    written = export.document(catalog, provenance=True)["catalog"]["socs"]["soc_a"]
    assert written["peripherals"][1] == {"value": "iom0", "provenance": record}
    assert written["peripherals"][0] == "mspi0"


# ---- the release-status filter ------------------------------------------------------


@pytest.fixture
def mixed(document):
    """soc_a public with board_a and an add-on; soc_b embargoed with its own core and board."""
    public(document)
    soc_b = copy.deepcopy(document["socs"]["soc_a"])
    soc_b["cores"][0]["core"] = "cortex-m4"
    soc_b["cores"][0]["options"] = {"fpu": "fpv4-sp-d16", "mve": "none"}
    soc_b["release_status"] = "embargoed"
    document["socs"]["soc_b"] = soc_b
    document["socs"]["soc_a"]["default_board"] = "board_a"
    document["parts"]["PART-B"] = {"soc": "soc_b", "release_status": "public"}
    document["boards"]["board_b"] = {
        "category": "evaluation",
        "part": "PART-B",
        "interfaces": {"iom0": {"controller": "iom0"}},
        "release_status": "public",
    }
    document["boards"]["board_a"]["interfaces"]["iom0"] = {"controller": "iom0"}
    document["memory_devices"]["secret_psram"] = {"technology": "psram", "capacity": "8M"}
    document["addons"] = {
        "shield": {
            "fits_boards": ["board_a", "board_b"],
            "occupies": ["iom0"],
            "population": {"iom0": "psram_8m"},
            "release_status": "public",
        },
        "secret_shield": {
            "fits_boards": ["board_a"],
            "occupies": ["iom0"],
            "population": {"iom0": "secret_psram"},
            "release_status": "public",
        },
    }
    document["compositions"] = {
        "board_a_shield": {"board": "board_a", "addons": ["shield"]},
        "board_a_secret": {"board": "board_a", "addons": ["secret_shield"]},
        "board_b_shield": {"board": "board_b", "addons": ["shield"]},
    }
    return overlay(document)


def test_the_filter_drops_every_entry_whose_chain_is_embargoed(mixed):
    written = mixed.to_dict()["catalog"]
    assert set(written["socs"]) == {"soc_a"}
    assert set(written["parts"]) == {"PART-A"}  # PART-B's Soc is embargoed
    assert set(written["boards"]) == {"board_a"}
    assert set(written["memory_devices"]) == {"psram_8m"}
    assert set(written["cores"]) == {"cortex-m55"}  # cortex-m4 only in soc_b


def test_the_filter_scrubs_references_and_drops_compositions(mixed):
    written = mixed.to_dict()["catalog"]
    assert set(written["addons"]) == {"shield"}  # secret_shield populates an embargoed device
    assert written["addons"]["shield"]["fits_boards"] == ["board_a"]
    assert set(written["compositions"]) == {"board_a_shield"}
    assert written["socs"]["soc_a"]["default_board"] == "board_a"
    assert list(EXPORT.iter_errors(mixed.to_dict())) == []


def test_the_filter_scrubs_shorthand_members(mixed):
    catalog = dataclasses.replace(mixed, shorthands={"AB": ("soc_a", "soc_b"), "B": ("soc_b",)})
    assert catalog.to_dict()["catalog"]["shorthands"] == {"AB": ["soc_a"]}


def test_the_filter_drops_a_default_board_it_drops(document):
    public(document)
    document["socs"]["soc_a"]["default_board"] = "board_a"
    document["boards"]["board_a"]["release_status"] = "embargoed"
    written = overlay(document).to_dict()["catalog"]
    assert "default_board" not in written["socs"]["soc_a"]
    assert "boards" not in written


def test_the_unfiltered_export_keeps_everything(mixed):
    unfiltered = export._document(mixed, filtered=False, provenance=False)["catalog"]
    assert set(unfiltered["socs"]) == {"soc_a", "soc_b"}
    assert set(unfiltered["compositions"]) == {"board_a_shield", "board_a_secret", "board_b_shield"}


# ---- the command line ----------------------------------------------------------------


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["--schema", "--export-schema"],
        ["--schema", "--provenance"],
        ["--export-schema", "--include-plugins"],
        ["--schema", "--check"],
        ["--json", "-", "--check"],
    ],
)
def test_the_cli_refuses_a_meaningless_combination(args):
    result = runner.invoke(app, ["export", *args])
    assert result.exit_code == 2, result.output


def test_the_cli_writes_and_checks_the_export(tmp_path):
    path = tmp_path / "export.json"
    assert runner.invoke(app, ["export", "--json", str(path)]).exit_code == 0
    assert path.read_text() == export.render(builtin(include_plugins=False).to_dict())
    assert runner.invoke(app, ["export", "--json", str(path), "--check"]).exit_code == 0
    path.write_text(path.read_text().replace("apollo510", "apollo511", 1))
    result = runner.invoke(app, ["export", "--json", str(path), "--check"])
    assert result.exit_code == 1
    assert "differs from a fresh export" in result.output
    missing = tmp_path / "missing.json"
    assert runner.invoke(app, ["export", "--json", str(missing), "--check"]).exit_code == 1
    fresh = export.render(builtin(include_plugins=False).to_dict())
    path.write_bytes(fresh.replace("\n", "\r\n").encode())  # what read_text would hide
    assert runner.invoke(app, ["export", "--json", str(path), "--check"]).exit_code == 1


def test_the_cli_export_names_an_overlay_in_identity(tmp_path):
    path = tmp_path / "board.yaml"
    path.write_text("schema_version: 1\n")
    result = runner.invoke(app, ["export", "--json", "-", "--overlay", str(path)])
    assert result.exit_code == 0, result.output
    (source,) = json.loads(result.output)["identity"]["sources"]
    assert source["label"] == "overlay:board.yaml"


def test_the_cli_writes_the_export_schema():
    result = runner.invoke(app, ["export", "--export-schema"])
    assert result.exit_code == 0
    assert result.output == schema.render(export=True)
