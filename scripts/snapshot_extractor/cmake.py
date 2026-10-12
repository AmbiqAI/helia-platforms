"""Read CMake ``set()`` calls and the default linker script per toolchain.

No other CMake is evaluated. Arguments keep their written text, with quotes,
comments and line continuations removed, so ``set(X "")`` reads as ``[""]``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath

from snapshot_extractor import ExtractError

_SPACE = re.compile(r"[ \t\r\n]+")
_BRACKET_OPEN = re.compile(r"\[(=*)\[")
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_UNQUOTED = re.compile(r'(?:[^\s()#"\\]|\\.)+')
TOOLCHAINS = ("armclang", "gcc")


@dataclass(frozen=True)
class Command:
    """One command invocation; ``depth`` counts the ``if()`` blocks around it."""

    name: str
    args: tuple[str, ...]
    depth: int


def _skip_space_and_comments(text: str, pos: int) -> int:
    while pos < len(text):
        match = _SPACE.match(text, pos)
        if match:
            pos = match.end()
            continue
        if text.startswith("#", pos):
            bracket = _BRACKET_OPEN.match(text, pos + 1)
            if bracket:
                close = "]" + bracket.group(1) + "]"
                end = text.find(close, bracket.end())
                if end < 0:
                    raise ExtractError("unterminated bracket comment")
                pos = end + len(close)
            else:
                end = text.find("\n", pos)
                pos = len(text) if end < 0 else end
            continue
        return pos
    return pos


def _quoted(text: str, pos: int) -> tuple[str, int]:
    """Read the quoted argument opening at ``pos``; return its text and the end."""
    out: list[str] = []
    pos += 1
    while pos < len(text):
        char = text[pos]
        if char == '"':
            return "".join(out), pos + 1
        if char == "\\" and pos + 1 < len(text):
            following = text[pos + 1]
            if following == "\n":  # line continuation
                pos += 2
                continue
            out.append(following if following in '"\\' else char + following)
            pos += 2
            continue
        out.append(char)
        pos += 1
    raise ExtractError("unterminated quoted argument")


def _arguments(text: str, pos: int) -> tuple[tuple[str, ...], int]:
    """Read arguments after an opening parenthesis up to its match."""
    args: list[str] = []
    depth = 0
    while True:
        pos = _skip_space_and_comments(text, pos)
        if pos >= len(text):
            raise ExtractError("unterminated command")
        char = text[pos]
        if char == ")":
            if depth == 0:
                return tuple(args), pos + 1
            depth -= 1
            args.append(char)
            pos += 1
        elif char == "(":
            depth += 1
            args.append(char)
            pos += 1
        elif char == '"':
            arg, pos = _quoted(text, pos)
            args.append(arg)
        elif bracket := _BRACKET_OPEN.match(text, pos):
            close = "]" + bracket.group(1) + "]"
            end = text.find(close, bracket.end())
            if end < 0:
                raise ExtractError("unterminated bracket argument")
            args.append(text[bracket.end() : end].removeprefix("\n"))
            pos = end + len(close)
        else:
            match = _UNQUOTED.match(text, pos)
            if match is None:
                raise ExtractError(f"cannot read CMake argument at {text[pos : pos + 20]!r}")
            args.append(match.group(0))
            pos = match.end()


def commands(text: str) -> list[Command]:
    """Every command invocation in ``text``, in source order."""
    found: list[Command] = []
    depth = 0
    pos = 0
    while True:
        pos = _skip_space_and_comments(text, pos)
        if pos >= len(text):
            return found
        match = _IDENTIFIER.match(text, pos)
        if match is None:
            raise ExtractError(f"expected a CMake command at {text[pos : pos + 20]!r}")
        pos = _skip_space_and_comments(text, match.end())
        if not text.startswith("(", pos):
            raise ExtractError(f"expected '(' after {match.group(0)}")
        args, pos = _arguments(text, pos + 1)
        name = match.group(0).lower()
        if name == "endif":
            depth -= 1
        found.append(Command(name, args, depth - (name in ("elseif", "else"))))
        if name == "if":
            depth += 1


def set_values(text: str) -> dict[str, list[str]]:
    """Every unconditional ``set()`` as variable name to its arguments.

    A ``set()`` inside ``if()``, a variable set twice, and the ``CACHE`` and
    ``PARENT_SCOPE`` forms are outside the parser's scope and raise.
    """
    values: dict[str, list[str]] = {}
    for command in commands(text):
        if command.name != "set":
            continue
        if not command.args:
            raise ExtractError("set() without a variable")
        name, *args = command.args
        if command.depth:
            raise ExtractError(f"set({name}) inside if(); conditional facts are not read")
        if "CACHE" in args or "PARENT_SCOPE" in args:
            raise ExtractError(f"set({name}) uses CACHE or PARENT_SCOPE")
        if name in values:
            raise ExtractError(f"{name} is set twice")
        values[name] = args
    return values


def default_scripts(text: str) -> dict[str, str]:
    """The default linker script per toolchain, as written.

    Either form counts: ``_nsx_linker_script_default`` passed as ``DEFAULT`` to
    ``nsx_select_linker_script``, or a direct ``set(NSX_LINKER_SCRIPT ...)``.
    The toolchain is the script's directory name, ``gcc`` or ``armclang``.
    """
    found = commands(text)
    selected = any(
        command.name == "nsx_select_linker_script"
        and "${_nsx_linker_script_default}" in command.args
        for command in found
    )
    variable = "_nsx_linker_script_default" if selected else "NSX_LINKER_SCRIPT"
    scripts: dict[str, str] = {}
    for command in found:
        if command.name != "set" or not command.args or command.args[0] != variable:
            continue
        if len(command.args) != 2:
            raise ExtractError(f"set({variable}) takes one path, found {command.args[1:]}")
        path = command.args[1]
        toolchain = PurePosixPath(path).parent.name
        if toolchain not in TOOLCHAINS:
            raise ExtractError(f"cannot tell the toolchain of linker script {path!r}")
        if toolchain in scripts:
            raise ExtractError(f"two default {toolchain} linker scripts")
        scripts[toolchain] = path
    if not scripts:
        raise ExtractError("no default linker script")
    return scripts
