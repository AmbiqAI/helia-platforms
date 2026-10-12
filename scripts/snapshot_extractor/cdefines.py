"""Collect object-like C ``#define`` lines and evaluate them to integers.

Text inside ``#if 0`` is skipped up to its ``#elif``, ``#else`` or ``#endif``.
Every other conditional branch is read, so a name defined twice with different
bodies is ambiguous, and evaluating it raises ``ExtractError``.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

from snapshot_extractor import ExtractError, cexpr

_DIRECTIVE = re.compile(r"\s*#\s*(\w+)\s*(.*)")
_DEFINE = re.compile(r"([A-Za-z_]\w*)(\(?)\s*(.*)", re.DOTALL)
_COMMENT_OR_LITERAL = re.compile(
    r"/\*.*?\*/|//[^\n]*|\"(?:\\.|[^\"\\\n])*\"|'(?:\\.|[^'\\\n])*'", re.DOTALL
)


class AmbiguousDefine(ExtractError):
    """A name has two different active definitions."""


def strip_comments(text: str) -> str:
    """Replace each C comment with a space, keeping its newlines and every literal."""

    def replace(match: re.Match[str]) -> str:
        token = match.group(0)
        if token.startswith(("/*", "//")):
            return " " + "\n" * token.count("\n")
        return token

    return _COMMENT_OR_LITERAL.sub(replace, text)


def _logical_lines(text: str) -> list[str]:
    """Join backslash-continued lines after comments are stripped."""
    return strip_comments(text).replace("\\\r\n", " ").replace("\\\n", " ").splitlines()


def collect(  # noqa: PLR0912 (one branch per directive)
    text: str, *, stop: re.Pattern[str] | None = None
) -> dict[str, list[str]]:
    """Map each object-like macro to its distinct bodies, in source order.

    Reading ends at the first line that ``stop`` matches, if given; conditionals
    still open there are not an error.
    """
    found: dict[str, list[str]] = {}
    # One entry per open conditional: (skipping, kind), kind "0", "1" or "other".
    stack: list[tuple[bool, str]] = []
    for line in _logical_lines(text):
        if stop is not None and stop.match(line):
            return found
        directive = _DIRECTIVE.match(line)
        if directive is None:
            continue
        name, rest = directive.group(1), directive.group(2).strip()
        if name in ("if", "ifdef", "ifndef"):
            kind = rest if name == "if" and rest in ("0", "1") else "other"
            stack.append((kind == "0", kind))
        elif name in ("elif", "else"):
            if not stack:
                raise ExtractError(f"#{name} without #if")
            _, kind = stack.pop()
            if kind == "0":
                stack.append((False, "other"))
            else:  # after "#if 1" no other branch is taken
                stack.append((kind == "1", kind))
        elif name == "endif":
            if not stack:
                raise ExtractError("#endif without #if")
            stack.pop()
        elif any(skipping for skipping, _ in stack):
            continue
        elif name == "define":
            match = _DEFINE.match(rest)
            if match is None:
                raise ExtractError(f"cannot read #define {rest!r}")
            macro, paren, body = match.groups()
            if paren:  # function-like
                continue
            bodies = found.setdefault(macro, [])
            if body.strip() not in bodies:
                bodies.append(body.strip())
        elif name == "undef":
            found.pop(rest.split()[0] if rest else "", None)
    if stack:
        raise ExtractError("unterminated #if")
    return found


class Defines:
    """Evaluate macros from one or more ``collect`` tables, later tables winning."""

    def __init__(self, *tables: Mapping[str, list[str]]) -> None:
        self._bodies: dict[str, list[str]] = {}
        for table in tables:
            self._bodies.update(table)
        self._cache: dict[str, int | None] = {}
        self._active: set[str] = set()

    def value(self, name: str) -> int | None:
        """The integer ``name`` expands to, or ``None`` when it is not an integer."""
        if name in self._cache:
            return self._cache[name]
        bodies = self._bodies.get(name)
        if bodies is None or name in self._active:
            return None
        if len(bodies) > 1:
            raise AmbiguousDefine(f"{name} has several definitions: {bodies}")
        self._active.add(name)
        try:
            result: int | None = cexpr.evaluate(bodies[0], self.value)
        except AmbiguousDefine:
            raise
        except ExtractError:
            result = None
        finally:
            self._active.discard(name)
        self._cache[name] = result
        return result

    def integers(self, names: Iterable[str]) -> dict[str, int]:
        """Each of ``names`` that evaluates to an integer."""
        values = {name: self.value(name) for name in names}
        return {name: value for name, value in values.items() if value is not None}
