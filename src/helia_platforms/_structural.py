"""The loader's structural stage: check a parsed document against the format declaration.

It reports every problem it finds rather than stopping at the first. What a
JSON Schema cannot express (keyed-list uniqueness, references, merges) is
left to later stages, except the keyed-list check, which needs no context.
"""

from __future__ import annotations

import difflib
import math
import re
from typing import Any, get_args

from helia_platforms import _format as fmt
from helia_platforms import _walk

SIZE_HINT = (
    "write a size as an integer number of bytes or as <integer>K, M or G "
    "(1024, 1024² or 1024³ bytes); forms such as 256k, 256KB, 256KiB or 1.5M are rejected"
)


class _Checker:
    def __init__(self, origin: str) -> None:
        self.origin = origin
        self.problems: list[str] = []

    def fail(self, path: str, message: str) -> None:
        where = f"{self.origin}: {path}" if path else self.origin
        self.problems.append(f"{where}: {message}")

    # -- dispatch -------------------------------------------------------------

    def check(self, value: Any, tp: Any, path: str, facts: bool) -> None:
        bare, markers = _walk.unwrap(tp)
        if fmt.NOT_FACT in markers:
            facts = False
        if fmt.OPAQUE in markers:
            self.check_json(value, path, ())
            return
        if (
            facts
            and isinstance(value, dict)
            and _walk.is_scalar_like(tp)
            and ("value" in value or "provenance" in value)
        ):
            self.check_wrapper(value, tp, path)
            return
        if fmt.SIZE in markers:
            self.check_size(value, path)
        elif _walk.is_object(bare):
            self.check_object(value, bare, path)
        elif _walk.is_union(bare) and set(get_args(bare)) <= {int, float}:
            self.check_scalar(value, float, markers, path)
        elif _walk.is_union(bare):
            self.check_union(value, bare, path, facts)
        elif _walk.is_literal(bare):
            self.check_literal(value, bare, path)
        elif getattr(bare, "__origin__", None) is dict:
            self.check_mapping(value, bare, path, facts)
        elif getattr(bare, "__origin__", None) is list:
            self.check_list(value, bare, markers, path, facts)
        else:
            self.check_scalar(value, bare, markers, path)

    # -- kinds ------------------------------------------------------------------

    def check_wrapper(self, value: dict, tp: Any, path: str) -> None:
        extra = set(value) - {"value", "provenance"}
        if extra:
            self.fail(path, f"a {{value, provenance}} form has unknown keys {sorted(extra)}")
        if "value" not in value or "provenance" not in value:
            self.fail(path, "a {value, provenance} form needs both keys")
        if "value" in value:
            self.check(value["value"], tp, path, facts=False)
        if "provenance" in value:
            self.check_object(value["provenance"], fmt.Provenance, f"{path}.provenance")

    def check_object(self, value: Any, obj: type, path: str) -> None:
        if not isinstance(value, dict):
            self.fail(path, f"expected a mapping, got {_describe(value)}")
            return
        declared = _walk.fields(obj)
        for key in value:
            if not isinstance(key, str):
                self.fail(path, f"key {key!r} is not a string")
            elif key not in declared:
                self.fail(_join(path, key), _unknown_key(key, declared))
        inherits = _walk.is_inheritable(obj) and "based_on" in value
        if not inherits:
            for name, field in declared.items():
                if field.required and name not in value:
                    self.fail(path, f"missing required key {name!r}")
        facts = _walk.carries_facts(obj)
        for key, item in value.items():
            if isinstance(key, str) and key in declared:
                self.check(item, declared[key].type, _join(path, key), facts)

    def check_mapping(self, value: Any, tp: Any, path: str, facts: bool) -> None:
        if not isinstance(value, dict):
            self.fail(path, f"expected a mapping, got {_describe(value)}")
            return
        key_tp, item_tp = get_args(tp)
        for key, item in value.items():
            if not isinstance(key, str):
                self.fail(path, f"key {key!r} must be a string; quote it")
                continue
            self.check_scalar(key, *_walk.unwrap(key_tp), _join(path, key))
            self.check(item, item_tp, _join(path, key), facts)

    def check_list(self, value: Any, tp: Any, markers: tuple, path: str, facts: bool) -> None:
        if not isinstance(value, list):
            self.fail(path, f"expected a list, got {_describe(value)}")
            return
        (item_tp,) = get_args(tp)
        for index, item in enumerate(value):
            self.check(item, item_tp, f"{path}[{index}]", facts)
        if fmt.BY_VALUE in markers:
            seen: list[Any] = []
            for item in map(_plain, value):
                if _contains(seen, item):
                    self.fail(path, f"{item!r} is listed twice")
                seen.append(item)
        keyed = _walk.marker(markers, fmt.Keyed)
        if keyed is not None:
            seen_keys: set[tuple] = set()
            for item in value:
                if not isinstance(item, dict) or not all(k in item for k in keyed.fields):
                    continue
                key = tuple(_plain(item[k]) for k in keyed.fields)
                if not all(isinstance(k, str) for k in key):
                    continue
                if key in seen_keys:
                    self.fail(path, f"two items have the same {'/'.join(keyed.fields)} {key}")
                seen_keys.add(key)

    def check_json(self, value: Any, path: str, enclosing: tuple[int, ...]) -> None:
        """An opaque value must be JSON data: no other types, string keys, no cycles."""
        if isinstance(value, dict | list):
            if id(value) in enclosing:
                self.fail(path, "the value contains itself")
                return
            enclosing = (*enclosing, id(value))
        if isinstance(value, dict):
            for key, item in value.items():
                if isinstance(key, str):
                    self.check_text(key, path)
                    self.check_json(item, _join(path, key), enclosing)
                else:
                    self.fail(path, f"key {key!r} must be a string; quote it")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                self.check_json(item, f"{path}[{index}]", enclosing)
        elif isinstance(value, str):
            self.check_text(value, path)
        elif isinstance(value, float) and not math.isfinite(value):
            self.fail(path, f"{value!r} is not a finite number")
        elif not (value is None or isinstance(value, int | float)):
            self.fail(path, f"expected JSON data, got {_describe(value)}")

    def check_union(self, value: Any, tp: Any, path: str, facts: bool) -> None:
        best: list[str] | None = None
        for alternative in get_args(tp):
            trial = _Checker(self.origin)
            trial.check(value, alternative, path, facts)
            if not trial.problems:
                return
            if best is None or len(trial.problems) < len(best):
                best = trial.problems
        self.problems.extend(best or [])

    def check_literal(self, value: Any, tp: Any, path: str) -> None:
        allowed = get_args(tp)
        if not any(type(value) is type(a) and value == a for a in allowed):
            choices = ", ".join(repr(a) for a in allowed)
            self.fail(path, f"{value!r} is not one of {choices}")

    def check_size(self, value: Any, path: str) -> None:
        if _is_int(value):
            if value < 0:
                self.fail(path, "a size cannot be negative")
        elif isinstance(value, str):
            if not re.fullmatch(fmt.SIZE_RE, value):
                self.fail(path, f"{value!r} is not a size: {SIZE_HINT}")
        else:
            self.fail(path, f"expected a size, got {_describe(value)}: {SIZE_HINT}")

    def check_scalar(self, value: Any, tp: Any, markers: tuple, path: str) -> None:
        if tp is str:
            if not isinstance(value, str):
                hint = "; quote it" if _is_number(value) or isinstance(value, bool) else ""
                self.fail(path, f"expected a string, got {_describe(value)}{hint}")
                return
            self.check_text(value, path)
            pattern = _walk.marker(markers, fmt.Pattern)
            if pattern is not None and not re.fullmatch(pattern.regex, value):
                reserved = value in ("value", "provenance")
                why = " (the names value and provenance are reserved)" if reserved else ""
                self.fail(path, f"{value!r} is not {pattern.what}{why}")
            return
        if tp is bool:
            if not isinstance(value, bool):
                self.fail(path, f"expected true or false, got {_describe(value)}")
            return
        if tp is int:
            ok = _is_int(value)
            what = "an integer"
        elif tp is Any:
            return
        else:  # float | int
            ok = _is_number(value)
            what = "a number"
        if not ok:
            self.fail(path, f"expected {what}, got {_describe(value)}")
            return
        if isinstance(value, float) and not math.isfinite(value):
            self.fail(path, f"{value!r} is not a finite number")
            return
        minimum = _walk.marker(markers, fmt.Minimum)
        if minimum is not None and value < minimum.value:
            self.fail(path, f"must be at least {minimum.value}")

    def check_text(self, value: str, path: str) -> None:
        """A string must encode as UTF-8; a lone surrogate from a JSON ``\\ud800`` does not."""
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            self.fail(path, f"{value!r} is not valid Unicode text (it has a lone surrogate)")


def conforms(value: Any, tp: Any, *, facts: bool) -> bool:
    """True when ``value`` has no structural problem as a ``tp``."""
    checker = _Checker("")
    checker.check(value, tp, "", facts)
    return not checker.problems


def check_document(data: Any, origin: str, *, require_version: bool = True) -> list[str]:
    """Return every structural problem in a parsed document (empty when it conforms)."""
    checker = _Checker(origin)
    if not isinstance(data, dict):
        checker.fail("", f"expected a mapping at the top level, got {_describe(data)}")
        return checker.problems
    body = {k: v for k, v in data.items() if k not in fmt.IGNORED_TOP_LEVEL}
    if not require_version and "schema_version" not in body:
        body["schema_version"] = fmt.SCHEMA_VERSION
    checker.check_object(body, fmt.Document, "")
    version = body.get("schema_version")
    if _is_int(version) and version != fmt.SCHEMA_VERSION:
        checker.fail(
            "schema_version",
            f"schema_version {version} is not read by this package, which reads "
            f"{fmt.SCHEMA_VERSION}; a newer helia-platforms may read it",
        )
    return checker.problems


# -- helpers --------------------------------------------------------------------


def _join(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key


def _is_int(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    return isinstance(value, int) or (isinstance(value, float) and value.is_integer())


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _plain(value: Any) -> Any:
    if isinstance(value, dict) and "value" in value:
        return value["value"]
    return value


def _contains(seen: list[Any], item: Any) -> bool:
    """Equality as JSON Schema's ``uniqueItems`` reads it: 4096 equals 4096.0, not true."""
    return any(
        s == item if _is_number(s) and _is_number(item) else type(s) is type(item) and s == item
        for s in seen
    )


def _describe(value: Any) -> str:  # noqa: PLR0911 (one return per kind of value)
    if value is None:
        return "nothing (null)"
    if isinstance(value, bool):
        return f"the boolean {str(value).lower()}"
    if isinstance(value, dict):
        return "a mapping"
    if isinstance(value, list):
        return "a list"
    if isinstance(value, str):
        return f"the string {value!r}"
    if _is_number(value):
        return f"the number {value!r}"
    return f"a {type(value).__name__} value"


def _unknown_key(key: str, declared: dict) -> str:
    message = f"unknown key {key!r}"
    close = difflib.get_close_matches(key, list(declared), n=1)
    if close:
        message += f"; did you mean {close[0]!r}?"
    return message + " (a newer helia-platforms may know it)"
