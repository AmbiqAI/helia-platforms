"""Tests for ``scripts/check_todo_markers.py`` and the shared ``scripts/hook_common.py``."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

import check_todo_markers as checker
import hook_common

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
HINT = checker.HINT


def _message(path: str, lineno: int, marker: str) -> str:
    return f"{path}:{lineno}: bare {marker} marker. {HINT}"


# Each row maps a case id to (one line of text, markers expected in order).
SINGLE_LINE_CASES: dict[str, tuple[str, list[str]]] = {
    "bare-todo": ("# TODO: fix this", ["TODO"]),
    "bare-fixme": ("// FIXME later", ["FIXME"]),
    "bare-hack": ("HACK around the vendor bug", ["HACK"]),
    "bare-xxx": ("XXX not sure", ["XXX"]),
    "two-on-one-line": ("TODO and FIXME", ["TODO", "FIXME"]),
    "issue-tag": ("# TODO(#12): fix this", []),
    "verify-tag": ("TODO(verify): check the datasheet", []),
    "issue-tag-on-other-marker": ("FIXME(#3) x", []),
    "unknown-tag": ("TODO(bob): x", ["TODO"]),
    "empty-issue-tag": ("TODO(#): x", ["TODO"]),
    "tag-after-space": ("TODO (#12): x", ["TODO"]),
    "lowercase-not-a-marker": ("todo: lowercase", []),
    "inside-longer-word": ("TODOS and XXXL", []),
    "end-of-sentence": ("Leave a TODO.", ["TODO"]),
    "in-url": ("see https://example.com/TODO/list", []),
    "relative-path": ("./TODO/x and ../FIXME", []),
    "absolute-path": ("/TODO/x", []),
    "file-name": ("read TODO.md", []),
    "comment-opener-glued": ("//TODO later", ["TODO"]),
    "word-slash-prefix": ("docs/TODO", ["TODO"]),
}


@pytest.mark.parametrize(
    ("line", "expected"),
    list(SINGLE_LINE_CASES.values()),
    ids=list(SINGLE_LINE_CASES.keys()),
)
def test_single_line(line: str, expected: list[str]) -> None:
    assert checker.check_text(line, "f.py") == [_message("f.py", 1, m) for m in expected]


def test_directive_silences_only_its_own_line() -> None:
    text = "TODO  # todo-markers: ignore\nFIXME\n"
    assert checker.check_text(text, "f.py") == [_message("f.py", 2, "FIXME")]


@pytest.mark.parametrize(
    ("text", "lineno"),
    [
        ("a\nb\nTODO\n", 3),
        ("a\r\nTODO\r\n", 2),
        ("a\rTODO\n", 1),
        ("a\fb\nTODO\n", 2),
        ("a\u2028TODO\n", 1),
        ("a\x85TODO\n", 1),
    ],
    ids=["lf", "crlf", "lone-cr", "form-feed", "line-separator", "next-line"],
)
def test_lines_split_on_newline_only(text: str, lineno: int) -> None:
    assert checker.check_text(text, "f.txt") == [_message("f.txt", lineno, "TODO")]


def test_split_lines_drops_only_a_trailing_cr() -> None:
    assert list(hook_common.split_lines("a\r\r\nb\r\n")) == [(1, "a\r"), (2, "b"), (3, "")]


def test_check_file_scans_non_utf8_text(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = tmp_path / "latin1.txt"
    target.write_bytes("café\nTODO\n".encode("latin-1"))
    assert checker.check_file(target) == [_message(str(target), 2, "TODO")]
    assert "skipped" not in capsys.readouterr().err


def test_check_file_skips_missing_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = tmp_path / "missing.md"
    assert checker.check_file(target) == []
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith(f"{target}: skipped (")


def test_main_returns_one_and_prints_findings_in_argument_order(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    second = tmp_path / "b.md"
    second.write_text("FIXME\n", encoding="utf-8")
    clean = tmp_path / "clean.md"
    clean.write_text("TODO(#1): tracked\n", encoding="utf-8")
    first = tmp_path / "a.md"
    first.write_text("x\nTODO\n", encoding="utf-8")
    assert checker.main([str(second), str(clean), str(first)]) == 1
    assert capsys.readouterr().out.splitlines() == [
        _message(str(second), 1, "FIXME"),
        _message(str(first), 2, "TODO"),
    ]


def test_main_returns_zero_for_clean_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    clean = tmp_path / "clean.md"
    clean.write_text("TODO(verify): unchecked claim\n", encoding="utf-8")
    assert checker.main([str(clean)]) == 0
    assert checker.main([]) == 0
    assert capsys.readouterr().out == ""


# pre-commit runs each hook script as a file, so its sibling import must resolve that way.
@pytest.mark.parametrize(
    ("script", "content"),
    [
        ("check_todo_markers.py", "TODO\n"),
        ("check_local_paths.py", "/private/tmp/x\n"),  # local-paths: ignore
    ],
)
def test_script_runs_as_a_file(tmp_path: Path, script: str, content: str) -> None:
    target = tmp_path / "f.txt"
    target.write_text(content, encoding="utf-8")
    clean = tmp_path / "clean.txt"
    clean.write_text("fine\n", encoding="utf-8")
    run = [sys.executable, str(SCRIPTS / script)]
    assert subprocess.run([*run, str(clean)], cwd=tmp_path, check=False).returncode == 0
    result = subprocess.run(
        [*run, str(target)], cwd=tmp_path, capture_output=True, text=True, check=False
    )
    assert result.returncode == 1
    assert result.stdout.startswith(f"{target}:1: ")
