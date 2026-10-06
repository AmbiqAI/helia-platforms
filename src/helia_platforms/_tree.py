"""Entry trees with provenance per fact path, and the merges of ADR 0002 section 2.5.

An entry is held as ``values`` (the file's data without provenance, sizes as
integers) plus ``records``, which maps every node's path to the record that
covers it (the nearest ``provenance`` in the file, else the default). A path
is a tuple of segments in ADR 0003's field-path grammar.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, get_args

from helia_platforms import _format as fmt
from helia_platforms import _walk
from helia_platforms.errors import PlatformError

Path = tuple[str, ...]
Record = dict[str, Any] | None

#: Keys ``based_on`` does not copy (RFC 0002 "Inheritance and derivation").
NOT_INHERITED = frozenset({"aliases", "default_board", "derives_from", "release_status"})

_SIZE_UNITS = {"K": 1024, "M": 1024**2, "G": 1024**3}


@dataclass
class Tree:
    """One entry: its values and the record covering each path."""

    values: dict[str, Any]
    records: dict[Path, Record] = field(default_factory=dict)


def to_bytes(value: Any) -> int:
    if isinstance(value, str):
        return int(value[:-1]) * _SIZE_UNITS[value[-1]]
    return int(value)


def segment(item: Any) -> str:
    """The path segment of a by-value list item (an address prints in hex)."""
    if isinstance(item, int) and not isinstance(item, bool):
        return hex(item)
    return str(item)


def item_key(item: dict, keyed: fmt.Keyed) -> str:
    return "@".join(str(item[k]) for k in keyed.fields)


# ---- normalizing a file entry ------------------------------------------------------


def normalize(raw: dict, obj: type, default: Record) -> Tree:
    """Split an entry as written into values and per-path records."""
    records: dict[Path, Record] = {}
    values = _normalize(raw, obj, (), default, out=records, facts=True)
    return Tree(values, records)


def _normalize(  # noqa: PLR0911, PLR0912 (one branch per declared kind)
    value: Any, tp: Any, path: Path, record: Record, *, out: dict, facts: bool
) -> Any:
    bare, markers = _walk.unwrap(tp)
    if fmt.NOT_FACT in markers:
        facts = False
    if fmt.OPAQUE in markers:
        return copy.deepcopy(value)
    if facts and _walk.is_scalar_like(tp) and isinstance(value, dict) and "value" in value:
        record, value = value["provenance"], value["value"]
    if facts:
        out[path] = record
    if fmt.SIZE in markers:
        return to_bytes(value)
    if _walk.is_union(bare) and isinstance(value, dict):
        bare = _pick_alternative(value, bare)
    if _walk.is_object(bare):
        declared = _walk.fields(bare)
        carries = _walk.carries_facts(bare)
        if carries and "provenance" in value:
            record = value["provenance"]
            if facts:
                out[path] = record
        return {
            key: _normalize(
                item, declared[key].type, (*path, key), record, out=out, facts=facts and carries
            )
            for key, item in value.items()
            if key != "provenance"
        }
    origin = getattr(bare, "__origin__", None)
    if origin is dict:
        _, item_tp = get_args(bare)
        return {
            key: _normalize(item, item_tp, (*path, key), record, out=out, facts=facts)
            for key, item in value.items()
        }
    if origin is list:
        (item_tp,) = get_args(bare)
        keyed = _walk.marker(markers, fmt.Keyed)
        result = []
        for item in value:
            # Normalize first, so the item's key is read from its plain values.
            found: dict[Path, Record] = {}
            plain = _normalize(item, item_tp, (), record, out=found, facts=facts)
            seg = item_key(plain, keyed) if keyed is not None else segment(plain)
            out.update({(*path, seg, *sub): rec for sub, rec in found.items()})
            result.append(plain)
        return result
    if isinstance(value, float) and value.is_integer() and bare is int:
        return int(value)
    return value


def _pick_alternative(value: dict, union: Any) -> Any:
    """For ``app_start``: the single form has scalar values, the per-core form mappings."""
    objects = [a for a in (_walk.unwrap(arg)[0] for arg in get_args(union)) if _walk.is_object(a)]
    mappings = [a for a in get_args(union) if getattr(a, "__origin__", None) is dict]
    if mappings and value and all(isinstance(v, dict) for v in value.values()):
        return mappings[0]
    return objects[0] if objects else union


# ---- the merge (ADR 0002 section 2.5) -----------------------------------------------


class MergeError(PlatformError):
    """A delta names a key the base lacks; ``problems`` lists each one."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("\n".join(problems))


def _collection(tp: Any) -> tuple[str | None, Any, Any]:
    """Classify a field: ("map", item type), ("keyed", marker), ("values", None) or None."""
    bare, markers = _walk.unwrap(tp)
    origin = getattr(bare, "__origin__", None)
    if origin is dict:
        return "map", get_args(bare)[1], None
    if origin is list:
        keyed = _walk.marker(markers, fmt.Keyed)
        if keyed is not None:
            return "keyed", get_args(bare)[0], keyed
        return "values", None, None
    return None, None, None


def _merge_collection(base: Any, delta: Any, tp: Any) -> Any:
    kind, item_tp, keyed = _collection(tp)
    if kind == "map":
        result = dict(base)
        nested = _collection(item_tp)[0] == "map"
        for key, item in delta.items():
            if nested and key in result:
                result[key] = _merge_collection(result[key], item, item_tp)
            else:
                result[key] = item
        return result
    if kind == "keyed":
        result = list(base)
        index = {item_key(item, keyed): i for i, item in enumerate(result)}
        for item in delta:
            key = item_key(item, keyed)
            if key in index:
                result[index[key]] = item
            else:
                index[key] = len(result)
                result.append(item)
        return result
    return list(base) + [item for item in delta if item not in base]


def merge(base: Tree, delta: Tree, obj: type, *, inherit_all: bool = False) -> Tree:
    """Apply ``delta`` (an overlay entry, or an Implementation's Soc-shaped keys) over ``base``."""
    declared = _walk.fields(obj)
    values = {
        k: copy.deepcopy(v) for k, v in base.values.items() if inherit_all or k not in NOT_INHERITED
    }
    moved: dict[Path, Path] = {}  # result path -> the delta path whose record it takes
    deltas: dict[str, Any] = {}
    # Copied, because the deltas below edit the result in place and both inputs are stored.
    for key, item in copy.deepcopy(delta.values).items():
        if key == "based_on":
            continue
        if _is_delta_key(key, declared):
            deltas[key] = item
        elif key == "extensions":
            values[key] = {**values.get(key, {}), **item}
        elif key in values and _collection(declared[key].type)[0] is not None:
            values[key] = _merge_collection(values[key], item, declared[key].type)
        else:
            values[key] = item
    problems = _apply_deltas(values, deltas, moved, declared)
    if problems:
        raise MergeError(problems)
    records: dict[Path, Record] = {}
    for path in iter_paths(values, obj):
        if path in moved:
            records[path] = delta.records.get(moved[path])
        elif path in delta.records:
            records[path] = delta.records[path]
        else:
            records[path] = base.records.get(path)
    return Tree(values, records)


def _is_delta_key(key: str, declared: dict) -> bool:
    field_ = declared.get(key)
    return field_ is not None and fmt.FILE_ONLY in _walk.unwrap(field_.type)[1]


def _apply_deltas(values: dict, deltas: dict, moved: dict, declared: dict) -> list[str]:
    problems: list[str] = []
    for key, change in deltas.items():
        if key.endswith("_removed"):
            target = key.removesuffix("_removed")
            problems += _remove(values, target, change, declared)
        elif key in ("memories_resized", "memories_rebased"):
            field_name = "size" if key == "memories_resized" else "base"
            regions = values.get("memories", {})
            for name, new in change.items():
                if name not in regions:
                    problems.append(f"{key} names region {name!r}, which the base lacks")
                    continue
                regions[name] = {**regions[name], field_name: new}
                moved[("memories", name, field_name)] = (key, name)
    _drop_dangling_access(values, deltas)
    return problems


def _remove(values: dict, target: str, names: list, declared: dict) -> list[str]:  # noqa: PLR0912
    problems = []
    current = values.get(target)
    kind, _, keyed = _collection(declared[target].type) if target in declared else (None,) * 3
    for name in names:
        if target == "clock_domains" and isinstance(name, str) and "." in name:
            domain, point = name.split(".", 1)
            points = (current or {}).get(domain, {})
            if point not in points:
                problems.append(f"clock_domains_removed names {name!r}, which the base lacks")
            else:
                del points[point]
            continue
        if kind == "map":
            if not current or name not in current:
                problems.append(f"{target}_removed names {name!r}, which the base lacks")
            else:
                del current[name]
        elif kind == "keyed" and keyed is not None:
            items = current if isinstance(current, list) else []
            key = item_key(name, keyed) if isinstance(name, dict) else name
            keys = [item_key(item, keyed) for item in items]
            if key not in keys:
                problems.append(f"{target}_removed names {key!r}, which the base lacks")
            else:
                items.pop(keys.index(key))
        elif kind == "values":
            if not current or name not in current:
                problems.append(f"{target}_removed names {name!r}, which the base lacks")
            else:
                current.remove(name)
    return problems


def _drop_dangling_access(values: dict, deltas: dict) -> None:
    """Removing a region, controller, core, NPU or accelerator removes access naming it."""
    gone = set()
    for key in ("memories", "peripherals", "cores", "npus", "accelerators"):
        gone.update(deltas.get(f"{key}_removed", []))
    if gone and "access" in values:
        values["access"] = [
            a for a in values["access"] if a["master"] not in gone and a["target"] not in gone
        ]


def iter_paths(value: Any, tp: Any, path: Path = ()) -> list[Path]:
    """Every fact path in a normalized value, as ``normalize`` records them."""
    paths = [path]
    bare, markers = _walk.unwrap(tp)
    if fmt.NOT_FACT in markers or fmt.OPAQUE in markers:
        return []
    if _walk.is_union(bare) and isinstance(value, dict):
        bare = _pick_alternative(value, bare)
    if _walk.is_object(bare) and isinstance(value, dict):
        declared = _walk.fields(bare)
        for key, item in value.items():
            if key in declared:
                paths += iter_paths(item, declared[key].type, (*path, key))
        return paths
    origin = getattr(bare, "__origin__", None)
    if origin is dict and isinstance(value, dict):
        _, item_tp = get_args(bare)
        for key, item in value.items():
            paths += iter_paths(item, item_tp, (*path, key))
    elif origin is list and isinstance(value, list):
        (item_tp,) = get_args(bare)
        keyed = _walk.marker(markers, fmt.Keyed)
        for item in value:
            if keyed is not None:
                paths += iter_paths(item, item_tp, (*path, item_key(item, keyed)))
            else:
                paths.append((*path, segment(item)))
    return paths


# ---- an Implementation over its Soc ---------------------------------------------------

_SOC_SHAPED = ("clock_domains", "operating_points", "boot_configs", "default_boot")
_SUBSET_DELTAS = (
    "memories_removed",
    "memories_resized",
    "memories_rebased",
    "peripherals_removed",
    "cores_removed",
    "npus_removed",
    "accelerators_removed",
    "clock_domains_removed",
    "boot_configs_removed",
    "operating_points_removed",
    "access_removed",
)


def realize(soc: Tree, implementation: Tree) -> Tree:
    """The Soc as the Implementation realizes it, by the merge rule of section 2.5.

    Clock caps and FVP substitutions are not applied here; the resolver
    applies them, because their semantics are RFC 0002's, not the merge's.
    """
    values: dict[str, Any] = {}
    records: dict[Path, Record] = {(): implementation.records.get(())}
    for key in _SOC_SHAPED:
        if key in implementation.values:
            values[key] = implementation.values[key]
    subset = implementation.values.get("subset", {})
    for key in _SUBSET_DELTAS:
        if key in subset:
            values[key] = subset[key]
    for path, record in implementation.records.items():
        if path[:1] == ("subset",) and len(path) > 1 and path[1] in _SUBSET_DELTAS:
            records[path[1:]] = record
        elif path[:1] and path[0] in _SOC_SHAPED:
            records[path] = record
    return merge(soc, Tree(values, records), fmt.Soc, inherit_all=True)


# ---- shorthands (ADR 0002 section 2.5, last paragraph) ---------------------------------


def expand_shorthands(tree: Tree, soc: dict) -> list[str]:
    """Expand ``cpu_mhz``/``npu_mhz`` and a single ``app_start`` in place.

    ``soc`` is the Soc whose core 0 and npu 0 the shorthands refer to (the
    entry itself for a Soc, its Soc for an Implementation).
    """
    problems: list[str] = []
    values, records = tree.values, tree.records
    cores = soc.get("cores") or []
    npus = soc.get("npus") or []
    for name, point in (values.get("operating_points") or {}).items():
        for short, units in (("cpu_mhz", cores), ("npu_mhz", npus)):
            if short not in point:
                continue
            if not units:
                kind = "core" if short == "cpu_mhz" else "NPU"
                problems.append(f"operating_points.{name}.{short} needs a {kind} 0")
                continue
            domain = units[0]["clock_domain"]
            mhz = point.pop(short)
            all_domains = values.setdefault("clock_domains", {})
            if domain not in all_domains and domain not in (soc.get("clock_domains") or {}):
                problems.append(f"operating_points.{name}.{short}: no clock domain {domain!r}")
                continue
            domains_ = all_domains.setdefault(domain, {})
            existing = domains_.get(name)
            if existing is not None and existing.get("mhz") != mhz:
                problems.append(
                    f"operating_points.{name}.{short} is {mhz} MHz but clock_domains."
                    f"{domain}.{name} is {existing.get('mhz')} MHz"
                )
                continue
            domains_[name] = {"mhz": mhz}
            source = records.pop(("operating_points", name, short), None)
            records[("clock_domains", domain, name)] = source
            records[("clock_domains", domain, name, "mhz")] = source
            point.setdefault("domains", {})[domain] = name
            records[("operating_points", name, "domains", domain)] = source
    core0 = cores[0]["id"] if cores else None
    for name, config in (values.get("boot_configs") or {}).items():
        start = config.get("app_start")
        if isinstance(start, dict) and "region" in start:
            if core0 is None:
                problems.append(f"boot_configs.{name}.app_start needs a core 0")
                continue
            config["app_start"] = {core0: start}
            prefix = ("boot_configs", name, "app_start")
            for path in [p for p in records if p[: len(prefix)] == prefix]:
                records[(*prefix, core0, *path[len(prefix) :])] = records.pop(path)
            records[prefix] = records.get((*prefix, core0))
    return problems
