# RFC 0002: the platform model and the API helia-platforms exposes

Status: Accepted, 2026-10-21 (drafted 2026-10-04). Builds on [RFC 0001](0001-platform-catalogue.md)
(the catalog and its data), on AmbiqAI/helia-aot#278 (the Soc/Board
split, typed NPU spec and alias design, captured verbatim in
[research/helia-aot-278.md](../research/helia-aot-278.md)), and on the
[review of RFC 0001](0001-platform-catalogue-review.md). With this RFC
accepted, the sections of RFC 0001 listed in
[Changes relative to RFC 0001](#changes-relative-to-rfc-0001) are
superseded. RFC 0001's appendix remains the reference for the data and its
sources.

## Summary

`helia-platforms` is a queryable model of Ambiq SoCs and the things that
realize them, not a static table. It exposes:

1. a **catalog** of specifications (SoCs), implementations of them
   (FPGA builds, FVP and RTL models, and non-default silicon), silicon
   parts, boards, add-ons and memory devices, every fact carrying
   provenance. Linker windows are not catalog content and the package
   ships none: they belong to the tools that link (#73, 2026-11-05);
2. a **resolver** that turns any accepted spelling into one target, with
   aliases, compositions, family shorthands and did-you-mean in one place;
3. **derived queries**: capabilities such as MVE, FP16 or an Ethos-U85 with
   256 MACs are computed from structural facts, never declared;
4. an **overlay** mechanism so a downstream tool, customer or bring-up team
   describes a new SoC, implementation or board by reference and delta,
   never by restating die facts, and gets a new immutable catalog back;
5. **exports**: a JSON catalog, a JSON Schema for overlays, and a CLI.

Tools keep their opinions. heliaAOT's placement order and alignment
policy, the profiler's reset and PMU planning, the estimator's energy model
all stay in their tools, keyed by canonical id. The package answers
questions of fact.

## Glossary

Each term has one meaning in this RFC, except `revision`, whose meaning depends on the entity that carries it (rows below).

| Term | Meaning |
|---|---|
| specification | A `Soc`: the full design as its datasheet and SDK headers describe it. |
| core instance (role) | A `CoreInstance` in `Soc.cores`: one core with its `role` (`application`, `radio`, `dsp`, `other`), options, clock domain and `programmable_by`. Index 0 is the primary application core. |
| master | A core, NPU or accelerator id, as the subject of an access entry. |
| access entry | An `Access`: whether one master reaches one target (a memory region, or a memory controller in `Soc.memory_controllers`, whose devices inherit the entry), which power domains must be awake, and with what guidance. Never inferred; `default_access` is a declared shorthand for them. |
| image slot | An `ImageSlot`: a range of NVM owned by one core for its image, supplied by the vendor or the customer. |
| clock domain | A `ClockDomain`: cores or accelerators clocked together, with the domain's own named points. |
| operating point | A system `OperatingPoint`: one point per clock domain. `target.cpu_mhz()` and `target.npu_mhz()` read the core-0 and npu-0 domains; `cpu_mhz`/`npu_mhz` are also overlay shorthand that expands to domain points. |
| implementation (kind) | An `Implementation`: a realization of a Soc. `kind` is `silicon`, `fpga`, `fvp` or `rtl`. It realizes the whole Soc unless it declares a validated subset or, for an FVP, its own memory map. An FPGA or FVP implementation is resolvable directly and carries its own carrier facts; it needs no board. |
| part | A `Part`: an orderable silicon device (ordering number, silicon revision, package, radio option). It references its Soc directly. |
| board (category, revision) | A `Board`: a PCB carrying one Part. `category` is `engineering`, `evaluation` or `custom`, a description, not a lifecycle; `revision` is the board revision, which can change the population. |
| revision (Soc) | `Soc.revision`: the design revision of the specification (for example a pre-silicon RTL revision). |
| revision (Part) | `Part.silicon_revision`: the silicon revision of the fitted die. |
| revision (Board, AddOn) | `Board.revision`, `AddOn.revision`: the board revision of the PCB. |
| add-on | An `AddOn`: a shield or daughter board that fits named boards, occupies board interfaces and brings its own population. |
| memory device | A `MemoryDevice`: an external memory part with technology, capacity, driver family and modes. |
| interface | A `MemoryInterface` on a board: controller, modes, XIP aperture and any alias windows. |
| population | Which memory device sits on which interface, as a board ships or as an add-on brings it. A mapping from interface name to device id. |
| provisioning | `Board.provisioning` (or `Implementation.provisioning` for an implementation with no board): the name of the boot configuration the fitted part or build ships with. |
| source label | Where a catalog entry came from: `builtin`, `entry_point:<distribution>`, `env:<path>` or `overlay:<path>`; see `Catalog.sources`. |
| boot configuration | A `BootConfig`: a named boot layout (sbl, nbl, or a custom layout) with its reservations, one application start per programmable core (`app_start`, core 0 by default) and what it `requires`. |
| reservation | A documented range of memory no core's image may use: boot ROM, an SBL partition. Radio firmware is an image slot, not a reservation. |
| linker profile | A named variant of a consumer's linker scripts (`default`, `nbl`). Not the profiler's clock profile (an operating point) and not a neuralspotx starter profile. |
| linker window | The range a piece of software's linker script (an SDK's, Zephyr's, a customer's) lets a build use in a region. Not catalog content: a consumer keeps its own and intersects them with `Target.application_ranges()` (#73). |
| series | The SDK product line (`apollo5`, `atomiq`). Not the profiler's AP3/AP4/AP5 tier, which is profiler policy. |
| origin | Catalog origin only: `builtin` or `overlay`, where an entry came from. The address an application links at is `BootConfig.app_start`; a linker window is the consumer's (#73). |
| provenance status | One of `datasheet`, `sdk`, `measured`, `fitted`, `derived`, `unverified` ([ADR 0003](../adr/0003-provenance-record.md)). The status `derived` marks a value computed from other sourced values, such as a size computed from two addresses. |
| derived capability | A query computed from structural facts (`isa().supports_fp16`). Not the same as `derives_from` or `based_on`; see [Inheritance and derivation](#inheritance-and-derivation). |
| target | The resolved, flattened view `resolve()` returns. Its `kind` is `board`, `part`, `implementation` or `soc`. |
| owner direction | Decisions recorded by the repository owner on 2026-10-04 and folded into the [review of RFC 0001](0001-platform-catalogue-review.md). |

## Principles

| # | Principle | Consequence |
|---|---|---|
| P1 | Facts, not opinions | No `preferred_memory_order`, no tool sections on built-ins. Tools derive policy from facts the package exposes (attachment, latency, ports). |
| P2 | Specification and implementations | A SoC is the full specification. An implementation realizes all of it by default or a validated subset (bring-up FPGA with less memory and lower clocks). An FVP declares its own memory map and names the Soc regions each model region stands in for ([ADR 0007](../adr/0007-fvp-memory-maps.md)). Production silicon is the full set and says nothing extra. |
| P3 | Declared structure, derived capability | Only structural facts are declared. "Supports FP16" is a function of the core's MVE option; "has NPU" is a function of an NPU instance being present; "which NPU" is a structured record. |
| P4 | Every fact has provenance | Status (datasheet, sdk, measured, fitted, derived, unverified), source, date, reviewer. Releases reject `unverified` unless allow-listed. Record and rules per [ADR 0003](../adr/0003-provenance-record.md). |
| P5 | Overlays compose by reference | `based_on`, `soc:`, `part:`; deltas and removals; unknown keys rejected with a suggestion; built-in ids cannot be shadowed. |
| P6 | One resolver | Canonical ids are the neuralspotx/SDK spellings, matched case-insensitively. Exact aliases and composition aliases resolve. Family shorthands (`AP5`, `AP510`) from the built-in shorthands table raise with candidates. Near misses suggest. |
| P7 | Immutable catalog, no global state | Loading an overlay returns a new catalog. Nothing registers into a process-global table (the class of bug in helia-aot#331). No I/O at import. |
| P8 | Stdlib runtime, schema as contract | Frozen dataclasses; PyYAML for overlays and typer for the CLI, nothing heavier; a published JSON Schema with `schema_version`; whether to offer a pydantic extra is [ADR 0002](../adr/0002-schema-format-and-runtime.md)'s open question 2. Format and runtime per ADR 0002. |

## Entity model

```
Core ───────┐                      Npu ──────────┐
 (IP: cortex-m55, cortex-m4,        (IP: arm ethos-u u85, 256 MACs)
  or a non-Arm DSP core)                          │
            ▼                                     ▼
Soc ── cores: [CoreInstance(id, role, core, options: CoreOptions, clock_domain, programmable_by)]
 │            (index 0: primary application core; CoreOptions: fpu, fpu_dp, mve, icache_kb, dcache_kb)
 │     npus: [NpuInstance(id, npu, axi_width_bits, base, irq, sram_port_hash, driven_by, clock_domain)]  accelerators: [...]
 │     memories: [MemoryRegion]   access: [Access(master, target, ...)], default_access
 │     peripherals: [name]   memory_controllers: [name] (those peripherals that are memory controllers)
 │     clock_domains: [ClockDomain]   operating_points: [OperatingPoint] (system points)
 │     boot_configs: {name: BootConfig}, default_boot    (sbl, nbl; app_start per programmable core)
 │     image_slots: {name: ImageSlot(core, region, offset, size, supplier)} (every Part's, unless replaced)
 │     sdk: SdkFacts (c_define, cmsis_header, ...)   default_board   aliases, release_status, provenance
 │
 ├── Implementation (kind: silicon | fpga | fvp | rtl; model; subset of the Soc; default = all;
 │                   the subset may remove the Soc's image slots;
 │                   may replace boot_configs, operating_points, clock domain points; an FPGA
 │                   holds its bitstream's facts and is carried by a Board of category fpga;
 │                   an FVP has no board and declares its own memories, each naming what it
 │                   stands_in_for)
 │
 ├── Part (silicon: references its Soc, and an Implementation only when a non-default one exists;
 │         ordering number, silicon revision, package, radio, jlink_device,
 │         per-part image slots such as the NVM-M41 radio-core slot, each replacing the Soc's
 │         slot of the same name)
 │
 ├── Board (category: engineering | evaluation | custom | fpga; revision; carries one Part,
 │          or for category fpga one fpga Implementation;
 │          memory interfaces; default population; provisioning (boot config in use);
 │          probe and trace facts; aliases)
 │
 └── AddOn (shield or daughter board: fits boards, occupies board interfaces, own population)

MemoryDevice: an external part (APS25616N, IS25WX064): technology, capacity, driver family, modes
Composition: a legacy alias -> board + add-ons (apollo4p_evb_disp_shield_rev2)
Resolved target: Board + AddOns | Part | Implementation | Soc -> one flattened, queryable view
```

### Core and Npu (IP blocks)

`Core` holds architecture facts the IP vendor fixes: `id` (cortex-m4,
cortex-m55), `arch` (armv7e-m, armv8.1-m, or a non-Arm ISA such as an
Xtensa DSP core's), `pmu` (dwt, armv8m), `has_dsp_extension`. Options the
vendor leaves to the implementer live on each core instance's `options`
(`CoreOptions`): `fpu` (none, fpv4-sp-d16, fpv5-sp-d16), `fpu_dp`, `mve`
(none, int, fp), `icache_kb`, `dcache_kb`.

`Npu` is structured, as #278 proposes and the owner direction requires:
`vendor` (arm), `family` (ethos-u), `model` (u55, u65, u85),
`macs_per_cycle` (256 for atomiq110's Ethos-U85, per helia-npu
`socs/atomiq110.yaml` and nsx-npu, as recorded in
[research/helia-estimator.md](../research/helia-estimator.md),
[research/queries-helia-estimator.md](../research/queries-helia-estimator.md)
and RFC 0001 appendix J). `accelerator_config` ("ethos-u85-256") is
derived. The Soc's `NpuInstance` adds the instance facts: id, base
address, IRQ, AXI width, `driven_by` (the core that programs it) and its
clock domain. Which memories it reaches, and over which port, are its
access entries. It stores no clocks: the NPU clock comes from the system
operating point (`target.npu_mhz(point)` for npu 0), and
`Target.npu_clocks(npu=)` is a derived view keyed by operating point. Driver
behaviour (command-stream chunking, Vela system configs, port arbitration
rules) stays in `helia-npu`, which reads the instance facts from here.

### Cores, accelerators and reachability

Ambiq parts already ship with more than one core (the Apollo510 Lite and
Apollo330 Plus Cortex-M4 radio core, DS-A510LS p33, DS-A330PS p33). `Soc.cores`
and `Soc.npus` are ordered, index 0 primary, and every single-core query
defaults to core 0 and npu 0. Reachability is an explicit access matrix
keyed by (master, target), never inferred from the address space; other
cores' NVM is held in image slots; operating points couple clock domains.
Definitions, queries and an example are in [0002-multicore.md](0002-multicore.md).

### Soc (the specification)

| Field | Category | Notes |
|---|---|---|
| `id`, `series`, `aliases` | identity | `series` is the SDK product line (apollo5, atomiq). The profiler's AP3/AP4/AP5 tier is profiler policy keyed by id. |
| `cores: [CoreInstance]` | structural | Ordered; index 0 is the primary application core. Capabilities derive per core. |
| `npus: [NpuInstance]`, `accelerators` | structural | Ordered; index 0 primary; each names `driven_by` and its clock domain. |
| `memories: [MemoryRegion]` | structural, with optional characterization | See below. |
| `access: [Access]`, `default_access` | structural | Reachability per (master, target), never inferred; `default_access` is a declared shorthand with provenance. |
| `clock_domains: [ClockDomain]` | structural | Each with its own named points. |
| `peripherals: [name]` | structural | Named list of every peripheral; an implementation's `peripherals_removed` removes from it. |
| `memory_controllers: [name]` | structural | The peripherals that are memory controllers (mspi0, iom4), each also in `peripherals`; empty by default. Only these, besides regions, may be an `Access` target, a `default_access` grant or a `MemoryInterface.controller`. Removing a peripheral removes it here too; `memory_controllers_removed` removes only the controller, for a package that pins out no memory on it (MSPI1 on the Apollo4 Blue Plus KBR, DS-A4BP p118). |
| `operating_points: [OperatingPoint]` | structural | System points: name, one point per clock domain, system HAL mode where the HAL has one; `target.cpu_mhz()` and `target.npu_mhz()` read the core-0 and npu-0 domains. heliaAOT `speeds` and the profiler `ClockDomain` are views. |
| `default_operating_point` | SDK fact, optional | Set where the SDK names a default; otherwise absent and the choice is tool policy. |
| `boot_configs: {name: BootConfig}`, `default_boot` | structural or SDK fact | The boot layouts the SDKs support, and the default. See Boot configurations. |
| `sdk: SdkFacts` | SDK fact | `c_define`, `cmsis_header`, default trace clock, J-Link's `-cpufreq` where it differs from the trace clock, HAL enums the SDK exposes per SoC, `build` (abi, float ABI). Supported toolchains are neuralspotx policy, not a catalog fact (#18). |
| `derives_from: Soc \| None` | structural | See [Inheritance and derivation](#inheritance-and-derivation). |
| `default_board: Board \| None` | convenience | Used only by an explicit `resolve_board(soc_id)`. Never used by `resolve()`. |
| `release_status` | governance | public or embargoed. Every entity carries one; see Release status. |
| `extensions` | per-tool, proposal | Overlay entries only; see Overlays. |

`MemoryRegion`: `name` (dtcm, ssram, mram, hblram, psram0), `technology`
(sram, mram, rram, psram, flash, nvm, dram), `attachment` (tcm, system, external),
`size`, `base`, optional `alternate_bases` where the silicon aliases the
region, `executable`, `writeable`, `cacheable`, optional
`characterization` (read and write latency, ports, max outstanding reads
and writes per port, `max_beats`, bandwidth) each value with provenance: latency, bandwidth and
ports only. Optional `dma_boundary`, its own fact with its own record: a
single DMA transfer does not cross an address that is a whole multiple of
it from the region's base, so the edges are `base + k * dma_boundary`, not
aligned addresses ([ADR 0011](../adr/0011-dma-boundary.md)). The package carries no energy data; the estimator's energy
coefficients stay in helia-estimator. Characterization is hardware: the
path's limits, as the SoC or IP documentation states them or as measured,
such as the Ethos-U85's per-port outstanding reads and writes. `max_beats`
is the burst split in bytes (64, 128 or 256) the path calls for, named after
the Ethos-U `AXI_SRAM` and `AXI_EXT` field, such as atomiq110's 128-byte SRAM
stripe. Values fitted to make a model match captures are the fit of the tool
that owns them, such as helia-npu, not facts here.

An overlay region may omit `base` (size only, no `based_on`, as RFC 0001
appendix E allowed). Such a region is excluded from the bounds and overlap
check, `classify_address()` returns `None` for it, and `placement_ranges()`
and `flash_load_address()` raise `PlatformError` when they need its
address. This holds whatever the region's `attachment`. The exception is
a device a board populates on an interface with no aperture: it has no
address, and `placement_ranges()` leaves it out. Built-in regions always
carry a base.

### Pre-silicon and silicon

The model covers both phases of a SoC's life, and does not treat the end
state as the only truth:

| Phase | What exists | Modelled as |
|---|---|---|
| Pre-silicon | An FPGA running a reduced build of the RTL (less memory, peripherals absent, lower clocks); an Arm FVP standing in for parts of the system | An `Implementation` of kind `fpga` carried by a `Board` of category `fpga` (Implementation atomiq110_fpga on Board atomiq110_fpga_turbo); an `Implementation` of kind `fvp` with no board. Both resolve directly by their ids |
| Silicon | Parts (with a `silicon_revision`) on boards that serve different needs at the same time | `Part` on a `Board` of category `engineering` (most pins exposed, for internal engineering), `evaluation` (smaller, laid out for customers) or `custom` (a customer's own board, defined in an overlay with its own interfaces, population and add-ons) |

A SoC can have engineering and evaluation boards at once; nothing orders
boards by category, and a board `revision` (which can change the
population) is separate from its category. Every target resolves through
the same API, so a tool written against an FPGA target keeps working on
silicon. How well each tool supports a category or an implementation kind
is that tool's marker.

### Implementation and Part

An `Implementation` names a `soc`, a `kind` and a subset expression:
memories removed, resized or rebased; peripherals removed from
`Soc.peripherals` (and so from `Soc.memory_controllers`); memory
controllers removed from `Soc.memory_controllers` alone; clock caps;
cores or accelerators removed. Everything not mentioned is inherited
from the specification. The validator rejects an implementation that
adds a memory or exceeds a clock; an FVP's own memory list, below, is
not a subset and is checked by its own rules. Rebasing stays available
because an FPGA build may move a region; no built-in uses it (the
atomiq110 FPGA uses the silicon addresses, per research/ambiqsuite.md).

Clock caps act on operating points: a point whose CPU or NPU clock exceeds
`max_cpu_mhz` or `max_npu_mhz` (the core-0 and npu-0 domains;
`max_domain_mhz` caps any domain) is dropped from the implementation. If the
Soc's default point is dropped, `default_operating_point` is `None`, and
`npu_clocks()` follows the remaining points. Removing the default point by
name with `operating_points_removed` clears it the same way. If no point survives, the
implementation must declare its own `operating_points`, adding or
replacing domain points through `Implementation.clock_domains`.

An FPGA is a reduced implementation of the specification on a carrier
board (decided on #104). The bitstream's difference from the Soc is an
Implementation of kind `fpga`: its subset, clock domains, operating
points, boot configurations, and values that depend on the image, such
as `trace_clock_mhz`. The carrier is a Board of category `fpga` that names
that Implementation in `implementation` instead of a Part; a Board names
exactly one of `part` and `implementation`. The Board holds the carrier
facts: `jlink_device`, `provisioning`, `interfaces` and `population`. A
second Implementation is added only when a second bitstream is used; a
bitstream that adds or changes hardware is its own Soc. A Part names only
a `silicon` Implementation. An FPGA Implementation may add a clock domain
the Soc lacks; the subset limits check only the domains the Soc has. The
built-in atomiq110 FPGA is Board `atomiq110_fpga_turbo` (the id
neuralspotx and helia-profiler use) carrying Implementation
`atomiq110_fpga` (facts from
[research/ambiqsuite.md](../research/ambiqsuite.md)):

- Clocks: each FPGA domain point overrides the Soc's point of the same
  name at the silicon clock divided by 10 (the helia-estimator owner,
  2026-10-27, #68). The HAL is built for CPU `lp` at 25 MHz,
  `ATOMIQ11X_FPGA 25` (`mcu/atomiq110/am_mcu_apollo.h:85-87`). mbhssain
  measured every point, CPU `ulp` 10, `lp` 25 and `hp` 50 MHz and NPU `ulp`
  10 and `hp` 50 MHz, on one FPGA image, and expects them to match across
  FPGA drops (review of #133), so all five are `measured`. All six system
  points keep the Soc's names, and the default `lp_ulp` is 25 MHz CPU and
  10 MHz NPU. nsx-core says the FPGA's HFRC is fixed at 25 MHz whatever
  the CPU mode (`modules/nsx-core/src/atomiq110/nsx_system_platform.c:66-69`),
  which disagrees with the measured 50 MHz point. The 12 and 48 MHz in the
  HAL's comment are examples of other images, not points.
- `peripherals_removed`: IOM2 to IOM11, `unverified`. Only AmbiqSuite's
  `am_bsp.c:1177-1179` says so, and the BSP header nsx-ambiq-sdk ships
  defines pins for IOM0 to IOM6.
- No J-Link device: no atomiq110 spelling is in SEGGER's stock database
  (#130).
- `trace_clock_mhz: 50`, status `measured` by mbhssain in the review of
  #133 (https://github.com/AmbiqAI/helia-platforms/pull/133#discussion_r4414528238).
  An AmbiqSuite program prints a numbered line over ITM, and
  `JLinkSWOViewerCLExe` samples SWO at 1 Mbaud while the SWO prescaler
  (ACPR) is swept and read back over SWD. Lines decode only for ACPR+1 =
  49 to 52, which puts the trace clock at 50.5 ± 0.5 MHz, the HFRC's
  500 MHz divided by 10 (AmbiqSuite `am_hal_itm.c`, `ATOMIQ11X_FPGA`
  branch). neuralspotx `neuralspotx-v0.9.0`,
  `src/neuralspotx/boards/atomiq110_fpga_turbo/debug.cmake:6-18`, says
  48 MHz, but 48 MHz decodes no lines at 1 Mbaud, nor at its own
  1.92 Mbaud. Whether the trace clock varies by FPGA image is open (#19).
- No external memory on the Board: nsx-psram has no mapping for it, and
  neither helia-profiler nor helia-npu says anything is fitted. The
  Implementation removes HBLRAM, which nsx-ambiq-sdk says the FPGA lacks
  (`boards/atomiq110_fpga_turbo/board.cmake:25-28`).

An FVP implementation names its `model` (corstone-320) and declares its
own `memories`, the complete memory list of the realized Soc: no Soc
region is inherited, and a region with a Soc region's name represents that
region. A model region lists the Soc regions it emulates in
`stands_in_for`; the Corstone-320's DDR region stands in for `hblram`,
`psram` and `rram`. Inherited access entries to Soc regions the FVP does
not list are dropped, and the FVP adds or replaces entries with its own
`access`. `memories` and `stands_in_for` are allowed only for kind `fvp`;
`access` is allowed for any kind, so an FPGA can restate a path whose
limits differ from silicon's. An FVP's `memories` replaces the
`memories_*` deltas rather than combining with them ([ADR 0007](../adr/0007-fvp-memory-maps.md)). The
estimator's Corstone-320 model of atomiq110 is therefore first-class
rather than a private convention. An Implementation's boot configurations
and operating points merge with the Soc's by key, and it removes any it
must not offer with `subset` (ADR 0002 section 2.5).

Production and engineering silicon is a `Part`. A Part references its
`soc` directly and names an `implementation` only when a non-default
silicon implementation exists; there are no implicit silicon
Implementation ids. A Part carries an ordering number (AP510NFA-CBR),
`silicon_revision`, package, radio option, `jlink_device`, and per-part
image slots. A Soc may carry image slots too; they apply to the bare Soc
and to every Part, and a Part's slot of the same name replaces one. On the
Apollo510 Lite and Apollo330 Plus parts the top of NVM (NVM-M41,
Cortex-M4 firmware), 16, 288 or 432 KB depending on the variant
(DS-A510LS p33, DS-A330PS p33, as recorded in
[research/datasheets.md](../research/datasheets.md)), is the radio core's
image slot, vendor-supplied by default. The Soc carries the 16 KB slot of
the plain parts, and each radio part replaces it with its larger one.

### Boot configurations

Boot layout is a named choice, not a single fact:

```
BootConfig: name, reserved: {purpose: (region, offset, size)},
            app_start: {core id: (region, offset)}   (a single (region, offset) means core 0),
            requires (sbl | none | custom), provenance
```

- The Soc carries the boot configurations its SDKs support and a
  `default_boot`. Datasheet-documented partitions (the Apollo510 NVM-SBL
  region) carry datasheet provenance. SDK conventions carry SDK
  provenance: the Apollo3 application start 0xC000 comes from the
  AmbiqSuite linker scripts and `AM_SECBOOT_DEFAULT_NONSECURE_MAIN` in
  `tools/apollo3_scripts/am_defines.py`; the Apollo4 start 0x18000 comes
  from the AmbiqSuite Apollo4 linker scripts, while
  `tools/apollo4_scripts/am_defines.py` sets 0xC000 and is recorded as a
  conflict ([research/ambiqsuite.md](../research/ambiqsuite.md)). The SBL
  reservation on Lite and 330 Plus parts is also an SDK convention.
- The atomiq110 Soc's `default_boot` is the no-bootloader layout, because
  the FPGA is the only atomiq110 hardware today (decided 2026-10-05, see
  #28). nsx-ambiq-sdk makes the same choice and keeps its sbl scripts for
  future silicon (`v5.2.24` `cmake/socs/atomiq110.cmake:20-23`). Revisit
  this default when atomiq110 silicon ships with an SBL.
- An Implementation's boot configurations merge with the Soc's by key
  (ADR 0002 section 2.5); it can remove some and replace the default. The
  atomiq110 FPGA offers only its no-bootloader layout; its flash addresses
  are the silicon ones (AmbiqSuite `tools/atomiq110_scripts/jlink-ota.txt`).
- A Board records its `provisioning`: which configuration the fitted part
  ships with. Ambiq EVBs ship SBL-provisioned; a customer board says what
  it uses; an FPGA Implementation records its own.
- The flash load address has one derivation:
  `Target.flash_load_address(core=0)` is the base of that core's
  `app_start` region in the selected configuration (after any
  implementation rebase) plus its offset. The selected configuration
  is the explicit `boot=` argument, else the board's provisioning, else
  the implementation's, else the default. `usable_nvm()` derives from the same selection. The package
  warns when an explicit selection differs from the board's provisioning.
- Documented reservations (boot ROM, SBL partition) and other cores'
  image slots are always subtracted. Stack, heap and toolchain carve-outs are not: they
  belong to the consumer's linker windows.
- `Target.application_ranges(core=0, *, include_discouraged=False)` is the
  address-level form of the same facts (#73, decided 2026-11-05): per
  region of `memories()` with a base, the disjoint half-open byte ranges
  `[start, end)` an application for that core may occupy under the
  selected boot configuration, in the region's own address space (its
  `base`, as `flash_load_address()` uses it), each with the region, core,
  boot, the core's access entry and a `derived` record naming the facts
  it came from. A region every byte of which is taken maps to an empty tuple; a
  region with no base is left out, so unknown and empty are told apart.
  It applies no `programmable_by` view. A consumer that links intersects
  these with its own linker windows; on the Apollo330 Plus and Apollo510
  Lite EVB parts the MRAM range is `[0x00410000, 0x00594000)`.

### Board, external memory and add-ons

A `Board` carries one Part, a `category` (`engineering`, `evaluation` or
`custom`) and a `revision`, probe and trace facts
(`jlink_device` override, measured trace clock), `provisioning`, and
aliases. `tier` and `channel` are gone: support level is a per-tool
marker keyed by id.

External memory is composed, not fixed, because the same board ships with
different populations across revisions (the Apollo330 Plus and Apollo510
Lite EVB rev 2.0 leave the PSRAM footprint empty), shields add memory (the
Apollo4 Plus display shield carries a PSRAM and an octal flash, and the
earlier Apollo4 display shield a different flash, QS-A4PDK p13), and
customers add daughter boards.

- `MemoryInterface` on the Board: name, controller (mspi0, mspi1, iom4),
  modes (octal DDR, hex), aperture base and maximum size, and optional
  `alternate_bases`: other windows onto the same device. A device
  populated on the interface takes the aperture base as its region's
  `base`, which `placement_ranges()` gives, and the others as its
  `alternate_bases`. Where a controller has a read/write window and a
  cached read-only XIP window, the read/write one is the aperture base:
  Apollo3 Blue Plus's MSPI1 is at 0x54000000 (XIPMM) with its XIP window
  0x04000000 as an alternate base (DS-A3P p82, p244, p249). An alternate
  base needs an aperture base, and no window (the aperture base or an
  alternate base, `aperture_max` long) may overlap an on-chip Soc region
  or another interface's window, the board's Implementation's included. The
  controller is a memory controller of the Soc (a `Soc.memory_controllers`
  entry); devices populated on the interface inherit that controller's
  access entries ([0002-multicore.md](0002-multicore.md)). An interface
  without aperture fields yields devices with no base: they are not
  addressable, `external_memories()` reports them without a base,
  `placement_ranges()` leaves them out, and the aperture validator skips
  them with a warning. A PSRAM on an IOM, which has no XIP aperture, is
  one: firmware reaches it only through its driver.
- `MemoryDevice`: an external part with technology, capacity,
  `driver_family`, supported modes and optional characterization, each
  value with provenance. Capacity and driver family are separate facts.
  Capacity is never inferred from a part marking or a BSP macro: the
  Apollo510 EVB PSRAM is 64 MB by hardware measurement although its BSP
  macro names a 256 Mb driver family. The driver family is recorded
  because the SDK uses it.
- `population`: which device sits on which interface as the board ships.
- `AddOn`: a shield or daughter board that names the boards it fits
  (`fits_boards`), the interfaces it occupies (`occupies`) and its own
  `population` on those interfaces. Its optional `modes` narrows an
  occupied interface's modes while it is fitted, each a mode the board's
  interface lists, keeping at least one mode of the add-on's device there
  (a device that lists no modes is not checked): the Apollo4 Plus Display
  Kit's shield runs MSPI0 in `octal-ddr` only, because MSPI1 is unusable
  while MSPI0 is in hex mode (DS-A4P p115). `Target.interfaces` carries
  the narrowed modes.
- The resolved target is board plus selected add-ons plus overlay. The
  validator rejects two devices on one interface, an add-on on an
  interface the board or another add-on already uses (an occupied
  interface counts even without a device), an add-on on a board it does
  not fit, a board interface with the same name as one of its
  Implementation's, and a device larger than its aperture.

AmbiqSuite's per-shield board directories (`apollo4p_evb_disp_shield_rev2`)
and neuralspotx's matching board id become entries in the catalog's
`compositions` table: an alias mapped to a board id and add-on ids.
`resolve("apollo4p_evb_disp_shield_rev2")` returns the `apollo4p_evb`
board target with the display shield `apollo4p_disp_shield` in
`Target.addons` (shield revision 1; the `_rev2` is the EVB revision,
QS-A4PDK p18). The kit's part number, `AMAP4PDISP` (the EVB with the
shield, QS-A4PDK p18), is a composition of the same board and add-on.
`Target.id` is the board id, and the legacy id is kept in
`Target.aliases`. heliaAOT artefact names use `Target.id`, except that
for a plain alias heliaAOT keeps the name the user passed and records the
canonical id alongside (decided; see [0002-migration.md](0002-migration.md)).

### Release status

Every entity (Soc, Implementation, Part, Board, AddOn, MemoryDevice)
carries a `release_status`: public or embargoed. It defaults to
`embargoed` when omitted, for built-in and overlay entries alike, and the
loader rejects a built-in entry that is not `public`
([ADR 0005](../adr/0005-publication-and-embargo.md)). Core and Npu IP
blocks carry no status. A target's effective
status is the most restrictive status along its reference chain (board,
its part or implementation, the Soc, selected add-ons and the memory
devices they populate). A `Composition` is not given a most-restrictive
status: it is scrubbed and shipped, as below.

The export filter uses the effective status and never ships an embargoed
entry or a target whose effective status is embargoed, and it scrubs
embargoed ids from every table and reference: shorthands, compositions,
`fits_boards`, `default_board` and aliases. A Composition is
dropped when its board or any of its add-ons is scrubbed, and so is a Core or Npu
that no exported Soc references (ADR 0005,
[RFC 0003](0003-export-and-pages.md)).

### Private and future silicon

Unreleased hardware never enters this repository (an unreleased SoC, or a
board, add-on or memory device for a released one), so the export filter is
defence in depth, not the primary control. `builtin()` side-loads them
from private packages in the entry-point group `helia_platforms.catalogs`
and from overlays in `HELIA_PLATFORMS_PATH`; side-loaded entries have
origin `overlay` and a source label, never shadow built-ins, and carry
provenance and `release_status`. Rules, load order and conflict errors are
in [0002-private-silicon.md](0002-private-silicon.md).

### Linker windows stay with the consumers

Linker windows are properties of software (an SDK's scripts, Zephyr's
devicetree, a customer's own script), not of the silicon, and the package
neither models nor ships them. Amended 2026-11-05 (#73, owner decision):
the first form of this section defined a `LinkEnvironment` schema, a
`Target.budget(env)` query, a `windows` command and an optional dataset
generated from the committed source snapshots. That was dropped before it
shipped. Windows describe an SDK's scripts, not the hardware; one consumer
budgets from them; a shipped dataset would pin one SDK snapshot while the
profiler builds against the SDK it qualifies; and a public wheel would
carry an internal tool's memory layout.

What the package gives instead is `Target.application_ranges()`, above:
the address ranges an application may occupy in each region after the
boot reservations and other cores' image slots, with no linker knowledge.
helia-profiler keeps its windows per link family and linker profile,
regenerated from the nsx-ambiq-sdk it builds against, and intersects them
with those ranges for its pre-build fit check; it keeps using the windows
for post-build accounting and placement verification. heliaAOT plans
against physical sizes (#28) and keeps its own Zephyr section-name table.
The committed snapshots stay as evidence for `check-sources` (ADR 0006),
which reads linker regions to check catalog facts but ships none.

## Derived capabilities

The package computes, and exposes both as typed properties and as a
stable string set (`Target.capabilities`) for tools that want one:

| Query on `Target` (per core; `core=` defaults to 0) | Derived from |
|---|---|
| `isa().has_dsp` | `Core.has_dsp_extension` |
| `isa().has_mve`, `isa().mve_flavour` | `CoreOptions.mve` |
| `isa().supports_fp16` | `CoreOptions.mve == fp` |
| `isa().supports_fp32` | `CoreOptions.fpu != none` |
| `isa().supports_fp64` | `CoreOptions.fpu_dp` |
| `isa().has_pmu`, `isa().pmu_kind` | `Core.pmu` (`has_pmu` is false for `none` and `dwt`) |
| `npu` (npu 0, `None` when absent), `npus()` | `Soc.npus` after the implementation subset |
| `has_external_memory(technology)` | board population plus selected add-ons |

heliaAOT maps these onto its `SocCapability` enum in its adapter; the
profiler's `SocCapabilities` builders consume them; `BLE` and `USB` tags
disappear from built-ins. Unknown or bespoke cores declared in an overlay
must state the `CoreOptions` explicitly; there is no "trust the
declaration" path because there is nothing to declare but facts.

## Resolution and naming

`resolve(name)` accepts a board id, a part id, an implementation id, a Soc
id, a composition alias, or an alias, case-insensitively, and returns one
resolved target. A Soc id always resolves to the bare Soc target, never to
a board (heliaAOT's bare `atomiq110` target stays valid, as #278
resolved). Resolution never depends on how many boards a catalog holds.
A Soc may name a `default_board`, which only the explicit
`resolve_board(soc_id)` uses. An implementation id (`atomiq110_fpga`)
resolves directly to an implementation target, and an FPGA board id
(`atomiq110_fpga_turbo`) to a board target over the same realized Soc.

The catalog holds two name tables besides ids and aliases:

- `compositions`: alias to (board id, add-on ids), so legacy per-shield
  ids resolve to a board plus its add-ons (see Board, external memory and
  add-ons).
- `shorthands`: shorthand to member ids (`AP5`, `AP510`). It is the only
  source of `AmbiguousPlatform`, which lists the members. Shorthands are
  built-in only.

Near misses raise `UnknownPlatform` with suggestions. Aliases and
composition aliases are unique across all entities; overlays may add
aliases but cannot shadow a built-in id, alias, composition or shorthand.
heliaAOT keeps printing the lowercase form; the profiler keeps the
neuralspotx spelling; both come from the same resolver.

## Overlays

One format for every downstream party: a tool shipping extra entries, a
customer describing a production board, a bring-up team describing an
FPGA cut. The complete overlay syntax is specified in
[ADR 0002](../adr/0002-schema-format-and-runtime.md) (#7); this RFC fixes
the semantics, not the syntax. The examples below
show one entry per entity kind, with field names as in the model.

Semantics every overlay entry shares:

- `based_on` copies facts, and `extensions` per tool key; aliases,
  `default_board`, `derives_from`, `release_status` and the provenance of
  changed values are not inherited
  (see [Inheritance and derivation](#inheritance-and-derivation)).
- Defaults: `release_status` is `embargoed` unless the entry declares it,
  and a value with no declared provenance has status `unverified`.
- Size suffixes `K`, `M` and `G` mean KiB, MiB and GiB (binary bytes),
  never bits. ADR #7 may change the spelling but not the unit.
- A Soc delta uses the same vocabulary as an implementation `Subset` where
  it applies: `memories_removed`, `memories_resized`, `memories_rebased`,
  `peripherals_removed`, `memory_controllers_removed`.
- Removing a region, memory controller, core, NPU or accelerator, in a
  delta or an implementation `subset`, also removes the inherited `access`
  entries that name it, and removing a peripheral removes it from the
  inherited `memory_controllers`. An `access` entry or `memory_controllers`
  name that the overlay entry itself writes and that names a removed unit
  is a reference error.
- `cpu_mhz` and `npu_mhz` in an overlay operating point are shorthand: they
  expand to a point of that name in the core-0 and npu-0 clock domains. A
  single `app_start` means core 0. The multicore forms are in
  [0002-multicore.md](0002-multicore.md).

A Soc delta:

```yaml
schema_version: 1
socs:
  my_soc:
    based_on: apollo510
    memories_resized: {ssram: 2M}
```

An Implementation (an FPGA cut):

```yaml
schema_version: 1
implementations:
  atomiq110_fpga_rev3:
    soc: atomiq110
    kind: fpga
    subset:
      memories_removed: [hblram]
      memories_resized: {dtcm: 256K}
      max_cpu_mhz: 25
      peripherals_removed: [iom2, iom3]     # illustrative ids
      boot_configs_removed: [sbl]           # the SDK keeps sbl for future silicon
    clock_domains:                      # domain ids illustrative
      cpu: {fpga: {mhz: 25}}            # image-dependent: 12, 25 (default), 48 MHz
      npu: {fpga: {mhz: 25}}
    operating_points:
      fpga: {domains: {cpu: fpga, npu: fpga}}
    # shorthand for clock_domains and operating_points above:
    #   operating_points: {fpga: {cpu_mhz: 25, npu_mhz: 25}}
    boot_configs:
      nbl_fpga: {reserved: {}, app_start: {region: rram, offset: 0}, requires: none}
    default_boot: nbl_fpga
boards:
  my_fpga_carrier:                      # the carrier: names the bitstream, not a Part
    category: fpga
    implementation: atomiq110_fpga_rev3
    provisioning: nbl_fpga
```

A MemoryDevice (an illustrative customer part):

```yaml
schema_version: 1
memory_devices:
  acme_psram_8m:
    technology: psram
    capacity: 8M
    driver_family: acme_xspi
    modes: [hex-ddr, octal-ddr]
```

A custom Board:

```yaml
schema_version: 1
boards:
  my_product_v1:
    category: custom
    revision: "1.0"
    part: AP510NFA-CBR
    interfaces:
      # Apollo510 datasheet DS-A510-1p1p0 p36 and p98: MSPI0 XIP 0x60000000-0x6FFFFFFF
      mspi0: {controller: mspi0, modes: [hex-ddr], aperture_base: 0x60000000, aperture_max: 256M}
    population: {mspi0: acme_psram_8m}
    provisioning: sbl
    extensions:
      helia_profiler: {sync_gpio: 27}
```

An AddOn:

```yaml
schema_version: 1
addons:
  my_psram_daughter:
    fits_boards: [apollo4p_evb]
    occupies: [mspi1]
    population: {mspi1: acme_psram_8m}
```

`load_overlay(source) -> Catalog` returns a new catalog; the built-in
catalog is never mutated. Unknown keys outside `extensions` are rejected
with a suggestion. A JSON Schema is published for editors and CI.

`extensions` is a proposal (see open question 4): an opaque, per-tool map
on Soc, Implementation, Board and AddOn entries that the package stores
and returns but never reads or validates, so one file can travel between
tools. Built-in entries may not carry it.

### Inheritance and derivation

This is the one definition of both relations.

- `based_on` is overlay inheritance and applies to any entity kind. The
  new entry copies the facts of the named entry, then applies its own
  deltas and removals. The result is an independent entry with its own id.
  Not inherited: `aliases`, `default_board`, `derives_from`, and
  `release_status` (the entry's own, default `embargoed`). Unchanged values
  keep the base entry's provenance; changed values take the overlay's
  provenance as declared, or status `unverified` where none is declared.
- `derives_from` is a relation between built-in Socs: a variant that
  shares another Soc's SDK headers (apollo510b derives from apollo510;
  apollo5b, which also reads apollo510's headers, is not in the catalog,
  #64). The validator requires equal physical regions.
- An overlay `based_on` does not imply `derives_from`. `my_soc` above is
  based on apollo510 but does not derive from it, and its resized SSRAM
  would fail the `derives_from` rule.

## Question surface

The state of each consumer on 2026-10-04, with file:line references, is in
`docs/research/queries-*.md`.

Every question a consumer's code asks of a platform today, the API in this
RFC that answers it, and the questions that remain the tool's own. "Target"
below is the resolved object returned by `resolve()`.

### heliaAOT

| Question asked today | Answered by | Owner |
|---|---|---|
| Is MVE (or DSP) available, for kernel selection | `target.isa().has_mve`, `target.isa().has_dsp` (core 0); `target.capabilities` string set for the existing membership tests | package |
| Native FP16 | `target.isa().supports_fp16` | package |
| Is there an NPU, and which | `target.npu` (npu 0: `None` or `NpuInstance` with `.npu.model`, `.npu.macs_per_cycle`, `.npu.accelerator_config`); `target.npus()` for all | package |
| Which core and NPU to compile for | core 0 and npu 0 implicitly; `platform.core` and `platform.npu` are future additive options | package default; choice is heliaAOT's |
| Memories and byte sizes to budget | On-chip RAM (DTCM, ITCM, SRAM) from `target.memories()`, except atomiq110's HBLRAM until its technology and CPU reach are confirmed (#19), NVM from `target.usable_nvm()` and external memories from `target.external_memories()`, for every module type. NVM leaves out the boot reservations and other cores' image slots, because planning into them would overwrite the bootloader or radio firmware. heliaAOT does not budget from a linker window (decided 2026-10-05, see #28) | package |
| Is ITCM present | `target.has_region("itcm")` | package |
| Minimum alignment | heliaAOT table keyed by `target.soc.id` (16 with MVE is a placement rule) | heliaAOT |
| Order to try memories | heliaAOT policy; inputs available as `region.attachment` and `region.characterization` | heliaAOT |
| CPU string for compiler flags | `target.core.id`, `target.core_options.fpu`, `.mve` | package |
| Name to print and to key artefacts | `target.id` (canonical) and `target.aliases`; heliaAOT lowercases, and for an alias keeps the name passed and records the canonical id (decided) | package |
| Zephyr section names for TCM | heliaAOT's own Zephyr section-name table (#73); no module type budgets from a linker window | heliaAOT |
| SoC list for the nsx manifest | `catalog.socs()` ids in neuralspotx spelling | package |

### helia-profiler

| Question asked today | Answered by | Owner |
|---|---|---|
| Which SoC, part, implementation is this board | `resolve(board).soc`, `.part`, `.implementation` | package |
| Core, PMU kind, MVE | `target.core`, `target.core.pmu`, `target.isa()` (core 0; `target.cores()` for all) | package |
| Clock speeds, names, default | `target.operating_points()`, `target.default_operating_point` (`None` where the SDK names no default), `target.cpu_mhz(point)`; HAL mode names from `DomainPoint.hal_mode` per domain (`OperatingPoint.hal_mode` is the system mode where the HAL has one) | package where the SDK names a default; otherwise profiler policy |
| Region sizes to report | `target.memories()`, `target.usable_nvm()`, `target.external_memories()` (physical) | package |
| Capacities for the pre-build fit check | `target.application_ranges()` intersected with the profiler's own windows for the build's link family and linker profile (#73); `target.memories()` and `target.usable_nvm()` where it has no window | package gives the ranges; the windows and the fallback are profiler policy |
| Linker windows for placement verification and measured used and free bytes | The profiler's own windows, regenerated from the nsx-ambiq-sdk it builds against (#73) | helia-profiler |
| Which region holds address X | `target.classify_address(addr)` over physical regions, as seen by core 0 (`master=` for another) | package |
| J-Link device name | `target.jlink_device` (board, else implementation, else part) | package |
| App flash load address | `target.flash_load_address()` from the selected boot configuration (explicit `boot=`, else board provisioning, else default) | package |
| Placement base addresses | `target.region(name).base` | package |
| Is PSRAM fitted | `target.has_external_memory("psram")` | package |
| D-cache present | `target.core_options.dcache_kb` | package |
| Shared SSRAM power domain, HAL enum names, C define, CMSIS header | `target.sdk` | package |
| Radio present | `target.part.radio` (`target.part` is `None` on Soc and implementation targets) | package |
| Trace clock | `target.trace_clock_mhz` (board, else implementation, else SDK default; `None` means core-clocked). On Apollo3 it is the 6 MHz TPIU clock, and J-Link's `-cpufreq` takes 48 MHz (the HFRC) instead, which J-Link divides by 8 itself (#67); that value is `target.sdk.jlink_cpufreq_mhz` | package |
| Is this an FPGA | `target.implementation.kind == "fpga"` (`target.implementation` is `None` on Soc targets and on parts with no non-default implementation) | package |
| RTT scan ranges | profiler rule over `target.region("dtcm")` or the M4 aperture | profiler |
| Reset strategy, clean-window timer, debug-domain gating, probe-attached cycle reads | profiler policy keyed by `target.soc.series` or id | profiler |
| USB transport support | profiler driver-support table | profiler |
| Sync, state, go, BLE-reset GPIO pins; channel; starter profile board | profiler board policy keyed by id, or `extensions.helia_profiler` in an overlay | profiler |
| Built-in or custom | `target.origin` (builtin, overlay) | package |
| Which heliaAOT target name | the same resolver; the private name map is deleted (see [0002-migration.md](0002-migration.md)) | package |

### helia-estimator and helia-npu

| Question asked today | Answered by | Owner |
|---|---|---|
| NPU clock in a named mode | `target.npu_mhz(name)` (npu 0), from the system operating point; `target.npu_clocks(npu=)` is a derived view | package |
| NPU family, model, MACs, AXI width | `target.npu.npu.family`, `.model`, `.macs_per_cycle`; `target.npu.axi_width_bits` | package |
| Which memories the NPU reaches and over which port class | `target.reachable(target.npu.id, region)`: the NPU's access entries, with `port` | package |
| Memory read and write latency, outstanding transactions, burst, AXI clock | `target.reachable(target.npu.id, name).characterization` where present, which overrides the region's for that master; else `target.region(name).characterization`; with provenance | package |
| Revision, origin, provenance roll-up | `target.soc.revision`, `target.origin`; the roll-up is deferred (`provenance()` below) | package |
| Vela memory mode for a placement; system-config file | helia-npu, from the port classes above | helia-npu |
| Burst-split codes, timing-adapter programming | helia-npu | helia-npu |
| Which memory holds const, arena, cache in a run | estimator run configuration | estimator |
| Energy per cycle and per bit | estimator model keyed by `target.soc.id` and mode | estimator |
| Per-run timing overrides | estimator | estimator |
| Load a SoC by id or path with overrides | `resolve`, `load_overlay` (merge, remove, provenance inheritance) | package |
| Same SoC on compile target and platform | `target.soc.id` equality | package |
| heliaAOT codegen proxy name | the shared resolver | package |

### neuralspotx and Zephyr

neuralspotx's role and its own questions are recorded in
[research/queries-neuralspotx-zephyr.md](../research/queries-neuralspotx-zephyr.md);
neuralspotx is a consumer (#18): it reads `target.soc`,
`soc.sdk.build.abi` and the exact-case ids from the catalog, and keeps its
own supported-toolchain list.
Zephyr enters through
heliaAOT's zephyr module type: the Zephyr board id equals the neuralspotx
board id. Zephyr link windows and section names are heliaAOT's own
(#73); the package does not carry them.

## API

Stdlib dataclasses, frozen. No I/O at import. Runtime dependencies are
PyYAML and typer for the CLI. The typer
range must overlap every consumer's own typer pin (helia-profiler caps
it, see research/queries-helia-profiler.md and helia-profiler#459); typer
stays a core dependency (decided).

### `helia_platforms.catalog`

```python
def builtin(include_plugins: bool = True) -> Catalog   # cached, immutable; plugins: entry points, then HELIA_PLATFORMS_PATH
def load_overlay(source: str | Path | Mapping, *, base: Catalog | None = None) -> Catalog

class Catalog:
    schema_version: int                         # the file format and export shape (ADR 0004)
    catalog_digest: str                         # sha256 of the data without provenance (ADR 0004)
    compositions: Mapping[str, Composition]     # alias -> board id and add-on ids
    shorthands: Mapping[str, tuple[str, ...]]   # built-in only; the only source of AmbiguousPlatform
    sources: Mapping[tuple[str, str], str]      # (table, entry id) -> source label
    def socs(self) -> tuple[Soc, ...]
    def implementations(self, soc: str | None = None) -> tuple[Implementation, ...]
    def parts(self, soc: str | None = None) -> tuple[Part, ...]
    def boards(self, soc: str | None = None) -> tuple[Board, ...]
    def cores(self) -> tuple[Core, ...]
    def npus(self) -> tuple[Npu, ...]
    def addons(self) -> tuple[AddOn, ...]
    def memory_devices(self) -> tuple[MemoryDevice, ...]
    def find(self, **predicates) -> tuple[Target, ...]   # core="cortex-m55", npu_model="u85", has_region="psram"
    def resolve(self, name: str, *, addons: Sequence[str] = (), boot: str | None = None) -> Target
    def suggest(self, name: str) -> tuple[str, ...]
    def identity(self) -> CatalogIdentity       # package and schema versions, digest, sources (ADR 0004)
    def to_dict(self) -> dict                   # the JSON export (RFC 0003)

class CatalogIdentity:                          # frozen; to_dict() has these keys
    package_version: str
    schema_version: int
    catalog_digest: str
    sources: tuple[SourceIdentity, ...]         # applied on top of the built-in data, in order

class SourceIdentity:                           # frozen; to_dict() has these keys
    label: str                                  # entry_point:<distribution>, env:<file> or overlay:<file>, no directory
    schema_version: int                         # as declared; the current one for a mapping that omits it
    sha256: str                                 # the parsed mapping, records removed on declared keys only; schema_version as read
    distribution_version: str | None            # entry points only
```

`sources` is keyed by table and id because cores, add-ons and memory
devices each have their own namespace, so an id can recur across tables.

### `helia_platforms.resolve`

```python
def resolve(name: str, *, addons: Sequence[str] = (), boot: str | None = None,
            catalog: Catalog | None = None) -> Target
def resolve_board(name: str, *, catalog: Catalog | None = None) -> Board   # a board id or alias; a Soc id returns Soc.default_board
def resolve_soc(name: str, *, catalog: Catalog | None = None) -> Soc

class UnknownPlatform(PlatformError):   suggestions: tuple[str, ...]
class AmbiguousPlatform(PlatformError): candidates: tuple[str, ...]   # shorthands table only
```

Resolution order:

1. An exact id or alias of a board, part, implementation or Soc, or a
   composition alias, case-insensitively, returns that target. A Soc id
   returns the bare Soc target. A composition alias returns its board
   target with its add-ons.
2. A shorthand from the `shorthands` table raises `AmbiguousPlatform`
   listing its members.
3. Anything else raises `UnknownPlatform` with suggestions.

The number of boards carrying a Soc never changes the result.
`resolve_board(soc_id)` returns `Soc.default_board` and raises
`PlatformError` if the Soc has none; it is the only call that uses
`default_board`.

`addons=` is valid only for board targets (including a composition, whose
add-ons it extends) and raises `PlatformError` otherwise. `boot=` is valid
for any target that has boot configurations and raises if the name is not
one of them.

### `helia_platforms.model`

```python
@dataclass(frozen=True) class Provenance: status, source, verified_on, verified_by, notes
@dataclass(frozen=True) class Core:       id, arch, pmu, has_dsp_extension, provenance   # arch may be a non-Arm ISA
@dataclass(frozen=True) class CoreOptions: fpu, fpu_dp, mve, icache_kb, dcache_kb
@dataclass(frozen=True) class CoreInstance: id, role, core, options: CoreOptions, clock_domain, programmable_by: str | None
@dataclass(frozen=True) class Npu:        vendor, family, model, macs_per_cycle; accelerator_config (property)
@dataclass(frozen=True) class NpuInstance: id, npu, axi_width_bits, base_address, irq, sram_port_hash, driven_by, clock_domain
@dataclass(frozen=True) class AcceleratorInstance: id, kind, ip, driven_by, clock_domain, base_address, irq
@dataclass(frozen=True) class MemoryRegion: name, technology, attachment, size, base, alternate_bases, executable, writeable, cacheable, characterization, dma_boundary: int | None, stands_in_for: tuple[str, ...], provenance   # stands_in_for: FVP regions only (ADR 0007)
@dataclass(frozen=True) class Access:     master, target, access, requires_awake, guidance, reason, address: int | None, port: int | None, characterization, provenance   # target: region or memory_controllers name
@dataclass(frozen=True) class DefaultAccess: master, access, scope, provenance   # scope: on_die
@dataclass(frozen=True) class MemoryCharacterization: read_latency_ns, write_latency_ns, max_outstanding_reads, max_outstanding_writes, max_beats, ports, axi_clock_hz, bandwidth_fraction  (each value may carry its own Provenance)
@dataclass(frozen=True) class ClockDomain: id, points: tuple[DomainPoint, ...]   # DomainPoint: name, mhz, hal_mode, provenance
@dataclass(frozen=True) class OperatingPoint: name, domains: Mapping[str, str], hal_mode, provenance   # domain id -> point name
@dataclass(frozen=True) class SdkFacts:   c_define, cmsis_header, trace_clock_mhz, jlink_cpufreq_mhz, hal_enums: Mapping[str, str], build: BuildFacts
@dataclass(frozen=True) class BuildFacts: abi, float_abi
@dataclass(frozen=True) class Soc:        id, series, aliases, cores, npus, accelerators, memories, access, default_access: DefaultAccess | None, peripherals, memory_controllers, clock_domains, operating_points, default_operating_point: str | None, boot_configs, default_boot, image_slots, sdk, derives_from, default_board: str | None, revision, release_status, extensions, provenance
@dataclass(frozen=True) class Implementation: id, soc, kind, model: str | None, subset: Subset, memories: tuple | None, access: tuple | None, clock_domains: tuple | None, operating_points: tuple | None, boot_configs: Mapping | None, default_boot: str | None, provisioning: str | None, jlink_device, trace_clock_mhz, interfaces, population, aliases, release_status, extensions, provenance   # None: inherit the Soc's (after clock caps); memories: kind fvp only (ADR 0007)
@dataclass(frozen=True) class Subset:     memories_removed, memories_resized, memories_rebased, peripherals_removed, memory_controllers_removed, cores_removed, npus_removed, accelerators_removed, clock_domains_removed, boot_configs_removed, operating_points_removed, image_slots_removed, access_removed, max_cpu_mhz, max_npu_mhz, max_domain_mhz
@dataclass(frozen=True) class BootConfig: name, reserved: tuple[Reservation, ...], app_start: Mapping[str, AppStart], requires, provenance   # AppStart: region, offset; reserved in written key order
@dataclass(frozen=True) class Reservation: region, offset, size, purpose, provenance
@dataclass(frozen=True) class Part:       id, soc, implementation: str | None, silicon_revision, package, radio, jlink_device, image_slots, aliases, release_status, provenance
@dataclass(frozen=True) class ImageSlot:  name, core, region, offset, size, supplier, provenance
@dataclass(frozen=True) class MemoryInterface: name, controller, modes, aperture_base, alternate_bases, aperture_max
@dataclass(frozen=True) class MemoryDevice: id, technology, capacity, driver_family, modes, characterization, aliases, release_status, provenance
@dataclass(frozen=True) class AddOn:      id, fits_boards, occupies, population: Mapping[str, str], modes: Mapping[str, tuple[str, ...]], revision, aliases, release_status, extensions, provenance
@dataclass(frozen=True) class Board:      id, category, revision, part: str | None, implementation: str | None, interfaces, population: Mapping[str, str], provisioning, jlink_device, trace_clock_mhz, aliases, release_status, extensions, provenance
@dataclass(frozen=True) class Composition: alias, board, addons; release_status (property, effective from what it references)
@dataclass(frozen=True) class AddressRange: start, end, region, core, boot: str | None, access: Access | None, provenance, field_provenance; size (property)   # [start, end) in the region's base address space, from Target.application_ranges() (#73)
```

A class that has `provenance` also has `field_provenance`: the records of
single values that differ from the class's own record, keyed by their
path within the object ([ADR 0003](../adr/0003-provenance-record.md)).
A region `external_memories()` builds carries its device's record and
the device's field records under the region's keys (`capacity` as `size`;
`driver_family` and `modes`, which a region lacks, are left out), except
`base` and each `alternate_bases.<address>`, which carry the interface
owner's (the board's or the implementation's) record for that window.

### `helia_platforms.target` (the resolved view)

```python
@dataclass(frozen=True)
class Target:
    id: str; kind: Literal["board", "part", "implementation", "soc"]
    soc: Soc; implementation: Implementation | None; part: Part | None; board: Board | None
    origin: Literal["builtin", "overlay"]
    release_status: Literal["public", "embargoed"]            # effective: most restrictive along the reference chain
    # structure
    core: Core; core_options: CoreOptions; npu: NpuInstance | None   # core-0 and npu-0 conveniences
    def cores(self, role: str | None = None) -> tuple[CoreInstance, ...]
    def npus(self) -> tuple[NpuInstance, ...]
    def accelerators(self) -> tuple[AcceleratorInstance, ...]
    def isa(self, core: int | str = 0) -> IsaFeatures
    def reachable(self, master: str, target: str) -> Access | None   # a region's own entry, else its controller's
    def npu_clocks(self, npu: int | str = 0) -> Mapping[str, int]   # derived from system operating points
    def memories(self, core: int | str = 0, *, include_discouraged: bool = False) -> tuple[MemoryRegion, ...]   # regions that core reaches, after subset, plus external regions whose interface it has an entry for; a discouraged entry is left out unless include_discouraged
    def placement_ranges(self, core: int | str = 0, *, include_discouraged: bool = False) -> Mapping[str, tuple[int, int]]   # (base, size) of the regions memories() gives; leaves out a populated device with no base; raises for any other region without one
    def cpu_mhz(self, point: str | None = None, core: int | str = 0) -> int
    def npu_mhz(self, point: str | None = None, npu: int | str = 0) -> int
    def region(self, name: str) -> MemoryRegion   # on an FVP, also a Soc region name a stands_in_for lists
    def has_region(self, name: str | None = None, *, technology=None, attachment=None) -> bool
    def has_external_memory(self, technology: str | None = None) -> bool
    def operating_points(self, domain: str | None = None) -> tuple[OperatingPoint | DomainPoint, ...]
    def operating_point(self, name: str | None = None, *, domain: str | None = None) -> OperatingPoint | DomainPoint
    default_operating_point: OperatingPoint | None
    capabilities: frozenset[str]                              # derived; stable spellings
    category: str | None; addons: tuple[AddOn, ...]           # None for implementation and soc targets
    interfaces: Mapping[str, MemoryInterface]                 # the implementation's and board's, with modes the fitted add-ons narrow
    # boot
    boot: BootConfig | None                                   # explicit boot=, else board, else implementation provisioning, else default
    def boot_configs(self) -> tuple[BootConfig, ...]
    def flash_load_address(self, core: int | str = 0) -> int   # from boot; raises if there is none
    image_slots: Mapping[str, ImageSlot]                      # the Soc's, each replaced by the part's slot of that name
    def usable_nvm(self, core: int | str = 0, *, include_discouraged: bool = False) -> Mapping[str, int]   # the customer's view: after reservations and other cores' slots; empty for a core only the vendor programs or with no loadable image
    def application_ranges(self, core: int | str = 0, *, include_discouraged: bool = False) -> Mapping[str, tuple[AddressRange, ...]]   # per region with a base: disjoint [start, end) in the region's base address space, less reservations and other cores' slots; () when all taken; a region with no base is left out (#73)
    # external memory
    def external_memories(self) -> tuple[MemoryRegion, ...]   # population plus add-ons, at aperture bases
    def classify_address(self, address: int, master: int | str = 0) -> str | None   # alternate_bases classify to the same region; per-master Access addresses resolved for master
    # debug and SDK
    jlink_device: str | None; trace_clock_mhz: int | float | None; sdk: SdkFacts   # board, else implementation, else part / SDK; trace_clock_mhz is an int when whole, a measured fraction kept
    aliases: tuple[str, ...]
    # provenance(): deferred until the estimator adapter defines the roll-up it needs (#58)
```

`core=` and `npu=` take an index or an id. `IsaFeatures` carries `has_dsp`, `has_mve`, `mve_flavour`, `supports_fp16`,
`supports_fp32`, `supports_fp64`, `has_pmu`, `pmu_kind`.

On an FVP target, `region(name)` also accepts the name of a Soc region
that one of the FVP's regions lists in `stands_in_for`, and returns the
region that stands in for it: `region("hblram")` on the Corstone-320
target returns its DDR region
([ADR 0007](../adr/0007-fvp-memory-maps.md)).

### Overlays, validation, export, CLI

`load_overlay` parses an overlay (syntax per ADR #7), validates it against
the JSON Schema and the semantic rules, and returns a new `Catalog`. The
JSON Schema already makes core, NPU and accelerator ids unique within their
lists, makes (master, target) pairs unique within `access`, and requires an
add-on's `modes` to list at least one mode. The semantic rules below are the
loader's (`catalog.py`, `_tree.py`), regenerated from the code on 2026-10-30
(#141); each is an error unless marked as a warning. All errors of a load are
reported together, and warnings are issued only when a load has no errors.
They check the entries of the load being made, not those already in its base.
This is the one list; 0002-multicore.md refers to it.

- **Names.** An id is defined once per load. Ids and aliases are unique,
  compared without case: Socs, implementations, parts, boards, compositions
  and shorthands share one namespace, and cores, add-ons and memory devices
  each have their own. No new id, alias, composition or shorthand may shadow
  a name in the base catalog. Only built-in files carry `shorthands`,
  `documents`, `repositories` or `unverified_allowed`.
- **Built-ins.** A built-in entry does not use `based_on`, writes
  `release_status: public` (cores excepted), carries no `extensions`, and
  has a provenance record for every fact. A built-in region has a base.
- **Deltas.** A delta key needs `based_on`, which names an entry of the
  same kind and forms no cycle; every required key is present after the
  merge. A `*_removed`, `*_resized` or `*_rebased` key names something the
  base has, and a delta does not both remove a memory controller and list
  it in its own `memory_controllers`. Removing operating points does not
  leave none unless the entry declares its own.
- **Shorthands.** `cpu_mhz` and `npu_mhz` in an operating point need a
  core 0 or NPU 0 whose clock domain exists, and agree with an explicit
  domain point of the same name. A single-form `app_start` needs a core 0.
- **Implementations.** `soc` names a Soc. `memories` is allowed only on
  kind `fvp`, and not with the `memories_*` subset deltas; `stands_in_for`
  appears only on an FVP's regions and names Soc regions the FVP does not
  list, each in at most one region
  ([ADR 0007](../adr/0007-fvp-memory-maps.md)). A subset does not resize a
  region past the Soc's size, and its own clock points do not exceed the
  Soc's highest point in that domain. `max_cpu_mhz` and `max_npu_mhz` need
  a core 0 or NPU 0, and `max_domain_mhz` names a domain; clock caps that
  drop every operating point need the implementation's own.
- **Soc references.** A Soc has a core, and core 0 has role
  `application`. Each core names a known core IP and a clock domain; each
  NPU and accelerator names a core in `driven_by` and a clock domain. An
  operating point names at least one domain point, and its `domains` keys
  and values name domains and their points. `default_operating_point`,
  `default_boot`, `derives_from` and `default_board` resolve, and the
  default board carries the Soc. `memory_controllers` names are
  peripherals. An `Access` master is a core, NPU or accelerator id, and a
  target is a region or memory controller; `default_access` names core 0.
- **Regions.** Regions do not overlap, at their bases or any alternate
  base. `derives_from` requires the same regions with equal technology,
  attachment, size, base and alternate bases.
- **Boot.** `app_start` keys name programmable cores (`programmable_by`
  set) and its regions exist. A reservation's region exists, the
  reservation ends inside it, and reservations in one boot config do not
  overlap. An implementation's or board's `provisioning` names a boot
  config of the Soc as realized.
- **Image slots.** A slot's owner is a programmable core with a `direct`
  entry for the slot's region. A slot has a nonzero size, ends inside its
  region, contains no other core's `app_start`, and overlaps no other slot
  or boot reservation. A Part's slots are checked against its Soc as
  realized, and its `image_slots_removed` does not name a slot its Soc
  carries unless the Part rewrites it.
- **Access coverage** (built-ins only). After `default_access` expansion,
  every region of a Soc, and of each implementation's Soc as realized, has
  at least one entry, which may be `access: none`.
- **Parts and boards.** A Part names a Soc, and a `silicon`
  Implementation of that Soc. A Board names exactly one of `part` and
  `implementation`; an implementation is of kind `fpga` on a board of
  category `fpga`, which names no part. A board interface does not share a
  name or a window with its implementation's interfaces.
- **Interfaces and population.** A `population` key names an interface
  and its value a memory device. An interface's controller is a memory
  controller of the Soc as realized, not one the implementation removed.
  A controller with no access entry draws a warning that its devices are
  unreachable (an error for built-ins). `alternate_bases` needs an
  `aperture_base`. An interface window (each base, `aperture_max` long)
  overlaps no on-chip region and no other window. A device is no larger
  than its aperture; an interface with no `aperture_max` draws a warning
  that its device is unchecked.
- **Add-ons and compositions.** `fits_boards` names boards. `population`
  and `modes` keys are interfaces the add-on occupies, and each exists on
  every board it fits. Its devices exist and fit the aperture. Its modes
  are among the board interface's modes, and leave its own device at least
  one of that device's modes (a device that lists no modes is not checked).
  A composition's board and add-ons exist; no add-on sits on a board it
  does not fit or on an interface the board populates or another add-on
  occupies (an occupied interface counts even without a device). Shorthand
  members are exact ids of Socs, implementations, parts or boards.

Merging, not validation: removing a core or region drops the inherited
image slots it owns or holds; removing a region, peripheral, memory
controller, core, NPU or accelerator drops the inherited access entries
naming it; and `peripherals_removed` drops the name from
`memory_controllers`. `default_access` gives core 0 an entry to every
on-die region and memory controller that no core already has one for;
external regions get none.

`helia_platforms.export` writes the JSON catalog,
filtered and scrubbed by effective release status, and the JSON Schemas
([RFC 0003](0003-export-and-pages.md)). The Markdown pages and the release
assets are built only from `builtin(include_plugins=False)`.
`helia-platforms` CLI: `list [socs|boards|parts|implementations]`,
`show <id> [--sources] [--provenance] [--addon <id>] [--boot <name>]`,
`validate <overlay>`, `check-sources` (compare against the committed SDK
and Zephyr snapshots; [ADR 0006](../adr/0006-drift-test-snapshots.md)),
`export --schema | --export-schema | --json <file> [--provenance] [--check] | --pages <dir> [--check] | --release <dir> [--check]`
(with `--include-plugins` and `--overlay` for `--json` only).

### Adapters, in the consumers

- heliaAOT: `SocPlatform.from_target(t)` builds the flattened view (name
  lowercased, `memories` from the physical on-chip RAM regions in
  `t.memories()`, leaving out atomiq110's `hblram` region until its
  technology and CPU reach are confirmed (#19), NVM from `t.usable_nvm()`
  without the boot reservations and other cores' image slots, and
  external memories from
  `t.external_memories()`, the same for every module type; heliaAOT
  passes no `boot=`, so the board's provisioning, else the
  implementation's, else `default_boot` selects the boot configuration;
  `capabilities` from
  `t.capabilities` mapped onto its enum plus its own policy tags (`MCU`), `min_alignment` and `preferred_memory_order`
  from heliaAOT tables keyed by `t.soc.id`). `platform.overlay:` and
  `platform.soc:` feed `load_overlay`.
- helia-profiler: `SocDef`/`BoardDef` become views over `Target`; its
  policy layer (`SocCapabilities`, GPIO records, reset strategies) stays
  and reads facts from `Target`; it keeps its windows table, regenerated
  from the nsx-ambiq-sdk it builds against, and intersects it with
  `t.application_ranges()` for its capacity checks (#73; physical sizes
  where it has no window); `target.custom_socs/custom_boards` is translated to
  the overlay format by a shim for one release.
- helia-npu: `SocDefinition` becomes a projection of `Target.npu`, its
  access entries (port classes) and the regions they name, taking an
  entry's characterization where present (it overrides the region's for
  that master) and the region's otherwise; its Vela and
  timing-adapter code is unchanged.

## Relationship to helia-aot#278

How each #278 phase lands, and the changes relative to #278's model, are
in [0002-migration.md](0002-migration.md#relationship-to-helia-aot278).

## Changes relative to RFC 0001

This RFC, accepted 2026-10-21, supersedes these parts of RFC 0001. The
rest of RFC 0001, and its appendix as the reference for data and sources,
stand.

| Topic | RFC 0001 | RFC 0002 | Why |
|---|---|---|---|
| Tool settings | Per-tool sections on built-ins (`helia_aot:` capabilities, preferred memory order, alignment; `profiler:` in custom entries) ("Facts, and each tool's settings") | No tool sections on built-ins; tool policy keyed by canonical id in each tool; overlays may carry `extensions` (proposal) | P1: the package holds facts, not opinions (owner direction; review 2.5) |
| Linker windows | A windows table in the package keyed by board, profile and link family ("Memory: physical regions and linker windows") | Not in the package at all (#73, 2026-11-05): consumers keep their own windows and intersect them with `Target.application_ranges()` | Windows are properties of software, not silicon |
| Capabilities | Declared lists per entry | Derived from `Core`, `CoreOptions` and `NpuInstance` | P3; declared lists drift (review 2.8) |
| `tier`, `channel` | Board fields | Removed; support level is a per-tool marker keyed by id | Tool policy, not fact |
| External memory | A PSRAM (and NVM) region per board | Board `interfaces` plus `population` plus add-ons, populated by `MemoryDevice`s | Board revisions and shields change what is fitted (research/datasheets.md section 7) |
| Boot layout | `app_flash_load_addr` as an accessor over the default window's MRAM origin | Named boot configurations on the Soc, replaceable by an Implementation, with board provisioning; `flash_load_address()` derived from the selected one | Apollo510, Lite and 330 Plus, and Apollo3/4 boot layouts differ and are a choice |
| Entity levels | Two levels (`SocDef`, `BoardDef`) plus IP blocks; an FPGA is a `BoardDef` with overrides | Four levels (Soc, Implementation, Part, Board) plus add-ons and memory devices; an FPGA is an Implementation on a Board of category `fpga`, with no board overrides | Pre-silicon implementations and per-part facts (review 2.2) |
| Publication | Public repo and 0.1.0 on PyPI before adoption ("Packaging and versions") | Decided in [ADR 0005](../adr/0005-publication-and-embargo.md) (publication, embargo and the private-to-public path) | A public release would ship embargoed parts (review 3.1) |
| Cores and accelerators | One core and at most one NPU per chip | Ordered `cores` and `npus` (index 0 primary), an explicit access matrix, image slots per core, system operating points over clock domains | Shipping parts already carry a radio core (Apollo510 Lite, Apollo330 Plus); single-core queries default to core 0 |
| Soc id resolution | A Soc id resolves to its board when the Soc has exactly one ("Names") | A Soc id always resolves to the bare Soc target; `default_board` only through `resolve_board(soc_id)` | Resolution must not change when a board is added; matches #278 |

## Migration and output changes

Each consumer's changed outputs, the pending data corrections, and the
parity test (issue #13) that covers each are in
[0002-migration.md](0002-migration.md).

## Open questions

1. Does the estimator want `OperatingPoint` to carry voltage or rail
   facts, or is that characterization with provenance like memory timing?
2. Closed 2026-11-05 (#73): no link-environment dataset. Linker windows
   stay with the consumers; the package gives
   `Target.application_ranges()`.
3. Of `helia-npu`'s `targets` (FVP, RTL, silicon), the FVP memory maps
   ([ADR 0007](../adr/0007-fvp-memory-maps.md)) and clock choices are
   implementation description and move here; the
   FVP binary, timing-adapter registers and run flags are harness
   configuration and stay. Confirm with the estimator owners.
4. Whether to adopt `extensions` as proposed (an opaque per-tool map on
   Soc, Implementation, Board and AddOn, overlay entries only), and
   whether it is enough for the profiler's custom-board measurement wiring
   or the profiler keeps its own sidecar file.
5. How power-domain names (used in `Access.requires_awake`) are spelled
   and sourced: the SDK HAL's power-control enums, a catalog vocabulary
   mapped to them, or both.
6. Whether private catalog packages are signed
   ([0002-private-silicon.md](0002-private-silicon.md)). A consumer records
   which private catalog it ran against through `Catalog.identity()`
   ([ADR 0004](../adr/0004-schema-and-catalogue-versions.md)).
