"""Plain-text views of a catalog and a resolved target, for ``helia-platforms list`` and ``show``.

Each row of ``show`` prints facts as ``name value`` and ends with their provenance
status (ADR 0003 section 1): one status alone, or the most common one followed by
each fact that differs, as ``name: status``. A row prints only the fact paths the
data states, so a model default never appears as a fact.
"""

from __future__ import annotations

import dataclasses
import textwrap
from collections import Counter
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any

from helia_platforms import _format as fmt
from helia_platforms import model
from helia_platforms._tree import Path, iter_values, realize, segment
from helia_platforms.catalog import Catalog
from helia_platforms.errors import PlatformError
from helia_platforms.target import Target

#: ``list`` tables, in the order they print.
KINDS = ("socs", "implementations", "parts", "boards")
_WIDTH = 100
_LABEL = 26
_ADDRESSES = frozenset({"base", "address", "aperture_base", "base_address", "alternate_bases"})
_SIZES = frozenset({"size", "capacity", "aperture_max", "memories_resized"})
_OFFSETS = frozenset({"offset", "memories_rebased"})

#: A fact's place: its entry's table and id, and its path in that entry.
Where = tuple[str, str, Path]


@dataclass
class _Fact:
    name: str
    record: model.Provenance
    where: Where


@dataclass
class _Row:
    label: str
    text: str
    facts: list[_Fact] = field(default_factory=list)


@dataclass(frozen=True)
class _At:
    """An object's place: its entry, the record carrier holding it, and the entry's fact paths.

    ``base`` is the carrier's path and ``path`` the object's; records key relative to ``base``.
    """

    carrier: Any
    table: str
    entry: str
    base: Path
    path: Path
    stated: frozenset[Path]

    def child(self, carrier: Any, *path: str) -> _At:
        """A carrier inside this object, with records of its own."""
        where = (*self.path, *path)
        return dataclasses.replace(self, carrier=carrier, base=where, path=where)

    def inner(self, *path: str) -> _At:
        """An object inside this one whose records the same carrier holds."""
        return dataclasses.replace(self, path=(*self.path, *path))


class _Entries:
    """Each entry's stated fact paths, computed once per entry."""

    def __init__(self, target: Target) -> None:
        self._target = target
        self._stated: dict[tuple[str, str], frozenset[Path]] = {}

    def at(self, table: str, entry: str, carrier: Any) -> _At:
        if (table, entry) not in self._stated:
            values = _tree(self._target, table, entry).values
            paths = iter_values(values, fmt.ENTITY_TABLES[table])
            self._stated[table, entry] = frozenset(p for p, _ in paths)
        return _At(carrier, table, entry, (), (), self._stated[table, entry])


def _tree(target: Target, table: str, entry: str) -> Any:
    """An entry's tree; the Soc as the target's implementation realizes it."""
    trees = target._catalog._trees
    if table == "socs" and target.implementation is not None:
        return realize(trees["socs", entry], trees["implementations", target.implementation.id])
    return trees[table, entry]


def entries(target: Target) -> list[tuple[str, str]]:
    """``(table, id)`` of every entry the target reads, in reference-chain order."""
    chain = [("socs", target.soc.id)]
    chain += [("cores", c.core) for c in target.soc.cores]
    chain += [("implementations", target.implementation.id)] if target.implementation else []
    chain += [("parts", target.part.id)] if target.part else []
    chain += [("boards", target.board.id)] if target.board else []
    chain += [("addons", a.id) for a in target.addons]
    chain += [("memory_devices", d.id) for _, d in target._devices]
    return list(dict.fromkeys(chain))


def stated_facts(target: Target) -> set[Where]:
    """The place of every leaf fact the target's entries state."""
    found = set()
    for table, entry in entries(target):
        values = _tree(target, table, entry).values
        for path, value in iter_values(values, fmt.ENTITY_TABLES[table]):
            if not isinstance(value, dict | list):
                found.add((table, entry, path))
    return found


def size(n: int) -> str:
    """Bytes as the data files write them: ``256K``, ``64M``, or a plain count."""
    for unit, suffix in ((1 << 30, "G"), (1 << 20, "M"), (1 << 10, "K")):
        if n >= unit and n % unit == 0:
            return f"{n // unit}{suffix}"
    return str(n)


def _text(name: str, value: Any) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int) and name in _ADDRESSES:
        return f"{value:#010x}"
    if isinstance(value, int) and name in _SIZES:
        return size(value)
    if isinstance(value, int) and name in _OFFSETS:
        return f"{value:#x}"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _leaves(path: Path, value: Any) -> Iterator[tuple[str, Path, str]]:
    """``(group, path, text)`` for each leaf under ``value``; a list or map is one group."""
    group = ".".join(path)
    if value is None or (isinstance(value, tuple | Mapping) and not value):
        return
    if dataclasses.is_dataclass(value):
        for f in dataclasses.fields(value):
            yield from _leaves((*path, f.name), getattr(value, f.name))
    elif isinstance(value, Mapping):
        for key, item in value.items():
            if dataclasses.is_dataclass(item):
                yield from _leaves((*path, key), item)
            else:
                yield group, (*path, key), f"{key}={_text(path[-1], item)}"
    elif isinstance(value, tuple):
        for item in value:
            if dataclasses.is_dataclass(item):
                key = "@".join(str(getattr(item, f.name)) for f in dataclasses.fields(item))
                yield from _leaves((*path, key), item)
            else:
                yield group, (*path, segment(item)), _text(path[-1], item)
    else:
        yield group, path, _text(path[-1], value)


def _row(
    label: str, at: _At, obj: Any, names: Iterable[str], *, lead: str = "", note: str = ""
) -> _Row:
    """A row of the stated facts ``names`` of ``obj``, which sits at ``at``.

    The text and the status come from the same leaves, so a row cannot count a fact
    it does not print.
    """
    groups: dict[str, list[str]] = {}
    facts = []
    for name in names:
        for group, path, text in _leaves((name,), getattr(obj, name)):
            where = (*at.path, *path)
            if where not in at.stated:
                continue
            groups.setdefault(group, []).append(text)
            relative = ".".join(where[len(at.base) :])
            record = at.carrier.field_provenance.get(relative, at.carrier.provenance)
            facts.append(_Fact(".".join(path), record, (at.table, at.entry, where)))
    chunks = [f"{group} {' '.join(texts)}" for group, texts in groups.items()]
    text = ", ".join([lead, *chunks] if lead else chunks) + (f" ({note})" if note else "")
    return _Row(label, text, facts)


def _status(facts: list[_Fact]) -> str:
    if not facts:
        return ""
    counts = Counter(f.record.status for f in facts)
    common = counts.most_common(1)[0][0]
    others = [f"{f.name}: {f.record.status}" for f in facts if f.record.status != common]
    return f"[{'; '.join([common, *others])}]"


def _details(facts: list[_Fact], indent: str) -> Iterator[str]:
    """Each distinct record once, with the facts it covers when there are several."""
    distinct: list[tuple[model.Provenance, list[str]]] = []
    for fact in facts:
        for seen, names in distinct:
            if seen == fact.record:
                names.append(fact.name)
                break
        else:
            distinct.append((fact.record, [fact.name]))
    for record, names in distinct:
        head = record.status
        if len(distinct) > 1:
            head += f" ({', '.join(names)})"
        if record.verified_on:
            head += f", verified {record.verified_on} by {record.verified_by}"
        yield from textwrap.wrap(
            head,
            _WIDTH,
            initial_indent=indent,
            subsequent_indent=f"{indent}    ",
            break_long_words=False,
        )
        for reference in record.source:
            yield f"{indent}  {reference}"
        if record.notes:
            yield from textwrap.wrap(
                record.notes,
                _WIDTH,
                initial_indent=f"{indent}  ",
                subsequent_indent=f"{indent}  ",
                break_long_words=False,
            )


def _render(sections: list[tuple[str, list[_Row]]], provenance: bool) -> str:
    lines: list[str] = []
    for title, rows in sections:
        if not rows:
            continue
        lines += ["", title]
        for row in rows:
            status = _status(row.facts)
            text = f"{row.text}  {status}" if status else row.text
            lines += textwrap.wrap(
                text,
                _WIDTH,
                initial_indent=f"  {row.label:<{_LABEL}} ",
                subsequent_indent=" " * (_LABEL + 3),
                break_on_hyphens=False,
                break_long_words=False,
            )
            if provenance:
                lines += _details(row.facts, " " * 6)
    return "\n".join(lines[1:]) + "\n"


# ---- list ---------------------------------------------------------------------------


def render_list(catalog: Catalog, kinds: Iterable[str] = KINDS) -> str:
    """One line per entry: id, what it belongs to, aliases and source label."""
    lines: list[str] = []
    for kind in kinds:
        table = catalog._tables.get(kind, {})
        lines += ["", kind] if lines else [kind]
        if not table:
            lines.append("  (none)")
        for entry_id, entry in table.items():
            what = {
                "socs": lambda e: f"series {e.series}",
                "implementations": lambda e: f"{e.kind} of {e.soc}",
                "parts": lambda e: f"part of {e.soc}",
                "boards": lambda e: f"{e.category} board, part {e.part}",
            }[kind](entry)
            aliases = f", aliases {', '.join(entry.aliases)}" if entry.aliases else ""
            label = catalog.sources.get((kind, entry_id), "?")
            lines.append(f"  {entry_id:<{_LABEL}} {what}{aliases}  ({label})")
    return "\n".join(lines) + "\n"


# ---- show ---------------------------------------------------------------------------


def render_target(
    target: Target,
    *,
    provenance: bool = False,
    sources: bool = False,
    requested_boot: str | None = None,
) -> str:
    """The resolved target, section by section; ``requested_boot`` is the caller's ``boot=``."""
    return _render(sections(target, sources=sources, requested_boot=requested_boot), provenance)


def sections(
    target: Target, *, sources: bool = False, requested_boot: str | None = None
) -> list[tuple[str, list[_Row]]]:
    """The rows of ``show``, by section."""
    at = _Entries(target)
    return [
        ("target", _identity(target, at, sources)),
        ("cores", _cores(target, at)),
        ("npus and accelerators", _units(target, at)),
        ("memories", _memories(target, at)),
        ("access", _access(target, at)),
        ("clocks", _clocks(target, at)),
        ("boot", _boot(target, at, requested_boot)),
        ("debug", _debug(target, at)),
        ("sdk", _sdk(target, at)),
        ("peripherals", _peripherals(target, at)),
    ]


def _soc(target: Target, at: _Entries) -> _At:
    return at.at("socs", target.soc.id, target.soc)


def _identity(target: Target, at: _Entries, sources: bool) -> list[_Row]:
    soc, impl, part, board = target.soc, target.implementation, target.part, target.board
    rows = [
        _Row("id", f"{target.id} ({target.kind}, {target.origin}, {target.release_status})"),
        _row("soc", _soc(target, at), soc, ["series", "revision"], lead=soc.id),
    ]
    rows += [_Row(n, getattr(soc, n)) for n in ("derives_from", "default_board") if getattr(soc, n)]
    if impl is not None:
        impl_at = at.at("implementations", impl.id, impl)
        rows.append(_row("implementation", impl_at, impl, ["soc", "kind", "model"], lead=impl.id))
        rows.append(_row("subset", impl_at, impl, ["subset"]))
    if part is not None:
        names = ["soc", "implementation", "silicon_revision", "package", "radio"]
        rows.append(_row("part", at.at("parts", part.id, part), part, names, lead=part.id))
    if board is not None:
        names = ["part", "category", "revision"]
        rows.append(_row("board", at.at("boards", board.id, board), board, names, lead=board.id))
    for addon in target.addons:
        names = ["fits_boards", "occupies", "revision"]
        rows.append(_row("add-on", at.at("addons", addon.id, addon), addon, names, lead=addon.id))
    for alias in target.aliases:
        composition = target._catalog.compositions.get(alias)
        if composition is not None:
            addons = f", add-ons {', '.join(composition.addons)}" if composition.addons else ""
            rows.append(_Row("composition", f"{alias}: board {composition.board}{addons}"))
    if target.aliases:
        rows.append(_Row("aliases", ", ".join(target.aliases)))
    rows.append(_Row("capabilities", " ".join(sorted(target.capabilities)) + " (derived)"))
    if sources:
        rows += [_Row(f"source of {kind}", label) for kind, label in _source_labels(target)]
    return [r for r in rows if r.label != "subset" or r.facts]


def _source_labels(target: Target) -> list[tuple[str, str]]:
    catalog = target._catalog
    chain = entries(target)
    chain += [("compositions", a) for a in target.aliases if a in catalog.compositions]
    return [(f"{t[:-1]} {i}", catalog.sources.get((t, i), "?")) for t, i in chain]


def _cores(target: Target, at: _Entries) -> list[_Row]:
    soc = _soc(target, at)
    names = ["core", "role", "clock_domain", "programmable_by", "options"]
    rows = [_row(c.id, soc.inner("cores", c.id), c, names) for c in target.soc.cores]
    for ip_id in dict.fromkeys(c.core for c in target.soc.cores):
        ip = target._catalog._entry("cores", ip_id)
        names = ["arch", "pmu", "has_dsp_extension"]
        rows.append(_row(ip_id, at.at("cores", ip_id, ip), ip, names))
    return rows


def _units(target: Target, at: _Entries) -> list[_Row]:
    soc = _soc(target, at)
    rows = []
    for npu in target.soc.npus:
        names = ["npu", "driven_by", "clock_domain", "axi_width_bits", "base_address", "irq"]
        note = f"Vela config {npu.npu.accelerator_config}, computed"
        rows.append(_row(npu.id, soc.inner("npus", npu.id), npu, names, note=note))
    for unit in target.soc.accelerators:
        names = ["kind", "ip", "driven_by", "clock_domain", "base_address", "irq"]
        rows.append(_row(unit.id, soc.inner("accelerators", unit.id), unit, names))
    return rows


_REGION = (
    "technology",
    "attachment",
    "base",
    "size",
    "alternate_bases",
    "executable",
    "writeable",
    "cacheable",
    "characterization",
    "stands_in_for",
)
_INTERFACE = ("controller", "modes", "aperture_base", "aperture_max")
_DEVICE = ("technology", "capacity", "driver_family", "modes", "characterization")


def _memories(target: Target, at: _Entries) -> list[_Row]:
    soc = _soc(target, at)
    rows = [_row(r.name, soc.child(r, "memories", r.name), r, _REGION) for r in target.soc.memories]
    populated = set()
    for (region, _), (owner, populator, interface, device) in zip(
        target._external, _populations(target, at), strict=True
    ):
        populated.add((owner.entry, interface))
        row = _row(region.name, populator, populator.carrier, ["population"])
        row.facts = [f for f in row.facts if f.where[2] == ("population", interface)]
        iface = _interface(owner, interface)
        computed = f"{size(region.size)} at {region.base:#010x}, computed"
        row.text = f"population.{interface} {device.id}, {iface.text} ({computed})"
        rows.append(_Row(row.label, row.text, row.facts + iface.facts))
    for owner in _interface_owners(target, at):
        for name in owner.carrier.interfaces:
            if (owner.entry, name) not in populated:
                row = _interface(owner, name)
                rows.append(_Row(f"interface {name}", f"{row.text} (unpopulated)", row.facts))
    for device_id in dict.fromkeys(d.id for _, d in target._devices):
        device = target._catalog._entry("memory_devices", device_id)
        device_at = at.at("memory_devices", device_id, device)
        rows.append(_row(f"device {device_id}", device_at, device, _DEVICE))
    nvm = target.usable_nvm()
    for name, free in nvm.items():
        rows.append(_Row(f"usable {name}", f"{size(free)} ({free} bytes; core 0, computed)"))
    return rows


def _interface(owner: _At, name: str) -> _Row:
    interface = owner.carrier.interfaces[name]
    return _row("", owner.inner("interfaces", name), interface, _INTERFACE)


def _interface_owners(target: Target, at: _Entries) -> list[_At]:
    owners = []
    if target.implementation is not None:
        impl = target.implementation
        owners.append(at.at("implementations", impl.id, impl))
    if target.board is not None:
        owners.append(at.at("boards", target.board.id, target.board))
    return owners


def _populations(target: Target, at: _Entries) -> list[tuple[_At, _At, str, model.MemoryDevice]]:
    """(interface owner, populator, interface, device) in ``Target._devices`` order."""
    pairs = []
    if target.implementation is not None:
        impl = at.at("implementations", target.implementation.id, target.implementation)
        pairs.append((impl, impl))
    if target.board is not None:
        board = at.at("boards", target.board.id, target.board)
        pairs.append((board, board))
        pairs += [(board, at.at("addons", a.id, a)) for a in target.addons]
    found = []
    for owner, populator in pairs:
        for interface, device_id in populator.carrier.population.items():
            device = target._catalog._entry("memory_devices", device_id)
            found.append((owner, populator, interface, device))
    return found


def _access(target: Target, at: _Entries) -> list[_Row]:
    soc = _soc(target, at)
    rows = []
    default = target.soc.default_access
    if default is not None:
        default_at = soc.child(default, "default_access")
        rows.append(_row("default", default_at, default, ["master", "access", "scope"]))
    names = [
        "master",
        "target",
        "access",
        "requires_awake",
        "guidance",
        "reason",
        "address",
        "port",
        "characterization",
    ]
    for entry in target.soc.access:
        entry_at = soc.child(entry, "access", f"{entry.master}@{entry.target}")
        rows.append(_row("entry", entry_at, entry, names))
    return rows


def _clocks(target: Target, at: _Entries) -> list[_Row]:
    soc = _soc(target, at)
    rows = []
    for domain in target.soc.clock_domains:
        for point in domain.points:
            point_at = soc.child(point, "clock_domains", domain.id, point.name)
            rows.append(_row(f"{domain.id}.{point.name}", point_at, point, ["mhz", "hal_mode"]))
    for op in target.soc.operating_points:
        op_at = soc.child(op, "operating_points", op.name)
        rows.append(_row(f"point {op.name}", op_at, op, ["domains", "hal_mode"]))
    rows.append(_row("soc", soc, target.soc, ["default_operating_point"]))
    return [r for r in rows if r.facts]


def _boot(target: Target, at: _Entries, requested: str | None) -> list[_Row]:
    soc = _soc(target, at)
    rows = []
    for config in target.soc.boot_configs.values():
        config_at = soc.child(config, "boot_configs", config.name)
        rows.append(_row(config.name, config_at, config, ["requires", "app_start"]))
        for r in config.reserved:
            reserved_at = config_at.child(r, "reserved", r.purpose)
            rows.append(
                _row(f"  reserved {r.purpose}", reserved_at, r, ["region", "offset", "size"])
            )
    selectors = [_row("soc", soc, target.soc, ["default_boot"])]
    for owner in _interface_owners(target, at):
        selectors.append(_row(owner.table[:-1], owner, owner.carrier, ["provisioning"]))
    rows += [r for r in selectors if r.facts]
    if target.boot is not None:
        rows.append(_selection(target.boot.name, selectors, requested))
    if target.part is not None:
        part = at.at("parts", target.part.id, target.part)
        for slot in target.part.image_slots.values():
            names = ["core", "region", "offset", "size", "supplier"]
            slot_at = part.child(slot, "image_slots", slot.name)
            rows.append(_row(f"image slot {slot.name}", slot_at, slot, names))
    for index, core in enumerate(target.soc.cores):
        if target.boot is None or core.id not in target.boot.app_start:
            continue
        try:
            text = f"{target.flash_load_address(index):#010x} (core {index}, computed)"
        except PlatformError as error:
            text = f"none (core {index}): {error}"
        rows.append(_Row("flash load address", text))
    return rows


def _selection(name: str, selectors: list[_Row], requested: str | None) -> _Row:
    """The selected boot and the fact that selects it, in ``resolve``'s order."""
    if requested is not None:
        return _Row("selected boot", f"{name} (by --boot)")
    by_label = {r.label: r for r in selectors if r.facts}
    for label, fact in (
        ("board", "provisioning"),
        ("implementation", "provisioning"),
        ("soc", "default_boot"),
    ):
        if label in by_label:
            return _Row("selected boot", f"{name} (by the {label}'s {fact})", by_label[label].facts)
    return _Row("selected boot", name)


def _debug(target: Target, at: _Entries) -> list[_Row]:
    owners = [
        ("boards", target.board),
        ("implementations", target.implementation),
        ("parts", target.part),
    ]
    rows = []
    for name, tables in (
        ("jlink_device", ("boards", "implementations", "parts")),
        ("trace_clock_mhz", ("boards", "implementations")),
    ):
        found = [(t, o) for t, o in owners if t in tables and o and getattr(o, name) is not None]
        for i, (table, owner) in enumerate(found):
            note = "used" if i == 0 else "overridden"
            rows.append(_row(table[:-1], at.at(table, owner.id, owner), owner, [name], note=note))
    sdk = target.soc.sdk
    if sdk is not None and sdk.trace_clock_mhz is not None:
        used = not any(r.text.startswith("trace_clock_mhz") for r in rows)
        note = "used" if used else "overridden"
        sdk_at = _soc(target, at).inner("sdk")
        rows.append(_row("soc sdk", sdk_at, sdk, ["trace_clock_mhz"], note=note))
    return rows


def _sdk(target: Target, at: _Entries) -> list[_Row]:
    sdk = target.soc.sdk
    if sdk is None:
        return []
    sdk_at = _soc(target, at).inner("sdk")
    rows = [_row("soc sdk", sdk_at, sdk, ["c_define", "cmsis_header", "hal_enums", "build"])]
    return [r for r in rows if r.facts]


def _peripherals(target: Target, at: _Entries) -> list[_Row]:
    soc = _soc(target, at)
    rows = []
    for name in ("memory_controllers", "peripherals"):
        count = len(getattr(target.soc, name))
        row = _row("soc", soc, target.soc, [name], note=f"{count}")
        if row.facts:
            rows.append(row)
    return rows
