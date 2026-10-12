"""The catalogue and ``load_overlay`` (RFC 0002 "helia_platforms.catalogue"; ADR 0002)."""

from __future__ import annotations

import functools
import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any

from helia_platforms import _digest, _parse, _structural, _walk, model
from helia_platforms import _format as fmt
from helia_platforms._build import build_entity
from helia_platforms._tree import (
    MergeError,
    Tree,
    expand_shorthands,
    fvp_problems,
    merge,
    normalize,
    realize,
)
from helia_platforms.errors import FormatError

#: Entity tables in load order, with the model class each builds.
_KINDS: dict[str, type] = {
    "cores": model.Core,
    "socs": model.Soc,
    "implementations": model.Implementation,
    "parts": model.Part,
    "boards": model.Board,
    "addons": model.AddOn,
    "memory_devices": model.MemoryDevice,
}
#: Kinds whose ids and aliases share the one namespace ``resolve()`` reads (section 2.3).
_RESOLVABLE = ("socs", "implementations", "parts", "boards")


def _empty() -> Mapping[Any, Any]:
    return MappingProxyType({})


@dataclass(frozen=True)
class Catalogue:
    """An immutable catalogue. ``load_overlay`` returns a new one; nothing is mutated."""

    schema_version: int = fmt.SCHEMA_VERSION
    compositions: Mapping[str, model.Composition] = field(default_factory=_empty)
    shorthands: Mapping[str, tuple[str, ...]] = field(default_factory=_empty)
    sources: Mapping[tuple[str, str], str] = field(default_factory=_empty)
    _tables: Mapping[str, Mapping[str, Any]] = field(default_factory=_empty, repr=False)
    _trees: Mapping[tuple[str, str], Tree] = field(default_factory=_empty, repr=False)

    def socs(self) -> tuple[model.Soc, ...]:
        return tuple(self._tables.get("socs", {}).values())

    def implementations(self, soc: str | None = None) -> tuple[model.Implementation, ...]:
        return tuple(
            i for i in self._tables.get("implementations", {}).values() if soc in (None, i.soc)
        )

    def parts(self, soc: str | None = None) -> tuple[model.Part, ...]:
        return tuple(p for p in self._tables.get("parts", {}).values() if soc in (None, p.soc))

    def boards(self, soc: str | None = None) -> tuple[model.Board, ...]:
        parts = self._tables.get("parts", {})
        return tuple(
            b
            for b in self._tables.get("boards", {}).values()
            if soc is None or (b.part in parts and parts[b.part].soc == soc)
        )

    def cores(self) -> tuple[model.Core, ...]:
        return tuple(self._tables.get("cores", {}).values())

    def npus(self) -> tuple[model.Npu, ...]:
        """The distinct Npu IP blocks the Socs instantiate."""
        seen: list[model.Npu] = []
        for soc in self.socs():
            for instance in soc.npus:
                if instance.npu not in seen:
                    seen.append(instance.npu)
        return tuple(seen)

    def addons(self) -> tuple[model.AddOn, ...]:
        return tuple(self._tables.get("addons", {}).values())

    def memory_devices(self) -> tuple[model.MemoryDevice, ...]:
        return tuple(self._tables.get("memory_devices", {}).values())

    @functools.cached_property
    def catalog_digest(self) -> str:
        """``sha256:<hex>`` of the built-in entries without provenance (ADR 0004 point 1).

        ADR 0004's ``catalogue_digest``; loading computes it (point 3). Entries from
        overlays and side-loaded sources are left out: ADR 0004 point 4 records those
        sources beside the digest, in ``identity()``.
        """

        def builtin(table: str, entries: Mapping[str, Any]) -> dict[str, Any]:
            return {k: v for k, v in entries.items() if self.sources.get((table, k)) == "builtin"}

        tables = {kind: builtin(kind, self._tables.get(kind, {})) for kind in _KINDS}
        # Only built-in files carry shorthands (ADR 0002 section 1).
        return _digest.catalog_digest(
            tables, builtin("compositions", self.compositions), self.shorthands
        )

    def _entry(self, kind: str, entry_id: str) -> Any:
        """One entry by table name and exact id; raises KeyError when absent."""
        return self._tables[kind][entry_id]

    def _realized(self, implementation: str) -> model.Soc:
        """The Soc as an Implementation realizes it: merged and clock-capped (``_tree.realize``)."""
        impl = self._tables["implementations"][implementation]
        tree = realize(self._trees[("socs", impl.soc)], self._trees[("implementations", impl.id)])
        return build_entity(model.Soc, fmt.Soc, tree, impl.soc)


_EMPTY = Catalogue()


def load_overlay(
    source: str | os.PathLike[str] | Mapping[str, Any], *, base: Catalogue | None = None
) -> Catalogue:
    """Load an overlay file or mapping over ``base`` and return a new catalogue.

    A mapping may omit ``schema_version`` (ADR 0002 section 2.2). Raises
    ``FormatError`` listing every problem found.
    """
    if isinstance(source, Mapping):
        data, origin, require = dict(source), "<mapping>", False
    else:
        path = Path(source)
        data, origin, require = _parse.parse_file(path), str(path), True
    return _load_documents([(data, origin)], base=base, builtin=False, require_version=require)


def _load_documents(
    documents: Iterable[tuple[Any, str]],
    *,
    base: Catalogue | None = None,
    builtin: bool,
    require_version: bool = True,
) -> Catalogue:
    """Load parsed documents as one source over ``base``."""
    base = base or _EMPTY
    problems: list[str] = []
    merged: dict[str, dict[str, tuple[Any, str]]] = {}
    compositions: dict[str, tuple[Any, str]] = {}
    shorthands: dict[str, tuple[Any, str]] = {}
    for data, origin in documents:
        found = _structural.check_document(data, origin, require_version=require_version)
        if found:
            problems += found
            continue
        for key, table in data.items():
            if key in fmt.BUILTIN_ONLY_KEYS and not builtin:
                problems.append(f"{origin}: {key}: only built-in files may carry {key!r}")
                continue
            target = (
                merged.setdefault(key, {})
                if key in _KINDS
                else compositions
                if key == "compositions"
                else shorthands
                if key == "shorthands"
                else None
            )
            if target is None:
                continue
            for entry_id, entry in table.items():
                if entry_id in target:
                    problems.append(f"{origin}: {key}.{entry_id}: defined twice")
                target[entry_id] = (entry, origin)
    if problems:
        raise FormatError("invalid catalogue", tuple(problems))
    loader = _Loader(base, builtin)
    return loader.load(merged, compositions, shorthands)


class _Loader:
    def __init__(self, base: Catalogue, builtin: bool) -> None:
        self.base = base
        self.builtin = builtin
        self.problems: list[str] = []
        self.trees: dict[tuple[str, str], Tree] = dict(base._trees)
        self.tables: dict[str, dict[str, Any]] = {k: dict(v) for k, v in base._tables.items()}
        self.sources: dict[tuple[str, str], str] = dict(base.sources)
        self.resolved: dict[tuple[str, str], Tree | None] = {}

    def fail(self, origin: str, where: str, message: str) -> None:
        self.problems.append(f"{origin}: {where}: {message}")

    def load(self, entries: dict, compositions: dict, shorthands: dict) -> Catalogue:
        self.check_names(entries, compositions, shorthands)
        new: dict[tuple[str, str], tuple[Tree, str]] = {}
        for kind in _KINDS:
            for entry_id, (_, origin) in entries.get(kind, {}).items():
                tree = self.tree(kind, entry_id, entries)
                if tree is not None:
                    new[(kind, entry_id)] = (tree, origin)
                    self.trees[(kind, entry_id)] = tree
        for (kind, entry_id), (tree, origin) in new.items():
            self.finish(kind, entry_id, tree, origin)
        if self.problems:
            raise FormatError("invalid catalogue", tuple(self.problems))
        built_compositions = dict(self.base.compositions)
        for alias, (raw, origin) in compositions.items():
            built_compositions[alias] = model.Composition(
                alias=alias, board=raw["board"], addons=tuple(raw.get("addons", ()))
            )
            self.sources[("compositions", alias)] = self.label(origin)
        built_shorthands = dict(self.base.shorthands)
        for name, (members, _) in shorthands.items():
            built_shorthands[name] = tuple(members)
        catalogue = Catalogue(
            compositions=MappingProxyType(built_compositions),
            shorthands=MappingProxyType(built_shorthands),
            sources=MappingProxyType(self.sources),
            _tables=MappingProxyType({k: MappingProxyType(v) for k, v in self.tables.items()}),
            _trees=MappingProxyType(self.trees),
        )
        self.check_references(catalogue, entries, compositions, shorthands)
        if self.problems:
            raise FormatError("invalid catalogue", tuple(self.problems))
        catalogue.catalog_digest  # noqa: B018 (computed at load, ADR 0004 point 3)
        return catalogue

    def label(self, origin: str) -> str:
        return "builtin" if self.builtin else f"overlay:{origin}"

    # -- names (section 2.3; RFC 0002 P5) ------------------------------------------

    def check_names(self, entries: dict, compositions: dict, shorthands: dict) -> None:
        def names_of(kind: str, entry_id: str, raw: dict) -> list[str]:
            return [entry_id, *[_plain(a) for a in raw.get("aliases", [])]]

        spaces: dict[str, list[tuple[str, str, str]]] = {}
        for kind, table in entries.items():
            space = "resolvable" if kind in _RESOLVABLE else kind
            for entry_id, (raw, origin) in table.items():
                for name in names_of(kind, entry_id, raw):
                    spaces.setdefault(space, []).append((name, f"{kind}.{entry_id}", origin))
        for alias, (_, origin) in compositions.items():
            spaces.setdefault("resolvable", []).append((alias, f"compositions.{alias}", origin))
        for name, (_, origin) in shorthands.items():
            spaces.setdefault("resolvable", []).append((name, f"shorthands.{name}", origin))
        existing = self.base_names()
        for space, names in spaces.items():
            seen: dict[str, str] = {}
            for name, where, origin in names:
                folded = name.casefold()
                if folded in seen and seen[folded] != where:
                    self.fail(origin, where, f"{name!r} is already used by {seen[folded]}")
                seen[folded] = where
                if folded in existing.get(space, {}):
                    self.fail(origin, where, f"{name!r} would shadow {existing[space][folded]}")

    def base_names(self) -> dict[str, dict[str, str]]:
        spaces: dict[str, dict[str, str]] = {}
        for kind, table in self.base._tables.items():
            space = "resolvable" if kind in _RESOLVABLE else kind
            for entry_id, entry in table.items():
                for name in (entry_id, *getattr(entry, "aliases", ())):
                    spaces.setdefault(space, {})[name.casefold()] = f"{kind}.{entry_id}"
        for alias in self.base.compositions:
            spaces.setdefault("resolvable", {})[alias.casefold()] = f"compositions.{alias}"
        for name in self.base.shorthands:
            spaces.setdefault("resolvable", {})[name.casefold()] = f"shorthands.{name}"
        return spaces

    # -- trees and merges ------------------------------------------------------------

    def tree(self, kind: str, entry_id: str, entries: dict, chain: tuple = ()) -> Tree | None:
        """The merged tree of one entry, resolving ``based_on`` within this load or the base."""
        key = (kind, entry_id)
        if key in self.resolved:
            return self.resolved[key]
        if entry_id not in entries.get(kind, {}):
            return self.trees.get(key)
        raw, origin = entries[kind][entry_id]
        where = f"{kind}.{entry_id}"
        decl = fmt.ENTITY_TABLES[kind]
        own = normalize(raw, decl, None if self.builtin else {"status": "unverified"})
        based_on = raw.get("based_on")
        result: Tree | None = own
        if based_on is None:
            deltas = [n for n in raw if n.endswith(("_removed", "_resized", "_rebased"))]
            for name in deltas:
                self.fail(origin, f"{where}.{name}", "a delta needs a based_on entry")
            expanded = self.expand(kind, own, own, origin, where)
            result = own if expanded and not deltas else None
        elif self.builtin:
            self.fail(origin, f"{where}.based_on", "built-in entries may not use based_on")
            result = None
        elif key in chain or based_on == entry_id:
            self.fail(origin, f"{where}.based_on", f"based_on forms a cycle at {based_on!r}")
            result = None
        else:
            base_tree = self.tree(kind, based_on, entries, (*chain, key))
            if base_tree is None:
                if not self.failed((kind, based_on)):
                    self.fail(origin, f"{where}.based_on", f"no {kind} entry {based_on!r}")
                result = None
            else:
                try:
                    expanded = self.expand(kind, own, merge(base_tree, own, decl), origin, where)
                    result = merge(base_tree, own, decl) if expanded else None
                except MergeError as exc:
                    for problem in exc.problems:
                        self.fail(origin, where, problem)
                    result = None
        self.resolved[key] = result
        return result

    def failed(self, key: tuple[str, str]) -> bool:
        """True for an entry of this load whose tree failed; its problems are reported."""
        return key in self.resolved and self.resolved[key] is None

    def expand(self, kind: str, own: Tree, merged: Tree, origin: str, where: str) -> bool:
        """Expand ``own``'s shorthands before any merge, as if it wrote the long forms.

        ``merged`` is the entry over its base, which supplies core 0, npu 0 and the
        Soc of an Implementation when ``own`` does not write them. Returns False
        when the shorthands cannot be expanded, so the entry must not be built.
        """
        if kind == "socs":
            soc_values = merged.values
        elif kind == "implementations":
            soc = merged.values["soc"]
            soc_tree = self.trees.get(("socs", soc))
            if soc_tree is None:
                if not self.failed(("socs", soc)):
                    self.fail(origin, where, f"no soc {soc!r}")
                return False
            soc_values = soc_tree.values
        else:
            return True
        problems = expand_shorthands(own, soc_values)
        for problem in problems:
            self.fail(origin, where, problem)
        return not problems

    def finish(self, kind: str, entry_id: str, tree: Tree, origin: str) -> None:
        where = f"{kind}.{entry_id}"
        decl = fmt.ENTITY_TABLES[kind]
        missing = [n for n, f in _fields(decl).items() if f.required and n not in tree.values]
        for name in missing:
            self.fail(origin, where, f"missing required key {name!r} after based_on")
        if missing:
            return
        if self.builtin:
            self.check_builtin(kind, where, tree, origin)
        try:
            entity = build_entity(_KINDS[kind], decl, tree, entry_id)
        except FormatError as exc:
            self.fail(origin, where, str(exc))
            return
        self.tables.setdefault(kind, {})[entry_id] = entity
        self.sources[(kind, entry_id)] = self.label(origin)

    def check_builtin(self, kind: str, where: str, tree: Tree, origin: str) -> None:
        values = tree.values
        if kind != "cores" and values.get("release_status") != "public":
            self.fail(origin, where, "a built-in entry must write release_status: public")
        if "extensions" in values:
            self.fail(origin, where, "built-in entries may not carry extensions")
        for name, region in (values.get("memories") or {}).items():
            if "base" not in region:
                self.fail(origin, f"{where}.memories.{name}", "a built-in region needs a base")
        for path, record in tree.records.items():
            if record is None:
                self.fail(origin, ".".join((where, *path)), "this fact has no provenance record")

    # -- references, checked after the merge (section 2.5) ---------------------------

    def check_references(
        self, catalogue: Catalogue, entries: dict, compositions: dict, shorthands: dict
    ) -> None:
        checks = {
            "socs": self.check_soc,
            "implementations": self.check_implementation,
            "parts": self.check_part,
            "boards": self.check_board,
            "addons": self.check_addon,
        }
        for kind, check in checks.items():
            for entry_id, (_, origin) in entries.get(kind, {}).items():
                entity = catalogue._tables.get(kind, {}).get(entry_id)
                if entity is not None:
                    check(catalogue, entity, origin)
        boards = catalogue._tables.get("boards", {})
        addons = catalogue._tables.get("addons", {})
        for alias, (raw, origin) in compositions.items():
            if raw["board"] not in boards:
                self.fail(origin, f"compositions.{alias}", f"no board {raw['board']!r}")
            for addon in raw.get("addons", []):
                if addon not in addons:
                    self.fail(origin, f"compositions.{alias}", f"no add-on {addon!r}")
        resolvable = {name for kind in _RESOLVABLE for name in catalogue._tables.get(kind, {})}
        for name, (members, origin) in shorthands.items():
            for member in members:
                if member not in resolvable:
                    self.fail(origin, f"shorthands.{name}", f"no entry {member!r}")

    def check_soc(self, catalogue: Catalogue, soc: model.Soc, origin: str) -> None:
        where = f"socs.{soc.id}"
        for problem in _soc_reference_problems(soc, catalogue):
            self.fail(origin, where, problem)
        for region in soc.memories:
            if region.stands_in_for:
                self.fail(
                    origin,
                    f"{where}.memories.{region.name}.stands_in_for",
                    "only a region of an fvp Implementation may stand in for others",
                )

    def check_implementation(
        self, catalogue: Catalogue, impl: model.Implementation, origin: str
    ) -> None:
        where = f"implementations.{impl.id}"
        if impl.soc not in catalogue._tables.get("socs", {}):
            self.fail(origin, where, f"no soc {impl.soc!r}")
            return
        trees = catalogue._trees
        own = fvp_problems(
            trees[("socs", impl.soc)].values, trees[("implementations", impl.id)].values
        )
        for problem in own:
            self.fail(origin, where, problem)
        if own:
            return  # realizing raises the same problems
        try:
            realized = catalogue._realized(impl.id)
        except MergeError as exc:
            for problem in exc.problems:
                self.fail(origin, f"{where}.subset", problem)
            return
        for problem in _soc_reference_problems(realized, catalogue):
            self.fail(origin, where, f"as realized: {problem}")
        if impl.provisioning is not None and impl.provisioning not in realized.boot_configs:
            self.fail(origin, where, f"provisioning {impl.provisioning!r} is not a boot config")
        self.check_population(catalogue, impl.interfaces, impl.population, where, origin)

    def check_part(self, catalogue: Catalogue, part: model.Part, origin: str) -> None:
        where = f"parts.{part.id}"
        socs = catalogue._tables.get("socs", {})
        if part.soc not in socs:
            self.fail(origin, where, f"no soc {part.soc!r}")
            return
        soc = socs[part.soc]
        if part.implementation is not None:
            impl = catalogue._tables.get("implementations", {}).get(part.implementation)
            if impl is None or impl.soc != part.soc:
                self.fail(origin, where, f"no implementation {part.implementation!r} of {soc.id}")
            else:
                try:
                    soc = catalogue._realized(impl.id)  # slots name what the Implementation keeps
                except MergeError:
                    return  # reported against the implementation
        cores = {c.id for c in soc.cores}
        regions = {r.name for r in soc.memories}
        for name, slot in part.image_slots.items():
            if slot.core not in cores:
                self.fail(origin, f"{where}.image_slots.{name}", f"no core {slot.core!r}")
            if slot.region not in regions:
                self.fail(origin, f"{where}.image_slots.{name}", f"no region {slot.region!r}")

    def check_board(self, catalogue: Catalogue, board: model.Board, origin: str) -> None:
        where = f"boards.{board.id}"
        part = catalogue._tables.get("parts", {}).get(board.part)
        if part is None:
            self.fail(origin, where, f"no part {board.part!r}")
            return
        if board.provisioning is not None and part.soc in catalogue._tables.get("socs", {}):
            try:
                soc = (
                    catalogue._realized(part.implementation)
                    if part.implementation
                    else catalogue._tables["socs"][part.soc]
                )
            except (KeyError, MergeError):
                return  # reported against the part or the implementation
            if board.provisioning not in soc.boot_configs:
                self.fail(
                    origin, where, f"provisioning {board.provisioning!r} is not a boot config"
                )
        self.check_population(catalogue, board.interfaces, board.population, where, origin)

    def check_addon(self, catalogue: Catalogue, addon: model.AddOn, origin: str) -> None:
        where = f"addons.{addon.id}"
        boards = catalogue._tables.get("boards", {})
        for board in addon.fits_boards:
            if board not in boards:
                self.fail(origin, f"{where}.fits_boards", f"no board {board!r}")
        for interface in addon.population:
            if interface not in addon.occupies:
                self.fail(origin, f"{where}.population", f"{interface!r} is not in occupies")
        self.check_population(catalogue, None, addon.population, where, origin)

    def check_population(
        self,
        catalogue: Catalogue,
        interfaces: Mapping[str, Any] | None,
        population: Mapping[str, str],
        where: str,
        origin: str,
    ) -> None:
        devices = catalogue._tables.get("memory_devices", {})
        for interface, device in population.items():
            if interfaces is not None and interface not in interfaces:
                self.fail(origin, f"{where}.population", f"no interface {interface!r}")
            if device not in devices:
                self.fail(origin, f"{where}.population", f"no memory device {device!r}")


def _soc_reference_problems(soc: model.Soc, catalogue: Catalogue) -> list[str]:
    """References inside one Soc that do not resolve (ADR 0002 section 2.5; RFC 0002)."""
    return [
        *_unit_problems(soc, catalogue),
        *_clock_problems(soc),
        *_boot_problems(soc),
        *_access_problems(soc),
        *_relation_problems(soc, catalogue),
    ]


def _unit_problems(soc: model.Soc, catalogue: Catalogue) -> list[str]:
    problems: list[str] = []
    domains = {d.id for d in soc.clock_domains}
    cores = {c.id for c in soc.cores}
    known_cores = catalogue._tables.get("cores", {})
    if soc.cores and soc.cores[0].role != "application":
        problems.append(f"core 0 ({soc.cores[0].id}) must have role application")
    for core in soc.cores:
        if core.core not in known_cores:
            problems.append(f"cores.{core.id}.core: no core IP {core.core!r}")
        if core.clock_domain not in domains:
            problems.append(f"cores.{core.id}.clock_domain: no domain {core.clock_domain!r}")
    for unit in (*soc.npus, *soc.accelerators):
        if unit.driven_by not in cores:
            problems.append(f"{unit.id}.driven_by: no core {unit.driven_by!r}")
        if unit.clock_domain not in domains:
            problems.append(f"{unit.id}.clock_domain: no domain {unit.clock_domain!r}")
    return problems


def _clock_problems(soc: model.Soc) -> list[str]:
    problems: list[str] = []
    domains = {d.id: {p.name for p in d.points} for d in soc.clock_domains}
    for point in soc.operating_points:
        if not point.domains:
            problems.append(f"operating_points.{point.name}: names no domain point")
        for domain, name in point.domains.items():
            if domain not in domains:
                problems.append(f"operating_points.{point.name}: no domain {domain!r}")
            elif name not in domains[domain]:
                problems.append(f"operating_points.{point.name}: no point {domain}.{name}")
    points = {p.name for p in soc.operating_points}
    if soc.default_operating_point is not None and soc.default_operating_point not in points:
        problems.append(f"default_operating_point: no point {soc.default_operating_point!r}")
    return problems


def _boot_problems(soc: model.Soc) -> list[str]:
    problems: list[str] = []
    cores = {c.id for c in soc.cores}
    regions = {r.name for r in soc.memories}
    if soc.default_boot is not None and soc.default_boot not in soc.boot_configs:
        problems.append(f"default_boot: no boot config {soc.default_boot!r}")
    for name, config in soc.boot_configs.items():
        for core, start in config.app_start.items():
            if core not in cores:
                problems.append(f"boot_configs.{name}.app_start: no core {core!r}")
            if start.region not in regions:
                problems.append(f"boot_configs.{name}.app_start: no region {start.region!r}")
        problems.extend(
            f"boot_configs.{name}.reserved.{r.purpose}: no region {r.region!r}"
            for r in config.reserved
            if r.region not in regions
        )
    return problems


def _access_problems(soc: model.Soc) -> list[str]:
    problems: list[str] = []
    cores = {c.id for c in soc.cores}
    masters = cores | {n.id for n in soc.npus} | {a.id for a in soc.accelerators}
    targets = {r.name for r in soc.memories} | set(soc.peripherals)
    for entry in soc.access:
        if entry.master not in masters:
            problems.append(f"access {entry.master}@{entry.target}: no master {entry.master!r}")
        if entry.target not in targets:
            problems.append(f"access {entry.master}@{entry.target}: no target {entry.target!r}")
    if soc.default_access is not None and soc.default_access.master not in cores:
        problems.append(f"default_access.master: no core {soc.default_access.master!r}")
    return problems


def _relation_problems(soc: model.Soc, catalogue: Catalogue) -> list[str]:
    problems: list[str] = []
    if soc.derives_from is not None and soc.derives_from not in catalogue._tables.get("socs", {}):
        problems.append(f"derives_from: no soc {soc.derives_from!r}")
    boards = catalogue._tables.get("boards", {})
    if soc.default_board is not None and soc.default_board not in boards:
        problems.append(f"default_board: no board {soc.default_board!r}")
    return problems


def _plain(value: Any) -> Any:
    return value["value"] if isinstance(value, dict) and "value" in value else value


def _fields(decl: type) -> dict:
    return _walk.fields(decl)
