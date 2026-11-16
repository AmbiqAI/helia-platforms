"""Markdown pages for each Soc and board, and an index (RFC 0003 "Markdown pages")."""

from __future__ import annotations

import io
import zipfile
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

from helia_platforms import export
from helia_platforms._show import size
from helia_platforms.errors import PlatformError

if TYPE_CHECKING:
    from helia_platforms.catalog import Catalog
    from helia_platforms.target import Target


def render(catalog: Catalog) -> dict[str, str]:
    """Each page by its path, from the filtered export plus what ``resolve()`` derives.

    Raises ``PlatformError`` when a page's target is not public.
    """
    document = export.document(catalog)
    member, identity = document["catalog"], document["identity"]
    footer = (
        f"\n---\n\nhelia-platforms {identity['package_version']}, "
        f"catalog `{identity['catalog_digest']}`.\n"
    )
    socs, boards = member.get("socs", {}), member.get("boards", {})
    for soc_id in socs:
        _public(catalog, soc_id)
    pages = {
        f"socs/{soc_id}.md": _soc(soc_id, soc, member) + footer for soc_id, soc in socs.items()
    }
    pages |= {
        f"boards/{board_id}.md": _board(board_id, board, member, _public(catalog, board_id))
        + footer
        for board_id, board in boards.items()
    }
    pages["index.md"] = _index(member) + footer
    return dict(sorted(pages.items()))


def release(catalog: Catalog) -> dict[str, str | bytes]:
    """The release assets: the export document and a zip of the pages, byte for byte stable."""
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zipped:
        for path, text in render(catalog).items():
            info = zipfile.ZipInfo(f"pages/{path}", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            zipped.writestr(info, text)
    return {
        "helia-platforms-export.json": export.render(export.document(catalog)),
        "helia-platforms-pages.zip": archive.getvalue(),
    }


def write(directory: Path, files: Mapping[str, str | bytes]) -> None:
    """Write each file under ``directory``; files already there and not written stay."""
    for path, content in files.items():
        target = directory / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content.encode("utf-8") if isinstance(content, str) else content)


def differences(directory: Path, files: Mapping[str, str | bytes]) -> list[str]:
    """Paths under ``directory`` that are missing, differ, or are not in ``files``."""
    found = []
    for path, content in files.items():
        expected = content.encode("utf-8") if isinstance(content, str) else content
        target = directory / path
        if not target.is_file() or target.read_bytes() != expected:
            found.append(path)
    if directory.is_dir():
        extra = (p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file())
        found += sorted(p for p in extra if p not in files)
    return found


def _public(catalog: Catalog, entry_id: str) -> Target:
    target = catalog.resolve(entry_id)
    if target.release_status != "public":
        raise PlatformError(
            f"{entry_id} is {target.release_status}; pages show public targets only"
        )
    return target


def _front(title: str, description: str) -> list[str]:
    return ["---", f"title: {title}", f"description: {description}", "---", ""]


def _table(header: Iterable[str], rows: Iterable[Iterable[Any]]) -> list[str]:
    header = list(header)
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return [*lines, ""]


def _aliases(entry: Mapping[str, Any]) -> list[str]:
    aliases = entry.get("aliases") or []
    return [f"Aliases: {', '.join(f'`{a}`' for a in aliases)}.", ""] if aliases else []


# ---- Soc pages ----------------------------------------------------------------------


def _soc(soc_id: str, soc: Mapping[str, Any], member: Mapping[str, Any]) -> str:
    lines = _front(soc_id, f"The {soc_id} Soc: cores, memory map, clocks and boot.")
    lines += [f"# {soc_id}", "", f"Series: `{soc['series']}`.", ""]
    lines += ["## Cores and NPUs", ""]
    lines += _table(
        ("Id", "Role", "Core", "Clock domain", "Programmed by"),
        (
            (
                c["id"],
                c["role"],
                c["core"],
                c["clock_domain"],
                _PROGRAMMED_BY[c.get("programmable_by")],
            )
            for c in soc["cores"]
        ),
    )
    if npus := soc.get("npus"):
        lines += _table(
            ("Id", "NPU", "MACs per cycle", "Driven by"),
            (
                (
                    n["id"],
                    f"{n['npu']['family']} {n['npu']['model']}",
                    n["npu"]["macs_per_cycle"],
                    n["driven_by"],
                )
                for n in npus
            ),
        )
    lines += ["## Memory map", ""]
    lines += _table(
        ("Region", "Base", "Size", "Technology", "Attachment"),
        (
            (
                name,
                f"`{r['base']:#010x}`" if "base" in r else "",
                size(r["size"]),
                r["technology"],
                r["attachment"],
            )
            for name, r in soc["memories"].items()
        ),
    )
    lines += ["## Clocks", ""]
    lines += _table(
        ("Domain", "Point", "MHz"),
        (
            (domain, point, p["mhz"])
            for domain, points in soc["clock_domains"].items()
            for point, p in points.items()
        ),
    )
    default = soc.get("default_operating_point")
    lines += _table(
        ("Operating point", "Domains", "Default"),
        (
            (
                name,
                ", ".join(f"{d} {p}" for d, p in op["domains"].items()),
                "yes" if name == default else "",
            )
            for name, op in soc.get("operating_points", {}).items()
        ),
    )
    if boot := soc.get("boot_configs"):
        lines += ["## Boot configurations", ""]
        lines += _table(
            ("Name", "Requires", "Application start", "Reserved", "Default"),
            (
                (
                    name,
                    b["requires"],
                    _app_start(b["app_start"]),
                    _reserved(b.get("reserved")),
                    "yes" if name == soc.get("default_boot") else "",
                )
                for name, b in boot.items()
            ),
        )
    parts = [p for p, e in member.get("parts", {}).items() if e["soc"] == soc_id]
    slots = [("the Soc", n, s) for n, s in soc.get("image_slots", {}).items()]
    slots += [
        (p, n, s) for p in parts for n, s in member["parts"][p].get("image_slots", {}).items()
    ]
    if slots:
        lines += [
            "## Image slots",
            "",
            "A part's slot replaces the Soc's slot of the same name.",
            "",
        ]
        lines += _table(
            ("Slot", "On", "Core", "Region", "Offset", "Size", "Supplier"),
            (
                (n, on, s["core"], s["region"], size(s["offset"]), size(s["size"]), s["supplier"])
                for on, n, s in slots
            ),
        )
    lines += ["## Implementations, parts and boards", ""]
    implementations = [
        i for i, e in member.get("implementations", {}).items() if e["soc"] == soc_id
    ]
    boards = [
        b
        for b, e in member.get("boards", {}).items()
        if e.get("part") in parts or e.get("implementation") in implementations
    ]
    lines += [
        f"- Implementations: {_list(implementations)}",
        f"- Parts: {_list(parts)}",
        f"- Boards: {_list(f'[{b}](../boards/{b}.md)' for b in boards)}",
        "",
    ]
    lines += _aliases(soc)
    return "\n".join(lines)


#: How a Soc page names each ``programmable_by`` (RFC 0002 multicore).
_PROGRAMMED_BY = {
    "customer": "customer",
    "vendor": "vendor only",
    "either": "customer or vendor",
    None: "no loadable image",
}


def _app_start(app_start: Mapping[str, Any]) -> str:
    if "region" in app_start:
        return f"{app_start['region']} + {size(app_start['offset'])}"
    return "; ".join(f"{core}: {_app_start(start)}" for core, start in app_start.items())


def _reserved(reserved: Mapping[str, Any] | None) -> str:
    return "; ".join(
        f"{name}: {r['region']} + {size(r['offset'])}, {size(r['size'])}"
        for name, r in (reserved or {}).items()
    )


def _list(items: Iterable[str]) -> str:
    items = list(items)
    return ", ".join(items) if items else "none"


# ---- board pages --------------------------------------------------------------------


def _carried(board: Mapping[str, Any], soc_id: str) -> str:
    """The line naming what a board carries: its Part, or an FPGA's Implementation (#104)."""
    kind, entry_id = (
        ("Part", board["part"]) if "part" in board else ("Implementation", board["implementation"])
    )
    return f"- {kind}: `{entry_id}`, of Soc [{soc_id}](../socs/{soc_id}.md)"


def _board(
    board_id: str, board: Mapping[str, Any], member: Mapping[str, Any], target: Target
) -> str:
    soc_id = target.soc.id
    lines = _front(board_id, f"The {board_id} board: its part, memories and derived values.")
    lines += [f"# {board_id}", ""]
    lines += [
        f"- Category: {board['category']}",
        _carried(board, soc_id),
        f"- Revision: {board.get('revision', 'not stated')}",
        f"- Provisioning: {board.get('provisioning', 'not stated')}",
        "",
    ]
    lines += ["## External memory", ""]
    devices = member.get("memory_devices", {})
    population = board.get("population", {})
    if population:
        lines += _table(
            ("Interface", "Device", "Technology", "Capacity", "Base"),
            (
                (
                    interface,
                    device,
                    devices[device]["technology"],
                    size(devices[device]["capacity"]),
                    _base(board, interface),
                )
                for interface, device in population.items()
            ),
        )
    else:
        lines += ["None populated.", ""]
    addons = [a for a, e in member.get("addons", {}).items() if board_id in e["fits_boards"]]
    compositions = [c for c, e in member.get("compositions", {}).items() if e["board"] == board_id]
    lines += [f"Add-ons that fit: {_list(addons)}. Compositions: {_list(compositions)}.", ""]
    lines += ["## Debug", ""]
    lines += [
        f"- J-Link device: {target.jlink_device or 'not stated'}",
        f"- Trace clock: {_mhz(target.trace_clock_mhz)}",
        *_cpufreq(target),
        *_ble_reset(target),
        "",
    ]
    lines += ["## Derived values", ""]
    lines += [f"Capabilities: {_list(sorted(target.capabilities))}.", ""]
    lines += _table(
        ("Operating point", "CPU MHz"),
        ((p.name, target.cpu_mhz(p.name)) for p in target.operating_points()),
    )
    try:
        usable = target.usable_nvm()
        address = f"`{target.flash_load_address():#010x}`"
    except PlatformError:
        usable, address = {}, "no boot configuration is selected"
    lines += [
        f"Usable NVM (core 0): {_list(f'{n} {size(b)}' for n, b in usable.items())}"
        f"{_set_aside(target, usable)}.",
        *(
            f"Only the vendor programs {c.id}, so it has no usable NVM."
            for c in target.soc.cores
            if c.programmable_by == "vendor"
        ),
        f"Flash load address (core 0): {address}.",
        "",
    ]
    lines += _aliases(board)
    return "\n".join(lines)


def _cpufreq(target: Target) -> list[str]:
    """J-Link's ``-cpufreq``, where the Soc's data gives one apart from the trace clock."""
    mhz = target.sdk.jlink_cpufreq_mhz if target.sdk else None
    if mhz is None:
        return []
    return [
        f"- J-Link's `-cpufreq`: {_mhz(mhz)}, not the {_mhz(target.trace_clock_mhz)} trace clock"
    ]


def _ble_reset(target: Target) -> list[str]:
    """The BLE controller's reset pad, on a board whose BSP defines one."""
    pad = target.ble_reset_gpio
    return [] if pad is None else [f"- BLE controller reset: GPIO {pad}"]


def _set_aside(target: Target, usable: Mapping[str, int]) -> str:
    """What ``usable_nvm()`` leaves out of core 0's regions: reservations, other cores' slots."""
    core = target.soc.cores[0].id
    found = [
        f"boot reservation {r.purpose} ({r.region} + {size(r.offset)}, {size(r.size)})"
        for r in (target.boot.reserved if target.boot else ())
        if r.region in usable
    ]
    found += [
        f"{s.supplier}-supplied image slot {s.name} of {s.core} "
        f"({s.region} + {size(s.offset)}, {size(s.size)})"
        for s in target.image_slots.values()
        if s.core != core and s.region in usable
    ]
    return f", after {' and '.join(found)}" if found else ""


def _base(board: Mapping[str, Any], interface: str) -> str:
    base = board.get("interfaces", {}).get(interface, {}).get("aperture_base")
    return f"`{base:#010x}`" if base is not None else "no base"


def _mhz(value: float | None) -> str:
    if value is None:
        return "core clock"
    return f"{int(value) if float(value).is_integer() else value} MHz"


# ---- the index ----------------------------------------------------------------------


def _index(member: Mapping[str, Any]) -> str:
    lines = _front("Ambiq Socs and boards", "Every public Soc and board in helia-platforms.")
    lines += ["# Ambiq Socs and boards", ""]
    parts = member.get("parts", {})
    impls = member.get("implementations", {})
    series: dict[str, list[str]] = {}
    for soc_id, soc in member.get("socs", {}).items():
        series.setdefault(soc["series"], []).append(soc_id)
    for name, soc_ids in sorted(series.items()):
        lines += [f"## {name}", ""]
        for soc_id in sorted(soc_ids):
            boards = sorted(
                b
                for b, e in member.get("boards", {}).items()
                if (parts[e["part"]] if "part" in e else impls[e["implementation"]])["soc"]
                == soc_id
            )
            links = ", ".join(f"[{b}](boards/{b}.md)" for b in boards) or "no boards"
            lines.append(f"- [{soc_id}](socs/{soc_id}.md): {links}")
        lines.append("")
    return "\n".join(lines)
