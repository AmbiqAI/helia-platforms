"""The runtime model (RFC 0002, "helia_platforms.model"; ADR 0002 section 4).

Every type is a frozen, slotted, keyword-only dataclass. Sequences are
tuples and mappings are read-only ``MappingProxyType`` views, so instances
are immutable and unhashable; tools key caches by id. A class that carries
facts has ``provenance`` (its record) and ``field_provenance`` (per-value
records that differ from it, keyed by path relative to the object).
"""

from __future__ import annotations

import datetime
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, ClassVar, Literal

ReleaseStatus = Literal["public", "embargoed"]
Status = Literal["datasheet", "sdk", "measured", "fitted", "derived", "unverified"]


def _empty() -> Mapping[str, Any]:
    return MappingProxyType({})


_frozen = dataclass(frozen=True, slots=True, kw_only=True)


@_frozen
class Provenance:
    """ADR 0003's record for a fact or a group of facts."""

    status: Status
    source: tuple[str, ...] = ()
    verified_on: datetime.date | None = None
    verified_by: str | None = None
    notes: str | None = None


UNVERIFIED = Provenance(status="unverified")
#: The ``_Carrier`` fields that hold records rather than data.
RECORD_FIELDS = frozenset({"provenance", "field_provenance"})


@_frozen
class _Carrier:
    provenance: Provenance = UNVERIFIED
    field_provenance: Mapping[str, Provenance] = field(default_factory=_empty)


# ---- IP blocks and instances -----------------------------------------------------


@_frozen
class Core(_Carrier):
    """A core IP block (RFC 0002 "Core and Npu")."""

    id: str
    arch: str
    pmu: str
    has_dsp_extension: bool


@_frozen
class CoreOptions:
    fpu: Literal["none", "fpv4-sp-d16", "fpv5-sp-d16"]
    mve: Literal["none", "int", "fp"]
    fpu_dp: bool = False
    icache_kb: int | None = None
    dcache_kb: int | None = None


@_frozen
class CoreInstance:
    id: str
    role: Literal["application", "radio", "dsp", "other"]
    core: str
    options: CoreOptions
    clock_domain: str
    programmable_by: Literal["customer", "vendor", "either"] | None = None


@_frozen
class Npu:
    vendor: str
    family: str
    model: str
    macs_per_cycle: int

    @property
    def accelerator_config(self) -> str:
        """The Vela accelerator configuration, for example ``ethos-u85-256``."""
        vendor_family = self.family.rsplit("-", 1)[0]
        return f"{vendor_family}-{self.model}-{self.macs_per_cycle}"


@_frozen
class NpuInstance:
    id: str
    npu: Npu
    driven_by: str
    clock_domain: str
    axi_width_bits: int | None = None
    base_address: int | None = None
    irq: int | None = None


@_frozen
class AcceleratorInstance:
    id: str
    kind: str
    driven_by: str
    clock_domain: str
    ip: str | None = None
    base_address: int | None = None
    irq: int | None = None


# ---- memories and access ----------------------------------------------------------


@_frozen
class MemoryCharacterization:
    read_latency_ns: float | None = None
    write_latency_ns: float | None = None
    max_outstanding: int | None = None
    burst_bytes: int | None = None
    ports: int | None = None
    axi_clock_hz: int | None = None
    bandwidth_fraction: float | None = None


@_frozen
class MemoryRegion(_Carrier):
    KEY: ClassVar[str] = "name"
    name: str
    technology: Literal["sram", "mram", "rram", "psram", "flash", "nvm", "dram"]
    attachment: Literal["tcm", "system", "external"]
    size: int
    base: int | None = None
    alternate_bases: tuple[int, ...] = ()
    executable: bool | None = None
    writeable: bool | None = None
    cacheable: bool | None = None
    characterization: MemoryCharacterization | None = None
    stands_in_for: tuple[str, ...] = ()  # Soc regions an FVP region emulates (ADR 0007)


@_frozen
class Access(_Carrier):
    master: str
    target: str
    access: Literal["direct", "none"]
    requires_awake: tuple[str, ...] = ()
    guidance: Literal["preferred", "allowed", "discouraged"] | None = None
    reason: str | None = None
    address: int | None = None
    port: Literal[0, 1] | None = None
    characterization: MemoryCharacterization | None = None


@_frozen
class DefaultAccess(_Carrier):
    master: str
    access: Literal["direct"]
    scope: Literal["on_die"]


# ---- clocks -------------------------------------------------------------------------


@_frozen
class DomainPoint(_Carrier):
    KEY: ClassVar[str] = "name"
    name: str
    mhz: float
    hal_mode: str | None = None


@_frozen
class ClockDomain:
    KEY: ClassVar[str] = "id"
    id: str
    points: tuple[DomainPoint, ...]


@_frozen
class OperatingPoint(_Carrier):
    KEY: ClassVar[str] = "name"
    name: str
    domains: Mapping[str, str] = field(default_factory=_empty)
    hal_mode: str | None = None


# ---- boot ---------------------------------------------------------------------------


@_frozen
class AppStart:
    region: str
    offset: int


@_frozen
class Reservation(_Carrier):
    KEY: ClassVar[str] = "purpose"
    purpose: str
    region: str
    offset: int
    size: int


@_frozen
class BootConfig(_Carrier):
    KEY: ClassVar[str] = "name"
    name: str
    app_start: Mapping[str, AppStart]
    requires: Literal["sbl", "none", "custom"]
    reserved: tuple[Reservation, ...] = ()


# ---- SDK facts ----------------------------------------------------------------------


@_frozen
class BuildFacts:
    abi: str | None = None
    float_abi: str | None = None
    toolchains: tuple[str, ...] = ()


@_frozen
class SdkFacts:
    c_define: str | None = None
    cmsis_header: str | None = None
    trace_clock_mhz: float | None = None
    hal_enums: Mapping[str, str] = field(default_factory=_empty)
    build: BuildFacts | None = None


# ---- entities ----------------------------------------------------------------------


@_frozen
class Soc(_Carrier):
    """A specification (RFC 0002 "Soc")."""

    id: str
    series: str
    cores: tuple[CoreInstance, ...]
    memories: tuple[MemoryRegion, ...]
    clock_domains: tuple[ClockDomain, ...]
    revision: str | None = None
    npus: tuple[NpuInstance, ...] = ()
    accelerators: tuple[AcceleratorInstance, ...] = ()
    access: tuple[Access, ...] = ()
    default_access: DefaultAccess | None = None
    peripherals: tuple[str, ...] = ()
    memory_controllers: tuple[str, ...] = ()
    operating_points: tuple[OperatingPoint, ...] = ()
    default_operating_point: str | None = None
    boot_configs: Mapping[str, BootConfig] = field(default_factory=_empty)
    default_boot: str | None = None
    sdk: SdkFacts | None = None
    derives_from: str | None = None
    default_board: str | None = None
    aliases: tuple[str, ...] = ()
    release_status: ReleaseStatus = "embargoed"
    extensions: Mapping[str, Any] = field(default_factory=_empty)


@_frozen
class AccessKey:
    master: str
    target: str


@_frozen
class Subset:
    memories_removed: tuple[str, ...] = ()
    memories_resized: Mapping[str, int] = field(default_factory=_empty)
    memories_rebased: Mapping[str, int] = field(default_factory=_empty)
    peripherals_removed: tuple[str, ...] = ()
    memory_controllers_removed: tuple[str, ...] = ()
    cores_removed: tuple[str, ...] = ()
    npus_removed: tuple[str, ...] = ()
    accelerators_removed: tuple[str, ...] = ()
    clock_domains_removed: tuple[str, ...] = ()
    boot_configs_removed: tuple[str, ...] = ()
    operating_points_removed: tuple[str, ...] = ()
    access_removed: tuple[AccessKey, ...] = ()
    max_cpu_mhz: float | None = None
    max_npu_mhz: float | None = None
    max_domain_mhz: Mapping[str, float] = field(default_factory=_empty)


@_frozen
class MemoryInterface:
    KEY: ClassVar[str] = "name"
    name: str
    controller: str
    modes: tuple[str, ...] = ()
    aperture_base: int | None = None
    aperture_max: int | None = None


@_frozen
class Implementation(_Carrier):
    """A realization of a Soc (RFC 0002 "Implementation and Part").

    ``clock_domains``, ``operating_points``, ``boot_configs`` and ``access``
    hold only what the Implementation writes; they merge with the Soc's (ADR
    0002 section 2.5). ``memories``, kind ``fvp`` only, replaces the Soc's
    whole list (ADR 0007). ``None`` means it writes none.
    """

    id: str
    soc: str
    kind: Literal["silicon", "fpga", "fvp", "rtl"]
    model: str | None = None
    subset: Subset = field(default_factory=Subset)
    memories: tuple[MemoryRegion, ...] | None = None
    access: tuple[Access, ...] | None = None
    clock_domains: tuple[ClockDomain, ...] | None = None
    operating_points: tuple[OperatingPoint, ...] | None = None
    boot_configs: Mapping[str, BootConfig] | None = None
    default_boot: str | None = None
    provisioning: str | None = None
    jlink_device: str | None = None
    trace_clock_mhz: float | None = None
    interfaces: Mapping[str, MemoryInterface] = field(default_factory=_empty)
    population: Mapping[str, str] = field(default_factory=_empty)
    aliases: tuple[str, ...] = ()
    release_status: ReleaseStatus = "embargoed"
    extensions: Mapping[str, Any] = field(default_factory=_empty)


@_frozen
class ImageSlot(_Carrier):
    KEY: ClassVar[str] = "name"
    name: str
    core: str
    region: str
    offset: int
    size: int
    supplier: Literal["vendor", "customer"]


@_frozen
class Part(_Carrier):
    id: str
    soc: str
    implementation: str | None = None
    silicon_revision: str | None = None
    package: str | None = None
    radio: str | None = None
    jlink_device: str | None = None
    image_slots: Mapping[str, ImageSlot] = field(default_factory=_empty)
    aliases: tuple[str, ...] = ()
    release_status: ReleaseStatus = "embargoed"


@_frozen
class Board(_Carrier):
    id: str
    category: Literal["engineering", "evaluation", "custom"]
    part: str
    revision: str | None = None
    interfaces: Mapping[str, MemoryInterface] = field(default_factory=_empty)
    population: Mapping[str, str] = field(default_factory=_empty)
    provisioning: str | None = None
    jlink_device: str | None = None
    trace_clock_mhz: float | None = None
    aliases: tuple[str, ...] = ()
    release_status: ReleaseStatus = "embargoed"
    extensions: Mapping[str, Any] = field(default_factory=_empty)


@_frozen
class AddOn(_Carrier):
    id: str
    fits_boards: tuple[str, ...]
    occupies: tuple[str, ...]
    population: Mapping[str, str]
    revision: str | None = None
    aliases: tuple[str, ...] = ()
    release_status: ReleaseStatus = "embargoed"
    extensions: Mapping[str, Any] = field(default_factory=_empty)


@_frozen
class MemoryDevice(_Carrier):
    id: str
    technology: Literal["sram", "mram", "rram", "psram", "flash", "nvm", "dram"]
    capacity: int
    driver_family: str | None = None
    modes: tuple[str, ...] = ()
    characterization: MemoryCharacterization | None = None
    aliases: tuple[str, ...] = ()
    release_status: ReleaseStatus = "embargoed"


@_frozen
class Composition:
    KEY: ClassVar[str] = "alias"
    alias: str
    board: str
    addons: tuple[str, ...] = ()


#: Model classes by the name of the format declaration they are built from.
BY_NAME: dict[str, type] = {
    cls.__name__: cls
    for cls in (
        Provenance, Core, CoreOptions, CoreInstance, Npu, NpuInstance, AcceleratorInstance,
        MemoryCharacterization, MemoryRegion, Access, DefaultAccess, DomainPoint, ClockDomain,
        OperatingPoint, AppStart, Reservation, BootConfig, BuildFacts, SdkFacts, Soc,
        AccessKey, Subset, MemoryInterface, Implementation, ImageSlot, Part, Board, AddOn,
        MemoryDevice, Composition,
    )
}  # fmt: skip
