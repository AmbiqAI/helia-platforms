"""Evaluate integer expressions in C, GNU ld, scatter-file and Kconfig syntax.

Literals take C suffixes (``U``, ``L``, ``UL``, ``ULL``), which are dropped, and,
where ``size_suffixes`` is set, the GNU ld ``K`` and ``M`` multipliers. Casts to
the C integer types are dropped. Division truncates toward zero, as in C.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping

from snapshot_extractor import ExtractError

_TOKEN = re.compile(
    r"\s*(?:(?P<num>0[xX][0-9a-fA-F]+|[0-9]+)(?P<suffix>[uUlLkKmM]*)"
    r"|(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
    r"|(?P<op><<|>>|<=|>=|==|!=|&&|\|\||[-+*/%&|^~!()<>]))"
)
_C_SUFFIX = re.compile(r"(?:[uU](?:ll|LL|l|L)?|(?:ll|LL|l|L)[uU]?)?")
_INTEGER_TYPES = frozenset(
    {
        *(f"{sign}int{bits}_t" for sign in ("", "u") for bits in (8, 16, 32, 64)),
        "int",
        "long",
        "short",
        "char",
        "unsigned",
        "signed",
        "size_t",
    }
)
# Binding power of each binary operator, as in C.
_BINARY: dict[str, int] = {
    "||": 1,
    "&&": 2,
    "|": 3,
    "^": 4,
    "&": 5,
    "==": 6,
    "!=": 6,
    "<": 7,
    ">": 7,
    "<=": 7,
    ">=": 7,
    "<<": 8,
    ">>": 8,
    "+": 9,
    "-": 9,
    "*": 10,
    "/": 10,
    "%": 10,
}


def _c_div(a: int, b: int) -> int:
    if b == 0:
        raise ExtractError("division by zero")
    quotient = abs(a) // abs(b)
    return quotient if (a < 0) == (b < 0) else -quotient


_APPLY: dict[str, Callable[[int, int], int]] = {
    "||": lambda a, b: int(bool(a) or bool(b)),
    "&&": lambda a, b: int(bool(a) and bool(b)),
    "|": lambda a, b: a | b,
    "^": lambda a, b: a ^ b,
    "&": lambda a, b: a & b,
    "==": lambda a, b: int(a == b),
    "!=": lambda a, b: int(a != b),
    "<": lambda a, b: int(a < b),
    ">": lambda a, b: int(a > b),
    "<=": lambda a, b: int(a <= b),
    ">=": lambda a, b: int(a >= b),
    "<<": lambda a, b: a << b,
    ">>": lambda a, b: a >> b,
    "+": lambda a, b: a + b,
    "-": lambda a, b: a - b,
    "*": lambda a, b: a * b,
    "/": _c_div,
    "%": lambda a, b: a - b * _c_div(a, b),
}


def tokenize(text: str, *, size_suffixes: bool = False) -> list[str | int]:
    """Split ``text`` into integers, identifiers and operators."""
    tokens: list[str | int] = []
    pos = 0
    text = text.rstrip()
    while pos < len(text):
        match = _TOKEN.match(text, pos)
        if match is None:
            raise ExtractError(f"cannot read {text[pos:].strip()!r} in {text.strip()!r}")
        pos = match.end()
        if match["num"] is not None:
            tokens.append(_literal(match["num"], match["suffix"], size_suffixes))
        else:
            tokens.append(match["name"] or match["op"])
    return tokens


def _literal(digits: str, suffix: str, size_suffixes: bool) -> int:
    if digits.lower().startswith("0x"):
        value = int(digits, 16)
    elif len(digits) > 1 and digits.startswith("0"):
        value = int(digits, 8)
    else:
        value = int(digits, 10)
    if _C_SUFFIX.fullmatch(suffix):
        return value
    if size_suffixes and suffix in ("K", "k"):
        return value * 1024
    if size_suffixes and suffix in ("M", "m"):
        return value * 1024 * 1024
    raise ExtractError(f"unknown integer suffix {suffix!r} on {digits}")


def evaluate(
    text: str,
    names: Mapping[str, int] | Callable[[str], int | None] | None = None,
    *,
    size_suffixes: bool = False,
) -> int:
    """Evaluate ``text``; ``names`` resolves identifiers, or raises ``ExtractError``."""
    if names is None or isinstance(names, Mapping):
        table: Mapping[str, int] = names or {}

        def resolve(name: str) -> int | None:
            return table.get(name)

    else:
        resolve = names
    parser = _Parser(tokenize(text, size_suffixes=size_suffixes), resolve, text)
    value = parser.expression(0)
    if parser.pos != len(parser.tokens):
        raise ExtractError(f"unexpected {parser.tokens[parser.pos]!r} in {text.strip()!r}")
    return value


class _Parser:
    """Precedence climbing over the token list."""

    def __init__(
        self, tokens: list[str | int], resolve: Callable[[str], int | None], text: str
    ) -> None:
        self.tokens = tokens
        self.pos = 0
        self.resolve = resolve
        self.text = text
        self.skipping = 0

    def _peek(self) -> str | int | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def _take(self) -> str | int:
        token = self._peek()
        if token is None:
            raise ExtractError(f"expression ends early: {self.text.strip()!r}")
        self.pos += 1
        return token

    def expression(self, min_power: int) -> int:
        left = self._unary()
        while True:
            op = self._peek()
            if not isinstance(op, str) or op not in _BINARY or _BINARY[op] <= min_power:
                return left
            self.pos += 1
            if (op == "&&" and not left) or (op == "||" and left):
                # As in C, the right operand is parsed but not evaluated.
                self.skipping += 1
                self.expression(_BINARY[op])
                self.skipping -= 1
                left = int(bool(left))
                continue
            right = self.expression(_BINARY[op])
            left = 0 if self.skipping else _APPLY[op](left, right)

    def _unary(self) -> int:  # noqa: PLR0911 (one return per kind of operand)
        token = self._take()
        if isinstance(token, int):
            return token
        if token == "(":
            if self._is_cast():
                return self._unary()
            value = self.expression(0)
            if self._take() != ")":
                raise ExtractError(f"unbalanced parentheses in {self.text.strip()!r}")
            return value
        if token == "-":
            return -self._unary()
        if token == "+":
            return self._unary()
        if token == "~":
            return ~self._unary()
        if token == "!":
            return int(not self._unary())
        if token[0].isalpha() or token[0] == "_":
            if self.skipping:
                return 0
            value = self.resolve(token)
            if value is None:
                raise ExtractError(f"{token} is not an integer in {self.text.strip()!r}")
            return value
        raise ExtractError(f"unexpected {token!r} in {self.text.strip()!r}")

    def _is_cast(self) -> bool:
        """Consume ``type)`` after an opening parenthesis when it names a C integer type."""
        end = self.pos
        while end < len(self.tokens) and self.tokens[end] in _INTEGER_TYPES:
            end += 1
        if end == self.pos or end >= len(self.tokens) or self.tokens[end] != ")":
            return False
        self.pos = end + 1
        return True
