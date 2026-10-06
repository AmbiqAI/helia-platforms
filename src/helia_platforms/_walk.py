"""Introspection over the declarations in ``_format``, shared by the checker and the generator."""

from __future__ import annotations

import functools
import types
import typing
from dataclasses import dataclass
from typing import Any, Literal, NotRequired, Required, Union, get_args, get_origin

from helia_platforms import _format as fmt


@dataclass(frozen=True)
class Field:
    """One key of a declared object."""

    name: str
    type: Any
    required: bool


def unwrap(tp: Any) -> tuple[Any, tuple[Any, ...]]:
    """Strip Required, NotRequired and Annotated; return the bare type and its markers."""
    markers: list[Any] = []
    while True:
        origin = get_origin(tp)
        if origin in (Required, NotRequired):
            tp = get_args(tp)[0]
        elif origin is typing.Annotated:
            tp, *extra = get_args(tp)
            markers.extend(extra)
        else:
            return tp, tuple(markers)


def is_object(tp: Any) -> bool:
    """True for a declared object (a TypedDict class)."""
    return isinstance(tp, type) and typing.is_typeddict(tp)


def is_union(tp: Any) -> bool:
    return get_origin(tp) in (Union, types.UnionType)


def is_literal(tp: Any) -> bool:
    return get_origin(tp) is Literal


@functools.cache
def fields(obj: type) -> dict[str, Field]:
    """The keys of a declared object, in declaration order."""
    hints = typing.get_type_hints(obj, include_extras=True)
    required = getattr(obj, "__required_keys__")  # noqa: B009 (ty cannot see TypedDict dunders)
    return {name: Field(name, tp, name in required) for name, tp in hints.items()}


def carries_facts(obj: type) -> bool:
    """True when the object's values are facts and it may carry a ``provenance`` record."""
    return "provenance" in fields(obj)


def is_inheritable(obj: type) -> bool:
    """True for an entity table entry, which may name a ``based_on`` entry."""
    return "based_on" in fields(obj)


def is_scalar_like(tp: Any) -> bool:
    """True where a fact may be written as ``{value, provenance}``: scalars and value lists."""
    bare, markers = unwrap(tp)
    if fmt.OPAQUE in markers:
        return False
    if fmt.SIZE in markers or fmt.BY_VALUE in markers or is_literal(bare):
        return True
    if is_union(bare):
        return all(is_scalar_like(arg) for arg in get_args(bare))
    return bare in (str, int, float, bool)


def marker(markers: tuple[Any, ...], kind: type) -> Any | None:
    """The first marker of class ``kind``, or None."""
    return next((m for m in markers if isinstance(m, kind)), None)
