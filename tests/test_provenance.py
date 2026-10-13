import pytest

from conftest import RECORD, SDK_SOURCE, as_builtin
from helia_platforms import FormatError, PlatformWarning, builtin, load_overlay
from helia_platforms.catalog import _load_documents

SHA = "b" * 40


def load_builtin(document):
    return _load_documents([(as_builtin(document), "builtin.yaml")], builtin=True)


def problems(document) -> str:
    with pytest.raises(FormatError) as exc:
        load_builtin(document)
    return "\n".join(exc.value.problems)


def with_size_record(document, record):
    """Give soc_a's tcm size its own record."""
    document["socs"]["soc_a"]["memories"]["tcm"]["size"] = {"value": "512K", "provenance": record}
    return document


def sourced(status, *sources, **extra):
    return {**RECORD, "status": status, "source": list(sources), **extra}


@pytest.mark.parametrize(
    "reference",
    [
        "doc:DS-TEST@1.0:p1",
        "doc:DS-TEST@1.0:p3-40",
        SDK_SOURCE,
        f"repo:AmbiqAI/sdk@{SHA}:src/a.c:10-12",
        "url:https://example.com/page",
        "fact:soc:soc_a:memories.nvm.base",
    ],
)
def test_valid_references_load(document, reference):
    load_builtin(with_size_record(document, sourced("derived", reference)))


@pytest.mark.parametrize(
    ("reference", "message"),
    [
        ("doc:DS-NONE@1.0:p1", "DS-NONE@1.0 is not in the source register"),
        ("doc:DS-TEST@9.9:p1", "DS-TEST@9.9 is not in the source register"),
        ("doc:DS-TEST@1.0:p41", "the document has 40 pages"),
        ("doc:DS-TEST@1.0:p9-3", "the page range runs backwards"),
        ("doc:DS-TEST:p1", "is not doc:"),
        ("repo:AmbiqAI/sdk@main:src/a.c", "'main' is neither a full SHA nor a registered tag"),
        ("repo:AmbiqAI/sdk@a9f4ec2:src/a.c", "'a9f4ec2' is an abbreviated SHA"),
        (
            f"repo:AmbiqAI/other@{SHA}:src/a.c",
            "repository 'AmbiqAI/other' is not in the source register",
        ),
        ("repo:AmbiqAI/sdk@v1.0.0:/abs/a.c", "is not repo:"),
        ("meas:board_a/xip-alias/2026-12-01", "measured after verified_on 2026-10-05"),
        ("meas:no_board/xip-alias/2026-07-05", "target 'no_board' does not resolve"),
        ("meas:board_a/XIP Alias/2026-07-05", "is not meas:"),
        ("url:http://example.com/page", "is not url:https://"),
        ("url:https://user:pw@example.com/page", "is not url:https://"),
        ("fact:soc:soc_a:memories.nope.base", "no such fact"),
        ("fact:widget:soc_a:memories", "is not fact:"),
        ("DS-TEST p1", "unknown reference kind"),
    ],
)
def test_invalid_references_are_rejected(document, reference, message):
    assert message in problems(with_size_record(document, sourced("derived", reference)))


def test_a_measurement_resolves_against_names_and_needs_evidence(document):
    measured = sourced("measured", "meas:board_a/xip-alias/2026-07-05")
    assert "a measured record needs a repo: or url: reference" in problems(
        with_size_record(document, measured)
    )
    measured["source"].append(SDK_SOURCE)
    load_builtin(with_size_record(document, measured))


@pytest.mark.parametrize(
    ("record", "message"),
    [
        (sourced("datasheet", SDK_SOURCE), "a datasheet record needs a doc: reference"),
        (sourced("sdk", "doc:DS-TEST@1.0:p1"), "a sdk record needs a repo: reference"),
        ({"status": "sdk", "source": [SDK_SOURCE]}, "a sdk record needs verified_on"),
        ({**RECORD, "status": "unverified"}, "an unverified record may not carry verified_on"),
        ({**RECORD, "verified_by": "not a login"}, "is not a GitHub login or @org/team"),
    ],
)
def test_record_rules(document, record, message):
    assert message in problems(with_size_record(document, record))


def test_an_unverified_value_needs_an_allow_list_entry(document):
    with_size_record(document, {"status": "unverified", "notes": "an estimate"})
    assert "memories.tcm.size: resolves to unverified" in problems(document)
    document["unverified_allowed"] = [
        {"fact": "fact:soc:soc_a:memories.tcm.size", "reason": "an estimate", "issue": "#19"}
    ]
    load_builtin(document)


def test_a_group_entry_covers_every_value_under_it(document):
    document["socs"]["soc_a"]["memories"]["tcm"]["provenance"] = {"status": "unverified"}
    document["unverified_allowed"] = [
        {"fact": "fact:soc:soc_a:memories.tcm", "reason": "pending", "issue": "#19"}
    ]
    load_builtin(document)


@pytest.mark.parametrize(
    ("fact", "message"),
    [
        ("fact:soc:soc_a:memories.gone.size", "names no fact"),
        ("fact:soc:soc_a:memories.tcm.size", "is no longer unverified; remove the entry"),
    ],
)
def test_a_stale_allow_list_entry_is_rejected(document, fact, message):
    document["unverified_allowed"] = [{"fact": fact, "reason": "pending", "issue": "#19"}]
    assert message in problems(document)


def test_a_derived_value_with_an_unverified_input_is_rejected(document):
    document["socs"]["soc_a"]["memories"]["nvm"]["size"] = {
        "value": "4M",
        "provenance": {"status": "unverified"},
    }
    document["unverified_allowed"] = [
        {"fact": "fact:soc:soc_a:memories.nvm.size", "reason": "pending", "issue": "#19"}
    ]
    with_size_record(document, sourced("derived", "fact:soc:soc_a:memories.nvm.size"))
    assert "derived from unverified fact:soc:soc_a:memories.nvm.size" in problems(document)


def test_a_derived_value_naming_itself_is_a_cycle(document):
    with_size_record(document, sourced("derived", "fact:soc:soc_a:memories.tcm.size"))
    assert "memories.tcm.size: its derived inputs form a cycle" in problems(document)


def test_two_derived_values_naming_each_other_are_a_cycle(document):
    with_size_record(document, sourced("derived", "fact:soc:soc_a:memories.ssram.size"))
    document["socs"]["soc_a"]["memories"]["ssram"]["size"] = {
        "value": "3M",
        "provenance": sourced("derived", "fact:soc:soc_a:memories.tcm.size"),
    }
    assert "its derived inputs form a cycle" in problems(document)


def test_an_alternate_base_is_addressed_as_an_integer(document):
    document["socs"]["soc_a"]["memories"]["tcm"]["alternate_bases"] = [0x10000000]
    load_builtin(
        with_size_record(
            document, sourced("derived", "fact:soc:soc_a:memories.tcm.alternate_bases.268435456")
        )
    )


def test_overlay_references_are_checked_for_form_only_and_warn(document):
    with_size_record(document, sourced("datasheet", "doc:DS-PRIVATE@1:p1"))
    load_overlay(document)  # not in the register: a private document is fine
    with_size_record(document, sourced("sdk", "repo:AmbiqAI/sdk@a9f4ec2:src/a.c"))
    with pytest.warns(PlatformWarning, match="abbreviated SHA"):
        load_overlay(document)


def test_the_register_and_allow_list_are_built_in_only(document):
    document["unverified_allowed"] = []
    with pytest.raises(FormatError, match="only built-in files may carry 'unverified_allowed'"):
        load_overlay(document)


def test_the_packaged_register_and_allow_list_load():
    assert builtin(include_plugins=False).socs() == ()
