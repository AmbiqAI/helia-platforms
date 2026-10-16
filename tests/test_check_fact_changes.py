"""Tests for ``scripts/check_fact_changes.py`` (ADR 0003 section 4)."""

from __future__ import annotations

import copy
import subprocess
from pathlib import Path

import pytest
import yaml

import check_fact_changes as checker
from conftest import RECORD, SDK_SOURCE, as_builtin
from helia_platforms.catalog import _load_documents


def load(document):
    return _load_documents([(as_builtin(copy.deepcopy(document)), "builtin.yaml")], builtin=True)


def check(base, head):
    return checker.problems(load(base), load(head))


def sourced(status, *sources, **extra):
    return {**RECORD, "status": status, "source": list(sources), **extra}


def tcm(document):
    return document["socs"]["soc_a"]["memories"]["tcm"]


def test_an_unchanged_catalog_passes(document):
    assert check(document, document) == []


def test_a_changed_value_under_an_unchanged_record_fails(document):
    head = copy.deepcopy(document)
    tcm(head)["size"] = "256K"
    (problem,) = check(document, head)
    assert problem.startswith("socs.soc_a.memories.tcm.size: changed from 524288 to 262144")


@pytest.mark.parametrize(
    "record",
    [
        sourced("sdk", SDK_SOURCE),
        sourced("datasheet", "doc:DS-OTHER@2.0:p1"),
        {**RECORD, "verified_on": "2026-10-06"},
    ],
    ids=["status", "source", "verified_on"],
)
def test_a_changed_value_with_a_changed_record_passes(document, record):
    head = copy.deepcopy(document)
    tcm(head)["size"] = {"value": "256K", "provenance": record}
    assert check(document, head) == []


def test_a_group_record_must_change_or_the_value_get_its_own(document):
    head = copy.deepcopy(document)
    head["socs"]["soc_a"]["memories"]["nvm"]["size"] = "2M"
    assert len(check(document, head)) == 1  # the Soc's record covers the region
    head["socs"]["soc_a"]["provenance"] = {**RECORD, "verified_on": "2026-10-06"}
    assert check(document, head) == []
    head["socs"]["soc_a"]["provenance"] = RECORD
    head["socs"]["soc_a"]["memories"]["nvm"]["provenance"] = sourced("sdk", SDK_SOURCE)
    assert check(document, head) == []


def test_source_order_does_not_count_as_a_change(document):
    two = ["doc:DS-TEST@1.0:p1", "doc:DS-OTHER@2.0:p1"]
    tcm(document)["size"] = {"value": "512K", "provenance": sourced("datasheet", *two)}
    head = copy.deepcopy(document)
    tcm(head)["size"] = {"value": "256K", "provenance": sourced("datasheet", *reversed(two))}
    assert len(check(document, head)) == 1


def test_verified_by_alone_never_counts(document):
    head = copy.deepcopy(document)
    tcm(head)["size"] = {"value": "256K", "provenance": {**RECORD, "verified_by": "someone-else"}}
    assert len(check(document, head)) == 1


def test_notes_count_only_between_two_unverified_records(document):
    def with_size(doc, size, record):
        tcm(doc)["size"] = {"value": size, "provenance": record}
        if record["status"] == "unverified":
            fact = "fact:soc:soc_a:memories.tcm.size"
            doc["unverified_allowed"] = [{"fact": fact, "reason": "test", "issue": "#1"}]
        return doc

    base = with_size(copy.deepcopy(document), "512K", {"status": "unverified", "notes": "a"})
    head = with_size(copy.deepcopy(document), "256K", {"status": "unverified", "notes": "b"})
    assert check(base, head) == []
    head = with_size(copy.deepcopy(document), "256K", {"status": "unverified", "notes": "a"})
    assert len(check(base, head)) == 1
    base = with_size(copy.deepcopy(document), "512K", {**RECORD, "notes": "a"})
    head = with_size(copy.deepcopy(document), "256K", {**RECORD, "notes": "b"})
    assert len(check(base, head)) == 1


def test_a_new_fact_path_is_exempt(document):
    head = copy.deepcopy(document)
    head["socs"]["soc_a"]["memories"]["itcm"] = {
        "technology": "sram",
        "attachment": "tcm",
        "base": 0x10000000,
        "size": "256K",
    }
    assert check(document, head) == []


def test_a_changed_derived_input_needs_a_changed_derived_record(document):
    derived = sourced("derived", "fact:soc:soc_a:memories.nvm.size")
    tcm(document)["size"] = {"value": "512K", "provenance": derived}
    head = copy.deepcopy(document)
    head["socs"]["soc_a"]["memories"]["nvm"]["size"] = {
        "value": "2M",
        "provenance": sourced("sdk", SDK_SOURCE),
    }
    (problem,) = check(document, head)
    assert problem.startswith("socs.soc_a.memories.tcm.size: its derived input")
    tcm(head)["size"]["provenance"] = {**derived, "verified_on": "2026-10-06"}
    assert check(document, head) == []


def test_a_derived_input_named_as_a_group_covers_its_values(document):
    derived = sourced("derived", "fact:soc:soc_a:memories.nvm")
    tcm(document)["size"] = {"value": "512K", "provenance": derived}
    head = copy.deepcopy(document)
    head["socs"]["soc_a"]["memories"]["nvm"]["base"] = {
        "value": 0x00500000,
        "provenance": sourced("sdk", SDK_SOURCE),
    }
    assert len(check(document, head)) == 1


def test_a_record_change_alone_is_a_reverification(document):
    head = copy.deepcopy(document)
    tcm(head)["provenance"] = sourced("sdk", SDK_SOURCE)
    assert check(document, head) == []


def test_a_changed_list_item_under_an_unchanged_record_fails(document):
    tcm(document)["alternate_bases"] = [0x30000000]
    head = copy.deepcopy(document)
    tcm(head)["alternate_bases"] = [0x30080000]
    (problem,) = check(document, head)
    assert problem.startswith("socs.soc_a.memories.tcm.alternate_bases: added 0x30080000")
    tcm(head)["provenance"] = {**RECORD, "verified_on": "2026-10-06"}
    assert check(document, head) == []


def test_a_removed_list_item_needs_a_changed_list_record(document):
    head = copy.deepcopy(document)
    head["socs"]["soc_a"]["memory_controllers"] = ["mspi0"]
    (problem,) = check(document, head)
    assert "removed iom0" in problem


def test_an_added_list_item_may_carry_its_own_record(document):
    head = copy.deepcopy(document)
    peripherals = head["socs"]["soc_a"]["peripherals"]
    peripherals.append("iom3")
    assert len(check(document, head)) == 1
    peripherals[-1] = {"value": "iom3", "provenance": sourced("sdk", SDK_SOURCE)}
    assert check(document, head) == []


def test_reordering_a_list_is_no_change(document):
    head = copy.deepcopy(document)
    head["socs"]["soc_a"]["peripherals"].reverse()
    assert check(document, head) == []


# ---- the command, against a git repository ------------------------------------------------


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def commit(repo: Path, document, message: str) -> str:
    data = repo / checker.DATA
    data.mkdir(parents=True, exist_ok=True)
    (data / "catalog.yaml").write_text(yaml.safe_dump(as_builtin(copy.deepcopy(document))))
    return commit_all(repo, message)


def commit_all(repo: Path, message: str) -> str:
    git(repo, "add", "-A")
    identity = ("-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false")
    git(repo, *identity, "commit", "-qm", message)
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q", "-b", "main")
    return tmp_path


def test_the_command_compares_the_merge_base_with_the_head(repo, document, capsys):
    base = commit(repo, document, "base")
    git(repo, "switch", "-qc", "change")
    tcm(document)["size"] = "256K"
    head = commit(repo, document, "change")
    git(repo, "switch", "-q", "main")
    tcm(document)["size"] = "128K"  # main moves on; only the merge base counts
    main = commit(repo, document, "main")
    assert checker.main(["--repo", str(repo), "--base", main, "--head", head]) == 1
    assert "changed from 524288 to 262144" in capsys.readouterr().out
    assert checker.main(["--repo", str(repo), "--base", base, "--head", base]) == 0


def test_the_command_finds_the_data_from_a_subdirectory(repo, document, monkeypatch):
    base = commit(repo, document, "base")
    tcm(document)["size"] = "256K"
    head = commit(repo, document, "change")
    monkeypatch.chdir(repo / "src")
    assert checker.main(["--base", base, "--head", head]) == 1


def test_a_revision_with_no_data_does_not_load(repo, document, capsys):
    (repo / "README").write_text("no data yet")
    base = commit_all(repo, "empty")
    head = commit(repo, document, "data")
    assert checker.main(["--repo", str(repo), "--base", base, "--head", head]) == 2
    assert "no data files" in capsys.readouterr().err


def test_the_command_reports_a_revision_that_does_not_load(repo, document, capsys):
    base = commit(repo, document, "base")
    document["socs"]["soc_a"]["memories"]["tcm"]["size"] = "not a size"
    head = commit(repo, document, "broken")
    assert checker.main(["--repo", str(repo), "--base", base, "--head", head]) == 2
    assert "the built-in data at the head" in capsys.readouterr().err
