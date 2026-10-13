"""The catalog and ``load_overlay`` (RFC 0002 "helia_platforms.catalog"; ADR 0002)."""

from __future__ import annotations

import dataclasses
import functools
import os
import threading
import warnings
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from importlib import resources
from importlib.metadata import entry_points
from importlib.resources.abc import Traversable
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from helia_platforms import __version__, _digest, _parse, _structural, _walk, model
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
from helia_platforms.errors import FormatError, PlatformError, PlatformWarning

if TYPE_CHECKING:
    from helia_platforms.target import Target

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
#: Where ``builtin()`` side-loads private catalogs from (RFC 0002 private silicon).
_ENTRY_POINT_GROUP = "helia_platforms.catalogs"
_PATH_VARIABLE = "HELIA_PLATFORMS_PATH"


def _empty() -> Mapping[Any, Any]:
    return MappingProxyType({})


@dataclass(frozen=True)
class SourceIdentity:
    """One source applied on top of the built-in data (ADR 0004 point 4).

    ``label`` has no directory. ``schema_version`` is the version the source was read
    at: the one it declares, or the current one for a mapping that omits it.
    """

    label: str
    schema_version: int
    sha256: str
    distribution_version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class CatalogIdentity:
    """What a consumer output records about the catalog it used (ADR 0004 point 4)."""

    package_version: str
    schema_version: int
    catalog_digest: str
    sources: tuple[SourceIdentity, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "package_version": self.package_version,
            "schema_version": self.schema_version,
            "catalog_digest": self.catalog_digest,
            "sources": [source.to_dict() for source in self.sources],
        }


@dataclass(frozen=True)
class Catalog:
    """An immutable catalog. ``load_overlay`` returns a new one; nothing is mutated."""

    schema_version: int = fmt.SCHEMA_VERSION
    compositions: Mapping[str, model.Composition] = field(default_factory=_empty)
    shorthands: Mapping[str, tuple[str, ...]] = field(default_factory=_empty)
    sources: Mapping[tuple[str, str], str] = field(default_factory=_empty)
    _tables: Mapping[str, Mapping[str, Any]] = field(default_factory=_empty, repr=False)
    _trees: Mapping[tuple[str, str], Tree] = field(default_factory=_empty, repr=False)
    _applied: tuple[SourceIdentity, ...] = field(default=(), repr=False)

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

        ADR 0004's ``catalogue_digest`` (ADR 0009); loading computes it (point 3). Entries from
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

    def resolve(self, name: str, *, addons: Sequence[str] = (), boot: str | None = None) -> Target:
        """``helia_platforms.resolve.resolve`` against this catalog."""
        from helia_platforms.resolve import _resolve  # noqa: PLC0415 (resolve imports this module)

        return _resolve(name, addons, boot, self)

    def suggest(self, name: str) -> tuple[str, ...]:
        """Resolvable names close to ``name``, best first."""
        from helia_platforms.resolve import suggest  # noqa: PLC0415 (resolve imports this module)

        return suggest(name, catalog=self)

    def find(self, **predicates: str) -> tuple[Target, ...]:
        """Every board, part, implementation and Soc target matching all ``predicates``.

        Predicates: ``core`` (core 0's IP id), ``npu_model``, ``has_region`` (a region
        name) and ``kind``.
        """
        from helia_platforms.resolve import find  # noqa: PLC0415 (resolve imports this module)

        return find(self, **predicates)

    def identity(self) -> CatalogIdentity:
        """The package and schema versions, the digest and each applied source, in order."""
        return CatalogIdentity(
            package_version=__version__,
            schema_version=self.schema_version,
            catalog_digest=self.catalog_digest,
            sources=self._applied,
        )

    def _entry(self, kind: str, entry_id: str) -> Any:
        """One entry by table name and exact id; raises KeyError when absent."""
        return self._tables[kind][entry_id]

    def _realized(self, implementation: str) -> model.Soc:
        """The Soc as an Implementation realizes it: merged and clock-capped (``_tree.realize``)."""
        impl = self._tables["implementations"][implementation]
        tree = realize(self._trees[("socs", impl.soc)], self._trees[("implementations", impl.id)])
        return build_entity(model.Soc, fmt.Soc, tree, impl.soc)


_EMPTY = Catalog()
_CACHE: dict[bool, Catalog] = {}
#: Held while a catalog loads, so a concurrent first call waits for it. Only the
#: thread holding it adds to ``_LOADING``, so a key found there means recursion.
_LOCK = threading.RLock()
_LOADING: set[bool] = set()


def builtin(include_plugins: bool = True) -> Catalog:
    """The built-in catalog, cached per ``include_plugins`` value.

    With ``include_plugins``, entry points in ``helia_platforms.catalogs``, then
    files in ``HELIA_PLATFORMS_PATH``, each load as an overlay on the catalog so
    far. Discovery runs at the first call; a failing source raises ``PlatformError``,
    as does a source that calls ``builtin()`` while it is being loaded.
    """
    key = bool(include_plugins)
    if key not in _CACHE:
        with _LOCK:
            if key in _LOADING:
                raise PlatformError("builtin() was called while the catalog was being loaded")
            if key not in _CACHE:  # another thread may have loaded it while this one waited
                _LOADING.add(key)
                try:
                    _CACHE[key] = _build(key)
                finally:
                    _LOADING.discard(key)
    return _CACHE[key]


def _build(include_plugins: bool) -> Catalog:
    if not include_plugins:
        return _load_documents(_data_documents(_data_root()), builtin=True)
    catalog = builtin(include_plugins=False)
    for label, origin, data, version in _side_loaded():
        catalog = _load_documents(
            [(data, origin)],
            base=catalog,
            builtin=False,
            require_version=True,
            source=label,
            distribution_version=version,
        )
    return catalog


def _data_root() -> Traversable:
    return resources.files("helia_platforms") / "data"


def _data_documents(root: Traversable) -> list[tuple[Any, str]]:
    """Parse every ``*.yaml`` file under ``root``, in path order (ADR 0002 section 1)."""
    found: list[tuple[str, Traversable]] = []
    pending = [(root, "")]
    while pending:
        node, prefix = pending.pop()
        for child in node.iterdir():
            if child.is_dir():
                pending.append((child, f"{prefix}{child.name}/"))
            elif child.name.endswith(".yaml"):
                found.append((f"{prefix}{child.name}", child))
    documents = []
    for name, file in sorted(found, key=lambda item: item[0]):
        origin = f"helia_platforms/data/{name}"
        try:
            text = file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise FormatError(f"{origin}: cannot be read: {exc}") from None
        documents.append((_parse.parse_yaml(text, origin), origin))
    return documents


def _side_loaded() -> Iterator[tuple[str, str, Any, str | None]]:
    """Yield (label, origin, data, distribution version) for each side-loaded source, in order.

    Every source declares ``schema_version``, a returned mapping included (ADR 0002 section 2.2).
    """
    found = entry_points(group=_ENTRY_POINT_GROUP)
    for entry in sorted(found, key=lambda e: (e.dist.name if e.dist else "", e.name)):
        label = f"entry_point:{entry.dist.name if entry.dist else '<unknown>'}"
        version = entry.dist.version if entry.dist else None
        try:
            result = entry.load()()
        except Exception as exc:
            raise PlatformError(f"{label}: entry point {entry.name!r} raised {exc!r}") from exc
        if isinstance(result, Mapping):
            yield label, f"{label} ({entry.name})", dict(result), version
        elif isinstance(result, str | os.PathLike):
            origin = f"{label} ({result})"
            yield label, origin, _parse.parse_file(Path(result), origin), version
        else:
            raise PlatformError(
                f"{label}: entry point {entry.name!r} returned {type(result).__name__}, "
                "not a mapping or a path"
            )
    for item in os.environ.get(_PATH_VARIABLE, "").split(os.pathsep):
        if not item:
            continue
        for file in _environment_files(Path(item)):
            label = f"env:{file}"
            yield label, label, _parse.parse_file(file, label), None


def _environment_files(path: Path) -> list[Path]:
    """A ``HELIA_PLATFORMS_PATH`` item: a directory's ``*.yaml`` files, or the path itself."""
    if not path.is_dir():
        return [path]
    try:
        return sorted(child for child in path.iterdir() if child.name.endswith(".yaml"))
    except OSError as exc:  # Path.glob would hide an unreadable directory
        raise FormatError(f"env:{path}: cannot be read: {exc}") from None


def load_overlay(
    source: str | os.PathLike[str] | Mapping[str, Any], *, base: Catalog | None = None
) -> Catalog:
    """Load an overlay file or mapping over ``base`` and return a new catalog.

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
    base: Catalog | None = None,
    builtin: bool,
    require_version: bool = True,
    source: str | None = None,
    distribution_version: str | None = None,
) -> Catalog:
    """Load parsed documents as one source over ``base``.

    ``source`` is the label of every entry loaded; by default it is ``builtin``
    or ``overlay:<origin>``. Each non-built-in document is recorded for ``identity()``.
    """
    base = base or _EMPTY
    documents = list(documents)  # read twice: checked, then recorded
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
        raise FormatError("invalid catalog", tuple(problems))
    applied = base._applied
    if not builtin:
        applied += tuple(
            SourceIdentity(
                label=_public_label(source or f"overlay:{origin}"),
                schema_version=_digest.read_version(data),
                sha256=_digest.source_sha256(data),
                distribution_version=distribution_version,
            )
            for data, origin in documents
        )
    loader = _Loader(base, builtin, source, applied)
    return loader.load(merged, compositions, shorthands)


def _public_label(label: str) -> str:
    """``label`` with any directory removed, so a shared record names no local path."""
    kind, _, where = label.partition(":")
    return f"{kind}:{Path(where).name}" if kind in ("env", "overlay") else label


class _Loader:
    def __init__(
        self,
        base: Catalog,
        builtin: bool,
        source: str | None = None,
        applied: tuple[SourceIdentity, ...] = (),
    ) -> None:
        self.base = base
        self.builtin = builtin
        self.source = source
        self.applied = applied
        self.problems: list[str] = []
        self.warnings: list[str] = []
        self.trees: dict[tuple[str, str], Tree] = dict(base._trees)
        self.tables: dict[str, dict[str, Any]] = {k: dict(v) for k, v in base._tables.items()}
        self.sources: dict[tuple[str, str], str] = dict(base.sources)
        self.resolved: dict[tuple[str, str], Tree | None] = {}

    def fail(self, origin: str, where: str, message: str) -> None:
        self.problems.append(f"{origin}: {where}: {message}")

    def warn(self, origin: str, where: str, message: str) -> None:
        self.warnings.append(f"{origin}: {where}: {message}")

    def load(self, entries: dict, compositions: dict, shorthands: dict) -> Catalog:
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
            raise FormatError("invalid catalog", tuple(self.problems))
        built_compositions = dict(self.base.compositions)
        for alias, (raw, origin) in compositions.items():
            built_compositions[alias] = model.Composition(
                alias=alias, board=raw["board"], addons=tuple(raw.get("addons", ()))
            )
            self.sources[("compositions", alias)] = self.label(origin)
        built_shorthands = dict(self.base.shorthands)
        for name, (members, _) in shorthands.items():
            built_shorthands[name] = tuple(members)
        catalog = Catalog(
            compositions=MappingProxyType(built_compositions),
            shorthands=MappingProxyType(built_shorthands),
            sources=MappingProxyType(self.sources),
            _tables=MappingProxyType({k: MappingProxyType(v) for k, v in self.tables.items()}),
            _trees=MappingProxyType(self.trees),
            _applied=self.applied,
        )
        self.check_references(catalog, entries, compositions, shorthands)
        # Problems first: a warning escalated to an error must not hide them.
        if self.problems:
            raise FormatError("invalid catalog", tuple(self.problems))
        catalog.catalog_digest  # noqa: B018 (computed at load, ADR 0004 point 3)
        for message in self.warnings:
            warnings.warn(message, PlatformWarning, stacklevel=4)  # the caller of load_overlay
        return catalog

    def label(self, origin: str) -> str:
        if self.source is not None:
            return self.source
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
        """Each name in the base, by namespace, mapped to its entry and that entry's source."""

        def owner(kind: str, entry_id: str) -> str:
            # Only built-in files carry shorthands, so they have no entry in ``sources``.
            source = "builtin" if kind == "shorthands" else self.base.sources.get((kind, entry_id))
            return f"{kind}.{entry_id} from {source}" if source else f"{kind}.{entry_id}"

        spaces: dict[str, dict[str, str]] = {}
        for kind, table in self.base._tables.items():
            space = "resolvable" if kind in _RESOLVABLE else kind
            for entry_id, entry in table.items():
                for name in (entry_id, *getattr(entry, "aliases", ())):
                    spaces.setdefault(space, {})[name.casefold()] = owner(kind, entry_id)
        for alias in self.base.compositions:
            spaces.setdefault("resolvable", {})[alias.casefold()] = owner("compositions", alias)
        for name in self.base.shorthands:
            spaces.setdefault("resolvable", {})[name.casefold()] = owner("shorthands", name)
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
        self, catalog: Catalog, entries: dict, compositions: dict, shorthands: dict
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
                entity = catalog._tables.get(kind, {}).get(entry_id)
                if entity is not None:
                    check(catalog, entity, origin)
        boards = catalog._tables.get("boards", {})
        addons = catalog._tables.get("addons", {})
        for alias, (raw, origin) in compositions.items():
            if raw["board"] not in boards:
                self.fail(origin, f"compositions.{alias}", f"no board {raw['board']!r}")
            for addon in raw.get("addons", []):
                if addon not in addons:
                    self.fail(origin, f"compositions.{alias}", f"no add-on {addon!r}")
            if raw["board"] in boards and all(a in addons for a in raw.get("addons", [])):
                placed = [addons[a] for a in raw.get("addons", [])]
                for problem in _placement_problems(boards[raw["board"]], placed):
                    self.fail(origin, f"compositions.{alias}", problem)
        resolvable = {name for kind in _RESOLVABLE for name in catalog._tables.get(kind, {})}
        for name, (members, origin) in shorthands.items():
            for member in members:
                if member not in resolvable:
                    self.fail(origin, f"shorthands.{name}", f"no entry {member!r}")

    def check_soc(self, catalog: Catalog, soc: model.Soc, origin: str) -> None:
        where = f"socs.{soc.id}"
        for problem in _soc_reference_problems(soc, catalog):
            self.fail(origin, where, problem)
        for problem in _derivation_problems(soc, catalog):
            self.fail(origin, where, problem)
        for region in soc.memories:
            if region.stands_in_for:
                self.fail(
                    origin,
                    f"{where}.memories.{region.name}.stands_in_for",
                    "only a region of an fvp Implementation may stand in for others",
                )
        if self.builtin:
            for name in _unreached_regions(soc):
                message = "no access entry after default_access expansion"
                self.fail(origin, f"{where}.memories.{name}", message)

    def check_implementation(
        self, catalog: Catalog, impl: model.Implementation, origin: str
    ) -> None:
        where = f"implementations.{impl.id}"
        if impl.soc not in catalog._tables.get("socs", {}):
            self.fail(origin, where, f"no soc {impl.soc!r}")
            return
        trees = catalog._trees
        own = fvp_problems(
            trees[("socs", impl.soc)].values, trees[("implementations", impl.id)].values
        )
        for problem in own:
            self.fail(origin, where, problem)
        if own:
            return  # realizing raises the same problems
        try:
            realized = catalog._realized(impl.id)
        except MergeError as exc:
            for problem in exc.problems:
                self.fail(origin, f"{where}.subset", problem)
            return
        for problem in _soc_reference_problems(realized, catalog):
            self.fail(origin, where, f"as realized: {problem}")
        if self.builtin:
            # A subset can drop a kept region's only entry. Gaps the Soc already has are
            # reported against the Soc, not again here.
            unreached = set(_unreached_regions(catalog._tables["socs"][impl.soc]))
            for name in _unreached_regions(realized):
                if name not in unreached:
                    message = "as realized: no access entry after default_access expansion"
                    self.fail(origin, f"{where}.memories.{name}", message)
        if impl.provisioning is not None and impl.provisioning not in realized.boot_configs:
            self.fail(origin, where, f"provisioning {impl.provisioning!r} is not a boot config")
        self.check_population(catalog, impl.interfaces, impl.population, where, origin)
        removed = impl.subset.peripherals_removed
        self.check_interfaces(catalog, realized, impl, where, origin, removed=removed)

    def check_part(self, catalog: Catalog, part: model.Part, origin: str) -> None:
        where = f"parts.{part.id}"
        socs = catalog._tables.get("socs", {})
        if part.soc not in socs:
            self.fail(origin, where, f"no soc {part.soc!r}")
            return
        soc = socs[part.soc]
        if part.implementation is not None:
            impl = catalog._tables.get("implementations", {}).get(part.implementation)
            if impl is None or impl.soc != part.soc:
                self.fail(origin, where, f"no implementation {part.implementation!r} of {soc.id}")
            else:
                try:
                    soc = catalog._realized(impl.id)  # slots name what the Implementation keeps
                except MergeError:
                    return  # reported against the implementation
        cores = {c.id: c for c in soc.cores}
        regions = {r.name for r in soc.memories}
        for name, slot in part.image_slots.items():
            if slot.core not in cores:
                self.fail(origin, f"{where}.image_slots.{name}", f"no core {slot.core!r}")
            elif cores[slot.core].programmable_by is None:
                message = f"core {slot.core!r} is not programmable, so it cannot own a slot"
                self.fail(origin, f"{where}.image_slots.{name}", message)
            if slot.region not in regions:
                self.fail(origin, f"{where}.image_slots.{name}", f"no region {slot.region!r}")
        for problem in _slot_overlap_problems(part, soc):
            self.fail(origin, where, problem)

    def check_board(self, catalog: Catalog, board: model.Board, origin: str) -> None:
        where = f"boards.{board.id}"
        part = catalog._tables.get("parts", {}).get(board.part)
        if part is None:
            self.fail(origin, where, f"no part {board.part!r}")
            return
        self.check_population(catalog, board.interfaces, board.population, where, origin)
        if part.soc not in catalog._tables.get("socs", {}):
            return  # reported against the part
        try:
            soc = (
                catalog._realized(part.implementation)
                if part.implementation
                else catalog._tables["socs"][part.soc]
            )
        except (KeyError, MergeError):
            return  # reported against the part or the implementation
        if board.provisioning is not None and board.provisioning not in soc.boot_configs:
            self.fail(origin, where, f"provisioning {board.provisioning!r} is not a boot config")
        impl = catalog._tables.get("implementations", {}).get(part.implementation)
        removed = impl.subset.peripherals_removed if impl is not None else ()
        self.check_interfaces(catalog, soc, board, where, origin, removed=removed)

    def check_addon(self, catalog: Catalog, addon: model.AddOn, origin: str) -> None:
        where = f"addons.{addon.id}"
        boards = catalog._tables.get("boards", {})
        for board in addon.fits_boards:
            if board not in boards:
                self.fail(origin, f"{where}.fits_boards", f"no board {board!r}")
        for interface in addon.population:
            if interface not in addon.occupies:
                self.fail(origin, f"{where}.population", f"{interface!r} is not in occupies")
        self.check_population(catalog, None, addon.population, where, origin)
        devices = catalog._tables.get("memory_devices", {})
        for board in (boards[b] for b in addon.fits_boards if b in boards):
            for problem in _placement_problems(board, [addon]):
                self.fail(origin, where, problem)
            for name in dict.fromkeys((*addon.occupies, *addon.population)):
                if name not in board.interfaces:
                    self.fail(origin, where, f"board {board.id!r} has no interface {name!r}")
            for name, device in addon.population.items():
                if name in board.interfaces and device in devices:
                    at = f"{where}.population.{name} on {board.id}"
                    self.check_aperture(board.interfaces[name], devices[device], at, origin)

    def check_population(
        self,
        catalog: Catalog,
        interfaces: Mapping[str, Any] | None,
        population: Mapping[str, str],
        where: str,
        origin: str,
    ) -> None:
        devices = catalog._tables.get("memory_devices", {})
        for interface, device in population.items():
            if interfaces is not None and interface not in interfaces:
                self.fail(origin, f"{where}.population", f"no interface {interface!r}")
            if device not in devices:
                self.fail(origin, f"{where}.population", f"no memory device {device!r}")

    def check_interfaces(
        self,
        catalog: Catalog,
        soc: model.Soc,
        owner: model.Board | model.Implementation,
        where: str,
        origin: str,
        *,
        removed: Iterable[str],
    ) -> None:
        """Controllers and apertures of ``owner``'s interfaces on ``soc``, the Soc as realized.

        ``removed`` lists the controllers the Implementation removed (RFC 0002
        multicore, "Memory reachability").
        """
        interfaces, population = owner.interfaces, owner.population
        reached = {a.target for a in _expanded_access(soc)}
        for name, interface in interfaces.items():
            at, controller = f"{where}.interfaces.{name}", interface.controller
            if controller in removed:
                self.fail(origin, at, f"controller {controller!r} is removed by the implementation")
            elif controller not in soc.peripherals:
                self.fail(origin, at, f"no controller {controller!r}")
            elif controller not in soc.memory_controllers:
                self.fail(origin, at, f"{controller!r} is not a memory controller of the Soc")
            elif controller not in reached:
                message = (
                    f"controller {controller!r} has no access entry; its devices are unreachable"
                )
                # Built-in interfaces must be covered (RFC 0002 "Overlays, validation").
                (self.fail if self.builtin else self.warn)(origin, at, message)
        devices = catalog._tables.get("memory_devices", {})
        for name, device in population.items():
            if name in interfaces and device in devices:
                at = f"{where}.population.{name}"
                self.check_aperture(interfaces[name], devices[device], at, origin)

    def check_aperture(
        self, interface: model.MemoryInterface, device: model.MemoryDevice, at: str, origin: str
    ) -> None:
        if interface.aperture_max is None:
            message = (
                f"interface {interface.name!r} has no aperture_max; {device.id!r} is unchecked"
            )
            self.warn(origin, at, message)
        elif device.capacity > interface.aperture_max:
            self.fail(
                origin,
                at,
                f"{device.id!r} ({device.capacity} bytes) exceeds the {interface.name!r} "
                f"aperture ({interface.aperture_max} bytes)",
            )


def _soc_reference_problems(soc: model.Soc, catalog: Catalog) -> list[str]:
    """References inside one Soc that do not resolve (ADR 0002 section 2.5; RFC 0002)."""
    return [
        *_unit_problems(soc, catalog),
        *_clock_problems(soc),
        *_boot_problems(soc),
        *_access_problems(soc),
        *_relation_problems(soc, catalog),
        *_layout_problems(soc),
    ]


def _unit_problems(soc: model.Soc, catalog: Catalog) -> list[str]:
    problems: list[str] = []
    domains = {d.id for d in soc.clock_domains}
    cores = {c.id for c in soc.cores}
    known_cores = catalog._tables.get("cores", {})
    if not soc.cores:
        problems.append("cores: a Soc needs at least one core")
    elif soc.cores[0].role != "application":
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
    cores = {c.id: c for c in soc.cores}
    regions = {r.name: r.size for r in soc.memories}
    if soc.default_boot is not None and soc.default_boot not in soc.boot_configs:
        problems.append(f"default_boot: no boot config {soc.default_boot!r}")
    for name, config in soc.boot_configs.items():
        for core, start in config.app_start.items():
            if core not in cores:
                problems.append(f"boot_configs.{name}.app_start: no core {core!r}")
            elif cores[core].programmable_by is None:
                problems.append(f"boot_configs.{name}.app_start: core {core!r} is not programmable")
            if start.region not in regions:
                problems.append(f"boot_configs.{name}.app_start: no region {start.region!r}")
        for i, r in enumerate(config.reserved):
            where = f"boot_configs.{name}.reserved.{r.purpose}"
            if r.region not in regions:
                problems.append(f"{where}: no region {r.region!r}")
            elif r.offset + r.size > regions[r.region]:
                problems.append(f"{where}: runs past the end of region {r.region!r}")
            problems.extend(
                f"{where} overlaps reserved.{o.purpose} in region {r.region!r}"
                for o in config.reserved[i + 1 :]
                if o.region == r.region
                and r.offset < o.offset + o.size
                and o.offset < r.offset + r.size
            )
    return problems


def _access_problems(soc: model.Soc) -> list[str]:
    problems: list[str] = []
    cores = {c.id for c in soc.cores}
    masters = cores | {n.id for n in soc.npus} | {a.id for a in soc.accelerators}
    problems.extend(
        f"memory_controllers: {name!r} is not in peripherals"
        for name in soc.memory_controllers
        if name not in soc.peripherals
    )
    targets = {r.name for r in soc.memories} | set(soc.memory_controllers)
    for entry in soc.access:
        key = f"access {entry.master}@{entry.target}"
        if entry.master not in masters:
            problems.append(f"{key}: no master {entry.master!r}")
        if entry.target in soc.peripherals and entry.target not in targets:
            problems.append(f"{key}: peripheral {entry.target!r} is not a memory controller")
        elif entry.target not in targets:
            problems.append(f"{key}: no target {entry.target!r}")
    default = soc.default_access
    if default is not None and default.master not in cores:
        problems.append(f"default_access.master: no core {default.master!r}")
    elif default is not None and default.master != soc.cores[0].id:
        problems.append(f"default_access.master: {default.master!r} is not core 0")
    return problems


def _relation_problems(soc: model.Soc, catalog: Catalog) -> list[str]:
    problems: list[str] = []
    if soc.derives_from is not None and soc.derives_from not in catalog._tables.get("socs", {}):
        problems.append(f"derives_from: no soc {soc.derives_from!r}")
    boards = catalog._tables.get("boards", {})
    if soc.default_board is not None:
        board = boards.get(soc.default_board)
        part = catalog._tables.get("parts", {}).get(board.part) if board else None
        if board is None:
            problems.append(f"default_board: no board {soc.default_board!r}")
        elif part is not None and part.soc != soc.id:
            message = f"default_board: board {board.id!r} carries Soc {part.soc!r}, not {soc.id!r}"
            problems.append(message)
    return problems


def _layout_problems(soc: model.Soc) -> list[str]:
    """Regions that overlap at their bases or alternate bases (only the latter if base is None)."""
    spans: list[tuple[str, int, int]] = []
    for region in soc.memories:
        if region.base is not None:
            spans.append((f"memories.{region.name}", region.base, region.size))
        spans += [
            (f"memories.{region.name} at alternate base {alt:#x}", alt, region.size)
            for alt in region.alternate_bases
        ]
    return [
        f"{a} ({a_base:#x}, {a_size} bytes) overlaps {b} ({b_base:#x}, {b_size} bytes)"
        for i, (a, a_base, a_size) in enumerate(spans)
        for b, b_base, b_size in spans[i + 1 :]
        if a_base < b_base + b_size and b_base < a_base + a_size
    ]


def _derivation_problems(soc: model.Soc, catalog: Catalog) -> list[str]:
    """``derives_from`` requires equal physical regions (RFC 0002 "Inheritance and derivation")."""
    parent = catalog._tables.get("socs", {}).get(soc.derives_from or "")
    if parent is None:
        return []  # no relation, or reported as a reference problem
    mine, theirs = _physical_regions(soc), _physical_regions(parent)
    return [
        f"derives_from {parent.id!r}: memories.{name} is not the same physical region"
        for name in sorted(mine.keys() | theirs.keys())
        if mine.get(name) != theirs.get(name)
    ]


def _physical_regions(soc: model.Soc) -> dict[str, tuple]:
    return {
        r.name: (r.technology, r.attachment, r.size, r.base, tuple(sorted(r.alternate_bases)))
        for r in soc.memories
    }


def _unreached_regions(soc: model.Soc) -> list[str]:
    """Regions with no access entry, ``none`` included, after ``default_access`` expansion."""
    reached = {a.target for a in _expanded_access(soc)}
    return [r.name for r in soc.memories if r.name not in reached]


def _expanded_access(soc: model.Soc) -> tuple[model.Access, ...]:
    """``soc.access`` plus the entries ``default_access`` grants (RFC 0002 multicore).

    Its master gets a ``direct`` entry to every on-die region and memory controller
    that no core has an entry for, so neither an explicit entry for core 0 nor a
    region another core owns is granted by default.
    """
    default = soc.default_access
    if default is None:
        return soc.access
    cores = {c.id for c in soc.cores}
    taken = {a.target for a in soc.access if a.master in cores}
    on_die = [r.name for r in soc.memories if r.attachment != "external"]
    return soc.access + tuple(
        model.Access(
            master=default.master,
            target=target,
            access=default.access,
            provenance=default.provenance,
        )
        for target in (*on_die, *soc.memory_controllers)
        if target not in taken
    )


def _placement_problems(board: model.Board, addons: Iterable[model.AddOn]) -> list[str]:
    """Add-ons on ``board`` that do not fit it or put a second device on an interface."""
    problems: list[str] = []
    holders = {name: f"board {board.id!r}" for name in board.population}
    for addon in addons:
        if board.id not in addon.fits_boards:
            problems.append(f"add-on {addon.id!r} does not fit board {board.id!r}")
        for name in addon.population:
            if name in holders:
                problems.append(
                    f"add-on {addon.id!r} and {holders[name]} both put a device on {name!r}"
                )
            holders[name] = f"add-on {addon.id!r}"
    return problems


def _slot_overlap_problems(part: model.Part, soc: model.Soc) -> list[str]:
    """Image slots that overlap each other or any boot configuration's reservation."""
    slots = [
        (f"image_slots.{name}", s.region, s.offset, s.size) for name, s in part.image_slots.items()
    ]
    reserved = [
        (f"boot_configs.{config}.reserved.{r.purpose}", r.region, r.offset, r.size)
        for config, boot in soc.boot_configs.items()
        for r in boot.reserved
    ]
    return [
        f"{a} overlaps {b} in region {a_region!r}"
        for i, (a, a_region, a_offset, a_size) in enumerate(slots)
        for b, b_region, b_offset, b_size in (*slots[i + 1 :], *reserved)
        if a_region == b_region and a_offset < b_offset + b_size and b_offset < a_offset + a_size
    ]


def _plain(value: Any) -> Any:
    return value["value"] if isinstance(value, dict) and "value" in value else value


def _fields(decl: type) -> dict:
    return _walk.fields(decl)
