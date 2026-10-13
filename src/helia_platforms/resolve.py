"""Resolve a name to a ``Target`` (RFC 0002 "helia_platforms.resolve", "Resolution and naming")."""

from __future__ import annotations

import difflib
import warnings
from collections.abc import Mapping, Sequence

from helia_platforms import model
from helia_platforms.catalog import Catalog, _placement_problems, builtin
from helia_platforms.errors import (
    AmbiguousPlatform,
    PlatformError,
    PlatformWarning,
    UnknownPlatform,
)
from helia_platforms.target import Kind, Target

#: Resolvable tables, with the kind of target each entry resolves to.
_KIND_OF: dict[str, Kind] = {
    "boards": "board",
    "parts": "part",
    "implementations": "implementation",
    "socs": "soc",
}
_EMBARGOED: model.ReleaseStatus = "embargoed"


def resolve(
    name: str,
    *,
    addons: Sequence[str] = (),
    boot: str | None = None,
    catalog: Catalog | None = None,
) -> Target:
    """Resolve a board, part, implementation or Soc id, a composition alias or an alias.

    Case-insensitive. A Soc id resolves to the bare Soc, never to a board. A shorthand
    raises ``AmbiguousPlatform``; anything else unknown raises ``UnknownPlatform``.
    """
    catalog = catalog if catalog is not None else builtin()
    found = _names(catalog).get(name.casefold())
    if found is None:
        raise UnknownPlatform(name, suggest(name, catalog=catalog))
    table, entry_id, _ = found
    if table == "shorthands":
        raise AmbiguousPlatform(name, catalog.shorthands[entry_id])
    composed: tuple[str, ...] = ()
    if table == "compositions":
        composition = catalog.compositions[entry_id]
        table, entry_id, composed = "boards", composition.board, composition.addons
    return _target(catalog, table, entry_id, (*composed, *addons), boot, via=name)


def resolve_board(name: str, *, catalog: Catalog | None = None) -> model.Board:
    """A board by id or alias; a Soc id gives its ``default_board`` (the only use of it)."""
    catalog = catalog if catalog is not None else builtin()
    found = _names(catalog).get(name.casefold())
    if found is not None and found[0] == "socs":
        soc = catalog._entry("socs", found[1])
        if soc.default_board is None:
            raise PlatformError(f"Soc {soc.id!r} names no default_board")
        return catalog._entry("boards", soc.default_board)
    if found is not None and found[0] == "compositions":
        return catalog._entry("boards", catalog.compositions[found[1]].board)
    if found is None or found[0] != "boards":
        raise UnknownPlatform(name, suggest(name, catalog=catalog), what="board")
    return catalog._entry("boards", found[1])


def resolve_soc(name: str, *, catalog: Catalog | None = None) -> model.Soc:
    """The Soc a name resolves to, as its implementation (if any) realizes it."""
    return resolve(name, catalog=catalog).soc


def suggest(name: str, *, catalog: Catalog | None = None) -> tuple[str, ...]:
    """Resolvable names close to ``name``, best first."""
    catalog = catalog if catalog is not None else builtin()
    names = _names(catalog)
    close = difflib.get_close_matches(name.casefold(), list(names), n=5, cutoff=0.6)
    return tuple(names[c][2] for c in close)


def find(catalog: Catalog, **predicates: str) -> tuple[Target, ...]:
    """Targets of every resolvable entry that match all ``predicates`` (see ``Catalog.find``)."""
    tests = {
        "core": lambda t, v: t.core.id == v,
        "npu_model": lambda t, v: t.npu is not None and t.npu.npu.model == v,
        "has_region": lambda t, v: t.has_region(v),
        "kind": lambda t, v: t.kind == v,
    }
    unknown = set(predicates) - set(tests)
    if unknown:
        raise TypeError(f"unknown predicates {sorted(unknown)}; use {sorted(tests)}")
    found = []
    for table in _KIND_OF:
        for entry_id in catalog._tables.get(table, {}):
            target = _target(catalog, table, entry_id, (), None, via=entry_id)
            if all(tests[k](target, v) for k, v in predicates.items()):
                found.append(target)
    return tuple(found)


def _target(
    catalog: Catalog,
    table: str,
    entry_id: str,
    addon_ids: Sequence[str],
    boot: str | None,
    *,
    via: str,
) -> Target:
    kind = _KIND_OF[table]
    entry = catalog._entry(table, entry_id)
    board = entry if kind == "board" else None
    part = catalog._entry("parts", board.part) if board else entry if kind == "part" else None
    impl_id = (
        entry_id if kind == "implementation" else part.implementation if part is not None else None
    )
    implementation = catalog._entry("implementations", impl_id) if impl_id else None
    soc_id = implementation.soc if implementation else part.soc if part else entry_id
    soc = catalog._realized(impl_id) if impl_id else catalog._entry("socs", soc_id)
    addons = _addons(catalog, board, addon_ids)
    devices = _devices(catalog, board, implementation, addons)
    chain = [e for e in (board, part, implementation, catalog._entry("socs", soc_id)) if e]
    chain += [*addons, *(device for _, device in devices)]
    status = _EMBARGOED if any(e.release_status == _EMBARGOED for e in chain) else "public"
    origin = "builtin" if catalog.sources.get((table, entry_id)) == "builtin" else "overlay"
    aliases = tuple(getattr(entry, "aliases", ()))
    if via.casefold() in {c.casefold() for c in catalog.compositions}:
        aliases += (via,)
    return Target(
        id=entry_id,
        kind=kind,
        soc=soc,
        implementation=implementation,
        part=part,
        board=board,
        origin=origin,
        release_status=status,
        addons=addons,
        aliases=aliases,
        boot=_select_boot(soc, board, implementation, boot, entry_id),
        _catalog=catalog,
        _devices=devices,
    )


def _addons(
    catalog: Catalog, board: model.Board | None, addon_ids: Sequence[str]
) -> tuple[model.AddOn, ...]:
    if not addon_ids:
        return ()
    if board is None:
        raise PlatformError("addons= applies only to a board target")
    known = {a.id.casefold(): a for a in catalog.addons()}
    for alias_owner in catalog.addons():
        known |= {a.casefold(): alias_owner for a in alias_owner.aliases}
    missing = [a for a in addon_ids if a.casefold() not in known]
    if missing:
        raise PlatformError(f"no add-on {missing[0]!r}")
    addons = tuple({known[a.casefold()].id: known[a.casefold()] for a in addon_ids}.values())
    problems = _placement_problems(board, addons)
    if problems:
        raise PlatformError("; ".join(problems))
    return addons


def _devices(
    catalog: Catalog,
    board: model.Board | None,
    implementation: model.Implementation | None,
    addons: tuple[model.AddOn, ...],
) -> tuple[tuple[model.MemoryInterface, model.MemoryDevice], ...]:
    """(interface, device) for each population: the implementation's, the board's, then add-ons'."""
    populations: list[tuple[Mapping[str, model.MemoryInterface], Mapping[str, str]]] = []
    if implementation is not None:
        populations.append((implementation.interfaces, implementation.population))
    if board is not None:
        populations.append((board.interfaces, board.population))
        populations += [(board.interfaces, addon.population) for addon in addons]
    return tuple(
        (interfaces[name], catalog._entry("memory_devices", device_id))
        for interfaces, population in populations
        for name, device_id in population.items()
    )


def _select_boot(
    soc: model.Soc,
    board: model.Board | None,
    implementation: model.Implementation | None,
    boot: str | None,
    entry_id: str,
) -> model.BootConfig | None:
    """``boot=``, else the board's provisioning, else the implementation's, else the default."""
    provisioned = next(
        (o.provisioning for o in (board, implementation) if o is not None and o.provisioning),
        None,
    )
    if boot is not None:
        if boot not in soc.boot_configs:
            raise PlatformError(f"{entry_id} has no boot configuration {boot!r}")
        if board is not None and board.provisioning not in (None, boot):
            warnings.warn(
                f"{entry_id}: boot {boot!r} differs from the board's provisioning "
                f"{board.provisioning!r}",
                PlatformWarning,
                stacklevel=4,
            )
        return soc.boot_configs[boot]
    name = provisioned or soc.default_boot
    return soc.boot_configs.get(name) if name else None


def _names(catalog: Catalog) -> dict[str, tuple[str, str, str]]:
    """Each resolvable name, casefolded, to its (table, id, spelling as written)."""
    found: dict[str, tuple[str, str, str]] = {}
    for table in _KIND_OF:
        for entry_id, entry in catalog._tables.get(table, {}).items():
            for name in (entry_id, *entry.aliases):
                found[name.casefold()] = (table, entry_id, name)
    for alias in catalog.compositions:
        found[alias.casefold()] = ("compositions", alias, alias)
    for shorthand in catalog.shorthands:
        found[shorthand.casefold()] = ("shorthands", shorthand, shorthand)
    return found
