"""Plain-text views of a catalog and a resolved target, for ``helia-platforms list`` and ``show``.

Each row of ``show`` ends with the provenance status of the values it prints
(ADR 0003 section 1). One status prints alone; several print as the most common
one followed by each value that differs, as ``field: status``.
"""

from __future__ import annotations

import textwrap
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import Any

from helia_platforms import model
from helia_platforms.catalog import Catalog
from helia_platforms.target import Target

#: ``list`` tables, in the order they print.
KINDS = ("socs", "implementations", "parts", "boards")
_WIDTH = 100
_LABEL = 26


@dataclass
class _Row:
    label: str
    text: str
    records: list[tuple[str, model.Provenance]] = field(default_factory=list)


def _record(carrier: Any, path: str = "") -> model.Provenance:
    """The record of the value at ``path`` in ``carrier``: its own, else the carrier's."""
    if path and path in carrier.field_provenance:
        return carrier.field_provenance[path]
    return carrier.provenance


def _values(carrier: Any, prefix: str, names: Iterable[str]) -> list[tuple[str, model.Provenance]]:
    """``(name, record)`` for each value ``prefix + name`` of ``carrier``."""
    return [(name, _record(carrier, f"{prefix}{name}")) for name in names]


def size(n: int) -> str:
    """Bytes as the data files write them: ``256K``, ``64M``, or a plain count."""
    for unit, suffix in ((1 << 30, "G"), (1 << 20, "M"), (1 << 10, "K")):
        if n >= unit and n % unit == 0:
            return f"{n // unit}{suffix}"
    return str(n)


def _status(records: list[tuple[str, model.Provenance]]) -> str:
    if not records:
        return ""
    counts = Counter(r.status for _, r in records)
    common = counts.most_common(1)[0][0]
    others = [f"{name}: {r.status}" for name, r in records if r.status != common]
    return f"[{'; '.join([common, *others])}]"


def _details(records: list[tuple[str, model.Provenance]], indent: str) -> Iterator[str]:
    """Each distinct record once, with the values it covers when there are several."""
    distinct: list[tuple[model.Provenance, list[str]]] = []
    for name, record in records:
        for seen, names in distinct:
            if seen == record:
                names.append(name)
                break
        else:
            distinct.append((record, [name]))
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
            status = _status(row.records)
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
                lines += _details(row.records, " " * 6)
    return "\n".join(lines[1:]) + "\n"


# ---- list ---------------------------------------------------------------------------


def render_list(catalog: Catalog, kinds: Iterable[str] = KINDS) -> str:
    """One line per entry: id, what it belongs to, aliases and source label."""
    lines: list[str] = []
    for kind in kinds:
        entries = catalog._tables.get(kind, {})
        lines += ["", kind] if lines else [kind]
        if not entries:
            lines.append("  (none)")
        for entry_id, entry in entries.items():
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


def render_target(target: Target, *, provenance: bool = False, sources: bool = False) -> str:
    """The resolved target, section by section, with a status on every row."""
    sections = [
        ("target", _identity(target, sources)),
        ("cores", _cores(target)),
        ("npus and accelerators", _units(target)),
        ("memories", _memories(target)),
        ("access", _access(target)),
        ("clocks", _clocks(target)),
        ("boot", _boot(target)),
        ("debug", _debug(target)),
        ("sdk", _sdk(target)),
        ("peripherals", _peripherals(target)),
    ]
    return _render(sections, provenance)


def _identity(target: Target, sources: bool) -> list[_Row]:
    soc, impl, part, board = target.soc, target.implementation, target.part, target.board
    rows = [
        _Row("id", f"{target.id} ({target.kind}, {target.origin}, {target.release_status})"),
        _Row("soc", f"{soc.id}, series {soc.series}", _values(soc, "", ["series"])),
    ]
    if soc.revision:
        rows.append(_Row("soc revision", soc.revision, _values(soc, "", ["revision"])))
    if impl is not None:
        text = impl.kind + (f", model {impl.model}" if impl.model else "")
        rows.append(_Row("implementation", f"{impl.id} ({text})", _values(impl, "", ["kind"])))
    if part is not None:
        facts = {
            "package": part.package,
            "radio": part.radio,
            "silicon_revision": part.silicon_revision,
        }
        set_ = {k: v for k, v in facts.items() if v is not None}
        text = ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in set_.items())
        rows.append(
            _Row("part", f"{part.id}" + (f" ({text})" if text else ""), _values(part, "", set_))
        )
    if board is not None:
        text = board.category + (f", revision {board.revision}" if board.revision else "")
        names = ["category", *(["revision"] if board.revision else [])]
        rows.append(_Row("board", f"{board.id} ({text})", _values(board, "", names)))
    rows += [_Row("add-on", a.id, _values(a, "", ["fits_boards"])) for a in target.addons]
    if target.aliases:
        rows.append(_Row("aliases", ", ".join(target.aliases)))
    rows.append(_Row("capabilities", " ".join(sorted(target.capabilities)) + " (derived)"))
    if sources:
        rows += [_Row(f"source of {kind}", label) for kind, label in _source_labels(target)]
    return rows


def _source_labels(target: Target) -> list[tuple[str, str]]:
    catalog = target._catalog
    chain = [("socs", target.soc.id)]
    chain += [("implementations", target.implementation.id)] if target.implementation else []
    chain += [("parts", target.part.id)] if target.part else []
    chain += [("boards", target.board.id)] if target.board else []
    chain += [("addons", a.id) for a in target.addons]
    chain += [("memory_devices", d.id) for _, d in target._devices]
    return [(f"{t[:-1]} {i}", catalog.sources.get((t, i), "?")) for t, i in dict.fromkeys(chain)]


def _cores(target: Target) -> list[_Row]:
    rows = []
    soc = target.soc
    for core in soc.cores:
        o = core.options
        fpu = o.fpu + (" with fp64" if o.fpu_dp else "")
        cache = f", I/D cache {o.icache_kb}/{o.dcache_kb} KB" if o.icache_kb is not None else ""
        text = f"{core.core}, {core.role}, fpu {fpu}, mve {o.mve}{cache}, clock {core.clock_domain}"
        names = ["core", "role", "clock_domain"]
        names += ["programmable_by"] if core.programmable_by else []
        names += [f"options.{n}" for n in ("fpu", "fpu_dp", "mve", "icache_kb", "dcache_kb")]
        rows.append(_Row(core.id, text, _values(soc, f"cores.{core.id}.", names)))
    for ip_id in dict.fromkeys(c.core for c in soc.cores):
        ip = target._catalog._entry("cores", ip_id)
        dsp = "dsp" if ip.has_dsp_extension else "no dsp"
        names = ["arch", "pmu", "has_dsp_extension"]
        rows.append(_Row(ip_id, f"{ip.arch}, pmu {ip.pmu}, {dsp}", _values(ip, "", names)))
    return rows


def _units(target: Target) -> list[_Row]:
    soc = target.soc
    rows = []
    for npu in soc.npus:
        ip = npu.npu
        text = (
            f"{ip.vendor} {ip.family} {ip.model}, {ip.macs_per_cycle} MACs/cycle "
            f"({ip.accelerator_config}), driven by {npu.driven_by}, clock {npu.clock_domain}"
        )
        if npu.axi_width_bits:
            text += f", AXI {npu.axi_width_bits} bits"
        names = [f"npu.{n}" for n in ("vendor", "family", "model", "macs_per_cycle")]
        names += ["driven_by", "clock_domain"]
        names += ["axi_width_bits"] if npu.axi_width_bits else []
        rows.append(_Row(npu.id, text, _values(soc, f"npus.{npu.id}.", names)))
    for unit in soc.accelerators:
        text = (
            f"{unit.kind}" + (f" ({unit.ip})" if unit.ip else "") + f", driven by {unit.driven_by}"
        )
        names = ["kind", "driven_by", "clock_domain"]
        rows.append(_Row(unit.id, text, _values(soc, f"accelerators.{unit.id}.", names)))
    return rows


def _region_text(region: model.MemoryRegion) -> str:
    base = "no base" if region.base is None else f"{region.base:#010x}"
    text = f"{region.technology} {region.attachment}, {base}, {size(region.size)}"
    if region.alternate_bases:
        text += ", also at " + ", ".join(f"{b:#010x}" for b in region.alternate_bases)
    flags = [n for n in ("executable", "writeable", "cacheable") if getattr(region, n)]
    if flags:
        text += ", " + ", ".join(flags)
    if region.stands_in_for:
        text += f", stands in for {', '.join(region.stands_in_for)}"
    return text


def _memories(target: Target) -> list[_Row]:
    rows = []
    for region in target.soc.memories:
        names = ["technology", "attachment", "size"]
        names += [
            n
            for n in ("base", "executable", "writeable", "cacheable")
            if getattr(region, n) is not None
        ]
        names += [f"alternate_bases.{b:#x}" for b in region.alternate_bases]
        rows.append(_Row(region.name, _region_text(region), _values(region, "", names)))
    for (region, controller), (owner, interface, device) in zip(
        target._external, _populations(target), strict=True
    ):
        text = f"{_region_text(region)}, device {device.id} on {controller}"
        records = [
            ("capacity", _record(device, "capacity")),
            ("technology", _record(device, "technology")),
        ]
        records.append(("aperture_base", _record(owner, f"interfaces.{interface}.aperture_base")))
        rows.append(_Row(region.name, text, records))
    nvm = target.usable_nvm()
    for name, free in nvm.items():
        rows.append(_Row(f"usable {name}", f"{size(free)} ({free} bytes; core 0, computed)"))
    return rows


def _populations(target: Target) -> list[tuple[Any, str, model.MemoryDevice]]:
    """(owner of the interface, interface name, device) in ``Target._devices`` order."""
    found = []
    owners = [(target.implementation, target.implementation)] if target.implementation else []
    if target.board is not None:
        owners.append((target.board, target.board))
        owners += [(target.board, addon) for addon in target.addons]
    for owner, populator in owners:
        for interface, device_id in populator.population.items():
            found.append((owner, interface, target._catalog._entry("memory_devices", device_id)))
    return found


def _access(target: Target) -> list[_Row]:
    soc = target.soc
    rows = []
    if soc.default_access is not None:
        d = soc.default_access
        text = f"{d.master} {d.access} to every on-die region and memory controller"
        rows.append(_Row("default", text, _values(d, "", ["master", "access", "scope"])))
    for entry in soc.access:
        text = entry.access
        for name in ("port", "guidance", "address"):
            value = getattr(entry, name)
            if value is not None:
                text += f", {name} {value:#x}" if name == "address" else f", {name} {value}"
        rows.append(_Row(f"{entry.master} -> {entry.target}", text, _values(entry, "", ["access"])))
    return rows


def _clocks(target: Target) -> list[_Row]:
    soc = target.soc
    rows = []
    for domain in soc.clock_domains:
        for point in domain.points:
            text = f"{point.mhz:g} MHz" + (f", HAL {point.hal_mode}" if point.hal_mode else "")
            names = ["mhz", *(["hal_mode"] if point.hal_mode else [])]
            rows.append(_Row(f"{domain.id}.{point.name}", text, _values(point, "", names)))
    for op in soc.operating_points:
        default = " (default)" if op.name == soc.default_operating_point else ""
        domains = ", ".join(f"{d} {p}" for d, p in op.domains.items())
        records = _values(op, "", ["domains"])
        if default:
            records += [("default", _record(soc, "default_operating_point"))]
        rows.append(_Row(f"point {op.name}", f"{domains}{default}", records))
    return rows


def _boot(target: Target) -> list[_Row]:
    soc = target.soc
    rows = []
    selected = target.boot.name if target.boot else None
    for config in soc.boot_configs.values():
        mark = " (selected)" if config.name == selected else ""
        starts = ", ".join(f"{c} at {s.region}+{s.offset:#x}" for c, s in config.app_start.items())
        names = [
            "requires",
            *(f"app_start.{c}.{f}" for c in config.app_start for f in ("region", "offset")),
        ]
        rows.append(
            _Row(
                config.name,
                f"requires {config.requires}, app {starts}{mark}",
                _values(config, "", names),
            )
        )
        for r in config.reserved:
            text = f"{r.region}+{r.offset:#x}, {size(r.size)}"
            rows.append(
                _Row(f"  reserved {r.purpose}", text, _values(r, "", ["region", "offset", "size"]))
            )
    if target.part is not None:
        for slot in target.part.image_slots.values():
            text = (
                f"{slot.core} in {slot.region}+{slot.offset:#x}, {size(slot.size)}, {slot.supplier}"
            )
            names = ["core", "region", "offset", "size", "supplier"]
            rows.append(_Row(f"image slot {slot.name}", text, _values(slot, "", names)))
    if target.boot is not None and target.boot.app_start:
        address = target.flash_load_address()
        rows.append(_Row("flash load address", f"{address:#010x} (core 0, computed)"))
    return rows


def _debug(target: Target) -> list[_Row]:
    rows = []
    for owner in (target.board, target.implementation, target.part):
        if owner is not None and owner.jlink_device is not None:
            rows.append(
                _Row("jlink_device", owner.jlink_device, _values(owner, "", ["jlink_device"]))
            )
            break
    for owner in (target.board, target.implementation):
        if owner is not None and owner.trace_clock_mhz is not None:
            text = f"{owner.trace_clock_mhz:g} MHz"
            rows.append(_Row("trace_clock_mhz", text, _values(owner, "", ["trace_clock_mhz"])))
            break
    else:
        sdk = target.soc.sdk
        if sdk is not None and sdk.trace_clock_mhz is not None:
            text = f"{sdk.trace_clock_mhz:g} MHz (the SDK's)"
            rows.append(
                _Row("trace_clock_mhz", text, _values(target.soc, "sdk.", ["trace_clock_mhz"]))
            )
    return rows


def _sdk(target: Target) -> list[_Row]:
    soc, sdk = target.soc, target.soc.sdk
    if sdk is None:
        return []
    rows = []
    for name in ("c_define", "cmsis_header"):
        value = getattr(sdk, name)
        if value is not None:
            rows.append(_Row(name, value, _values(soc, "sdk.", [name])))
    for key, value in sdk.hal_enums.items():
        rows.append(_Row(f"hal_enums.{key}", value, _values(soc, "sdk.hal_enums.", [key])))
    build = sdk.build
    if build is not None:
        for name in ("abi", "float_abi"):
            value = getattr(build, name)
            if value is not None:
                rows.append(_Row(f"build.{name}", value, _values(soc, "sdk.build.", [name])))
        if build.toolchains:
            records = _values(soc, "sdk.build.toolchains.", build.toolchains)
            rows.append(_Row("build.toolchains", ", ".join(build.toolchains), records))
    return rows


def _peripherals(target: Target) -> list[_Row]:
    soc = target.soc
    rows = []
    for name in ("memory_controllers", "peripherals"):
        items = getattr(soc, name)
        if items:
            text = f"({len(items)}) " + ", ".join(items)
            rows.append(_Row(name, text, _values(soc, f"{name}.", items)))
    return rows
