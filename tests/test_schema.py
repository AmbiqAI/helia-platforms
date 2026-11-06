"""The JSON Schema: staleness, field parity, RFC examples and the conformance corpus."""

import copy
import dataclasses
import json
import re
from pathlib import Path
from typing import Any, cast

import jsonschema
import pytest

from conftest import BASE_DOCUMENT
from helia_platforms import _format as fmt
from helia_platforms import _parse, _walk, model, schema
from helia_platforms._structural import check_document

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = jsonschema.Draft202012Validator(json.loads(schema.committed()))


def test_committed_schema_is_current():
    assert schema.committed() == schema.render(), (
        "the committed schema is stale; run "
        "`uv run helia-platforms export --schema > "
        f"src/helia_platforms/schema/{schema.SCHEMA_FILE}`"
    )


def test_schema_is_a_valid_draft_2020_12_schema():
    jsonschema.Draft202012Validator.check_schema(schema.generate())


# Keys that exist only in files: deltas, shorthands and based_on (ADR 0002 section 3).
def _file_keys(decl: type) -> set[str]:
    return {
        name
        for name, f in _walk.fields(decl).items()
        if name != "provenance" and fmt.FILE_ONLY not in _walk.unwrap(f.type)[1]
    }


def _model_keys(cls: type) -> set[str]:
    skip = {"provenance", "field_provenance", getattr(cls, "KEY", None)}
    if cls.__name__ in {k.__name__ for k in fmt.ENTITY_TABLES.values()}:
        skip.add("id")
    return {f.name for f in dataclasses.fields(cast(Any, cls))} - skip


@pytest.mark.parametrize(
    "decl",
    [obj for obj in vars(fmt).values() if _walk.is_object(obj) and obj.__name__ in model.BY_NAME],
    ids=lambda obj: obj.__name__,
)
def test_every_file_key_maps_to_a_runtime_field(decl):
    assert _file_keys(decl) == _model_keys(model.BY_NAME[decl.__name__])


def _rfc_examples():
    for path in sorted((ROOT / "docs" / "rfcs").glob("0002-*.md")):
        text = path.read_text()
        for match in re.finditer(r"```yaml\n(.*?)```", text, re.S):
            block = match.group(1)
            if re.search(r"^schema_version:", block, re.M):
                line = text[: match.start()].count("\n") + 2
                yield pytest.param(block, id=f"{path.name}:{line}")


@pytest.mark.parametrize("block", list(_rfc_examples()))
def test_rfc_0002_examples_conform(block):
    data = _parse.parse_yaml(block, "example")
    assert check_document(data, "example") == []
    VALIDATOR.validate(data)


def test_the_rfc_has_example_overlays():
    assert len(list(_rfc_examples())) >= 5


# ---- conformance corpus: the structural stage and jsonschema agree ----------------


def _edit(path: str, value):
    """A corpus case: the base document with one value at a dotted path replaced."""
    doc = copy.deepcopy(BASE_DOCUMENT)
    *parents, last = path.split(".")
    node = doc
    for key in parents:
        node = node[int(key)] if isinstance(node, list) else node[key]
    if value is _DELETE:
        del node[last]
    else:
        node[last] = value
    return doc


_DELETE = object()
SOC = "socs.soc_a"
SDK = {"status": "sdk"}
CORPUS = {
    "base": (BASE_DOCUMENT, True),
    "size suffix": (_edit(f"{SOC}.memories.tcm.size", "1G"), True),
    "size lowercase": (_edit(f"{SOC}.memories.tcm.size", "64k"), False),
    "size KB": (_edit(f"{SOC}.memories.tcm.size", "64KB"), False),
    "size fraction": (_edit(f"{SOC}.memories.tcm.size", "1.5M"), False),
    "size negative": (_edit(f"{SOC}.memories.tcm.size", -1), False),
    "size bool": (_edit(f"{SOC}.memories.tcm.size", True), False),
    "unknown key": (_edit(f"{SOC}.memroies", {}), False),
    "unknown top": (_edit("platforms", {}), False),
    "bad enum": (_edit(f"{SOC}.memories.tcm.technology", "sdram"), False),
    "upper name": (
        _edit(f"{SOC}.memories.DTCM", BASE_DOCUMENT["socs"]["soc_a"]["memories"]["tcm"]),
        False,
    ),
    "reserved name": (
        _edit(f"{SOC}.memories.value", BASE_DOCUMENT["socs"]["soc_a"]["memories"]["tcm"]),
        False,
    ),
    "bad id": (_edit("parts.1bad", {"soc": "soc_a"}), False),
    "number for string": (_edit("parts.PART-A.silicon_revision", 1.0), False),
    "string for number": (_edit(f"{SOC}.clock_domains.cpu.lp.mhz", "96"), False),
    "bool for int": (_edit(f"{SOC}.npus.0.npu.macs_per_cycle", True), False),
    "port 1": (_edit(f"{SOC}.access.0.port", 1), True),
    "port true": (_edit(f"{SOC}.access.0.port", True), False),
    "dma_boundary suffix": (_edit(f"{SOC}.memories.tcm.dma_boundary", "4K"), True),
    "dma_boundary bool": (_edit(f"{SOC}.memories.tcm.dma_boundary", True), False),
    "missing required": (_edit(f"{SOC}.series", _DELETE), False),
    "based_on lifts required": (_edit("socs.soc_b", {"based_on": "soc_a"}), True),
    "wrapper": (
        _edit(f"{SOC}.memories.tcm.size", {"value": "1M", "provenance": {"status": "sdk"}}),
        True,
    ),
    "wrapper partial": (_edit(f"{SOC}.memories.tcm.size", {"value": "1M"}), False),
    "wrapper extra": (
        _edit(f"{SOC}.memories.tcm.size", {"value": "1M", "provenance": {"status": "sdk"}, "x": 1}),
        False,
    ),
    "wrapper on not-fact": (
        _edit(f"{SOC}.release_status", {"value": "public", "provenance": {"status": "sdk"}}),
        False,
    ),
    "bad status": (_edit(f"{SOC}.provenance", {"status": "confirmed"}), False),
    "bad date": (_edit(f"{SOC}.provenance", {"status": "sdk", "verified_on": "5 Oct 2026"}), False),
    "duplicate value": (_edit(f"{SOC}.peripherals", ["iom0", "iom0"]), False),
    "duplicate number": (_edit(f"{SOC}.memories.tcm.alternate_bases", [4096, 4096.0]), False),
    "wrapper on list item": (
        _edit(f"{SOC}.peripherals", ["mspi0", {"value": "iom0", "provenance": {"status": "sdk"}}]),
        True,
    ),
    "wrapper around wrapped items": (
        _edit(
            f"{SOC}.peripherals",
            {"value": [{"value": "iom0", "provenance": SDK}], "provenance": SDK},
        ),
        False,
    ),
    "wrapper around plain items": (
        _edit(f"{SOC}.peripherals", {"value": ["mspi0", "iom0"], "provenance": SDK}),
        True,
    ),
    "subset removal wrapped twice": (
        _edit(
            "implementations",
            {
                "cut": {
                    "soc": "soc_a",
                    "kind": "fpga",
                    "subset": {
                        "peripherals_removed": {
                            "value": [{"value": "iom0", "provenance": SDK}],
                            "provenance": SDK,
                        }
                    },
                }
            },
        ),
        False,
    ),
    "per-core app_start": (
        _edit(f"{SOC}.boot_configs.sbl.app_start", {"cm55_0": {"region": "nvm", "offset": 0}}),
        True,
    ),
    "bad app_start": (_edit(f"{SOC}.boot_configs.sbl.app_start", {"region": "nvm"}), False),
    "domain point removal": (
        _edit("socs.soc_b", {"based_on": "soc_a", "clock_domains_removed": ["cpu.hp"]}),
        True,
    ),
    "bad domain point": (
        _edit("socs.soc_b", {"based_on": "soc_a", "clock_domains_removed": ["cpu.HP"]}),
        False,
    ),
    "extensions": (
        _edit("boards.board_a.extensions", {"tool": {"anything": [1, {"x": None}]}}),
        True,
    ),
    "extensions bad tool": (_edit("boards.board_a.extensions", {"Tool": {}}), False),
    "extensions on part": (_edit("parts.PART-A.extensions", {}), False),
    "null value": (_edit(f"{SOC}.revision", None), False),
    "schema_version string": (_edit("schema_version", "1"), False),
    "dollar schema": (_edit("$schema", "x.json"), True),
}


@pytest.mark.parametrize(("document", "valid"), CORPUS.values(), ids=CORPUS.keys())
def test_loader_and_jsonschema_agree(document, valid):
    loader_ok = check_document(document, "corpus") == []
    schema_ok = VALIDATOR.is_valid(document)
    assert (loader_ok, schema_ok) == (valid, valid)
