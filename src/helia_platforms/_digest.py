"""``catalogue_digest`` and the source hash of ADR 0004 points 1 and 4."""

from __future__ import annotations

import dataclasses
import functools
import hashlib
import json
import typing
from collections.abc import Mapping
from typing import Any, get_args, get_origin

from helia_platforms import _format as fmt
from helia_platforms import _walk, model

#: Instance lists whose order is a fact (ADR 0002 section 2.4).
_ORDERED = (model.CoreInstance, model.NpuInstance, model.AcceleratorInstance)
#: Lists keyed by (master, target), projected as lists sorted by that pair.
_PAIRS = (model.Access, model.AccessKey)


def canonical(value: Any) -> bytes:
    """The bytes ADR 0004 point 1 hashes."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value)).hexdigest()


def catalogue_digest(
    tables: Mapping[str, Mapping[str, Any]],
    compositions: Mapping[str, model.Composition],
    shorthands: Mapping[str, tuple[str, ...]],
) -> str:
    """Hash entity tables, compositions and shorthands by ADR 0004 point 1's projection."""
    projection = {kind: _keyed(entries) for kind, entries in tables.items()}
    projection["compositions"] = _keyed(compositions)
    projection["shorthands"] = {name: sorted(members) for name, members in shorthands.items()}
    return sha256(projection)


def project(value: Any) -> Any:
    """A model object as JSON data, with records removed and collections projected by kind."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        cls = type(value)
        return {
            f.name: _field(cls, f.name, getattr(value, f.name))
            for f in dataclasses.fields(value)
            if f.name not in model.RECORD_FIELDS  # records are not data (ADR 0004 point 1)
        }
    if isinstance(value, Mapping):
        return _keyed(value)
    if isinstance(value, tuple):
        raise TypeError("a tuple is projected by the field that holds it")
    return value


def _keyed(entries: Mapping[str, Any]) -> dict[str, Any]:
    return {key: project(item) for key, item in entries.items()}


def _field(cls: type, name: str, value: Any) -> Any:
    if name == "extensions":
        # Unreachable from Catalogue.catalogue_digest, since built-in entries may not
        # carry extensions; kept so a hand-built model still projects.
        return _opaque(value)
    if isinstance(value, tuple):
        return _sequence(value, _item_type(cls, name))
    return project(value)


@functools.cache
def _item_type(cls: type, name: str) -> Any:
    """The item type of a ``tuple[X, ...]`` field, optional or not."""
    hint = typing.get_type_hints(cls)[name]
    for tp in (hint, *get_args(hint)):
        if get_origin(tp) is tuple:
            return get_args(tp)[0]
    raise TypeError(f"{cls.__name__}.{name} is not declared as a tuple")


def _sequence(items: tuple[Any, ...], item_type: Any) -> Any:
    if item_type in _ORDERED:
        return [project(item) for item in items]
    if item_type in _PAIRS:
        return sorted(map(project, items), key=lambda p: (p["master"], p["target"]))
    key = getattr(item_type, "KEY", None)
    if key is not None:
        return {getattr(item, key): project(item) for item in items}
    if dataclasses.is_dataclass(item_type):
        raise TypeError(f"no projection is defined for a list of {item_type.__name__}")
    return sorted(items)


def _opaque(value: Any) -> Any:
    """Opaque tool data (``extensions``), unfrozen but otherwise unchanged."""
    if isinstance(value, Mapping):
        return {key: _opaque(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_opaque(item) for item in value]
    return value


def source_sha256(document: Mapping[str, Any]) -> str:
    """Hash a parsed overlay document as ADR 0004 point 4 specifies.

    Records are removed and ``{value, provenance}`` forms unwrapped only on keys the
    format declares; ``extensions`` values are hashed unchanged.
    """
    top = {k: v for k, v in document.items() if k not in fmt.IGNORED_TOP_LEVEL}
    return sha256(_strip(top, fmt.Document, facts=False))


def _strip(value: Any, tp: Any, facts: bool) -> Any:  # noqa: PLR0911
    bare, markers = _walk.unwrap(tp)
    if fmt.OPAQUE in markers:
        return value
    if fmt.NOT_FACT in markers:
        facts = False
    if facts and isinstance(value, dict) and _walk.is_scalar_like(tp) and "value" in value:
        return _strip(value["value"], tp, facts=False)
    if _walk.is_object(bare) and isinstance(value, dict):
        declared = _walk.fields(bare)
        inner = _walk.carries_facts(bare)
        return {
            key: _strip(item, declared[key].type, inner) if key in declared else item
            for key, item in value.items()
            if not (key == "provenance" and key in declared)
        }
    if _walk.is_union(bare):
        return _strip(value, _branch(value, bare), facts)
    if get_origin(bare) is dict and isinstance(value, dict):
        item_tp = get_args(bare)[1]
        return {key: _strip(item, item_tp, facts) for key, item in value.items()}
    if get_origin(bare) is list and isinstance(value, list):
        (item_tp,) = get_args(bare)
        return [_strip(item, item_tp, facts) for item in value]
    return value


def _branch(value: Any, union: Any) -> Any:
    """The union member a value takes: an object whose keys it uses, else a mapping."""
    alternatives = [_walk.unwrap(arg)[0] for arg in get_args(union)]
    if isinstance(value, dict):
        for alt in alternatives:
            if _walk.is_object(alt) and set(value) <= set(_walk.fields(alt)):
                return alt
        for alt in alternatives:
            if get_origin(alt) is dict:
                return alt
    return alternatives[0]
