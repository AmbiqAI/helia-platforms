"""Build model objects from entry trees (ADR 0002 section 4)."""

from __future__ import annotations

import dataclasses
import datetime
import types
import typing
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, get_args, get_origin

from helia_platforms import _format as fmt
from helia_platforms import _walk, model
from helia_platforms._tree import Path, Record, Tree, item_key, segment
from helia_platforms.errors import FormatError


def provenance(record: Record) -> model.Provenance | None:
    """Turn a record as written into a ``Provenance``; None stays None."""
    if record is None:
        return None
    verified_on = record.get("verified_on")
    if verified_on is not None:
        try:
            verified_on = datetime.date.fromisoformat(verified_on)
        except ValueError:
            raise FormatError(f"verified_on {verified_on!r} is not a calendar date") from None
    return model.Provenance(
        status=record["status"],
        source=tuple(record.get("source", ())),
        verified_on=verified_on,
        verified_by=record.get("verified_by"),
        notes=record.get("notes"),
    )


def freeze(value: Any, memo: dict[int, Any] | None = None) -> Any:
    """Deep-freeze JSON-compatible data: mappings to read-only views, lists to tuples.

    ``memo`` maps ``id()`` of each container already frozen to its result, so a
    sub-object that YAML aliases share is frozen once and stays shared.
    """
    memo = {} if memo is None else memo
    if id(value) in memo:
        return memo[id(value)]
    if isinstance(value, dict):
        frozen: Any = MappingProxyType({k: freeze(v, memo) for k, v in value.items()})
    elif isinstance(value, list):
        frozen = tuple(freeze(v, memo) for v in value)
    else:
        return value
    memo[id(value)] = frozen
    return frozen


class _Builder:
    def __init__(self, tree: Tree) -> None:
        self.records = tree.records

    def record(self, path: Path) -> model.Provenance:
        for cut in range(len(path), -1, -1):
            if path[:cut] in self.records:
                return provenance(self.records[path[:cut]]) or model.UNVERIFIED
        return model.UNVERIFIED

    def build(self, cls: type, decl: type, values: dict, path: Path, key: str | None) -> Any:
        hints = typing.get_type_hints(cls)
        declared = _walk.fields(decl)
        kwargs: dict[str, Any] = {}
        carrier = issubclass(cls, model._Carrier)
        for f in dataclasses.fields(typing.cast(Any, cls)):
            if f.name in ("provenance", "field_provenance"):
                continue
            if key is not None and f.name == getattr(cls, "KEY", None):
                kwargs[f.name] = key
            elif f.name in values and f.name in declared:
                kwargs[f.name] = self.convert(
                    values[f.name], hints[f.name], declared[f.name].type, (*path, f.name)
                )
            elif f.name in values:  # an entity id, which is its table key
                kwargs[f.name] = values[f.name]
        if carrier:
            own = self.record(path)
            kwargs["provenance"] = own
            kwargs["field_provenance"] = MappingProxyType(self.differing(path, own, cls, decl))
        return cls(**kwargs)

    def differing(self, path: Path, own: model.Provenance, cls: type, decl: type) -> dict:
        """Per-value records under ``path`` that differ from ``own``, stopping at carriers."""
        result: dict[str, model.Provenance] = {}
        for sub, rec in self.records.items():
            if sub[: len(path)] != path or sub == path or not _is_own_leaf(sub[len(path) :], decl):
                continue
            value = provenance(rec) or model.UNVERIFIED
            if value != own:
                result[".".join(sub[len(path) :])] = value
        return dict(sorted(result.items()))

    def convert(self, value: Any, hint: Any, decl: Any, path: Path) -> Any:  # noqa: PLR0911
        bare_decl, markers = _walk.unwrap(decl)
        if fmt.OPAQUE in markers or (get_origin(hint) is Mapping and _is_any_map(hint)):
            return freeze(value)
        hint = _strip_optional(hint)
        origin = get_origin(hint)
        if dataclasses.is_dataclass(hint):
            if hint is model.ClockDomain:
                raise TypeError("clock domains are built by their container")
            obj = _object_decl(bare_decl, value)
            return self.build(hint, obj, value, path, None)
        if origin is tuple:
            item_hint = get_args(hint)[0]
            if item_hint is model.ClockDomain:
                return self.clock_domains(value, bare_decl, path)
            if isinstance(value, dict):  # a keyed mapping held as a tuple at run time
                _, item_decl = get_args(bare_decl)
                return tuple(
                    self.keyed(item_hint, item_decl, item, (*path, k), k)
                    for k, item in value.items()
                )
            (item_decl,) = get_args(bare_decl)
            keyed = _walk.marker(markers, fmt.Keyed)
            if dataclasses.is_dataclass(item_hint):
                return tuple(
                    self.convert(
                        item,
                        item_hint,
                        item_decl,
                        (*path, item_key(item, keyed)) if keyed else (*path, segment(item)),
                    )
                    for item in value
                )
            return tuple(value)
        if origin is Mapping:
            _, item_hint = get_args(hint)
            _, item_decl = get_args(_mapping_decl(bare_decl))
            if dataclasses.is_dataclass(item_hint):
                return MappingProxyType(
                    {
                        k: self.keyed(item_hint, item_decl, v, (*path, k), k)
                        for k, v in value.items()
                    }
                )
            return MappingProxyType(dict(value))
        if hint is float and isinstance(value, int):
            return float(value)
        return value

    def keyed(self, cls: type, decl: Any, value: dict, path: Path, key: str) -> Any:
        return self.build(cls, _object_decl(_walk.unwrap(decl)[0], value), value, path, key)

    def clock_domains(self, value: dict, decl: Any, path: Path) -> tuple:
        _, points_decl = get_args(decl)
        _, point_decl = get_args(_walk.unwrap(points_decl)[0])
        return tuple(
            model.ClockDomain(
                id=domain,
                points=tuple(
                    self.keyed(model.DomainPoint, point_decl, p, (*path, domain, name), name)
                    for name, p in points.items()
                ),
            )
            for domain, points in value.items()
        )


def _is_own_leaf(rel: Path, decl: type) -> bool:
    """True when ``rel`` names a scalar value of ``decl`` itself, not of a nested carrier."""
    tp: Any = decl
    for seg in rel:
        bare, markers = _walk.unwrap(tp)
        if _walk.is_union(bare):
            bare = _union_step(bare, seg)
        if _walk.is_object(bare):
            declared = _walk.fields(bare)
            if seg not in declared:
                return False
            tp = declared[seg].type
        elif get_origin(bare) is dict:
            tp = get_args(bare)[1]
        elif get_origin(bare) is list:
            if fmt.BY_VALUE in markers or _walk.marker(markers, fmt.Keyed) is None:
                return True  # a by-value list item ends the path
            tp = get_args(bare)[0]
        else:
            return False
        child, _ = _walk.unwrap(tp)
        if _walk.is_object(child) and issubclass(
            model.BY_NAME.get(child.__name__, object), model._Carrier
        ):
            return False
    bare, markers = _walk.unwrap(tp)
    if _walk.is_union(bare) and not _walk.is_scalar_like(tp):
        return False
    return not (_walk.is_object(bare) or get_origin(bare) in (dict, list))


def _union_step(union: Any, seg: str) -> Any:
    """For ``app_start``: the single form if ``seg`` is one of its keys, else the per-core form."""
    for arg in get_args(union):
        bare = _walk.unwrap(arg)[0]
        if _walk.is_object(bare) and seg in _walk.fields(bare):
            return bare
    for arg in get_args(union):
        bare = _walk.unwrap(arg)[0]
        if get_origin(bare) is dict:
            return bare
    return union


def _mapping_decl(bare: Any) -> Any:
    if _walk.is_union(bare):
        for arg in get_args(bare):
            candidate = _walk.unwrap(arg)[0]
            if get_origin(candidate) is dict:
                return candidate
    return bare


def _strip_optional(hint: Any) -> Any:
    if get_origin(hint) in (typing.Union, types.UnionType):
        args = [a for a in get_args(hint) if a is not type(None)]
        if len(args) == 1:
            return args[0]
    return hint


def _is_any_map(hint: Any) -> bool:
    return get_args(hint)[1] is Any


def _object_decl(bare: Any, value: Any) -> type:
    if _walk.is_object(bare):
        return bare
    if _walk.is_union(bare):
        for arg in get_args(bare):
            candidate = _walk.unwrap(arg)[0]
            if _walk.is_object(candidate):
                return candidate
    raise TypeError(f"no object declaration in {bare!r}")


def build_entity(cls: type, decl: type, tree: Tree, entry_id: str) -> Any:
    """Build one entity (Soc, Board, ...) from its tree."""
    values = dict(tree.values)
    values.pop("based_on", None)
    return _Builder(tree).build(cls, decl, {**values, "id": entry_id}, (), None)
