"""The file format of ADR 0002 section 2, declared once for the loader and the schema generator.

This module must not use ``from __future__ import annotations``: with it,
``TypedDict.__required_keys__`` ignores ``Required`` and ``NotRequired``
(ADR 0002, Context). The structural stage (``_structural``) and the JSON
Schema generator (``schema``) both walk these declarations.
"""

from dataclasses import dataclass
from typing import Annotated, Any, Literal, NotRequired, Required, TypedDict

# ---- markers carried in Annotated[...] ------------------------------------


@dataclass(frozen=True)
class Pattern:
    """The string must match ``regex`` in full."""

    regex: str
    what: str


@dataclass(frozen=True)
class Minimum:
    """The number must be at least ``value``."""

    value: int


@dataclass(frozen=True)
class Keyed:
    """A list of objects keyed by ``fields``; the loader rejects a repeated key."""

    fields: tuple[str, ...]


class _Flag:
    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self) -> str:
        return self.name


SIZE = _Flag("SIZE")  # bytes, or "<integer><K|M|G>" (section 2.6)
BY_VALUE = _Flag("BY_VALUE")  # a list of names or values, keyed by the value itself
NOT_FACT = _Flag("NOT_FACT")  # a key that is not a fact (section 2.7)
FILE_ONLY = _Flag("FILE_ONLY")  # a delta or shorthand key with no runtime field
ORDERED = _Flag("ORDERED")  # a keyed list whose order is a fact, index 0 primary (section 2.4)
OPAQUE = _Flag("OPAQUE")  # any JSON-compatible value, never read (section 2.8)

SIZE_RE = r"^[0-9]+[KMG]$"
DATE_RE = r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"

Id = Annotated[str, Pattern(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$", "an id")]
Name = Annotated[str, Pattern(r"^(?!(?:value|provenance)$)[a-z][a-z0-9_]*$", "a lowercase name")]
DomainPointRef = Annotated[
    str,
    Pattern(
        r"^(?!(?:value|provenance)(?:\.|$))[a-z][a-z0-9_]*"
        r"(?:\.(?!(?:value|provenance)$)[a-z][a-z0-9_]*)?$",
        "a domain name or <domain>.<point>",
    ),
]
ToolName = Annotated[str, Pattern(r"^[a-z][a-z0-9_]*$", "a tool name")]
Size = Annotated[int | str, SIZE]
Address = Annotated[int, Minimum(0)]
Count = Annotated[int, Minimum(0)]
Mhz = Annotated[float | int, Minimum(0)]

Ids = Annotated[list[Id], BY_VALUE]
Names = Annotated[list[Name], BY_VALUE]
ReleaseStatus = Annotated[Literal["public", "embargoed"], NOT_FACT]


# ---- provenance (ADR 0003's record; its rules are checked elsewhere) -------


class Provenance(TypedDict):
    status: Required[Literal["datasheet", "sdk", "measured", "fitted", "derived", "unverified"]]
    source: NotRequired[Annotated[list[str], BY_VALUE]]
    verified_on: NotRequired[Annotated[str, Pattern(DATE_RE, "a YYYY-MM-DD date")]]
    verified_by: NotRequired[str]
    notes: NotRequired[str]


class _Facts(TypedDict, total=False):
    """Base of every object whose values are facts; any such object may carry a record."""

    provenance: Annotated[Provenance, NOT_FACT]


class _Inheritable(_Facts, total=False):
    """Base of every entity table: an overlay entry may name a ``based_on`` entry."""

    based_on: Annotated[Id, NOT_FACT, FILE_ONLY]


class _Entity(_Inheritable, total=False):
    """Base of the entities that carry aliases and a release status (not Core)."""

    aliases: Annotated[Ids, NOT_FACT]
    release_status: ReleaseStatus


Extensions = Annotated[dict[ToolName, Annotated[Any, OPAQUE]], NOT_FACT]


# ---- memories and access ----------------------------------------------------


class MemoryCharacterization(_Facts, total=False):
    """Timing of a memory path as the SoC documents it or as measured on it.

    The outstanding limits (per port, reads and writes apart) and burst_bytes are the
    hardware's limits on the path. Limits a driver programs (Ethos-U AXI_SRAM, AXI_EXT)
    and values fitted to a model belong to that tool.
    """

    read_latency_ns: Annotated[float | int, Minimum(0)]
    write_latency_ns: Annotated[float | int, Minimum(0)]
    max_outstanding_reads: Count
    max_outstanding_writes: Count
    burst_bytes: Count
    ports: Count
    axi_clock_hz: Count
    bandwidth_fraction: Annotated[float | int, Minimum(0)]


class MemoryRegion(_Facts):
    technology: Required[Literal["sram", "mram", "rram", "psram", "flash", "nvm", "dram"]]
    attachment: Required[Literal["tcm", "system", "external"]]
    size: Required[Size]
    base: NotRequired[Address]
    alternate_bases: NotRequired[Annotated[list[Address], BY_VALUE]]
    executable: NotRequired[bool]
    writeable: NotRequired[bool]
    cacheable: NotRequired[bool]
    characterization: NotRequired[MemoryCharacterization]
    stands_in_for: NotRequired[Names]  # on an FVP Implementation's regions only (ADR 0007)


class Access(_Facts):
    master: Required[Name]
    target: Required[Name]
    access: Required[Literal["direct", "none"]]
    requires_awake: NotRequired[Names]
    guidance: NotRequired[Literal["preferred", "allowed", "discouraged"]]
    reason: NotRequired[str]
    address: NotRequired[Address]
    port: NotRequired[Literal[0, 1]]
    characterization: NotRequired[MemoryCharacterization]


class AccessKey(TypedDict):
    master: Required[Name]
    target: Required[Name]


class RemovedAccess(_Facts):
    """A pair an implementation's subset removes: a fact, unlike a ``based_on`` delta's pair."""

    master: Required[Name]
    target: Required[Name]


class DefaultAccess(_Facts):
    master: Required[Name]
    access: Required[Literal["direct"]]
    scope: Required[Literal["on_die"]]


# ---- cores, NPUs and accelerators -------------------------------------------


class CoreOptions(_Facts):
    fpu: Required[Literal["none", "fpv4-sp-d16", "fpv5-sp-d16"]]
    mve: Required[Literal["none", "int", "fp"]]
    fpu_dp: NotRequired[bool]
    icache_kb: NotRequired[Count]
    dcache_kb: NotRequired[Count]


class CoreInstance(_Facts):
    id: Required[Annotated[Name, NOT_FACT]]
    role: Required[Literal["application", "radio", "dsp", "other"]]
    core: Required[Id]
    options: Required[CoreOptions]
    clock_domain: Required[Name]
    programmable_by: NotRequired[Literal["customer", "vendor", "either"]]


class Npu(_Facts):
    vendor: Required[str]
    family: Required[str]
    model: Required[str]
    macs_per_cycle: Required[Count]


class NpuInstance(_Facts):
    id: Required[Annotated[Name, NOT_FACT]]
    npu: Required[Npu]
    driven_by: Required[Name]
    clock_domain: Required[Name]
    axi_width_bits: NotRequired[Count]
    base_address: NotRequired[Address]
    irq: NotRequired[Count]
    sram_port_hash: NotRequired[Count]


class AcceleratorInstance(_Facts):
    id: Required[Annotated[Name, NOT_FACT]]
    kind: Required[str]
    driven_by: Required[Name]
    clock_domain: Required[Name]
    ip: NotRequired[str]
    base_address: NotRequired[Address]
    irq: NotRequired[Count]


# ---- clocks and operating points --------------------------------------------


class DomainPoint(_Facts):
    mhz: Required[Mhz]
    hal_mode: NotRequired[str]


class OperatingPoint(_Facts, total=False):
    domains: dict[Name, Name]
    hal_mode: str
    cpu_mhz: Annotated[Mhz, FILE_ONLY]
    npu_mhz: Annotated[Mhz, FILE_ONLY]


ClockDomains = dict[Name, dict[Name, DomainPoint]]


# ---- boot ---------------------------------------------------------------------


class Reservation(_Facts):
    region: Required[Name]
    offset: Required[Size]
    size: Required[Size]


class AppStart(_Facts):
    region: Required[Name]
    offset: Required[Size]


class BootConfig(_Facts):
    app_start: Required[AppStart | dict[Name, AppStart]]
    requires: Required[Literal["sbl", "none", "custom"]]
    reserved: NotRequired[dict[Name, Reservation]]


# ---- SDK facts ----------------------------------------------------------------


class BuildFacts(_Facts, total=False):
    abi: str
    float_abi: str
    # Deprecated (#18): neuralspotx policy, not a fact. No built-in data sets it, and
    # check-sources no longer compares it; the field goes once no open branch uses it.
    toolchains: Annotated[list[str], BY_VALUE]


class SdkFacts(_Facts, total=False):
    c_define: str
    cmsis_header: str
    trace_clock_mhz: Mhz
    hal_enums: dict[str, str]
    build: BuildFacts


# ---- entities -----------------------------------------------------------------


class Core(_Inheritable):
    arch: Required[str]
    pmu: Required[str]
    has_dsp_extension: Required[bool]


class Soc(_Entity):
    series: Required[str]
    cores: Required[Annotated[list[CoreInstance], Keyed(("id",)), ORDERED]]
    memories: Required[dict[Name, MemoryRegion]]
    clock_domains: Required[ClockDomains]
    revision: NotRequired[str]
    npus: NotRequired[Annotated[list[NpuInstance], Keyed(("id",)), ORDERED]]
    accelerators: NotRequired[Annotated[list[AcceleratorInstance], Keyed(("id",)), ORDERED]]
    access: NotRequired[Annotated[list[Access], Keyed(("master", "target"))]]
    default_access: NotRequired[DefaultAccess]
    peripherals: NotRequired[Names]
    memory_controllers: NotRequired[Names]
    operating_points: NotRequired[dict[Name, OperatingPoint]]
    default_operating_point: NotRequired[Name]
    boot_configs: NotRequired[dict[Name, BootConfig]]
    default_boot: NotRequired[Name]
    sdk: NotRequired[SdkFacts]
    derives_from: NotRequired[Annotated[Id, NOT_FACT]]
    default_board: NotRequired[Annotated[Id, NOT_FACT]]
    extensions: NotRequired[Extensions]
    # Deltas over a based_on entry (section 2.5).
    memories_removed: NotRequired[Annotated[Names, NOT_FACT, FILE_ONLY]]
    memories_resized: NotRequired[Annotated[dict[Name, Size], FILE_ONLY]]
    memories_rebased: NotRequired[Annotated[dict[Name, Address], FILE_ONLY]]
    cores_removed: NotRequired[Annotated[Names, NOT_FACT, FILE_ONLY]]
    npus_removed: NotRequired[Annotated[Names, NOT_FACT, FILE_ONLY]]
    accelerators_removed: NotRequired[Annotated[Names, NOT_FACT, FILE_ONLY]]
    peripherals_removed: NotRequired[Annotated[Names, NOT_FACT, FILE_ONLY]]
    clock_domains_removed: NotRequired[
        Annotated[list[DomainPointRef], BY_VALUE, NOT_FACT, FILE_ONLY]
    ]
    boot_configs_removed: NotRequired[Annotated[Names, NOT_FACT, FILE_ONLY]]
    operating_points_removed: NotRequired[Annotated[Names, NOT_FACT, FILE_ONLY]]
    access_removed: NotRequired[
        Annotated[list[AccessKey], Keyed(("master", "target")), NOT_FACT, FILE_ONLY]
    ]


class Subset(_Facts, total=False):
    memories_removed: Names
    memories_resized: dict[Name, Size]
    memories_rebased: dict[Name, Address]
    peripherals_removed: Names
    cores_removed: Names
    npus_removed: Names
    accelerators_removed: Names
    clock_domains_removed: Annotated[list[DomainPointRef], BY_VALUE]
    boot_configs_removed: Names
    operating_points_removed: Names
    access_removed: Annotated[list[RemovedAccess], Keyed(("master", "target"))]
    max_cpu_mhz: Mhz
    max_npu_mhz: Mhz
    max_domain_mhz: dict[Name, Mhz]


class MemoryInterface(_Facts):
    controller: Required[Name]
    modes: NotRequired[Annotated[list[str], BY_VALUE]]
    aperture_base: NotRequired[Address]
    aperture_max: NotRequired[Size]


class Implementation(_Entity):
    soc: Required[Id]
    kind: Required[Literal["silicon", "fpga", "fvp", "rtl"]]
    model: NotRequired[str]
    subset: NotRequired[Subset]
    # Kind fvp only: the complete memory list (ADR 0007).
    memories: NotRequired[dict[Name, MemoryRegion]]
    # Any kind: entries that add to or replace the Soc's, by (master, target).
    access: NotRequired[Annotated[list[Access], Keyed(("master", "target"))]]
    clock_domains: NotRequired[ClockDomains]
    operating_points: NotRequired[dict[Name, OperatingPoint]]
    boot_configs: NotRequired[dict[Name, BootConfig]]
    default_boot: NotRequired[Name]
    provisioning: NotRequired[Name]
    jlink_device: NotRequired[str]
    trace_clock_mhz: NotRequired[Mhz]
    interfaces: NotRequired[dict[Name, MemoryInterface]]
    population: NotRequired[dict[Name, Id]]
    extensions: NotRequired[Extensions]


class ImageSlot(_Facts):
    core: Required[Name]
    region: Required[Name]
    offset: Required[Size]
    size: Required[Size]
    supplier: Required[Literal["vendor", "customer"]]


class Part(_Entity):
    soc: Required[Id]
    implementation: NotRequired[Id]
    silicon_revision: NotRequired[str]
    package: NotRequired[str]
    radio: NotRequired[str]
    jlink_device: NotRequired[str]
    image_slots: NotRequired[dict[Name, ImageSlot]]
    image_slots_removed: NotRequired[Annotated[Names, NOT_FACT, FILE_ONLY]]


class Board(_Entity):
    category: Required[Literal["engineering", "evaluation", "custom", "fpga"]]
    # Exactly one: a silicon board names its Part, an FPGA carrier its fpga Implementation (#104).
    part: NotRequired[Id]
    implementation: NotRequired[Id]
    revision: NotRequired[str]
    interfaces: NotRequired[dict[Name, MemoryInterface]]
    population: NotRequired[dict[Name, Id]]
    provisioning: NotRequired[Name]
    jlink_device: NotRequired[str]
    trace_clock_mhz: NotRequired[Mhz]
    extensions: NotRequired[Extensions]


class AddOn(_Entity):
    fits_boards: Required[Ids]
    occupies: Required[Names]
    population: Required[dict[Name, Id]]
    revision: NotRequired[str]
    extensions: NotRequired[Extensions]


class MemoryDevice(_Entity):
    technology: Required[Literal["sram", "mram", "rram", "psram", "flash", "nvm", "dram"]]
    capacity: Required[Size]
    driver_family: NotRequired[str]
    modes: NotRequired[Annotated[list[str], BY_VALUE]]
    characterization: NotRequired[MemoryCharacterization]


class Composition(TypedDict):
    board: Required[Id]
    addons: NotRequired[Ids]


# ---- the source register and the release allow-list (ADR 0003) ----------------------

Revision = Annotated[str, Pattern(r"^[0-9A-Za-z][0-9A-Za-z._-]*$", "a revision")]
RepositoryName = Annotated[
    str, Pattern(r"^[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)?$", "owner/name or a bare name")
]
Sha1 = Annotated[str, Pattern(r"^[0-9a-f]{40}$", "a full 40-hex commit SHA")]


class RegisterDocument(TypedDict):
    """One revision of a document of record (ADR 0003 section 2)."""

    document_id: Required[str]
    date: Required[Annotated[str, Pattern(r"^[0-9]{4}-[0-9]{2}(-[0-9]{2})?$", "YYYY-MM[-DD]")]]
    pages: Required[Annotated[int, Minimum(1)]]
    sha256: Required[Annotated[str, Pattern(r"^[0-9a-f]{64}$", "a 64-hex SHA256")]]


class RegisterRepository(TypedDict):
    url: Required[str]
    host: NotRequired[str]  # the system hosting a repository that is not on GitHub
    tags: NotRequired[dict[Revision, Sha1]]


class AllowedUnverified(TypedDict):
    fact: Required[Annotated[str, Pattern(r"^fact:.+$", "a fact: reference")]]
    reason: Required[str]
    issue: Required[Annotated[str, Pattern(r"^#[0-9]+$", "an issue, #N")]]


# ---- the document -------------------------------------------------------------


class Document(TypedDict, total=False):
    schema_version: Required[Annotated[int, Minimum(1)]]
    cores: dict[Id, Core]
    socs: dict[Id, Soc]
    implementations: dict[Id, Implementation]
    parts: dict[Id, Part]
    boards: dict[Id, Board]
    addons: dict[Id, AddOn]
    memory_devices: dict[Id, MemoryDevice]
    compositions: dict[Id, Composition]
    shorthands: dict[Id, Ids]
    documents: dict[Id, dict[Revision, RegisterDocument]]
    repositories: dict[RepositoryName, RegisterRepository]
    unverified_allowed: list[AllowedUnverified]


# ---- the JSON export (RFC 0003 "Schema and versioning") ---------------------------

Digest = Annotated[str, Pattern(r"^sha256:[0-9a-f]{64}$", "a sha256 digest")]


class ExportSource(TypedDict):
    label: Required[str]
    schema_version: Required[Annotated[int, Minimum(1)]]
    sha256: Required[Digest]
    distribution_version: Required[str | None]


class ExportIdentity(TypedDict):
    package_version: Required[str]
    schema_version: Required[Annotated[int, Minimum(1)]]
    catalog_digest: Required[Digest]
    sources: Required[list[ExportSource]]


class Export(TypedDict):
    schema_version: Required[Annotated[int, Minimum(1)]]
    identity: Required[ExportIdentity]
    catalog: Required[Document]


#: Top-level keys that hold entity tables, in load order.
ENTITY_TABLES: dict[str, type] = {
    "cores": Core,
    "socs": Soc,
    "implementations": Implementation,
    "parts": Part,
    "boards": Board,
    "addons": AddOn,
    "memory_devices": MemoryDevice,
}

#: Keys only built-in files may carry (ADR 0002 section 1).
BUILTIN_ONLY_KEYS = frozenset({"shorthands", "documents", "repositories", "unverified_allowed"})

#: Ignored at the top level of a JSON file (section 2.1).
IGNORED_TOP_LEVEL = frozenset({"$schema"})

SCHEMA_VERSION = 1
