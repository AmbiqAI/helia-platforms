import copy
import dataclasses
import json
from types import MappingProxyType

import pytest
import yaml

import helia_platforms
from conftest import RECORD
from helia_platforms import _digest, _parse
from helia_platforms.catalog import _EMPTY, _load_documents, load_overlay
from helia_platforms.errors import FormatError


def builtin_grade(document):
    """The base document with what built-in entries need: a record and public status."""
    for kind, table in document.items():
        if kind == "schema_version":
            continue
        for entry in table.values():
            entry.setdefault("provenance", RECORD)
            if kind != "cores":
                entry["release_status"] = "public"
    return document


def digest_of(document):
    return _load_documents([(document, "builtin.yaml")], builtin=True).catalog_digest


@pytest.fixture
def builtin_document(document):
    return builtin_grade(document)


def reversed_dict(mapping):
    return dict(reversed(list(mapping.items())))


def test_canonical_bytes():
    assert (
        _digest.canonical({"b": 1, "a": "é", "c": [2, 1]}) == '{"a":"é","b":1,"c":[2,1]}'.encode()
    )
    with pytest.raises(ValueError):
        _digest.canonical({"a": float("nan")})


def test_digest_form(builtin_document):
    found = digest_of(builtin_document)
    assert found.startswith("sha256:")
    assert len(found) == len("sha256:") + 64


def test_reordering_value_lists_and_keyed_collections_keeps_digest(builtin_document):
    before = digest_of(copy.deepcopy(builtin_document))
    soc = builtin_document["socs"]["soc_a"]
    soc["peripherals"].reverse()
    soc["access"].reverse()
    soc["memories"] = reversed_dict(soc["memories"])
    soc["clock_domains"] = {
        k: reversed_dict(v) for k, v in reversed_dict(soc["clock_domains"]).items()
    }
    soc["operating_points"] = reversed_dict(soc["operating_points"])
    soc["boot_configs"] = reversed_dict(soc["boot_configs"])
    builtin_document["socs"] = reversed_dict(builtin_document["socs"])
    builtin_document["cores"] = reversed_dict(builtin_document["cores"])
    assert digest_of(builtin_document) == before


def test_reordering_cores_changes_digest(builtin_document):
    soc = _load_documents([(builtin_document, "b")], builtin=True)._entry("socs", "soc_a")
    second = dataclasses.replace(soc.cores[0], id="cm55_1")
    one = dataclasses.replace(soc, cores=(soc.cores[0], second))
    other = dataclasses.replace(soc, cores=(second, soc.cores[0]))

    def digest(entry):
        return _digest.catalog_digest({"socs": {"soc_a": entry}}, {}, {})

    assert digest(one) != digest(other)


def test_provenance_only_change_keeps_digest(builtin_document):
    before = digest_of(copy.deepcopy(builtin_document))
    soc = builtin_document["socs"]["soc_a"]
    soc["provenance"] = {**RECORD, "source": ["doc:DS-OTHER@2.0:p9"], "verified_on": "2026-10-12"}
    soc["memories"]["tcm"]["size"] = {"value": "512K", "provenance": RECORD}
    assert digest_of(builtin_document) == before


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d["socs"]["soc_a"]["memories"]["tcm"].update(size="256K"),
        lambda d: d["socs"]["soc_a"]["peripherals"].append("iom3"),
        lambda d: d["parts"]["PART-A"].update(aliases=["part_a_alias"]),
    ],
    ids=["value", "value-list-member", "alias"],
)
def test_data_change_changes_digest(builtin_document, change):
    before = digest_of(copy.deepcopy(builtin_document))
    change(builtin_document)
    assert digest_of(builtin_document) != before


def test_an_integer_and_the_same_float_give_the_same_digest(builtin_document):
    def digest(mhz):
        document = copy.deepcopy(builtin_document)
        document["implementations"] = {
            "impl": {
                "soc": "soc_a",
                "kind": "fpga",
                "subset": {"max_domain_mhz": {"cpu": mhz}},
                "provenance": RECORD,
                "release_status": "public",
            }
        }
        return digest_of(document)

    assert digest(96) == digest(96.0)


def test_values_canonical_cannot_encode_fail_to_load(document):
    document["boards"]["board_a"]["extensions"] = {"tool": float("nan")}
    with pytest.raises(FormatError, match=r"boards\.board_a\.extensions\.tool"):
        load_overlay(document)


def test_digest_covers_built_in_entries_only(builtin_document):
    base = _load_documents([(builtin_document, "builtin.yaml")], builtin=True)
    overlay = {
        "schema_version": 1,
        "memory_devices": {"dev": {"technology": "psram", "capacity": "8M"}},
    }
    assert load_overlay(overlay, base=base).catalog_digest == base.catalog_digest
    assert load_overlay({"schema_version": 1}).catalog_digest == _EMPTY.catalog_digest


def test_extensions_are_opaque(builtin_document):
    board = load_overlay(builtin_document)._entry("boards", "board_a")

    def digest(extensions):
        entry = dataclasses.replace(board, extensions=MappingProxyType(extensions))
        return _digest.catalog_digest({"boards": {"board_a": entry}}, {}, {})

    assert digest({"tool": ("b", "a")}) != digest({"tool": ("a", "b")})


def test_source_sha256_matches_for_a_file_and_the_same_mapping(tmp_path, document):
    path = tmp_path / "overlay.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    assert _digest.source_sha256(_parse.parse_file(path)) == _digest.source_sha256(document)


def test_source_sha256_reads_per_core_app_start_keyed_like_app_start(document):
    def source(record):
        app_start = {"region": "nvm", "offset": {"value": 0, "provenance": record}}
        boot = document["socs"]["soc_a"]["boot_configs"]["nbl"]
        boot["app_start"] = {"offset": app_start}  # a core named offset
        return _digest.source_sha256(document)

    assert source(RECORD) == source({**RECORD, "notes": "changed"})


def test_loading_computes_the_digest(document):
    assert "catalog_digest" in vars(load_overlay(document))


def test_source_sha256_strips_records_on_declared_keys_only(document):
    before = _digest.source_sha256(copy.deepcopy(document))
    soc = document["socs"]["soc_a"]
    soc["provenance"] = {**RECORD, "notes": "changed"}
    soc["memories"]["tcm"]["size"] = {"value": "512K", "provenance": RECORD}
    document["$schema"] = "helia-platforms-v1.schema.json"
    assert _digest.source_sha256(document) == before

    document["boards"]["board_a"]["extensions"] = {"tool": {"provenance": "a"}}
    with_extension = _digest.source_sha256(copy.deepcopy(document))
    document["boards"]["board_a"]["extensions"] = {"tool": {"provenance": "b"}}
    assert _digest.source_sha256(document) != with_extension


def test_source_sha256_sees_value_changes(document):
    before = _digest.source_sha256(copy.deepcopy(document))
    document["socs"]["soc_a"]["memories"]["tcm"]["size"] = "256K"
    assert _digest.source_sha256(document) != before


def test_identity_records_each_overlay_in_order(tmp_path, document):
    path = tmp_path / "private" / "overlay.yaml"
    path.parent.mkdir()
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    from_file = load_overlay(path)
    device = {"memory_devices": {"dev": {"technology": "psram", "capacity": "8M"}}}
    both = load_overlay(device, base=from_file)
    identity = both.identity()
    assert identity.package_version == helia_platforms.__version__
    assert identity.schema_version == 1
    assert identity.catalog_digest == both.catalog_digest
    file_source, mapping_source = identity.sources
    assert file_source == from_file.identity().sources[0]
    assert (file_source.label, mapping_source.label) == (
        "overlay:overlay.yaml",
        "overlay:<mapping>",
    )
    assert mapping_source.schema_version == 1  # omitted, so read at the current version
    assert mapping_source.distribution_version is None


def test_a_file_and_the_same_mapping_record_the_same_hash(tmp_path, document):
    path = tmp_path / "overlay.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    (from_file,) = load_overlay(path).identity().sources
    (from_mapping,) = load_overlay(document).identity().sources
    assert from_file.sha256 == from_mapping.sha256 == _digest.source_sha256(document)


def test_identity_to_dict_is_json(document):
    found = json.loads(json.dumps(load_overlay(document).identity().to_dict()))
    assert set(found) == {"package_version", "schema_version", "catalog_digest", "sources"}
    assert set(found["sources"][0]) == {"label", "schema_version", "sha256", "distribution_version"}
    assert _EMPTY.identity().sources == ()
