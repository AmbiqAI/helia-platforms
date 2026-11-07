"""The JSON export of a catalog, filtered by release status (RFC 0003)."""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, get_args

from helia_platforms import _format as fmt
from helia_platforms import _walk
from helia_platforms._tree import Path, _pick_alternative, item_key, segment

if TYPE_CHECKING:
    from helia_platforms.catalog import Catalog

_PUBLIC = "public"


def document(catalog: Catalog, *, provenance: bool = False) -> dict[str, Any]:
    """The export: ``schema_version``, ``identity`` and the filtered ``catalog``.

    With ``provenance``, ``catalog`` keeps every record in the file format; that form is
    for internal use until ADR 0005's audit is done (RFC 0003 "Provenance").
    """
    return _document(catalog, filtered=True, provenance=provenance)


def render(export: Mapping[str, Any]) -> str:
    """Sorted keys, two-space indentation and a final newline, so equal inputs give equal bytes."""
    return json.dumps(export, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _document(catalog: Catalog, *, filtered: bool, provenance: bool) -> dict[str, Any]:
    """The export, unfiltered only for ADR 0005's distribution test."""
    kept = _kept(catalog) if filtered else _everything(catalog)
    member: dict[str, Any] = {"schema_version": catalog.schema_version}
    for kind, decl in fmt.ENTITY_TABLES.items():
        entries = {
            entry_id: _entry(catalog, kind, entry_id, decl, kept, provenance=provenance)
            for entry_id in catalog._tables.get(kind, {})
            if entry_id in kept[kind]
        }
        if entries:
            member[kind] = entries
    compositions = {
        alias: {"board": c.board, **({"addons": list(c.addons)} if c.addons else {})}
        for alias, c in catalog.compositions.items()
        if alias in kept["compositions"]
    }
    if compositions:
        member["compositions"] = compositions
    shorthands = {
        name: [m for m in members if _resolvable(kept, m)]
        for name, members in catalog.shorthands.items()
    }
    if shorthands := {name: members for name, members in shorthands.items() if members}:
        member["shorthands"] = shorthands
    return {
        "schema_version": catalog.schema_version,
        "identity": catalog.identity().to_dict(),
        "catalog": member,
    }


# ---- release status (RFC 0002 "Release status"; RFC 0003 "Release status, filtering") ------


def _everything(catalog: Catalog) -> dict[str, set[str]]:
    kept = {kind: set(catalog._tables.get(kind, {})) for kind in fmt.ENTITY_TABLES}
    kept["compositions"] = set(catalog.compositions)
    return kept


def _kept(catalog: Catalog) -> dict[str, set[str]]:
    """The ids the filter ships, by table: each public in itself and along its chain."""
    kept: dict[str, set[str]] = {kind: set() for kind in fmt.ENTITY_TABLES}
    kept["memory_devices"] = {d.id for d in catalog.memory_devices() if d.release_status == _PUBLIC}
    for kind in ("socs", "implementations", "parts", "boards"):
        for entry_id in catalog._tables.get(kind, {}):
            if catalog.resolve(entry_id).release_status == _PUBLIC:
                kept[kind].add(entry_id)
    for addon in catalog.addons():
        devices = set(addon.population.values())
        fits = set(addon.fits_boards) & kept["boards"]
        if addon.release_status == _PUBLIC and devices <= kept["memory_devices"] and fits:
            kept["addons"].add(addon.id)
    kept["cores"] = {
        instance.core for soc in catalog.socs() if soc.id in kept["socs"] for instance in soc.cores
    }
    kept["compositions"] = {
        alias
        for alias, c in catalog.compositions.items()
        if c.board in kept["boards"] and set(c.addons) <= kept["addons"]
    }
    return kept


def _resolvable(kept: Mapping[str, set[str]], entry_id: str) -> bool:
    return any(entry_id in kept[kind] for kind in ("socs", "implementations", "parts", "boards"))


def _scrub(kind: str, values: dict[str, Any], kept: Mapping[str, set[str]]) -> dict[str, Any]:
    """``values`` without references to entries the filter drops."""
    if kind == "socs":
        for key, table in (("default_board", "boards"), ("derives_from", "socs")):
            if key in values and values[key] not in kept[table]:
                del values[key]
    if "based_on" in values and values["based_on"] not in kept[kind]:
        del values["based_on"]
    if kind == "addons":
        values["fits_boards"] = [b for b in values["fits_boards"] if b in kept["boards"]]
    return values


# ---- entries in the file format ---------------------------------------------------------


def _entry(
    catalog: Catalog,
    kind: str,
    entry_id: str,
    decl: type,
    kept: Mapping[str, set[str]],
    *,
    provenance: bool,
) -> dict[str, Any]:
    """One entry after its ``based_on`` merge, written as the file format writes it."""
    tree = catalog._trees[(kind, entry_id)]
    values = _scrub(kind, copy.deepcopy(tree.values), kept)
    if not provenance:
        return values
    return _with_records(values, decl, (), tree.records, inherited=None)


def _with_records(  # noqa: PLR0911 (one branch per declared kind)
    value: Any, tp: Any, path: Path, records: Mapping[Path, Any], *, inherited: Any
) -> Any:
    """``value`` with each record written where it differs from the one it inherits.

    A record goes on an object as ``provenance`` and on a scalar or value list as the
    ``{value, provenance}`` form; a mapping or keyed list passes it to each item.
    """
    bare, markers = _walk.unwrap(tp)
    if fmt.NOT_FACT in markers or fmt.OPAQUE in markers:
        return value
    record = records.get(path, inherited)
    if _walk.is_scalar_like(tp):
        if isinstance(value, list) and _items_differ(value, path, records, record):
            return [  # a value list's items cannot carry records inside the list's form
                _wrap(item, records.get((*path, segment(item)), record), inherited)
                for item in value
            ]
        return _wrap(value, record, inherited)
    if _walk.is_union(bare) and isinstance(value, dict):
        bare = _pick_alternative(value, bare)
    if _walk.is_object(bare):
        declared = _walk.fields(bare)
        own = {}
        if _walk.carries_facts(bare) and record != inherited:
            own, inherited = {"provenance": copy.deepcopy(record)}, record
        return own | {
            key: _with_records(item, declared[key].type, (*path, key), records, inherited=inherited)
            for key, item in value.items()
        }
    origin = getattr(bare, "__origin__", None)
    if origin is dict:
        _, item_tp = get_args(bare)
        return {
            key: _with_records(item, item_tp, (*path, key), records, inherited=inherited)
            for key, item in value.items()
        }
    if origin is list:
        (item_tp,) = get_args(bare)
        keyed = _walk.marker(markers, fmt.Keyed)
        return [
            _with_records(
                item,
                item_tp,
                (*path, item_key(item, keyed) if keyed is not None else segment(item)),
                records,
                inherited=inherited,
            )
            for item in value
        ]
    return value


def _items_differ(items: list, path: Path, records: Mapping[Path, Any], record: Any) -> bool:
    return any(records.get((*path, segment(item)), record) != record for item in items)


def _wrap(item: Any, record: Any, inherited: Any) -> Any:
    return item if record == inherited else {"value": item, "provenance": copy.deepcopy(record)}
