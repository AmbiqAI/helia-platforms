"""``check-sources``: the built-in catalog against the committed snapshots (ADR 0006 section 3)."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from helia_platforms import model
from helia_platforms.catalog import Catalog
from helia_platforms.errors import PlatformError

SDK, NSX, ZEPHYR = "nsx-ambiq-sdk.json", "neuralspotx.json", "zephyr.json"
#: Repositories the snapshots hold; an ``sdk`` record citing one must cite a held revision.
SNAPSHOTTED = frozenset(
    {
        "AmbiqAI/nsx-ambiq-sdk",
        "AmbiqAI/neuralspotx",
        "zephyrproject-rtos/zephyr",
        "zephyrproject-rtos/hal_ambiq",
    }
)
#: The SDK's spellings of catalog values (``NSX_SOC_ARCH_CLASS``, ``NSX_SOC_PMU_TIER``).
_ARCH = {"armv6_m": "armv6-m", "armv7e_m": "armv7e-m", "armv8_1m": "armv8.1-m"}
_PMU = {"none": "dwt"}
#: Each region's base and size defines in ``am_reg_base_addresses.h``, per Soc; a size of
#: ``""`` means the header has no size define for that region.
REGISTERS: dict[str, dict[str, tuple[str, str]]] = {
    "apollo510": {
        "itcm": ("ITCM_BASEADDR", "ITCM_MAX_SIZE"),
        "dtcm": ("DTCM_BASEADDR", "DTCM_MAX_SIZE"),
        "ssram": ("SSRAM_BASEADDR", "SSRAM_MAX_SIZE"),
        "mram": ("MRAM_BASEADDR", "MRAM_MAX_SIZE"),
    },
    "apollo4p": {
        "tcm": ("TCM_BASEADDR", "TCM_MAX_SIZE"),
        "ssram0": ("SSRAM0_BASEADDR", "SSRAM0_MAX_SIZE"),
        "extram": ("EXTRAM_BASEADDR", "EXTRAM_MAX_SIZE"),
        "ssram1": ("SSRAM1_BASEADDR", "SSRAM1_MAX_SIZE"),
        "mram": ("MRAM_BASEADDR", "MRAM_MAX_SIZE"),
    },
    "apollo4l": {
        "tcm": ("TCM_BASEADDR", "TCM_MAX_SIZE"),
        "ssram0": ("SSRAM0_BASEADDR", "SSRAM0_MAX_SIZE"),
        "mram": ("MRAM_BASEADDR", "MRAM_MAX_SIZE"),
    },
    **{
        soc: {
            "dtcm": ("DTCM_BASEADDR", "DTCM_MAX_SIZE"),
            "ssram": ("SSRAM_BASEADDR", "SSRAM_MAX_SIZE"),
            "mram": ("MRAM_BASEADDR", "MRAM_MAX_SIZE"),
        }
        for soc in ("apollo510L", "apollo330P")
    },
    # SRAM_BASEADDR is the start of TCM, not of the catalog's sram region, so it is left out.
    "apollo3": {"tcm": ("TCM_BASEADDR", "TCM_MAX_SIZE"), "flash": ("FLASH_BASEADDR", "")},
    "apollo3p": {"tcm": ("TCM_BASEADDR", "TCM_MAX_SIZE"), "flash": ("FLASH_BASEADDR", "")},
}
#: The ``am_hal_flash.h`` sizes Apollo3 states and the regions whose sizes add up to each;
#: its SRAM size covers TCM and SRAM together.
HAL_FLASH: dict[str, dict[str, tuple[str, ...]]] = {
    soc: {"AM_HAL_FLASH_TOTAL_SIZE": ("flash",), "AM_HAL_FLASH_SRAM_SIZE": ("tcm", "sram")}
    for soc in ("apollo3", "apollo3p")
}
#: apollo510b builds against mcu/apollo510, so its snapshot reads apollo510's header.
REGISTERS["apollo510b"] = dict(REGISTERS["apollo510"])
#: CMake's boolean constants, compared case-insensitively; a non-zero number is also true
#: (CMake reads one with ``strtod``, so in decimal or hexadecimal).
_CMAKE_TRUE = {"1", "ON", "YES", "TRUE", "Y"}
_CMAKE_FALSE = {"0", "OFF", "NO", "FALSE", "N", "IGNORE", "NOTFOUND", ""}
_NUMBER = re.compile(r"[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?")
_HEX = re.compile(r"[+-]?0[xX]([0-9a-fA-F]+\.?[0-9a-fA-F]*|\.[0-9a-fA-F]+)([pP][+-]?\d+)?")
#: Apollo names its apertures MSPI<n>; atomiq110 names them XSPI<n>, with secure aliases (#120).
_APERTURE = re.compile(r"^((MSPI|XSPI)(\d+))_APERTURE_START(_SECURE)?_ADDR$")
#: The controller id each aperture prefix belongs to: atomiq110's CMSIS blocks are XSPIMC<n>.
_CONTROLLER = {"MSPI": "mspi", "XSPI": "xspimc"}
_REPO = re.compile(r"^repo:(?P<repo>[^@]+)@(?P<rev>[^:]+):")
MISSING = "in the catalog"


@dataclass(frozen=True)
class Finding:
    """One disagreement, at a key path of one snapshot file."""

    snapshot: str
    at: tuple[str, ...]
    rule: str
    message: str


@dataclass(frozen=True)
class Exception_:
    snapshot: str
    at: tuple[str, ...]
    rule: str
    reason: str
    issue: str

    def covers(self, finding: Finding) -> bool:
        return (
            finding.snapshot == self.snapshot
            and finding.at[: len(self.at)] == self.at
            and finding.rule == self.rule
        )


@dataclass(frozen=True)
class Result:
    findings: tuple[Finding, ...]  # not covered by an exception
    excepted: tuple[tuple[Finding, Exception_], ...]
    stale: tuple[Exception_, ...]  # covers nothing that was compared

    @property
    def ok(self) -> bool:
        return not self.findings and not self.stale


def check(catalog: Catalog, directory: Path) -> Result:
    """Compare ``catalog`` with the snapshots in ``directory`` and apply its exceptions list."""
    snapshots = {name: json.loads((directory / name).read_text()) for name in (SDK, NSX, ZEPHYR)}
    found = list(_Comparison(catalog, snapshots).findings())
    exceptions = load_exceptions(directory / "exceptions.yaml")
    missing = [f for f in found if f.rule == MISSING]
    left, excepted, used = [], [], set()
    for finding in found:
        covers = [e for e in exceptions if e.covers(finding)]
        if covers:
            excepted.append((finding, covers[0]))
            used |= {id(e) for e in covers}  # an overlapping exception is in use too
        else:
            left.append(finding)
    # Under an id the catalog lacks nothing is compared, so only a path the snapshot lacks is stale.
    stale = [
        e
        for e in exceptions
        if id(e) not in used
        and not (
            _resolves(snapshots.get(e.snapshot), e.at)
            and any(m.snapshot == e.snapshot and e.at[: len(m.at)] == m.at for m in missing)
        )
    ]
    return Result(tuple(left), tuple(excepted), tuple(stale))


def load_exceptions(path: Path) -> list[Exception_]:
    import yaml  # noqa: PLC0415 (importing the CLI reads no YAML)

    entries = (yaml.safe_load(path.read_text()) or {}).get("exceptions") or []
    return [
        Exception_(e["snapshot"], tuple(e["at"]), e["rule"], e["reason"], str(e["issue"]))
        for e in entries
    ]


def render(result: Result) -> str:
    lines = [f"{f.snapshot}: {'.'.join(f.at)}: {f.rule}: {f.message}" for f in result.findings]
    lines += [
        f"{e.snapshot}: {'.'.join(e.at)}: {e.rule}: stale exception (covers no finding)"
        for e in result.stale
    ]
    lines.append(
        f"{len(result.findings)} disagreements, {len(result.excepted)} excepted, "
        f"{len(result.stale)} stale exceptions"
    )
    return "\n".join(lines) + "\n"


class _Comparison:
    def __init__(self, catalog: Catalog, snapshots: Mapping[str, Any]) -> None:
        self.catalog = catalog
        self.sdk = snapshots[SDK]["socs"]
        self.zephyr = snapshots[ZEPHYR]["boards"]
        self.revisions: dict[str, set[str]] = {}
        for snapshot in snapshots.values():
            for source in snapshot["metadata"]["sources"]:
                self.revisions.setdefault(source["repository"], set()).add(source["revision"])
        self.socs = {s.id.casefold(): s for s in catalog.socs()}

    def findings(self) -> Iterator[Finding]:
        for name, block in self.sdk.items():
            soc = self.socs.get(name.casefold())
            if soc is None:
                yield Finding(SDK, ("socs", name), MISSING, f"no soc {name!r}")
            else:
                yield from self.sdk_soc(name, block, soc)
        for name, block in self.zephyr.items():
            yield from self.zephyr_board(name, block)
        yield from self.revisions_cited()

    # -- nsx-ambiq-sdk -------------------------------------------------------------------

    def sdk_soc(self, name: str, block: Mapping[str, Any], soc: model.Soc) -> Iterator[Finding]:
        at = ("socs", name, "facts", "values")
        facts = block["facts"]["values"]
        core = soc.cores[0]
        ip = self.catalog._entry("cores", core.core)
        sdk = soc.sdk or model.SdkFacts()
        build = sdk.build or model.BuildFacts()
        equal = [
            ("series", "NSX_SOC_SERIES", soc.series, _one(facts, "NSX_SOC_SERIES")),
            ("core", "NSX_SOC_CORE", ip.id, _one(facts, "NSX_SOC_CORE")),
            ("arch", "NSX_SOC_ARCH_CLASS", ip.arch, _spell(_ARCH, facts, "NSX_SOC_ARCH_CLASS")),
            ("pmu", "NSX_SOC_PMU_TIER", ip.pmu, _spell(_PMU, facts, "NSX_SOC_PMU_TIER")),
            ("dsp", "NSX_SOC_HAS_DSP", ip.has_dsp_extension, _flag(facts, "NSX_SOC_HAS_DSP")),
            ("mve", "NSX_SOC_HAS_MVE", core.options.mve != "none", _flag(facts, "NSX_SOC_HAS_MVE")),
            ("fpu", "NSX_SOC_HAS_FPU", core.options.fpu != "none", _flag(facts, "NSX_SOC_HAS_FPU")),
            ("npu", "NSX_SOC_CAPABILITIES", bool(soc.npus), "npu" in facts["NSX_SOC_CAPABILITIES"]),
            ("abi", "NSX_ABI_FLAGS", build.abi, _one(facts, "NSX_ABI_FLAGS")),
            ("float_abi", "NSX_FLOAT_ABI", build.float_abi, _one(facts, "NSX_FLOAT_ABI")),
            ("trace clock", "NSX_SEGGER_CPUFREQ", sdk.trace_clock_mhz, _mhz(facts)),
        ]
        if (fpu := _one(facts, "NSX_FPU")) not in (None, ""):
            equal.append(("fpu", "NSX_FPU", core.options.fpu, fpu))
        yield from _equal(
            SDK,
            ("socs", name, "cmsis", "values", "__FPU_DP"),
            "fpu_dp",
            core.options.fpu_dp,
            bool(block["cmsis"]["values"].get("__FPU_DP", 0)),  # CMSIS reads an absent one as 0
        )
        for rule, key, ours, theirs in equal:
            yield from _equal(SDK, (*at, key), rule, ours, theirs)
        if sdk.c_define not in facts.get("NSX_SOC_COMPILE_DEFINITIONS", []):
            yield Finding(
                SDK,
                (*at, "NSX_SOC_COMPILE_DEFINITIONS"),
                "c_define",
                f"{sdk.c_define!r} is not among the compile definitions",
            )
        if (address := _one(facts, "NSX_SEGGER_PF_ADDR")) is not None:
            try:
                ours: int | str = self.catalog.resolve(soc.id).flash_load_address()
            except PlatformError as exc:
                ours = str(exc)
            yield from _equal(
                SDK, (*at, "NSX_SEGGER_PF_ADDR"), "flash load address", ours, int(address, 16)
            )
        yield from self.registers(name, block, soc)
        yield from self.hal_flash(name, block, soc)
        yield from self.containment(
            SDK, ("socs", name, "linker"), _linker_regions(block), soc, _apertures(block, soc)
        )

    def hal_flash(self, name: str, block: Mapping[str, Any], soc: model.Soc) -> Iterator[Finding]:
        """Each ``HAL_FLASH`` size against its regions; an absent define or region is a finding."""
        defines = block.get("flash", {}).get("values", {})
        sizes = {r.name: r.size for r in soc.memories}
        for define, regions in HAL_FLASH.get(soc.id, {}).items():
            at = ("socs", name, "flash", "values", define)
            lacking = [r for r in regions if r not in sizes]
            if define not in defines:
                yield Finding(SDK, at, "flash header", f"the snapshot has no {define}")
            elif lacking:
                yield Finding(SDK, at, "flash header", _no_region(soc, lacking))
            else:
                ours = sum(sizes[r] for r in regions)
                yield from _equal(SDK, at, "flash header", ours, defines[define])

    def registers(self, name: str, block: Mapping[str, Any], soc: model.Soc) -> Iterator[Finding]:
        """Each ``REGISTERS`` define against its region; an absent define or region is a finding."""
        defines = block["registers"]["values"]
        at = ("socs", name, "registers", "values")
        regions = {r.name: r for r in soc.memories}
        for region_name, names in REGISTERS.get(soc.id, {}).items():
            region = regions.get(region_name)
            if region is None:
                yield Finding(SDK, (*at, names[0]), "register", _no_region(soc, [region_name]))
                continue
            for define, ours in zip(names, (region.base, region.size), strict=False):
                if not define:
                    continue  # the header has no such define
                if define not in defines:
                    yield Finding(SDK, (*at, define), "register", f"{define} is not defined")
                    continue
                yield from _equal(SDK, (*at, define), "register", ours, defines[define])

    def containment(
        self,
        snapshot: str,
        at: tuple[str, ...],
        regions: Iterable[tuple[tuple[str, ...], int, int | None]],
        soc: model.Soc,
        apertures: list[tuple[int, int]],
    ) -> Iterator[Finding]:
        """Each region inside one gap-free run of physical regions, or an external aperture.

        A region with no length or a zero one (an unsized or ``EMPTY 0`` scatter region) is
        checked by its origin; a negative length is a finding.
        """
        runs = _runs(soc)
        for path, base, size in regions:
            if size is not None and size < 0:
                yield Finding(
                    snapshot, (*at, *path), "region containment", f"{base:#x} has length {size}"
                )
                continue
            end = base + (size or 1)
            if any(lo <= base and end <= hi for lo, hi in apertures):
                continue  # external memory, which ADR 0006 does not compare
            if not any(lo <= base and end <= hi for lo, hi in runs):
                span = f"{base:#x} (no length)" if size is None else f"{base:#x}+{size:#x}"
                yield Finding(
                    snapshot,
                    (*at, *path),
                    "region containment",
                    f"{span} lies in no gap-free run of {soc.id}'s regions",
                )

    def _sdk_name(self, soc: str) -> str | None:
        return next((k for k in self.sdk if k.casefold() == soc.casefold()), None)

    # -- Zephyr --------------------------------------------------------------------------

    def zephyr_board(self, name: str, block: Mapping[str, Any]) -> Iterator[Finding]:
        target = self._board(name)
        if target is None:
            yield Finding(ZEPHYR, ("boards", name), MISSING, f"no board {name!r}")
            return
        at = ("boards", name)
        soc = block["board"]["values"]["soc"]
        yield from _equal(
            ZEPHYR,
            (*at, "board", "values", "soc"),
            "board soc",
            target.soc.id.casefold(),
            soc.casefold(),
        )
        nodes = block["devicetree"]["memory"]
        regions = [((node,), n["base"], n["size"]) for node, n in nodes.items()]
        sdk_name = self._sdk_name(soc)
        apertures = _apertures(self.sdk[sdk_name], target.soc) if sdk_name is not None else []
        yield from self.containment(
            ZEPHYR, (*at, "devicetree", "memory"), regions, target.soc, apertures
        )

    # -- provenance ----------------------------------------------------------------------

    def revisions_cited(self) -> Iterator[Finding]:
        """Each ``sdk`` record citing a snapshotted repository cites a revision held."""
        seen: set[str] = set()
        for (kind, entry_id), tree in sorted(self.catalog._trees.items()):
            for path, record in sorted(tree.records.items()):
                if not record or record.get("status") != "sdk":
                    continue
                for source in record.get("source", ()):
                    match = _REPO.match(source)
                    if not match or match["repo"] not in SNAPSHOTTED or source in seen:
                        continue
                    seen.add(source)
                    if match["rev"] not in self.revisions.get(match["repo"], set()):
                        where = ".".join((kind, entry_id, *path))
                        yield Finding(
                            _snapshot_of(match["repo"]),
                            ("metadata", "sources"),
                            "sdk revision",
                            f"{where} cites {match['repo']}@{match['rev']}, "
                            "which no snapshot holds",
                        )

    def _board(self, name: str) -> Any:
        try:
            target = self.catalog.resolve(name)
        except PlatformError:
            return None
        return target if target.kind == "board" else None


def _equal(
    snapshot: str, at: tuple[str, ...], rule: str, ours: Any, theirs: Any
) -> Iterator[Finding]:
    if ours != theirs:
        yield Finding(snapshot, at, rule, f"catalog {_show(ours)}, snapshot {_show(theirs)}")


def _show(value: Any) -> str:
    return (
        f"{value:#x}"
        if isinstance(value, int) and not isinstance(value, bool) and value > 9
        else repr(value)
    )


def _one(facts: Mapping[str, list[str]], key: str) -> str | None:
    values = facts.get(key)
    return values[0] if values else None


def _spell(spelling: Mapping[str, str], facts: Mapping[str, list[str]], key: str) -> str | None:
    value = _one(facts, key)
    return spelling.get(value, value) if value is not None else None


def _flag(facts: Mapping[str, list[str]], key: str) -> bool | str | None:
    """``key`` as CMake's ``if(<constant>)`` reads it; any other value is returned as written."""
    value = _one(facts, key)
    if value is None:
        return None
    word = value.upper()
    if word in _CMAKE_TRUE or word in _CMAKE_FALSE or word.endswith("-NOTFOUND"):
        return word in _CMAKE_TRUE
    if _HEX.fullmatch(value):
        return float.fromhex(value) != 0
    return float(value) != 0 if _NUMBER.fullmatch(value) else value


def _mhz(facts: Mapping[str, list[str]]) -> float | None:
    hz = _one(facts, "NSX_SEGGER_CPUFREQ")
    if hz is None:
        return None
    whole, rest = divmod(int(hz), 1_000_000)
    return whole if rest == 0 else int(hz) / 1_000_000


def _resolves(data: Any, at: tuple[str, ...]) -> bool:
    """True when every key of ``at`` is in ``data``, one level per key."""
    for key in at:
        if not isinstance(data, Mapping) or key not in data:
            return False
        data = data[key]
    return True


def _no_region(soc: model.Soc, names: Iterable[str]) -> str:
    return f"the catalog's {soc.id} has no region {', '.join(map(repr, names))}"


def _linker_regions(
    block: Mapping[str, Any],
) -> Iterator[tuple[tuple[str, ...], int, int | None]]:
    for toolchain, linker in block["linker"].items():
        for script, regions in linker["scripts"].items():
            for region, r in regions.items():
                yield (toolchain, "scripts", script, region), r["origin"], r.get("length")


def _apertures(block: Mapping[str, Any], soc: model.Soc) -> list[tuple[int, int]]:
    """The XIP apertures of ``soc``'s memory controllers that the header defines, as ``[lo, hi)``.

    ``*_APERTURE_END_ADDR`` is already exclusive: MSPI1's end is MSPI2's start. A secure
    alias (``*_APERTURE_START_SECURE_ADDR``) is an aperture of its own. A shared header's
    aperture for a controller the Soc lacks (apollo510b's MSPI2 and MSPI3) is not external memory.
    """
    defines = block["registers"]["values"]
    controllers = set(soc.memory_controllers)
    found = []
    for name, start in defines.items():
        match = _APERTURE.match(name)
        if match and f"{_CONTROLLER[match[2]]}{match[3]}" in controllers:
            end = f"{match[1]}_APERTURE_END{match[4] or ''}_ADDR"
            if end in defines:
                found.append((start, defines[end]))
    return found


def _runs(soc: model.Soc) -> list[tuple[int, int]]:
    """Gap-free runs of the Soc's regions, each alias of a region counted as its own range."""
    spans = sorted(
        (base, base + r.size)
        for r in soc.memories
        for base in (r.base, *r.alternate_bases)
        if base is not None
    )
    runs: list[list[int]] = []
    for lo, hi in spans:
        if runs and lo <= runs[-1][1]:
            runs[-1][1] = max(runs[-1][1], hi)
        else:
            runs.append([lo, hi])
    return [(lo, hi) for lo, hi in runs]


def _snapshot_of(repository: str) -> str:
    return {"AmbiqAI/nsx-ambiq-sdk": SDK, "AmbiqAI/neuralspotx": NSX}.get(repository, ZEPHYR)
