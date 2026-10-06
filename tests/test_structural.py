import pytest

from helia_platforms._structural import check_document


def problems(document, **kwargs):
    return check_document(document, "doc", **kwargs)


def soc(document):
    return document["socs"]["soc_a"]


def test_the_fixture_conforms(document):
    assert problems(document) == []


def test_unknown_key_suggests_the_closest(document):
    soc(document)["memroies"] = {}
    (found,) = [p for p in problems(document) if "memroies" in p]
    assert "did you mean 'memories'?" in found
    assert "a newer helia-platforms may know it" in found


@pytest.mark.parametrize("size", ["256k", "256KB", "256KiB", "256Kb", "1.5M", -1, True])
def test_bad_sizes_are_rejected_with_a_hint(document, size):
    soc(document)["memories"]["tcm"]["size"] = size
    (found,) = problems(document)
    assert "socs.soc_a.memories.tcm.size" in found


@pytest.mark.parametrize("size", [0, 524288, "512K", "3M", "1G", 512.0])
def test_sizes_accept_bytes_and_binary_suffixes(document, size):
    soc(document)["memories"]["tcm"]["size"] = size
    assert problems(document) == []


def test_a_string_field_given_a_number_asks_for_quotes(document):
    document["parts"]["PART-A"]["silicon_revision"] = 1.0
    (found,) = problems(document)
    assert "expected a string, got the number 1.0; quote it" in found


@pytest.mark.parametrize("name", ["value", "provenance"])
def test_value_and_provenance_are_reserved_names(document, name):
    soc(document)["memories"][name] = soc(document)["memories"].pop("tcm")
    (found,) = problems(document)
    assert "reserved" in found


def test_names_are_lowercase(document):
    soc(document)["memories"]["DTCM"] = soc(document)["memories"].pop("tcm")
    (found,) = problems(document)
    assert "'DTCM' is not a lowercase name" in found


def test_ids_keep_case_and_allow_dashes(document):
    document["parts"]["AP510NFA-CBR"] = document["parts"].pop("PART-A")
    document["boards"]["board_a"]["part"] = "AP510NFA-CBR"
    assert problems(document) == []


def test_repeated_keyed_list_items_are_rejected(document):
    soc(document)["access"].append(dict(soc(document)["access"][0]))
    (found,) = problems(document)
    assert "same master/target" in found


def test_repeated_values_are_rejected(document):
    soc(document)["peripherals"].append("iom0")
    (found,) = problems(document)
    assert "'iom0' is listed twice" in found


def test_value_provenance_form_is_accepted_on_facts(document):
    soc(document)["memories"]["tcm"]["size"] = {"value": "512K", "provenance": {"status": "sdk"}}
    assert problems(document) == []


def test_value_provenance_form_needs_both_keys(document):
    soc(document)["memories"]["tcm"]["size"] = {"value": "512K"}
    assert any("needs both keys" in p for p in problems(document))


def test_value_provenance_form_is_rejected_on_keys_that_are_not_facts(document):
    soc(document)["release_status"] = {"value": "public", "provenance": {"status": "sdk"}}
    assert problems(document)


def test_based_on_lifts_required_keys(document):
    document["socs"]["soc_b"] = {"based_on": "soc_a", "memories_resized": {"ssram": "2M"}}
    assert problems(document) == []


def test_missing_required_keys_are_reported(document):
    del soc(document)["series"]
    (found,) = problems(document)
    assert "missing required key 'series'" in found


def test_a_file_must_declare_its_schema_version(document):
    del document["schema_version"]
    assert any("schema_version" in p for p in problems(document))
    assert problems(document, require_version=False) == []


def test_other_schema_versions_are_refused(document):
    document["schema_version"] = 2
    (found,) = problems(document)
    assert "schema_version 2 is not read by this package" in found


def test_dollar_schema_is_ignored(document):
    document["$schema"] = "../../schema/helia-platforms-v1.schema.json"
    assert problems(document) == []


def test_extensions_hold_any_json(document):
    document["boards"]["board_a"]["extensions"] = {"helia_profiler": {"sync_gpio": 27, "x": [1]}}
    assert problems(document) == []


def test_app_start_accepts_the_per_core_form(document):
    config = soc(document)["boot_configs"]["sbl"]
    config["app_start"] = {"cm55_0": {"region": "nvm", "offset": "64K"}}
    assert problems(document) == []


def test_every_problem_is_reported(document):
    soc(document)["series"] = 5
    soc(document)["memories"]["tcm"]["size"] = "1.5M"
    soc(document)["memories"]["tcm"]["technology"] = "dram"
    assert len(problems(document)) == 3
