"""Black-box tests for ``scripts/check_local_paths.py`` (issue #26)."""

from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "check_local_paths.py"
HINT = "Cite repositories by name and revision instead (see CONTRIBUTING.md)."


def _load_checker() -> ModuleType:
    """Import the script by path, since ``scripts/`` is not a package."""
    spec = importlib.util.spec_from_file_location("check_local_paths", SCRIPT)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot build an import spec for {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


checker = _load_checker()


def _message(path: str, lineno: int, matched: str) -> str:
    return f"{path}:{lineno}: local filesystem path '{matched}'. {HINT}"


# Each row maps a case id to (one line of text, matched substrings expected in order).
SINGLE_LINE_CASES: dict[str, tuple[str, list[str]]] = {
    # macOS home
    "macos-home": ("cd /Users/alice/repo", ["/Users/alice/"]),
    "macos-home-one-char-name": ("/Users/a/x", ["/Users/a/"]),
    "macos-home-dotted-name": ("/Users/first.last-2/x", ["/Users/first.last-2/"]),
    "macos-home-unicode-name": ("/Users/zoë/x", ["/Users/zoë/"]),
    "macos-home-replacement-char-first": ("/Users/\ufffdric/x", ["/Users/\ufffdric/"]),
    "macos-home-under-system-data-volume": (
        "/System/Volumes/Data/Users/alice/x",
        ["/System/Volumes/Data/Users/alice/"],
    ),
    "macos-home-no-slash-at-eol": ("ls /Users/alice", ["/Users/alice"]),
    "macos-home-trailing-dot-not-in-name": ("see /Users/alice.", ["/Users/alice"]),
    "macos-home-before-quote": ('p = "/Users/alice"', ["/Users/alice"]),
    "macos-home-before-space": ("/Users/alice is mine", ["/Users/alice"]),
    "macos-angle-placeholder-not-matched": ("/Users/<name>/repo", []),
    "macos-brace-placeholder-not-matched": ("/Users/{user}/repo", []),
    "macos-ellipsis-not-matched": ("/Users/.../repo", []),
    "macos-users-slash-alone-not-matched": ("the /Users/ tree", []),
    "macos-users-alone-not-matched": ("ls /Users", []),
    "macos-after-word-char-not-matched": ("GET /api/Users/{id}", []),
    "macos-after-dot-not-matched": ("./Users/alice/x", []),
    "macos-after-hyphen-not-matched": ("x-/Users/alice/x", []),
    "macos-lowercase-users-scope-not-matched": ("scope:/users/read", []),
    # Linux home
    "linux-home": ("/home/bob/src", ["/home/bob/"]),
    "linux-home-no-slash-at-eol": ("cd /home/bob", ["/home/bob"]),
    "linux-home-replacement-char-inside": ("/home/a\ufffdb/x", ["/home/a\ufffdb/"]),
    "linux-home-under-var": ("/var/home/alice/x", ["/var/home/alice/"]),
    "linux-home-under-usr": ("/usr/home/alice/x", ["/usr/home/alice/"]),
    "linux-home-under-export": ("/export/home/alice/x", ["/export/home/alice/"]),
    "linux-home-root-after-word-char-not-matched": ("x/var/home/alice/", []),
    "linux-dollar-placeholder-not-matched": ("/home/$USER/src", []),
    "linux-angle-placeholder-not-matched": ("/home/<name>/src", []),
    "linux-homes-not-matched": ("/homes/x/src", []),
    "linux-home-inside-relative-path-not-matched": ("src/app/home/components/x", []),
    # Windows home
    "windows-backslash": (r"C:\Users\carol\x", ["C:\\Users\\"]),
    "windows-forward-slash": ("D:/Users/dave/x", ["D:/Users/"]),
    "windows-doubled-backslash-json": (r"C:\\Users\\carol", [r"C:\\Users\\"]),
    "windows-mixed-separators": (r"C:\Users/x", ["C:\\Users/"]),
    "windows-doubled-then-slash": (r"C:\\Users/x", [r"C:\\Users/"]),
    "windows-lowercase-drive": (r"c:\Users\x", ["c:\\Users\\"]),
    "windows-lowercase-users": ("E:/users/x", ["E:/users/"]),
    "windows-uppercase-users": (r"F:\USERS\x", ["F:\\USERS\\"]),
    "windows-no-separator-not-matched": (r"C:Users\x", []),
    "windows-no-trailing-separator-not-matched": (r"see C:\Users", []),
    "windows-digit-drive-not-matched": (r"1:\Users\x", []),
    "windows-drive-after-letter-not-matched": (r"XC:\Users\x", []),
    # Windows shell (WSL, Cygwin, MSYS)
    "shell-mnt-drive": ("/mnt/c/Users/x", ["/mnt/c/Users/"]),
    "shell-mnt-uppercase-drive-lowercase-users": ("/mnt/D/users/x", ["/mnt/D/users/"]),
    "shell-cygdrive": ("/cygdrive/c/Users/x", ["/cygdrive/c/Users/"]),
    "shell-root-drive": ("/c/Users/x", ["/c/Users/"]),
    "shell-after-word-char-not-matched": ("x/mnt/c/Users/", []),
    "shell-two-letter-drive-not-matched": ("/mnt/cd/Users/", []),
    # macOS scratch
    "private-tmp": ("/private/tmp/build", ["/private/tmp/"]),
    "var-folders": ("/var/folders/xy/T/", ["/var/folders/"]),
    "var-folders-under-private": ("/private/var/folders/x", ["/var/folders/"]),
    "private-alone-not-matched": ("/private/etc", []),
    "var-alone-not-matched": ("/var/log", []),
    # Cloud sync
    "cloud-storage": ("~/Library/CloudStorage/Box/x", ["Library/CloudStorage/"]),
    "icloud-docs": ("Mobile Documents/com~apple~CloudDocs/x", ["com~apple~CloudDocs"]),
    "onedrive-hyphen-org-slash": ("~/OneDrive-Contoso/x", ["OneDrive-Contoso/"]),
    "onedrive-spaced-org-backslash": (r"OneDrive - Contoso\Docs", ["OneDrive - Contoso\\"]),
    "onedrive-no-hyphen-not-matched": ("sync with OneDrive today", []),
    "onedrive-hyphen-word-not-matched": ("a OneDrive-backed share", []),
    "onedrive-empty-org-not-matched": ("OneDrive-/x", []),
    "onedrive-hyphen-word-then-separator-not-matched": ("a OneDrive-backed share at x/y", []),
    "onedrive-spaced-org-with-spaces": ("~/OneDrive - Ambiq Micro/x", ["OneDrive - Ambiq Micro/"]),
    "onedrive-spaced-prose-before-url-not-matched": ("OneDrive - see https://docs.example/x", []),
    "onedrive-hyphen-org-64-chars": ("OneDrive-" + "a" * 64 + "/x", ["OneDrive-" + "a" * 64 + "/"]),
    "onedrive-hyphen-org-65-chars-not-matched": ("OneDrive-" + "a" * 65 + "/x", []),
    # Ignore directive
    "directive-hash-comment": ("/Users/alice/x  # local-paths: ignore", []),
    "directive-html-comment": ("<!-- local-paths: ignore --> /home/bob/", []),
    # URL exemption: only remote schemes exempt a finding inside them
    "https-url-exempt": ("https://example.com/Users/alice/x", []),
    "https-url-exempt-scratch-path": ("https://example.com/private/tmp/x", []),
    "http-uppercase-scheme-exempt": ("HTTP://example.com/var/folders/x", []),
    "git-plus-https-url-exempt": ("git+https://github.com/org/home/x", []),
    "s3-url-exempt": ("s3://bucket/home/models/x", []),
    "ssh-url-exempt": ("ssh://git@srv/home/git/r.git", []),
    "ftp-url-exempt": ("ftp://srv/Users/1/x", []),
    "sftp-uppercase-scheme-exempt": ("SFTP://h/home/a/x", []),
    "url-exempt-bare-path-after-flagged": ("https://h/home/b/ and /home/b/", ["/home/b/"]),
    "json-path-after-url-value": (
        '{"a":"https://x.y","b":"/Users/alice/repo"}',
        ["/Users/alice/"],
    ),
    "markdown-link-target-after-url": ("[https://g.com/x](/Users/alice/repo)", ["/Users/alice/"]),
    "html-text-after-href-url": (
        '<a href="https://g.com/x">/Users/alice/x</a>',
        ["/Users/alice/"],
    ),
    "vscode-url-not-exempt": ("vscode://file/Users/alice/a.py", ["/Users/alice/"]),
    # The Windows form must not fire; the macOS form still reports /Users/x after the colon.
    "windows-boundary-kept-inside-vscode-url": ("vscode://fileC:/Users/x", ["/Users/x"]),
    "cursor-url-not-exempt": ("cursor://file/home/a/x", ["/home/a/"]),
    "obsidian-url-not-exempt": ("obsidian://open?path=/Users/alice/x", ["/Users/alice/"]),
    "unknown-scheme-not-exempt": ("zzz://h/home/a/x", ["/home/a/"]),
    "scheme-not-split-from-longer-run": ("myhttps://h/home/a/x", ["/home/a/"]),
    "file-url-not-exempt": ("file:///Users/alice/x", ["/Users/alice/"]),
    "file-url-uppercase-scheme-not-exempt": ("FILE:///home/bob/x", ["/home/bob/"]),
    "url-scheme-after-match-not-exempt": ("/Users/alice/https://x", ["/Users/alice/"]),
    # A loopback host or a query string removes the remote-URL exemption
    "http-localhost-not-exempt": ("http://localhost:8000/Users/alice/x", ["/Users/alice/"]),
    "https-loopback-ipv4-not-exempt": ("https://127.0.0.1/home/bob/x", ["/home/bob/"]),
    "http-loopback-ipv6-not-exempt": ("http://[::1]:8080/home/bob/x", ["/home/bob/"]),
    "http-any-address-not-exempt": ("http://0.0.0.0/Users/a/", ["/Users/a/"]),
    "http-localhost-uppercase-with-user": ("HTTP://me@LOCALHOST/home/bob", ["/home/bob"]),
    "ssh-localhost-not-exempt": ("ssh://git@localhost/home/git/r.git", ["/home/git/"]),
    "https-localhost-named-remote-host-exempt": ("https://localhost.example.com/home/a/", []),
    "https-ipv6-remote-host-exempt": ("https://[2001:db8::1]/home/a/x", []),
    "https-query-not-exempt": (
        "https://example.com/view?file=/Users/alice/x",
        ["/Users/alice/"],
    ),
    "https-query-relative-route-not-matched": ("https://example.com/?q=api/Users/bob", []),
    "https-fragment-exempt": ("https://example.com/app#/home/settings", []),
    "https-fragment-after-query-exempt": ("https://example.com/?q=1#/home/settings", []),
    "https-question-mark-in-fragment-not-query": (
        "https://example.com/#/settings?next=/home/dashboard",
        [],
    ),
    "https-query-before-fragment-not-exempt": (
        "https://example.com/?a=/home/bob#/home/x",
        ["/home/bob"],
    ),
    "localhost-relative-route-not-matched": ("http://localhost:8000/api/Users/42", []),
    "loopback-relative-route-not-matched": ("curl http://127.0.0.1:8080/api/home/status", []),
    "localhost-query-relative-route-not-matched": ("http://localhost/?q=api/Users/bob", []),
    "localhost-query-not-exempt": ("http://localhost/?q=/Users/bob", ["/Users/bob"]),
    # Single-dash compiler and linker options
    "option-include-macos": ("-I/Users/alice/sdk/include", ["/Users/alice/"]),
    "option-library-linux": ("-L/home/bob/lib", ["/home/bob/"]),
    "option-isystem-macos": ("cc -isystem/Users/alice/sdk", ["/Users/alice/"]),
    "option-quoted-linux-root": ('"-I/var/home/alice/x"', ["/var/home/alice/"]),
    "option-shell-drive": ("-I/mnt/c/Users/x", ["/mnt/c/Users/"]),
    "option-windows-drive": (r"-IC:\Users\carol\x", ["C:\\Users\\"]),
    "option-json-escaped": (r'"-I\/Users\/alice\/x"', [r"\/Users\/alice\/"]),
    "option-placeholder-not-matched": ("-I/Users/<name>/x", []),
    "option-after-word-char-not-matched": ("x-I/Users/alice/x", []),
    "option-double-dash-not-matched": ("--I/Users/alice/x", []),
    "option-glued-relative-path-not-matched": ("cc -Isrc/home/widgets/include x.c", []),
    "option-glued-relative-users-not-matched": ("-Ithird_party/Users/include", []),
    "option-library-glued-relative-path-not-matched": ("-Lbuild/home/lib", []),
    # Windows-side WSL UNC paths
    "wsl-dollar-unc": (r"\\wsl$\Ubuntu\home\alice\x", ["\\\\wsl$\\Ubuntu\\home\\alice\\"]),
    "wsl-localhost-unc": (
        r"\\wsl.localhost\Ubuntu-22.04\home\alice\x",
        ["\\\\wsl.localhost\\Ubuntu-22.04\\home\\alice\\"],
    ),
    "wsl-unc-json-escaped": (
        r"\\\\wsl$\\Ubuntu\\home\\alice\\x",
        [r"\\\\wsl$\\Ubuntu\\home\\alice\\"],
    ),
    "wsl-unc-forward-slashes": ("//wsl$/Ubuntu/home/alice/x", ["//wsl$/Ubuntu/home/alice/"]),
    "wsl-unc-uppercase-host-at-eol": (r"\\WSL$\Ubuntu\home\alice", [r"\\WSL$\Ubuntu\home\alice"]),
    "wsl-unc-placeholders-not-matched": (r"\\wsl$\<distro>\home\<name>\x", []),
    "wsl-unc-outside-home-not-matched": (r"\\wsl$\Ubuntu\opt\x", []),
    # JSON-escaped POSIX paths
    "json-escaped-macos-home": (r'"\/Users\/alice\/repo"', [r"\/Users\/alice\/"]),
    "json-escaped-linux-home": (r'"\/home\/bob\/x"', [r"\/home\/bob\/"]),
    "json-escaped-private-tmp": (r'"\/private\/tmp\/x"', [r"\/private\/tmp\/"]),
    "json-escaped-shell-drive": (r'"\/mnt\/c\/Users\/x"', [r"\/mnt\/c\/Users\/"]),
    "json-escaped-placeholder-not-matched": (r'"\/Users\/<name>\/x"', []),
    "json-escaped-relative-route-not-matched": (r'"\/api\/Users\/bob"', []),
    "json-escaped-after-word-char-not-matched": (r"x\/Users\/alice", []),
    # Several findings: left to right, never overlapping
    "multiple-ordered-by-position": (
        "/home/bob/ and /Users/alice/ and OneDrive-X/",
        ["/home/bob/", "/Users/alice/", "OneDrive-X/"],
    ),
    "multiple-same-form": ("/Users/a/ /Users/b/", ["/Users/a/", "/Users/b/"]),
    "multiple-nested-in-one-path": (
        "/Users/alice/Library/CloudStorage/x",
        ["/Users/alice/", "Library/CloudStorage/"],
    ),
    "overlap-leftmost-windows-wins": ("C:/Users/alice/x", ["C:/Users/"]),
}


@pytest.mark.parametrize(
    ("text", "expected"),
    list(SINGLE_LINE_CASES.values()),
    ids=list(SINGLE_LINE_CASES.keys()),
)
def test_check_text_single_line(text: str, expected: list[str]) -> None:
    assert checker.check_text(text, "f.txt") == [_message("f.txt", 1, m) for m in expected]


def test_message_format_is_exact() -> None:
    text = "intro\nsee /Users/alice/x\n"
    assert checker.check_text(text, "notes/a.md") == [
        "notes/a.md:2: local filesystem path '/Users/alice/'. "
        "Cite repositories by name and revision instead (see CONTRIBUTING.md)."
    ]


def test_line_numbers_are_one_based_and_in_line_order() -> None:
    text = "/home/bob/\nclean\n\nOneDrive-Acme/docs\n"
    assert checker.check_text(text, "f.md") == [
        _message("f.md", 1, "/home/bob/"),
        _message("f.md", 4, "OneDrive-Acme/"),
    ]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("a\x0cb\n/home/alice/", [(2, "/home/alice/")]),
        ("a\u2028/home/alice/", [(1, "/home/alice/")]),
        ("ok\r\n/home/bob\r\nx\r\n/Users/alice\r\n", [(2, "/home/bob"), (4, "/Users/alice")]),
    ],
    ids=[
        "form-feed-does-not-split",
        "unicode-line-separator-does-not-split",
        "crlf-line-numbers-and-cr-stripped",
    ],
)
def test_lines_split_on_newline_only(text: str, expected: list[tuple[int, str]]) -> None:
    assert checker.check_text(text, "f.txt") == [_message("f.txt", n, m) for n, m in expected]


def test_directive_silences_only_its_own_line() -> None:
    text = "/Users/a/  # local-paths: ignore\n/Users/b/\n"
    assert checker.check_text(text, "f.py") == [_message("f.py", 2, "/Users/b/")]


@pytest.mark.parametrize(
    "separator",
    ["\r", "\f", "\u2028", "\x85"],
    ids=["lone-cr", "form-feed", "line-separator", "next-line"],
)
def test_directive_silences_only_its_own_segment(separator: str) -> None:
    text = f"x  # local-paths: ignore{separator}/Users/b/\n"
    assert checker.check_text(text, "f.py") == [_message("f.py", 1, "/Users/b/")]


def test_directive_silences_a_path_in_its_own_segment() -> None:
    assert checker.check_text("a\f/Users/b/  # local-paths: ignore\n", "f.py") == []


@pytest.mark.parametrize(
    "text",
    ["", "\n", "plain prose\nwith two lines\n"],
    ids=["empty", "blank-line", "prose"],
)
def test_clean_text_has_no_findings(text: str) -> None:
    assert checker.check_text(text, "f.txt") == []


def test_check_file_reports_with_the_path_as_given(tmp_path: Path) -> None:
    target = tmp_path / "a.md"
    target.write_text("ok\n/private/tmp/x\n", encoding="utf-8")
    assert checker.check_file(target) == [_message(str(target), 2, "/private/tmp/")]


def test_check_file_scans_non_utf8_text(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = tmp_path / "latin1.txt"
    target.write_bytes("café\n/home/bob/x\n".encode("latin-1"))
    assert checker.check_file(target) == [_message(str(target), 2, "/home/bob/")]
    assert "skipped" not in capsys.readouterr().err


def test_check_file_reads_undecodable_byte_as_name_char(tmp_path: Path) -> None:
    target = tmp_path / "latin1-name.txt"
    target.write_bytes(b"/Users/\xe9ric/x\n")
    assert checker.check_file(target) == [_message(str(target), 1, "/Users/\ufffdric/")]


def test_check_file_keeps_lone_cr_inside_a_line(tmp_path: Path) -> None:
    target = tmp_path / "cr.txt"
    target.write_bytes(b"a\rb /home/bob/x\n/Users/al/\n")
    assert checker.check_file(target) == [
        _message(str(target), 1, "/home/bob/"),
        _message(str(target), 2, "/Users/al/"),
    ]


def test_check_file_skips_missing_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = tmp_path / "missing.md"
    assert checker.check_file(target) == []
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith(f"{target}: skipped (")


def test_check_file_scans_symlink_target_without_following(tmp_path: Path) -> None:
    link = tmp_path / "link"
    try:
        os.symlink("/home/alice/project", link)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlinks unsupported here: {exc}")
    assert checker.check_file(link) == [_message(str(link), 1, "/home/alice/")]


def test_main_returns_zero_for_clean_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    clean = tmp_path / "clean.md"
    clean.write_text("nothing local here\n", encoding="utf-8")
    assert checker.main([str(clean)]) == 0
    assert capsys.readouterr().out == ""


def test_main_returns_one_and_prints_findings_in_argument_order(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    second = tmp_path / "b.md"
    second.write_text("/home/bob/\n", encoding="utf-8")
    clean = tmp_path / "clean.md"
    clean.write_text("fine\n", encoding="utf-8")
    first = tmp_path / "a.md"
    first.write_text("x\nOneDrive-Acme/y\n", encoding="utf-8")
    assert checker.main([str(second), str(clean), str(first)]) == 1
    assert capsys.readouterr().out.splitlines() == [
        _message(str(second), 1, "/home/bob/"),
        _message(str(first), 2, "OneDrive-Acme/"),
    ]


def test_main_returns_zero_with_no_filenames(capsys: pytest.CaptureFixture[str]) -> None:
    assert checker.main([]) == 0
    assert capsys.readouterr().out == ""


PERF_LINE_LENGTH = 200_000
# Each input is one line of about 200 KB built to provoke regex backtracking.
ADVERSARIAL_INPUTS: dict[str, str] = {
    "run-of-x": "x" * PERF_LINE_LENGTH,
    "onedrive-hyphen-then-long-run": "OneDrive-" + "x" * PERF_LINE_LENGTH,
    "repeated-spaced-onedrive": "OneDrive - x " * (PERF_LINE_LENGTH // 13),
    "repeated-exempt-https-home": "https://x/Users/a/ " * (PERF_LINE_LENGTH // 19),
    "quoted-hex-string": '"' + "0123456789abcdef" * (PERF_LINE_LENGTH // 16) + '"',
    "repeated-single-dash-options": "-I " * (PERF_LINE_LENGTH // 3),
    "repeated-json-escaped-slashes": "\\/" * (PERF_LINE_LENGTH // 2),
    "run-of-backslashes": "\\" * PERF_LINE_LENGTH,
    "repeated-wsl-prefix": "\\\\wsl$\\x" * (PERF_LINE_LENGTH // 8),
    "wsl-prefix-then-long-dotted-name": "\\\\wsl$\\a" + "." * PERF_LINE_LENGTH,
    "unclosed-ipv6-host": "http://[" + "0:" * (PERF_LINE_LENGTH // 2),
    "repeated-localhost-query-urls": "http://localhost/?q " * (PERF_LINE_LENGTH // 20),
}


# A regex call holds the GIL, so a runaway scan is bounded by running it in a child process.
_TIMED_SCAN = """
import importlib.util, os, sys, time
sys.path.insert(0, os.path.dirname(sys.argv[1]))
spec = importlib.util.spec_from_file_location("check_local_paths", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
text = sys.stdin.read()
start = time.perf_counter()
count = len(module.check_text(text, "f.txt"))
print(count, time.perf_counter() - start)
"""
HARD_TIMEOUT_S = 20


@pytest.mark.parametrize(
    "text", list(ADVERSARIAL_INPUTS.values()), ids=list(ADVERSARIAL_INPUTS.keys())
)
def test_adversarial_line_scans_quickly(text: str) -> None:
    try:
        result = subprocess.run(
            [sys.executable, "-c", _TIMED_SCAN, str(SCRIPT)],
            input=text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=HARD_TIMEOUT_S,
            check=True,
        )
    except subprocess.TimeoutExpired:
        pytest.fail(f"scan did not finish within {HARD_TIMEOUT_S} s")
    count, elapsed = result.stdout.split()
    assert int(count) == 0
    assert float(elapsed) < 2.0


def _local_paths_hook() -> dict[str, object]:
    config = yaml.safe_load((REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    hooks = [hook for repo in config["repos"] for hook in repo["hooks"]]
    return next(hook for hook in hooks if hook["id"] == "local-paths")


def test_hook_selects_text_and_symlinks() -> None:
    hook = _local_paths_hook()
    assert hook.get("types") == []
    types_or = hook.get("types_or")
    assert isinstance(types_or, list)
    assert {"text", "symlink"} <= set(types_or)


@pytest.mark.parametrize(
    ("path", "excluded"),
    [
        ("tests/test_check_local_paths.py", True),
        ("tests/other.py", False),
        ("scripts/check_local_paths.py", False),
        ("docs/tests/test_check_local_paths.py", False),
    ],
    ids=["this-test-file", "other-test", "the-script", "same-name-elsewhere"],
)
def test_hook_excludes_only_this_test_file(path: str, excluded: bool) -> None:
    exclude = _local_paths_hook().get("exclude")
    assert isinstance(exclude, str)
    assert (re.search(exclude, path) is not None) is excluded
