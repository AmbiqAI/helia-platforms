"""The resolved view of a board, part, implementation or Soc (RFC 0002 "helia_platforms.target")."""

from __future__ import annotations

import functools
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, TypeVar

from helia_platforms import model
from helia_platforms.catalog import Catalog, _expanded_access
from helia_platforms.errors import PlatformError

Kind = Literal["board", "part", "implementation", "soc"]
#: Technologies a region can hold non-volatile code in (``usable_nvm``).
_NVM = frozenset({"mram", "rram", "flash", "nvm"})


@dataclass(frozen=True)
class IsaFeatures:
    """ISA features of one core, from its IP block and options (RFC 0002 "Derived capabilities")."""

    has_dsp: bool
    has_mve: bool
    mve_flavour: Literal["none", "int", "fp"]
    supports_fp16: bool
    supports_fp32: bool
    supports_fp64: bool
    has_pmu: bool
    pmu_kind: str


@dataclass(frozen=True)
class Target:
    """One name resolved: the Soc as realized, plus what the part, board and add-ons add.

    Build it with ``resolve()``; the fields are the reference chain and the effective
    status, and the methods answer RFC 0002's question surface.
    """

    id: str
    kind: Kind
    soc: model.Soc
    implementation: model.Implementation | None
    part: model.Part | None
    board: model.Board | None
    origin: Literal["builtin", "overlay"]
    release_status: model.ReleaseStatus
    addons: tuple[model.AddOn, ...]
    aliases: tuple[str, ...]
    boot: model.BootConfig | None
    _catalog: Catalog = field(repr=False, compare=False)
    _devices: tuple[tuple[model.MemoryInterface, model.MemoryDevice], ...] = field(
        default=(), repr=False, compare=False
    )

    # -- structure ----------------------------------------------------------------------

    @property
    def core(self) -> model.Core:
        """Core 0's IP block."""
        return self._core_ip(self.soc.cores[0])

    @property
    def core_options(self) -> model.CoreOptions:
        return self.soc.cores[0].options

    @property
    def npu(self) -> model.NpuInstance | None:
        """NPU 0, or ``None`` when the target has none."""
        return self.soc.npus[0] if self.soc.npus else None

    @property
    def category(self) -> str | None:
        return self.board.category if self.board else None

    def cores(self, role: str | None = None) -> tuple[model.CoreInstance, ...]:
        return tuple(c for c in self.soc.cores if role in (None, c.role))

    def npus(self) -> tuple[model.NpuInstance, ...]:
        return self.soc.npus

    def accelerators(self) -> tuple[model.AcceleratorInstance, ...]:
        return self.soc.accelerators

    def isa(self, core: int | str = 0) -> IsaFeatures:
        instance = self._core(core)
        ip, options = self._core_ip(instance), instance.options
        return IsaFeatures(
            has_dsp=ip.has_dsp_extension,
            has_mve=options.mve != "none",
            mve_flavour=options.mve,
            supports_fp16=options.mve == "fp",
            supports_fp32=options.fpu != "none",
            supports_fp64=options.fpu_dp,
            has_pmu=ip.pmu != "none",
            pmu_kind=ip.pmu,
        )

    @functools.cached_property
    def capabilities(self) -> frozenset[str]:
        """Derived capability names (core 0 and the board's memories), lowercase and stable."""
        isa = self.isa()
        found = {
            "dsp": isa.has_dsp,
            "mve": isa.has_mve,
            "mve_fp": isa.mve_flavour == "fp",
            "fp16": isa.supports_fp16,
            "fp32": isa.supports_fp32,
            "fp64": isa.supports_fp64,
            "pmu": isa.has_pmu,
            "npu": self.npu is not None,
        }
        found |= {r.technology: True for r in self.external_memories()}
        return frozenset(name for name, present in found.items() if present)

    # -- memory ---------------------------------------------------------------------------

    @functools.cached_property
    def _access(self) -> tuple[model.Access, ...]:
        return _expanded_access(self.soc)

    def reachable(self, master: str, target: str) -> model.Access | None:
        """``master``'s ``Access`` entry for ``target`` (an external region's: its controller's)."""
        controller = self._controller_of(target)
        key = controller if controller is not None else target
        return next((a for a in self._access if a.master == master and a.target == key), None)

    @functools.cached_property
    def _external(self) -> tuple[tuple[model.MemoryRegion, str], ...]:
        """External regions with their interface's controller, named ``<technology><n>``."""
        counts: dict[str, int] = {}
        regions = []
        for interface, device in self._devices:
            n = counts.get(device.technology, 0)
            counts[device.technology] = n + 1
            region = model.MemoryRegion(
                name=f"{device.technology}{n}",
                technology=device.technology,
                attachment="external",
                size=device.capacity,
                base=interface.aperture_base,
                characterization=device.characterization,
                provenance=device.provenance,
                field_provenance=device.field_provenance,
            )
            regions.append((region, interface.controller))
        return tuple(regions)

    def external_memories(self) -> tuple[model.MemoryRegion, ...]:
        """Devices the board and its add-ons populate, at their interfaces' aperture bases."""
        return tuple(region for region, _ in self._external)

    def has_external_memory(self, technology: str | None = None) -> bool:
        return any(technology in (None, r.technology) for r in self.external_memories())

    def memories(self, core: int | str = 0) -> tuple[model.MemoryRegion, ...]:
        """Regions ``core`` has a ``direct`` entry for, then external regions it reaches."""
        master = self._core(core).id
        direct = {a.target for a in self._access if a.master == master and a.access == "direct"}
        own = tuple(r for r in self.soc.memories if r.name in direct)
        return own + tuple(r for r, controller in self._external if controller in direct)

    def placement_ranges(self, core: int | str = 0) -> Mapping[str, tuple[int, int]]:
        """``(base, size)`` of each region ``core`` reaches; raises for a region with no base."""
        ranges = {}
        for region in self.memories(core):
            if region.base is None:
                raise PlatformError(f"{self.id}: region {region.name!r} has no base")
            ranges[region.name] = (region.base, region.size)
        return MappingProxyType(ranges)

    def region(self, name: str) -> model.MemoryRegion:
        """A region by name; on an FVP, also a Soc region one of its regions stands in for."""
        for region in (*self.soc.memories, *self.external_memories()):
            if region.name == name:
                return region
        for region in self.soc.memories:
            if name in region.stands_in_for:
                return region
        raise PlatformError(f"{self.id} has no region {name!r}")

    def has_region(
        self,
        name: str | None = None,
        *,
        technology: str | None = None,
        attachment: str | None = None,
    ) -> bool:
        return any(
            name in (None, r.name)
            and technology in (None, r.technology)
            and attachment in (None, r.attachment)
            for r in (*self.soc.memories, *self.external_memories())
        )

    def classify_address(self, address: int, master: int | str = 0) -> str | None:
        """The region at ``address`` as ``master`` sees it, or ``None``."""
        who = self._master(master)
        for region in (*self.soc.memories, *self.external_memories()):
            entry = self.reachable(who, region.name)
            bases = [region.base, *region.alternate_bases]
            if entry is not None and entry.address is not None:
                bases = [entry.address]
            if any(b is not None and b <= address < b + region.size for b in bases):
                return region.name
        return None

    # -- clocks ---------------------------------------------------------------------------

    @property
    def default_operating_point(self) -> model.OperatingPoint | None:
        name = self.soc.default_operating_point
        return None if name is None else self._system_point(name)

    def operating_points(
        self, domain: str | None = None
    ) -> tuple[model.OperatingPoint, ...] | tuple[model.DomainPoint, ...]:
        """System operating points, or the points of one clock domain."""
        if domain is None:
            return self.soc.operating_points
        return self._domain(domain).points

    def operating_point(
        self, name: str | None = None, *, domain: str | None = None
    ) -> model.OperatingPoint | model.DomainPoint:
        """A system point by name (default: the default point), or one domain's point.

        For a domain with no ``name``, the point the default system point selects.
        """
        if domain is not None:
            if name is None:
                default = self._system_point(None)
                name = default.domains.get(domain)
            return self._domain_point(domain, name)
        return self._system_point(name)

    def cpu_mhz(self, point: str | None = None, core: int | str = 0) -> int:
        return self._mhz(self._core(core).clock_domain, point)

    def npu_mhz(self, point: str | None = None, npu: int | str = 0) -> int:
        return self._mhz(self._npu(npu).clock_domain, point)

    def npu_clocks(self, npu: int | str = 0) -> Mapping[str, int]:
        """That NPU's clock in each system operating point that sets it, by point name."""
        domain = self._npu(npu).clock_domain
        points = self.soc.operating_points
        return MappingProxyType(
            {p.name: self._mhz(domain, p.name) for p in points if domain in p.domains}
        )

    # -- boot -----------------------------------------------------------------------------

    def boot_configs(self) -> tuple[model.BootConfig, ...]:
        return tuple(self.soc.boot_configs.values())

    def flash_load_address(self, core: int | str = 0) -> int:
        """Base of the core's ``app_start`` region in the selected boot, plus its offset."""
        start = self._app_start(core)
        base = self.region(start.region).base
        if base is None:
            raise PlatformError(f"{self.id}: region {start.region!r} has no base")
        return base + start.offset

    def usable_nvm(self, core: int | str = 0) -> Mapping[str, int]:
        """Bytes per non-volatile region ``core`` reaches, less reservations and others' slots."""
        instance = self._core(core)
        taken: dict[str, int] = {}
        for reservation in self.boot.reserved if self.boot else ():
            taken[reservation.region] = taken.get(reservation.region, 0) + reservation.size
        slots = self.part.image_slots.values() if self.part else ()
        for slot in slots:
            if slot.core != instance.id:
                taken[slot.region] = taken.get(slot.region, 0) + slot.size
        return MappingProxyType(
            {
                r.name: r.size - taken.get(r.name, 0)
                for r in self.memories(core)
                if r.technology in _NVM and r.attachment != "external"
            }
        )

    # -- debug and SDK ----------------------------------------------------------------------

    @property
    def jlink_device(self) -> str | None:
        """The board's name, else the implementation's, else the part's."""
        for owner in (self.board, self.implementation, self.part):
            if owner is not None and owner.jlink_device is not None:
                return owner.jlink_device
        return None

    @property
    def trace_clock_mhz(self) -> float | None:
        """The board's measured trace clock, else the implementation's, else the SDK's."""
        for owner in (self.board, self.implementation):
            if owner is not None and owner.trace_clock_mhz is not None:
                return owner.trace_clock_mhz
        return self.soc.sdk.trace_clock_mhz if self.soc.sdk else None

    @property
    def sdk(self) -> model.SdkFacts | None:
        return self.soc.sdk

    # -- helpers --------------------------------------------------------------------------

    def _core(self, core: int | str) -> model.CoreInstance:
        return _pick(self.soc.cores, core, f"{self.id}: no core")

    def _npu(self, npu: int | str) -> model.NpuInstance:
        return _pick(self.soc.npus, npu, f"{self.id}: no NPU")

    def _master(self, master: int | str) -> str:
        return self._core(master).id if isinstance(master, int) else master

    def _core_ip(self, instance: model.CoreInstance) -> model.Core:
        return self._catalog._entry("cores", instance.core)

    def _controller_of(self, name: str) -> str | None:
        return next((c for r, c in self._external if r.name == name), None)

    def _domain(self, domain: str) -> model.ClockDomain:
        found = next((d for d in self.soc.clock_domains if d.id == domain), None)
        if found is None:
            raise PlatformError(f"{self.id} has no clock domain {domain!r}")
        return found

    def _domain_point(self, domain: str, name: str | None) -> model.DomainPoint:
        point = next((p for p in self._domain(domain).points if p.name == name), None)
        if point is None:
            raise PlatformError(f"{self.id}: domain {domain!r} has no point {name!r}")
        return point

    def _system_point(self, name: str | None) -> model.OperatingPoint:
        name = name if name is not None else self.soc.default_operating_point
        if name is None:
            raise PlatformError(f"{self.id} has no default operating point; name one")
        point = next((p for p in self.soc.operating_points if p.name == name), None)
        if point is None:
            raise PlatformError(f"{self.id} has no operating point {name!r}")
        return point

    def _mhz(self, domain: str, point: str | None) -> int:
        system = self._system_point(point)
        if domain not in system.domains:
            raise PlatformError(
                f"{self.id}: operating point {system.name!r} sets no {domain!r} clock"
            )
        return round(self._domain_point(domain, system.domains[domain]).mhz)

    def _app_start(self, core: int | str) -> model.AppStart:
        instance = self._core(core)
        if self.boot is None:
            raise PlatformError(f"{self.id} has no boot configuration")
        start = self.boot.app_start.get(instance.id)
        if start is None:
            raise PlatformError(
                f"{self.id}: boot {self.boot.name!r} has no app_start for {instance.id!r}"
            )
        return start


_Unit = TypeVar("_Unit", model.CoreInstance, model.NpuInstance)


def _pick(items: tuple[_Unit, ...], key: int | str, missing: str) -> _Unit:
    if isinstance(key, int):
        if 0 <= key < len(items):
            return items[key]
    else:
        for item in items:
            if item.id == key:
                return item
    raise PlatformError(f"{missing} {key!r}")
