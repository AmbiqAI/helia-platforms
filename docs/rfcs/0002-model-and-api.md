# RFC 0002: the platform model and the API helia-platforms exposes

Status: Draft, 2026-10-04. Builds on [RFC 0001](0001-platform-catalogue.md)
(the catalogue and its data), on AmbiqAI/helia-aot#278 (the Soc/Board
split, typed NPU spec and alias design, captured verbatim in
[research/helia-aot-278.md](../research/helia-aot-278.md)), and on the
[review of RFC 0001](0001-platform-catalogue-review.md). Where this RFC
and RFC 0001 disagree, this RFC wins; RFC 0001's appendix remains the
reference for the data and its sources.

## Summary

`helia-platforms` is a queryable model of Ambiq SoCs and the things that
realize them, not a static table. It exposes:

1. a **catalogue** of specifications (SoCs), implementations of them
   (silicon parts, FPGA builds, FVP and RTL models), boards, and linker
   windows, every fact carrying provenance;
2. a **resolver** that turns any accepted spelling into one target, with
   aliases, family shorthands and did-you-mean in one place;
3. **derived queries**: capabilities such as MVE, FP16 or an Ethos-U85 with
   256 MACs are computed from structural facts, never declared;
4. an **overlay** mechanism so a downstream tool, customer or bring-up team
   describes a new SoC, implementation or board by reference and delta,
   never by restating die facts, and gets a new immutable catalogue back;
5. **exports**: a JSON catalogue, a JSON Schema for overlays, and a CLI.

Tools keep their opinions. heliaAOT's placement order and alignment
policy, the profiler's reset and PMU planning, the estimator's energy model
all stay in their tools, keyed by canonical id. The package answers
questions of fact.

## Principles

| # | Principle | Consequence |
|---|---|---|
| P1 | Facts, not opinions | No `preferred_memory_order`, no tool sections on built-ins. Tools derive policy from facts the package exposes (attachment, latency, ports). |
| P2 | Specification and implementations | A SoC is the full specification. An implementation realizes all of it by default or a validated subset (bring-up FPGA with less memory and lower clocks, an FVP with substituted memories). Production silicon is the full set and says nothing extra. |
| P3 | Declared structure, derived capability | Only structural facts are declared. "Supports FP16" is a function of the core's MVE option; "has NPU" is a function of an NPU instance being present; "which NPU" is a structured record. |
| P4 | Every fact has provenance | Status (datasheet, sdk, measured, fitted, derived, unverified), source, date, reviewer. Releases reject `unverified` unless allow-listed. |
| P5 | Overlays compose by reference | `based_on`, `soc:`, `part:`; deltas and removals; unknown keys rejected with a suggestion; built-in ids cannot be shadowed. |
| P6 | One resolver | Canonical ids are the neuralspotx/SDK spellings, matched case-insensitively. Exact aliases resolve. Family shorthands (`AP5`, `AP510`) raise with candidates. Near misses suggest. |
| P7 | Immutable catalogue, no global state | Loading an overlay returns a new catalogue. Nothing registers into a process-global table (the class of bug in helia-aot#331). No I/O at import. |
| P8 | Stdlib runtime, schema as contract | Frozen dataclasses; PyYAML for overlays and typer for the CLI, nothing heavier; a published JSON Schema with `schema_version`; pydantic export as an optional extra. |

## Entity model

```
Core ───────┐                      Npu ──────────┐
 (IP: cortex-m55)                   (IP: arm ethos-u u85 256 MACs)
            │                                     │
            ▼                                     ▼
Soc ── core: CoreInstance(core, fpu, mve, caches)  npu: NpuInstance(npu, clocks, base, irq)
 │     memories: [MemoryRegion]        operating_points: [OperatingPoint]
 │     sdk: SdkFacts (c_define, cmsis_header, ...)   aliases, provenance
 │
 ├── Implementation (kind: silicon | fpga | fvp | rtl; subset or remap of the Soc; default = all)
 │     ├── boot_configs: {name: BootConfig}, default    (sbl, nbl, or a custom FPGA layout)
 │     └── Part (silicon: ordering number, silicon revision, package, radio, jlink_device,
 │               per-part NVM reservations such as radio firmware)
 │
 ├── Board (stage: fpga | eb | evb | custom; revision; carries one Implementation or Part;
 │          memory interfaces; default population; provisioning (boot config in use);
 │          probe and trace facts; aliases)
 │
 └── AddOn (shield or daughter board: occupies board interfaces, brings MemoryDevices)

MemoryDevice: an external part (APS25616N, IS25WX064): technology, capacity, interface modes
Resolved target: Board + AddOns + overlay | Implementation | Soc -> one flattened, queryable view
Link environments (stack/heap carve-outs, toolchain scripts) are outside the core model.
```

### Core and Npu (IP blocks)

`Core` holds architecture facts Arm fixes: `id` (cortex-m4, cortex-m55),
`arch` (armv7e-m, armv8.1-m), `pmu` (dwt, armv8m), `has_dsp_extension`.
Options Arm leaves to the implementer live on the Soc's `CoreInstance`:
`fpu` (none, fpv4-sp-d16, fpv5-sp-d16), `fpu_dp`, `mve` (none, int, fp),
`icache`, `dcache`.

`Npu` is structured, as #278 proposes and the owner direction requires:
`vendor` (arm), `family` (ethos-u), `model` (u55, u65, u85),
`macs_per_cycle` (256). `accelerator_config` ("ethos-u85-256") is derived.
The Soc's `NpuInstance` adds the instance facts: clocks per operating
point, base address, IRQ, which memories it can reach and over which port.
Driver behaviour (command-stream chunking, Vela system configs, port
arbitration rules) stays in `helia-npu`, which reads the instance facts
from here.

### Soc (the specification)

| Field | Kind | Notes |
|---|---|---|
| `id`, `series`, `aliases` | identity | `series` is the SDK product line (apollo5, atomiq). The profiler's AP3/AP4/AP5 tier is profiler policy keyed by id. |
| `core: CoreInstance` | structural | Capabilities derive from it. |
| `npu: NpuInstance \| None` | structural | |
| `memories: [MemoryRegion]` | structural, with optional characterization | See below. |
| `operating_points: [OperatingPoint]` | structural | name, cpu MHz, npu MHz, HAL mode name; heliaAOT `speeds` and the profiler `ClockDomain` are views. |
| `sdk: SdkFacts` | SDK fact | `c_define`, `cmsis_header`, default trace clock, HAL enums the SDK exposes per SoC. |
| `derives_from: Soc \| None` | structural | apollo510b and apollo5b derive from apollo510 (shared headers); the validator requires equal physical regions. |
| `release_status` | governance | public or embargoed; the build filter never ships embargoed entries. |

`MemoryRegion`: `name` (dtcm, ssram, mram, hblram, psram0), `technology`
(sram, mram, rram, psram, flash, nvm), `attachment` (tcm, system, external),
`size`, `base`, `executable`, `writeable`, `cacheable`, optional
`characterization` (read and write latency, ports, max outstanding,
burst, bandwidth) each value with provenance. The estimator's memory
timing lands here; its energy coefficients stay in the estimator.

### Bring-up lifecycle

Ambiq silicon moves through stages, and the model follows them rather than
treating the end state as the only truth:

| Stage | What exists | Modelled as |
|---|---|---|
| Pre-tapeout | FPGA running a subset of the RTL: less memory, peripherals absent, lower clocks, sometimes a different address map; an Arm FVP standing in for parts of the system | `Implementation` of kind `fpga` or `fvp`, carried by a `Board` of stage `fpga` (atomiq110_fpga_turbo, apollo510L_fpga_turbo) |
| First silicon | Engineering board with an early silicon revision | `Part` with a `silicon_revision`, on a `Board` of stage `eb` |
| Release | Evaluation board with production silicon | `Part` on a `Board` of stage `evb`, with board `revision` (populations change between revisions) |
| Customer | The customer's own board | `Board` of stage `custom`, defined in an overlay by reference to a Part, with its own interfaces, population and add-ons |

Every stage resolves through the same API, so a tool written against an
FPGA target keeps working as the EB and EVB arrive. Stage is a fact about
the board; how well each tool supports a stage is that tool's marker.

### Implementation and Part

An `Implementation` names a `soc`, a `kind` and a subset expression:
memories removed, resized or rebased; peripherals absent; clock caps; NPU
absent. Everything not mentioned is inherited from the specification. The
validator rejects an implementation that adds a memory or exceeds a
clock. Rebasing is allowed because FPGA builds move regions (the
atomiq110 FPGA places SSRAM and MRAM at different bases from silicon). An
FVP implementation names the model (corstone-320) and the substitutions it
makes, so the estimator's "Corstone-320 as a subset of atomiq110" is
first-class rather than a private convention.

Production and engineering silicon is a `Part`: ordering number
(AP510NFA-CBR), `silicon_revision`, package, radio option, `jlink_device`,
and per-part NVM reservations. The Apollo510 Lite and Apollo330 Plus parts
reserve the top of MRAM for radio firmware, 16, 288 or 432 KB depending on
the radio variant, so that reservation lives on the Part, not the Soc.

### Boot configurations

Boot layout is a named choice, not a single fact:

```
BootConfig: name, reserved: [(region, offset, size, purpose)], app_origin (region, offset),
            requires_provisioning (sbl | none | custom), provenance
```

- The Soc carries the boot configurations its SDKs support and a default.
  Datasheet-documented partitions (the Apollo510 NVM-SBL region) carry
  datasheet provenance; SDK conventions (Apollo3 0xC000, Apollo4 0x18000,
  the SBL reservation on Lite and 330 Plus parts) carry SDK provenance.
- An Implementation can replace the set. The atomiq110 FPGA declares only
  its no-bootloader layout at its own MRAM base.
- A Board records its `provisioning`: which configuration the fitted part
  ships with. Ambiq EVBs ship SBL-provisioned; a customer board says what
  it uses.
- Queries derive from the selected configuration: `flash_load_address()`,
  `usable_nvm()`. A consumer may select a non-default configuration
  explicitly; the package warns when it differs from the board's
  provisioning.
- Documented reservations (boot ROM, SBL partition, radio firmware) are
  always subtracted. Stack, heap and toolchain carve-outs are not: they
  belong to link environments.

### Board, external memory and add-ons

A `Board` carries one Part (`eb`, `evb`, `custom`) or Implementation
(`fpga`), a `stage` and a `revision`, probe and trace facts
(`jlink_device` override, measured trace clock), `provisioning`, and
aliases. `tier` and `channel` are gone: support level is a per-tool
marker keyed by id.

External memory is composed, not fixed, because the same board ships with
different populations across revisions (the Apollo330 Plus and Apollo510
Lite EVB rev 2.0 leave the PSRAM footprint empty), shields add memory (the
Apollo4 Plus display shield rev 1 and rev 2 carry different PSRAM and
flash), and customers add daughter boards.

- `MemoryInterface` on the Board: name, controller (mspi0, mspi1, iom4),
  modes (octal DDR, hex), XIP aperture base and maximum size.
- `MemoryDevice`: an external part with technology, capacity, supported
  modes and optional characterization, each value with provenance. Capacity
  is never inferred from a part marking or a BSP macro: the Apollo510 EVB
  PSRAM is 64 MB by hardware measurement although its BSP macro names a
  256 Mb driver family. The driver family is recorded separately, as a
  fact the SDK uses.
- `population`: which device sits on which interface as the board ships.
- `AddOn`: a shield or daughter board that occupies named interfaces and
  brings devices. It names the boards it fits.
- The resolved target is board plus selected add-ons plus overlay. The
  validator rejects two devices on one interface, an add-on on a board it
  does not fit, and a device larger than its aperture.

AmbiqSuite's per-shield board directories (`apollo4p_evb_disp_shield_rev2`)
and neuralspotx's matching board id become one board plus an add-on; the
old ids resolve as aliases to that composition.

### Link environments

Linker windows are properties of software (an SDK's scripts, Zephyr's
devicetree, a customer's own script), not of the silicon. The core model
does not carry them. The package defines a `LinkEnvironment` schema
(owner, link family, profile, per-region usable window, source, revision)
and accepts one wherever a budget is asked for. An optional dataset of
environments generated from nsx-ambiq-sdk and Zephyr at pinned revisions
ships separately for consumers that want a conservative default; the
profiler's windows table seeds it, and an extractor script regenerates it
rather than hand-copying.

## Derived capabilities

The package computes, and exposes both as typed properties and as a
stable string set for tools that want one:

| Query | Derived from |
|---|---|
| `has_dsp_extension` | `Core.has_dsp_extension` |
| `has_mve`, `mve_flavour` | `CoreInstance.mve` |
| `supports_fp16` | `CoreInstance.mve == fp` |
| `supports_fp32` | `CoreInstance.fpu != none` |
| `supports_fp64` | `CoreInstance.fpu_dp` |
| `has_pmu`, `pmu_kind` | `Core.pmu` |
| `has_npu`, `npu` | `Soc.npu` after the implementation subset |
| `has_external_memory(technology)` | board regions |
| `memory_roles()` | regions present after subset and board composition |

heliaAOT maps these onto its `SocCapability` enum in its adapter; the
profiler's `SocCapabilities` builders consume them; `BLE` and `USB` tags
disappear from built-ins. Unknown or bespoke cores declared in an overlay
must state the `CoreInstance` options explicitly; there is no "trust the
declaration" path because there is nothing to declare but facts.

## Resolution and naming

`resolve(name)` accepts a board id, an implementation id, a Soc id, or an
alias, case-insensitively, and returns one resolved target. A Soc id
resolves to its board when exactly one board carries it, otherwise it
resolves to the bare specification (heliaAOT's bare `atomiq110` target
stays valid, as #278 resolved). Family shorthands raise
`AmbiguousPlatform` listing members; near misses raise
`UnknownPlatform` with suggestions. Aliases are unique across all
entities; overlays may add aliases but cannot shadow a built-in id or
alias. heliaAOT keeps printing the lowercase form; the profiler keeps the
neuralspotx spelling; both come from the same resolver.

## Overlays

One format for every downstream party: a tool shipping extra entries, a
customer describing a production board, a bring-up team describing an
FPGA cut.

```yaml
schema_version: 2
socs:
  my_soc:
    based_on: apollo510
    memories:
      ssram: {size: 2M}
implementations:
  atomiq110_fpga_rev3:
    soc: atomiq110
    kind: fpga
    memories: {remove: [hblram], dtcm: {size: 256K}}
    clocks: {max_mhz: 25}
boards:
  my_product_v1:
    based_on: apollo510_evb
    memories:
      remove: [nvm]
      psram: {size: 8M, technology: psram, attachment: external}
    extensions:
      helia_profiler: {sync_gpio: 27}
```

`load_overlay(source) -> Catalogue` returns a new catalogue; the built-in
catalogue is never mutated. `extensions` is an opaque, per-tool namespace
the package stores and returns but never reads or validates; it exists so
one file can travel between tools. Unknown keys outside `extensions` are
rejected with a suggestion. A JSON Schema is published for editors and
CI.

## State of the consumers on 2026-10-04

Read against each repository's `origin/main`; details and file:line
references are in `docs/research/queries-*.md`.

- heliaAOT (ea5cd6c0): one `SocPlatform` type with seven fields and 17
  registered targets. Custom platforms are already run-local (#331 fixed by
  PR #334), and the built-in memory sizes already carry linker-window
  figures with script citations, so part of RFC 0001's Phase 2 budget
  change has happened inside heliaAOT. Nothing from #278's model exists
  yet; no branch for it.
- helia-profiler (b195e29f): nine SoCs, thirteen boards, a windows table
  with per-row source citations, a typed `SocCapabilities` policy layer,
  and a custom overlay format with unknown-key rejection. No test checks
  the windows table against the SDK scripts.
- helia-estimator with helia-npu (5991d9f1): one SoC (atomiq110) in a
  schema with modes, memories classified by NPU AXI port, timing and
  bandwidth per memory, and provenance per value with per-field overrides.
  An override format with merge and remove semantics and provenance
  inheritance.
- neuralspotx (6afb7d2) and nsx-ambiq-sdk (9d4463a): 17 boards, 11 SoC
  fact files, exact-case SoC ids, per-board J-Link overrides on eight
  boards, starter profiles keyed by exact board id. heliaAOT's nsx
  manifest template spells one SoC id in the wrong case.

## Question surface

Every question a consumer's code asks of a platform today, the API in this
RFC that answers it, and the questions that remain the tool's own. "Target"
below is the resolved object returned by `resolve()`.

### heliaAOT

| Question asked today | Answered by | Owner |
|---|---|---|
| Is MVE (or DSP) available, for kernel selection | `target.isa.has_mve`, `target.isa.has_dsp`; `target.capabilities` string set for the existing membership tests | package |
| Native FP16 | `target.isa.supports_fp16` | package |
| Is there an NPU, and which | `target.npu` (`None` or `NpuInstance` with `.model`, `.macs_per_cycle`, `.accelerator_config`) | package |
| Memories and byte sizes to budget | `target.budget(link_family)` for the link environment; `target.memories()` for physical regions | package |
| Is ITCM present | `target.has_region("itcm")` | package |
| Minimum alignment | heliaAOT table keyed by `target.soc.id` (16 with MVE is a placement rule) | heliaAOT |
| Order to try memories | heliaAOT policy; inputs available as `region.attachment` and `region.characterization` | heliaAOT |
| CPU string for compiler flags | `target.core.id`, `target.core_options.fpu`, `.mve` | package |
| Name to print and to key artefacts | `target.id` (canonical) and `target.aliases`; heliaAOT lowercases | package |
| Zephyr section names for TCM | Zephyr `LinkEnvironment` from the optional dataset; heliaAOT template reads its section names | dataset, heliaAOT |
| SoC list for the nsx manifest | `catalogue.socs()` ids in neuralspotx spelling | package |
| Which link family for a module type | heliaAOT policy (`zephyr` for the zephyr module type, `gnu` otherwise) | heliaAOT |

### helia-profiler

| Question asked today | Answered by | Owner |
|---|---|---|
| Which SoC, part, implementation is this board | `resolve(board).soc`, `.part`, `.implementation` | package |
| Core, PMU kind, MVE | `target.core`, `target.core.pmu`, `target.isa` | package |
| Clock speeds, names, default | `target.operating_points()`, `target.default_operating_point` | package (default is an SDK fact where the SDK names one; otherwise profiler policy) |
| Region sizes and capacities | `target.memories()`, `target.usable_nvm()`; `target.budget(env)` with a link environment | package; environment is profiler choice |
| Linker windows per toolchain and profile | `LinkEnvironment` from the optional SDK dataset or the build's own script | dataset or profiler |
| Which region holds address X | `target.classify_address(addr, family)` | package |
| J-Link device name | `target.jlink_device` (board override, else part) | package |
| App flash load address | `target.flash_load_address(profile)` from the MRAM window origin | package |
| Placement base addresses | `target.region(name).base` | package |
| Is PSRAM fitted | `target.has_region(technology="psram")` | package |
| D-cache present | `target.core_options.dcache` | package |
| Shared SSRAM power domain, HAL enum names, C define, CMSIS header | `target.sdk` | package |
| Radio present | `target.part.radio` | package |
| Trace clock | `target.trace_clock_mhz` (board measured value, else SDK default; `None` means core-clocked) | package |
| Is this an FPGA carrier | `target.implementation.kind == "fpga"` | package |
| RTT scan ranges | profiler rule over `target.region("dtcm")` or the M4 aperture | profiler |
| Reset strategy, clean-window timer, debug-domain gating, probe-attached cycle reads | profiler policy keyed by `target.soc.series` or id | profiler |
| USB transport support | profiler driver-support table | profiler |
| Sync, state, go, BLE-reset GPIO pins; channel; starter profile board | profiler board policy keyed by id, or `extensions.helia_profiler` in an overlay | profiler |
| Built-in or custom | `target.origin` (builtin, overlay) | package |
| Which heliaAOT target name | the same resolver; the private name map is deleted | package |

### helia-estimator and helia-npu

| Question asked today | Answered by | Owner |
|---|---|---|
| NPU clock in a named mode | `target.operating_point(name).npu_mhz` | package |
| NPU family, model, MACs, AXI width | `target.npu.npu.family`, `.model`, `.macs_per_cycle`; `target.npu.axi_width_bits` | package |
| Which memories the NPU reaches and over which port class | `target.npu.memory_ports` mapping region name to port class | package |
| Memory read and write latency, outstanding transactions, burst, AXI clock | `target.region(name).characterization` with provenance | package |
| Revision, origin, provenance roll-up | `target.soc.revision`, `target.origin`, `target.provenance()` | package |
| Vela memory mode for a placement; system-config file | helia-npu, from the port classes above | helia-npu |
| Burst-split codes, timing-adapter programming | helia-npu | helia-npu |
| Which memory holds const, arena, cache in a run | estimator run configuration | estimator |
| Energy per cycle and per bit | estimator model keyed by `target.soc.id` and mode | estimator |
| Per-run timing overrides | estimator | estimator |
| Load a SoC by id or path with overrides | `resolve`, `load_overlay` (merge, remove, provenance inheritance) | package |
| Same SoC on compile target and platform | `target.soc.id` equality | package |
| heliaAOT codegen proxy name | the shared resolver | package |

### neuralspotx and Zephyr

neuralspotx is a source today, not a consumer. Its questions (which SoC
is this board, which toolchains build it, is module M compatible with SoC
S) are answered by its own `board.yaml` and registry, and the package
mirrors the facts: `board.soc`, `soc.build.toolchains`, `soc.build.abi`
and the exact-case ids. Zephyr enters through heliaAOT's zephyr module
type: the Zephyr board id equals the neuralspotx board id, and the package
carries Zephyr link windows and section names per board for the boards
Zephyr ships, pinned to a Zephyr revision.

## API

Stdlib dataclasses, frozen. No I/O at import. Runtime dependencies are
PyYAML, used only by `load_overlay`, and typer for the CLI (heliaAOT
already depends on typer, so no consumer gains a new dependency).

### `helia_platforms.catalogue`

```python
def builtin() -> Catalogue                      # cached, immutable
def load_overlay(source: str | Path | Mapping, *, base: Catalogue | None = None) -> Catalogue

class Catalogue:
    schema_version: int
    catalogue_version: str                      # data release, independent of the package version
    def socs(self) -> tuple[Soc, ...]
    def implementations(self, soc: str | None = None) -> tuple[Implementation, ...]
    def parts(self, soc: str | None = None) -> tuple[Part, ...]
    def boards(self, soc: str | None = None) -> tuple[Board, ...]
    def cores(self) -> tuple[Core, ...]
    def npus(self) -> tuple[Npu, ...]
    def find(self, **predicates) -> tuple[Target, ...]   # core="cortex-m55", npu_model="u85", has_region="psram"
    def resolve(self, name: str) -> Target
    def suggest(self, name: str) -> tuple[str, ...]
    def to_dict(self) -> dict                   # the JSON export
```

### `helia_platforms.resolve`

```python
def resolve(name: str, *, addons: Sequence[str] = (), boot: str | None = None,
            catalogue: Catalogue | None = None) -> Target
def resolve_board(name) -> Board
def resolve_soc(name) -> Soc

class UnknownPlatform(PlatformError):   suggestions: tuple[str, ...]
class AmbiguousPlatform(PlatformError): candidates: tuple[str, ...]   # family shorthands
```

Resolution order: exact id or alias of a board, implementation, part, or
Soc, case-insensitively; a Soc id with exactly one board returns that
board's target; a Soc id with several boards returns the bare Soc target;
a family shorthand raises `AmbiguousPlatform`; anything else raises
`UnknownPlatform` with suggestions.

### `helia_platforms.model`

```python
@dataclass(frozen=True) class Provenance: status, source, verified_on, verified_by, notes
@dataclass(frozen=True) class Core:       id, arch, pmu, has_dsp_extension
@dataclass(frozen=True) class CoreOptions: fpu, fpu_dp, mve, icache_kb, dcache_kb
@dataclass(frozen=True) class Npu:        vendor, family, model, macs_per_cycle; accelerator_config (property)
@dataclass(frozen=True) class NpuInstance: npu, axi_width_bits, base_address, irq, memory_ports, clocks_by_operating_point
@dataclass(frozen=True) class MemoryRegion: name, technology, attachment, size, base, executable, writeable, cacheable, characterization, provenance
@dataclass(frozen=True) class MemoryCharacterization: read_latency_ns, write_latency_ns, max_outstanding, burst_bytes, ports, axi_clock_hz, bandwidth_fraction  (each value may carry its own Provenance)
@dataclass(frozen=True) class OperatingPoint: name, cpu_mhz, npu_mhz, hal_mode, provenance
@dataclass(frozen=True) class SdkFacts:   c_define, cmsis_header, trace_clock_mhz, hal_enums: Mapping[str, str], build: BuildFacts
@dataclass(frozen=True) class BuildFacts: abi, float_abi, toolchains
@dataclass(frozen=True) class Soc:        id, series, aliases, core, core_options, npu, memories, operating_points, sdk, derives_from, revision, release_status, provenance
@dataclass(frozen=True) class Implementation: id, soc, kind, subset: Subset, boot_configs, default_boot, aliases, provenance
@dataclass(frozen=True) class Subset:     memories_removed, memories_resized, memories_rebased, peripherals_removed, max_cpu_mhz, max_npu_mhz, npu_removed
@dataclass(frozen=True) class BootConfig: name, reserved: tuple[Reservation, ...], app_origin, requires_provisioning, provenance
@dataclass(frozen=True) class Reservation: region, offset, size, purpose, provenance
@dataclass(frozen=True) class Part:       id, implementation, silicon_revision, package, radio, jlink_device, reservations, aliases
@dataclass(frozen=True) class MemoryInterface: name, controller, modes, aperture_base, aperture_max
@dataclass(frozen=True) class MemoryDevice: id, technology, capacity, modes, characterization, provenance
@dataclass(frozen=True) class AddOn:      id, fits_boards, occupies, devices, revision, aliases, provenance
@dataclass(frozen=True) class Board:      id, stage, revision, part | implementation, interfaces, population, provisioning, jlink_device, trace_clock_mhz, aliases, extensions, provenance
@dataclass(frozen=True) class LinkEnvironment: owner, link_family, profile, regions: Mapping[str, WindowRegion], source, revision
@dataclass(frozen=True) class WindowRegion: origin, length, app_window, section_names
```

### `helia_platforms.target` (the resolved view)

```python
@dataclass(frozen=True)
class Target:
    id: str; kind: Literal["board", "implementation", "soc"]
    soc: Soc; implementation: Implementation | None; part: Part | None; board: Board | None
    origin: Literal["builtin", "overlay"]
    # structure
    core: Core; core_options: CoreOptions; isa: IsaFeatures; npu: NpuInstance | None
    def memories(self) -> tuple[MemoryRegion, ...]            # on-die after subset, plus external_memories()
    def region(self, name: str) -> MemoryRegion
    def has_region(self, name: str | None = None, *, technology=None, attachment=None) -> bool
    def operating_points(self) -> tuple[OperatingPoint, ...]
    def operating_point(self, name: str | None = None) -> OperatingPoint
    default_operating_point: OperatingPoint
    capabilities: frozenset[str]                              # derived; stable spellings
    stage: str; addons: tuple[AddOn, ...]
    # boot
    boot: BootConfig                                          # selected, else board provisioning, else default
    def boot_configs(self) -> tuple[BootConfig, ...]
    def flash_load_address(self) -> int
    def usable_nvm(self) -> Mapping[str, int]                 # after documented reservations only
    # external memory
    def external_memories(self) -> tuple[MemoryRegion, ...]   # population plus add-ons, at aperture bases
    # link environments (optional)
    def budget(self, environment: LinkEnvironment) -> Mapping[str, int]
    def classify_address(self, address: int) -> str | None   # physical regions
    # debug and SDK
    jlink_device: str | None; trace_clock_mhz: int | None; sdk: SdkFacts
    aliases: tuple[str, ...]
    def provenance(self) -> ProvenanceSummary                 # worst status per group, for reports
```

`IsaFeatures` carries `has_dsp`, `has_mve`, `mve_flavour`, `supports_fp16`,
`supports_fp32`, `supports_fp64`, `has_pmu`, `pmu_kind`.

### Overlays, validation, export, CLI

`load_overlay` parses the format in the Overlays section, validates it
against the JSON Schema and the semantic rules (ids unique, no shadowing,
`based_on` resolves, regions inside physical bounds and non-overlapping,
a subset never adds, FP16 only with MVE-FP, provenance required on
built-ins), and returns a new `Catalogue`. `helia_platforms.export` writes
the JSON catalogue, the JSON Schema and Markdown pages.
`helia-platforms` CLI: `list [socs|boards|parts|implementations]`,
`show <id>`, `windows <id> [--family --profile]`, `validate <overlay>`,
`check-sources` (compare against the committed SDK and Zephyr snapshots),
`export`.

### Adapters, in the consumers

- heliaAOT: `SocPlatform.from_target(t, module_type)` builds the flattened
  view (name lowercased, `memories` from `t.budget(env)` with the environment heliaAOT picks per module type, `capabilities`
  from `t.capabilities` mapped onto its enum plus its own policy tags,
  `min_alignment` and `preferred_memory_order` from heliaAOT tables keyed
  by `t.soc.id`). `platform.overlay:` and `platform.soc:` feed
  `load_overlay`.
- helia-profiler: `SocDef`/`BoardDef` become views over `Target`; its
  policy layer (`SocCapabilities`, GPIO records, reset strategies) stays
  and reads facts from `Target`; its windows table is deleted in favour of
  the generated SDK environment dataset; `target.custom_socs/custom_boards` is translated to the
  overlay format by a shim for one release.
- helia-npu: `SocDefinition` becomes a projection of `Target.npu` and
  `Target.memories()` with their characterization; its Vela and
  timing-adapter code is unchanged.

## Relationship to helia-aot#278

| #278 phase | Where it lands |
|---|---|
| 0: `resolve_platform` stops mutating the registry (#331) | heliaAOT, unchanged; the package's immutable catalogue removes the class of bug for adopters. |
| 1: Soc/Board split, `NpuSpec`, ISA derivation | This package. `SocPlatform` stays heliaAOT's flattened view, built by an adapter. |
| 2: `platform.soc:` config surface | heliaAOT accepts the overlay format (`platform.overlay`) and a `platform.soc:` shorthand that builds a one-entry overlay. |
| 3: NPU variant cross-check | heliaAOT, reading `NpuInstance.accelerator_config` from here. |
| 4: aliases and family shorthands | This package's resolver. |

Changes relative to #278's model: an implementation layer between Soc and
Board (bring-up FPGA, FVP, and the J-Link device per part), capabilities
derived from `CoreInstance` options rather than a cpu-string table,
`preferred_memory_order` and `min_alignment` removed from the shared
model, memory regions with technology, attachment and characterization,
operating points instead of a speeds list, provenance on every fact, and
an immutable catalogue with overlays instead of registration.

## Open questions


1. Does the estimator want `OperatingPoint` to carry voltage or rail
   facts, or is that characterization with provenance like memory timing?
2. Should the package ship the Zephyr link windows for the boards Zephyr
   supports, or expose a hook so a Zephyr-aware consumer supplies them?
3. Of `helia-npu`'s `targets` (FVP, RTL, silicon), the memory substitutions
   and clock choices are implementation description and move here; the
   FVP binary, timing-adapter registers and run flags are harness
   configuration and stay. Confirm with the estimator owners.
4. Whether `extensions` is enough for the profiler's custom-board
   measurement wiring, or whether the profiler keeps its own sidecar file.
